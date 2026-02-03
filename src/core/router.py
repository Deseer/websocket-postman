"""指令路由引擎"""
import json
import re
from dataclasses import dataclass
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.config import get_config
from src.core.parser import CommandParser, ParsedCommand
from src.core.permission import PermissionChecker, PermissionCheckResult
from src.core.ws_client import WebSocketClientManager
from src.models.command_set import Category, Command, CommandSet
from src.models.database import DatabaseManager
from src.models.user import User
from src.utils.logger import logger


@dataclass
class RouteResult:
    """路由结果"""
    success: bool
    target_ws: str | None = None
    command_set: CommandSet | None = None
    command: Command | None = None
    response: str | None = None
    error_message: str | None = None
    is_system_command: bool = False


class CommandRouter:
    """指令路由引擎"""
    
    _instance: "CommandRouter | None" = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance
    
    def __init__(self):
        if self._initialized:
            return
        
        self._command_sets: list[CommandSet] = []
        self._categories: list[Category] = []
        self._public_sets: list[CommandSet] = []
        self._prefix_map: dict[str, CommandSet] = {}
        self._group_sets: dict[str, list[CommandSet]] = {}
        
        self._parser: CommandParser | None = None
        self._permission_checker = PermissionChecker()
        self._ws_manager = WebSocketClientManager.instance()
        
        self._initialized = True
    
    def load_from_config(self):
        """从配置加载指令集"""
        config = get_config()
        
        # 加载分类
        self._categories = [
            Category.from_config(cat.model_dump())
            for cat in config.categories
        ]
        
        # 加载指令集
        self._command_sets = [
            CommandSet.from_config(cs.model_dump())
            for cs in config.command_sets
        ]
        
        # 建立索引
        self._build_indexes()
        
        # 初始化解析器
        prefixes = list(self._prefix_map.keys())
        self._parser = CommandParser(prefixes)
        
        logger.info(f"已加载 {len(self._categories)} 个分类, {len(self._command_sets)} 个指令集")
    
    def _build_indexes(self):
        """建立索引"""
        self._public_sets = []
        self._prefix_map = {}
        self._group_sets = {}  # category_id -> [command_sets]
        self._name_to_set = {}  # command_set name -> command_set
        
        for cs in self._command_sets:
            # 公共指令集
            if cs.is_public:
                self._public_sets.append(cs)
            
            # 前缀映射
            if cs.prefix:
                self._prefix_map[cs.prefix] = cs
            
            # 名称映射（用于强制指令集路由）
            self._name_to_set[cs.name.lower()] = cs
            

    
    async def get_or_create_user(self, qq_id: int, nickname: str = "") -> User:
        """获取或创建用户"""
        async with DatabaseManager.session() as session:
            result = await session.execute(
                select(User).where(User.qq_id == qq_id)
            )
            user = result.scalar_one_or_none()
            
            if user is None:
                user = User(
                    qq_id=qq_id,
                    nickname=nickname,
                    selected_styles={},
                    allowed_switch_groups=[],
                )
                session.add(user)
                await session.commit()
                await session.refresh(user)
            
            return user
    
    async def route(
        self,
        message: str,
        user_id: int,
        group_id: int | None = None,
        nickname: str = "",
        self_id: int = 0,
        raw_event: dict | None = None,
    ) -> RouteResult:
        """
        路由指令到目标 WebSocket
        
        路由逻辑：
        1. 检查是否为强制指令集路由（格式：指令集名 指令）
        2. 解析消息
        3. 如果有指令集前缀，直接使用指定的指令集
        4. 否则按优先级查找：公共指令集 -> 用户选择的风格 -> 默认指令集 -> 其他
        5. 检查权限
        6. 转发到目标 WebSocket
        """
        if self._parser is None:
            self.load_from_config()
        
        # 获取用户
        user = await self.get_or_create_user(user_id, nickname)
        
        # 检查是否为强制指令集路由（格式：指令集名 指令）
        forced_result = await self._try_forced_route(message, user, group_id, self_id, raw_event)
        if forced_result:
            return forced_result
        
        # 解析指令
        parsed = self._parser.parse(message)
        
        if not parsed.is_command:
            # 不是指令，应用 final 规则
            return await self._apply_final_rule(message)
        
        # 检查是否为系统指令
        system_result = await self._handle_system_command(parsed, user, group_id)
        if system_result:
            return system_result
        
        # 查找指令集和指令
        command_set, command = await self._find_command(parsed, user)
        
        if command_set is None or command is None:
            # 没有找到指令，应用 final 规则
            return await self._apply_final_rule(message)
        
        # 检查权限
        permission_result = self._permission_checker.check_command_permission(
            user, command, group_id
        )
        
        if not permission_result.allowed:
            return RouteResult(
                success=False,
                error_message=permission_result.message,
            )
        
        # 转发到目标 WebSocket
        final_message = message
        if command_set.strip_prefix:
            final_message = re.sub(r'^\W+', '', message)
            
        response = await self._forward_to_ws(
            target_ws=command_set.target_ws,
            message=final_message,
            user_id=user.qq_id,
            group_id=group_id,
            self_id=self_id,
            raw_event=raw_event,
        )
        
        return RouteResult(
            success=True,
            target_ws=command_set.target_ws,
            command_set=command_set,
            command=command,
            response=response,
        )
    
    async def _find_command(
        self,
        parsed: ParsedCommand,
        user: User,
    ) -> tuple[CommandSet | None, Command | None]:
        """查找指令对应的指令集"""
        # 如果有前缀，使用指定的指令集
        if parsed.prefix:
            cs = self._prefix_map.get(parsed.prefix)
            if cs:
                cmd = cs.find_command(parsed.command)
                if cmd:
                    return cs, cmd
        
        # 先检查公共指令集
                cmd = cs.find_command(cmd_name)
                if cmd:
                    return cs, cmd
        
        # 优先级路由：
        # 1. 如果是公共指令集且包含此指令，记录下来但不作为唯一选择（因为用户可能有更具体的选择）
        # 2. 检查分类下的用户选择
        # 3. 检查分类下的默认选择
        # 4. 最后才是宽泛匹配
        
        matches: list[tuple[CommandSet, Command]] = []
        
        # 查找所有匹配的指令集
        for cs in self._command_sets:
            cmd = cs.find_command(cmd_name)
            if cmd:
                matches.append((cs, cmd))
        
        if not matches:
            return None, None
            
        # 排序策略：
        # - 用户选择的风格优先
        # - 对应的分类设置了默认值次之
        # - 优先级 (priority) 高的优先
        # - 公共指令集次之
        
        def score_match(match: tuple[CommandSet, Command]):
            cs, cmd = match
            score = 0
            
            # 基础分：优先级
            score += cs.priority * 10
            
            # 是否在用户选择的分类风格中
            if cs.category:
                selected_style_id = (user.selected_styles or {}).get(cs.category)
                if selected_style_id == cs.id:
                    score += 1000  # 用户选择具有最高权重
                
                # 检查分类默认值
                category = next((c for c in self._categories if c.id == cs.category), None)
                if category and category.default_command_set == cs.id:
                    score += 100 # 默认指令集次高权重
            
            # 公共指令集权重较低（除非它就是用户选择的）
            if cs.is_public:
                score += 50
                
            return score
            
        # 按分数降序排列
        matches.sort(key=score_match, reverse=True)
        return matches[0]
    
    async def _try_forced_route(
        self,
        message: str,
        user: User,
        group_id: int | None,
        self_id: int = 0,
        raw_event: dict | None = None,
    ) -> RouteResult | None:
        """
        尝试强制指令集路由
        
        格式：指令集名 指令
        例如：hrkbot /个人信息
        """
        import re
        
        # 匹配格式：指令集名(非空白字符) 空格 指令
        match = re.match(r'^(\S+)\s+(/\S+.*)$', message.strip())
        if not match:
            return None
        
        cs_name = match.group(1).lower()
        actual_command = match.group(2)
        
        # 查找指定的指令集
        target_cs = self._name_to_set.get(cs_name)
        if not target_cs:
            return None
        
        # 解析实际指令
        parsed = self._parser.parse(actual_command)
        if not parsed.is_command:
            return None
        
        # 查找指令
        cmd = target_cs.find_command(parsed.command)
        if not cmd:
            return RouteResult(
                success=False,
                error_message=f"指令集 {target_cs.name} 中没有指令 {parsed.command}",
                is_system_command=True,
            )
        
        # 检查权限
        permission_result = self._permission_checker.check_command_permission(
            user, cmd, group_id
        )
        
        if not permission_result.allowed:
            return RouteResult(
                success=False,
                error_message=permission_result.message,
            )
        
        # 转发到目标 WebSocket（使用原始实际指令）
        final_message = actual_command
        if target_cs.strip_prefix:
            final_message = re.sub(r'^\W+', '', actual_command)
            
        response = await self._forward_to_ws(
            target_ws=target_cs.target_ws,
            message=final_message,
            user_id=user.qq_id,
            group_id=group_id,
            self_id=self_id,
            raw_event=raw_event,
        )
        
        return RouteResult(
            success=True,
            target_ws=target_cs.target_ws,
            command_set=target_cs,
            command=cmd,
            response=response,
        )
    
    async def _handle_system_command(
        self,
        parsed: ParsedCommand,
        user: User,
        group_id: int | None,
    ) -> RouteResult | None:
        """处理系统内置指令"""
        cmd = parsed.command.lower()
        
        if cmd == "/help":
            return await self._handle_help(user)
        elif cmd == "/list":
            return await self._handle_list(parsed.args, user)
        elif cmd == "/style":
            return await self._handle_style(parsed.args, user)
        elif cmd == "/status":
            return await self._handle_status()
        elif cmd == "/admin":
            return await self._handle_admin(parsed.args, user)
        
        return None
    
    async def _handle_help(self, user: User) -> RouteResult:
        """处理 /help 指令"""
        lines = [
            "📖 指令帮助",
            "",
            "系统指令：",
            "  /help - 显示帮助信息",
            "  /status - 显示系统状态",
            "  /list - 列出所有分类",
            "  /list <分类> - 列出分类下的指令集",
            "  /style list - 列出可选风格",
            "  /style select <组> <风格> - 选择风格",
            "  /style current - 查看当前风格",
            "",
            "你也可以使用指令集前缀临时调用：",
            "  <指令集名称>:<指令>",
            "  例如：可爱风格:/chat 你好",
        ]
        
        return RouteResult(
            success=True,
            response="\n".join(lines),
            is_system_command=True,
        )
    
    async def _handle_list(self, args: str, user: User) -> RouteResult:
        """处理 /list 指令"""
        args = args.strip()
        
        if not args:
            # 列出所有分类
            lines = ["📂 可用分类：", ""]
            for cat in sorted(self._categories, key=lambda c: c.order):
                lines.append(f"  【{cat.display_name}】")
                lines.append(f"    /list {cat.display_name}")
            
            if not self._categories:
                lines.append("  暂无分类")
            
            return RouteResult(
                success=True,
                response="\n".join(lines),
                is_system_command=True,
            )
        
        # 列出指定分类下的指令集
        category = None
        args_lower = args.lower()
        for cat in self._categories:
            if (cat.display_name.lower() == args_lower or 
                cat.name == args or 
                cat.id == args):
                category = cat
                break
        
        if category is None:
            return RouteResult(
                success=False,
                error_message=f"分类 '{args}' 不存在",
                is_system_command=True,
            )
        
        lines = [f"📂 {category.display_name}"]
        
        if category.description:
            lines.append("")
            lines.append(category.description)
        
        lines.append("")
        lines.append("可选风格：")
        
        for cs in self._command_sets:
            if cs.category == category.id:
                # 检查用户选择
                selected = (user.selected_styles or {}).get(category.id)
                current = " ✓ 当前" if selected == cs.id else ""
                
                lines.append(f"  【{cs.name}】{current}")
                if cs.description:
                    lines.append(f"    {cs.description}")
        
        return RouteResult(
            success=True,
            response="\n".join(lines),
            is_system_command=True,
        )
    
    async def _handle_style(self, args: str, user: User) -> RouteResult:
        """处理 /style 指令"""
        parts = args.strip().split()
        
        if not parts or parts[0] == "list":
            # 列出可选风格（按分类组织）
            lines = ["🎨 可选风格：", ""]
            
            for cat in self._categories:
                sets = self._group_sets.get(cat.id, [])
                if not sets:
                    continue
                
                # 显示分类名称
                lines.append(f"【{cat.display_name}】")
                selected = (user.selected_styles or {}).get(cat.id)
                
                for cs in sets:
                    current = " ✓" if selected == cs.id else ""
                    lock = "" if cat.allow_user_switch else " 🔒"
                    lines.append(f"  {cs.name}{current}{lock}")
                
                lines.append("")
            
            if len(lines) == 2:
                lines.append("  暂无可选风格")
            
            lines.append("用法: /style select <分类> <风格>")
            
            return RouteResult(
                success=True,
                response="\n".join(lines),
                is_system_command=True,
            )
        
        if parts[0] == "current":
            # 显示当前选择
            lines = ["🎨 当前风格：", ""]
            
            for category_id, style_id in (user.selected_styles or {}).items():
                # 查找分类名称
                cat_name = category_id
                for cat in self._categories:
                    if cat.id == category_id:
                        cat_name = cat.display_name
                        break
                
                # 查找指令集名称
                for cs in self._command_sets:
                    if cs.id == style_id:
                        lines.append(f"  {cat_name}: {cs.name}")
                        break
            
            if len(lines) == 2:
                lines.append("  暂未选择任何风格")
            
            return RouteResult(
                success=True,
                response="\n".join(lines),
                is_system_command=True,
            )
        
        if parts[0] == "select" and len(parts) >= 3:
            category_name = parts[1]
            style_name = " ".join(parts[2:])
            
            # 查找分类（支持 display_name 和 id）
            target_cat = None
            for cat in self._categories:
                if (cat.display_name.lower() == category_name.lower() or 
                    cat.id == category_name or
                    cat.name == category_name):
                    target_cat = cat
                    break
            
            if target_cat is None:
                return RouteResult(
                    success=False,
                    error_message=f"分类 '{category_name}' 不存在",
                    is_system_command=True,
                )
            
            # 检查权限（使用分类的 allow_user_switch）
            permission = self._permission_checker.check_style_switch_permission(
                user, target_cat.allow_user_switch
            )
            
            if not permission.allowed:
                return RouteResult(
                    success=False,
                    error_message=permission.message,
                    is_system_command=True,
                )
            
            # 查找指令集（在该分类下）
            target_cs = None
            for cs in self._group_sets.get(target_cat.id, []):
                if cs.name.lower() == style_name.lower() or cs.id == style_name:
                    target_cs = cs
                    break
            
            if target_cs is None:
                return RouteResult(
                    success=False,
                    error_message=f"分类 '{target_cat.display_name}' 下没有风格 '{style_name}'",
                    is_system_command=True,
                )
            
            # 更新用户选择（使用分类ID作为key）
            async with DatabaseManager.session() as session:
                result = await session.execute(
                    select(User).where(User.qq_id == user.qq_id)
                )
                db_user = result.scalar_one_or_none()
                if db_user:
                    styles = dict(db_user.selected_styles or {})
                    styles[target_cat.id] = target_cs.id
                    db_user.selected_styles = styles
                    await session.commit()
            
            return RouteResult(
                success=True,
                response=f"✅ 已切换【{target_cat.display_name}】分类到【{target_cs.name}】风格",
                is_system_command=True,
            )
        
        return RouteResult(
            success=False,
            error_message="用法: /style [list|current|select <分类> <风格>]",
            is_system_command=True,
        )
    
    async def _handle_status(self) -> RouteResult:
        """处理 /status 指令"""
        ws_status = self._ws_manager.get_status()
        
        lines = ["📊 系统状态：", ""]
        lines.append(f"指令集: {len(self._command_sets)} 个")
        lines.append(f"分类: {len(self._categories)} 个")
        lines.append("")
        lines.append("WebSocket 连接：")
        
        for ws_id, status in ws_status.items():
            state = "✅ 已连接" if status["connected"] else "❌ 未连接"
            lines.append(f"  {status['name']}: {state}")
        
        return RouteResult(
            success=True,
            response="\n".join(lines),
            is_system_command=True,
        )
    
    async def _handle_admin(self, args: str, user: User) -> RouteResult:
        """处理 /admin 指令"""
        if not self._permission_checker.is_admin(user.qq_id):
            return RouteResult(
                success=False,
                error_message="你没有管理员权限",
                is_system_command=True,
            )
        
        parts = args.strip().split()
        
        if not parts:
            lines = [
                "🔧 管理员指令：",
                "",
                "  /admin allow <QQ号> <互斥组> - 允许用户切换风格",
                "  /admin deny <QQ号> <互斥组> - 禁止用户切换风格",
                "  /admin set <QQ号> <互斥组> <风格> - 为用户设置风格",
                "  /admin privilege <QQ号> [on|off] - 设置用户特权",
            ]
            return RouteResult(
                success=True,
                response="\n".join(lines),
                is_system_command=True,
            )
        
        cmd = parts[0]
        
        if cmd == "allow" and len(parts) >= 3:
            target_qq = int(parts[1])
            group = parts[2]
            
            async with DatabaseManager.session() as session:
                result = await session.execute(
                    select(User).where(User.qq_id == target_qq)
                )
                target_user = result.scalar_one_or_none()
                
                if target_user is None:
                    target_user = User(qq_id=target_qq, allowed_switch_groups=[])
                    session.add(target_user)
                
                groups = list(target_user.allowed_switch_groups or [])
                if group not in groups:
                    groups.append(group)
                    target_user.allowed_switch_groups = groups
                
                await session.commit()
            
            return RouteResult(
                success=True,
                response=f"✅ 已允许用户 {target_qq} 切换 {group} 风格",
                is_system_command=True,
            )
        
        if cmd == "deny" and len(parts) >= 3:
            target_qq = int(parts[1])
            group = parts[2]
            
            async with DatabaseManager.session() as session:
                result = await session.execute(
                    select(User).where(User.qq_id == target_qq)
                )
                target_user = result.scalar_one_or_none()
                
                if target_user:
                    groups = list(target_user.allowed_switch_groups or [])
                    if group in groups:
                        groups.remove(group)
                        target_user.allowed_switch_groups = groups
                    await session.commit()
            
            return RouteResult(
                success=True,
                response=f"✅ 已禁止用户 {target_qq} 切换 {group} 风格",
                is_system_command=True,
            )
        
        if cmd == "set" and len(parts) >= 4:
            target_qq = int(parts[1])
            group = parts[2]
            style_name = " ".join(parts[3:])
            
            # 查找指令集
            target_cs = None
            for cs in self._group_sets.get(group, []):
                if cs.name == style_name or cs.id == style_name:
                    target_cs = cs
                    break
            
            if target_cs is None:
                return RouteResult(
                    success=False,
                    error_message=f"风格 '{style_name}' 不存在",
                    is_system_command=True,
                )
            
            async with DatabaseManager.session() as session:
                result = await session.execute(
                    select(User).where(User.qq_id == target_qq)
                )
                target_user = result.scalar_one_or_none()
                
                if target_user is None:
                    target_user = User(qq_id=target_qq, selected_styles={})
                    session.add(target_user)
                
                styles = dict(target_user.selected_styles or {})
                styles[group] = target_cs.id
                target_user.selected_styles = styles
                await session.commit()
            
            return RouteResult(
                success=True,
                response=f"✅ 已为用户 {target_qq} 设置 {group} 风格为【{target_cs.name}】",
                is_system_command=True,
            )
        
        if cmd == "privilege" and len(parts) >= 2:
            target_qq = int(parts[1])
            enable = parts[2].lower() == "on" if len(parts) > 2 else True
            
            async with DatabaseManager.session() as session:
                result = await session.execute(
                    select(User).where(User.qq_id == target_qq)
                )
                target_user = result.scalar_one_or_none()
                
                if target_user is None:
                    target_user = User(qq_id=target_qq)
                    session.add(target_user)
                
                target_user.is_privileged = enable
                await session.commit()
            
            state = "开启" if enable else "关闭"
            return RouteResult(
                success=True,
                response=f"✅ 已{state}用户 {target_qq} 的特权",
                is_system_command=True,
            )
        
        return RouteResult(
            success=False,
            error_message="无效的管理员指令",
            is_system_command=True,
        )
    
    async def _apply_final_rule(self, message: str) -> RouteResult:
        """应用 Final 规则"""
        config = get_config()
        final = config.final
        
        if final.action == "reject":
            # 如果 send_message 为 False，不返回错误消息
            error_msg = final.message if getattr(final, 'send_message', True) else None
            return RouteResult(
                success=False,
                error_message=error_msg,
            )
        elif final.action == "forward" and final.target_ws:
            response = await self._forward_to_ws(
                final.target_ws,
                message,
                0,
                None,
            )
            return RouteResult(
                success=True,
                target_ws=final.target_ws,
                response=response,
            )
        else:  # allow
            return RouteResult(
                success=True,
                response=None,
            )
    
    async def _forward_to_ws(
        self,
        target_ws: str,
        message: str,
        user_id: int,
        group_id: int | None,
        self_id: int = 0,
        raw_event: dict | None = None,
    ) -> str | None:
        """转发消息到目标 WebSocket"""
        import time
        import random
        import copy
        
        # 优先使用原始事件进行透传
        if raw_event:
            # 浅拷贝一份以修改必要字段
            event = copy.deepcopy(raw_event)
            event["self_id"] = self_id
            
            # 强制将 message 字段设为字符串，以提高兼容性
            # Matcha 等实现可能发送 Message Segment Array，而某些简易 Bot 可能只接受 String
            event["message"] = message
            event["raw_message"] = message
        else:
            # 兼容：如果无原始事件，手动构造 OneBot v11 消息事件
            event = {
                "time": int(time.time()),
                "self_id": self_id,
                "post_type": "message",
                "message_type": "group" if group_id else "private",
                "sub_type": "normal",
                "message_id": random.randint(1, 1000000),
                "user_id": user_id,
                "message": message,
                "raw_message": message,
                "font": 0,
                "sender": {
                    "user_id": user_id,
                    "nickname": "User",
                    "sex": "unknown",
                    "age": 0
                }
            }
            if group_id:
                event["group_id"] = group_id
        
        payload_str = json.dumps(event, ensure_ascii=False)
        logger.info(f"Forwarding to [{target_ws}]: {payload_str}")
        
        # 事件推送通常不需要等待响应，改为直接发送
        success = await self._ws_manager.send_to(target_ws, payload_str)
        
        if not success:
            logger.error(f"Failed to forward message to {target_ws}")
            # 失败也不返回错误给用户，以免刷屏，只记录日志
            return None
            
        # 成功转发不返回任何消息给用户，实现无感转发
        return None
    
    # 分类和指令集管理 API
    def get_categories(self) -> list[Category]:
        """获取所有分类"""
        return self._categories
    
    def get_command_sets(self) -> list[CommandSet]:
        """获取所有指令集"""
        return self._command_sets
    
    def get_command_set(self, id: str) -> CommandSet | None:
        """获取指定指令集"""
        for cs in self._command_sets:
            if cs.id == id:
                return cs
        return None
    
    def get_mutual_exclusive_groups(self) -> dict[str, list[CommandSet]]:
        """获取所有分类及其指令集（互斥组）"""
        return self._group_sets
