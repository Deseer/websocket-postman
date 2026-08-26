"""指令集管理 API"""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field, model_validator

from src.core.router import CommandRouter
from src.config import (
    CommandConfig,
    CommandSetConfig,
    ConfigManager,
    get_config,
    validate_command_matchers,
)

router = APIRouter()


class CommandCreate(BaseModel):
    """创建指令请求"""
    name: str
    aliases: list[str] = Field(default_factory=list)
    is_regex: bool = False
    description: str = ""
    is_privileged: bool = False
    time_restriction: dict | None = None
    group_restriction: list[int] = Field(default_factory=list)
    user_whitelist: list[int | str] = Field(default_factory=list)
    user_blacklist: list[int | str] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_matchers(self):
        """让前端在保存时直接得到可读的正则错误。"""
        validate_command_matchers(self.name, self.aliases, self.is_regex)
        return self


class CommandSetCreate(BaseModel):
    """创建指令集请求"""
    id: str
    name: str
    prefix: str | None = None
    category: str | None = None
    description: str = ""
    is_public: bool = False
    target_ws: str = Field(min_length=1)
    priority: int = 0
    strip_prefix: bool = False
    enabled: bool = True
    user_access_list: str | None = None
    group_access_list: str | None = None
    is_default: bool = False
    inverse_mode: bool = False
    require_prefix_in_groups: list[int | str] = Field(default_factory=list)
    exclude_patterns: list[str] = Field(default_factory=list)
    commands: list[CommandCreate] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_routing_rules(self):
        CommandSetConfig(
            id=self.id,
            name=self.name,
            target_ws=self.target_ws,
            require_prefix_in_groups=self.require_prefix_in_groups,
            exclude_patterns=self.exclude_patterns,
        )
        return self


class CommandSetUpdate(BaseModel):
    """更新指令集请求"""
    name: str | None = None
    prefix: str | None = None
    category: str | None = None
    description: str | None = None
    is_public: bool | None = None
    target_ws: str | None = None
    priority: int | None = None
    strip_prefix: bool | None = None
    enabled: bool | None = None
    user_access_list: str | None = None
    group_access_list: str | None = None
    is_default: bool | None = None
    inverse_mode: bool | None = None
    require_prefix_in_groups: list[int | str] | None = None
    exclude_patterns: list[str] | None = None
    commands: list[CommandCreate] | None = None

    @model_validator(mode="after")
    def validate_target(self):
        if "target_ws" in self.model_fields_set and not self.target_ws:
            raise ValueError("目标连接不能为空")
        if self.require_prefix_in_groups is not None:
            invalid_groups = [
                item
                for item in self.require_prefix_in_groups
                if not isinstance(item, int) and item != "@any"
            ]
            if invalid_groups:
                raise ValueError("强制前缀群聊仅支持群号或 @any")
        if self.exclude_patterns is not None:
            import re

            for pattern in self.exclude_patterns:
                if not pattern:
                    raise ValueError("排除正则不能为空")
                try:
                    compiled = re.compile(pattern)
                except re.error as exc:
                    raise ValueError(f"无效的排除正则 {pattern!r}: {exc}") from exc
                if compiled.match(""):
                    raise ValueError(f"排除正则不能匹配空字符串: {pattern!r}")
        return self


@router.get("")
async def get_command_sets():
    """获取所有指令集"""
    config = get_config()
    command_sets = config.command_sets
    
    result = []
    for cs in command_sets:
        result.append({
            "id": cs.id,
            "name": cs.name,
            "prefix": cs.prefix,
            "category": cs.category,
            "description": cs.description,
            "is_public": cs.is_public,
            "target_ws": cs.target_ws,
            "priority": cs.priority,
            "strip_prefix": cs.strip_prefix,
            "enabled": getattr(cs, 'enabled', True),
            "user_access_list": getattr(cs, 'user_access_list', None),
            "group_access_list": getattr(cs, 'group_access_list', None),
            "is_default": getattr(cs, 'is_default', False),
            "inverse_mode": getattr(cs, 'inverse_mode', False),
            "require_prefix_in_groups": getattr(cs, 'require_prefix_in_groups', []),
            "exclude_patterns": getattr(cs, 'exclude_patterns', []),
            "commands": [
                {
                    "name": cmd.name,
                    "aliases": cmd.aliases,
                    "is_regex": cmd.is_regex,
                    "description": cmd.description,
                    "is_privileged": cmd.is_privileged,
                    "time_restriction": cmd.time_restriction.model_dump()
                    if cmd.time_restriction
                    else None,
                    "group_restriction": cmd.group_restriction,
                    "user_whitelist": cmd.user_whitelist,
                    "user_blacklist": cmd.user_blacklist,
                }
                for cmd in cs.commands
            ],
        })
    
    return result


@router.get("/groups/mutual-exclusive")
async def get_mutual_exclusive_groups():
    """获取所有互斥组。必须注册在动态 ID 路由之前。"""
    command_router = CommandRouter()
    groups = command_router.get_mutual_exclusive_groups()

    return {
        group: [{"id": cs.id, "name": cs.name} for cs in sets]
        for group, sets in groups.items()
    }


@router.get("/{command_set_id}")
async def get_command_set(command_set_id: str):
    """获取指定指令集"""
    command_router = CommandRouter()
    cs = command_router.get_command_set(command_set_id)
    
    if cs is None:
        raise HTTPException(status_code=404, detail="指令集不存在")
    
    return {
        "id": cs.id,
        "name": cs.name,
        "prefix": cs.prefix,
        "category": cs.category,
        "description": cs.description,
        "is_public": cs.is_public,
        "target_ws": cs.target_ws,
        "priority": cs.priority,
        "strip_prefix": cs.strip_prefix,
        "enabled": cs.enabled,
        "user_access_list": cs.user_access_list,
        "group_access_list": cs.group_access_list,
        "is_default": cs.is_default,
        "inverse_mode": cs.inverse_mode,
        "require_prefix_in_groups": cs.require_prefix_in_groups,
        "exclude_patterns": cs.exclude_patterns,
        "commands": [
            {
                "name": cmd.name,
                "aliases": cmd.aliases,
                "is_regex": cmd.is_regex,
                "description": cmd.description,
                "is_privileged": cmd.is_privileged,
            }
            for cmd in cs.commands
        ],
    }


@router.post("")
async def create_command_set(data: CommandSetCreate):
    """创建指令集"""
    config = get_config()
    
    # 检查 ID 是否已存在
    for cs in config.command_sets:
        if cs.id == data.id:
            raise HTTPException(status_code=400, detail="指令集 ID 已存在")
    
    # 创建指令列表
    commands = [
        CommandConfig(
            name=cmd.name,
            aliases=cmd.aliases,
            is_regex=cmd.is_regex,
            description=cmd.description,
            is_privileged=cmd.is_privileged,
            time_restriction=cmd.time_restriction,
            group_restriction=cmd.group_restriction,
            user_whitelist=cmd.user_whitelist,
            user_blacklist=cmd.user_blacklist,
        )
        for cmd in data.commands
    ]
    
    # 添加指令集
    new_command_set = CommandSetConfig(
        id=data.id,
        name=data.name,
        prefix=data.prefix,
        category=data.category,
        description=data.description,
        is_public=data.is_public,
        target_ws=data.target_ws,
        priority=data.priority,
        strip_prefix=data.strip_prefix,
        enabled=data.enabled,
        user_access_list=data.user_access_list,
        group_access_list=data.group_access_list,
        is_default=data.is_default,
        inverse_mode=data.inverse_mode,
        require_prefix_in_groups=data.require_prefix_in_groups,
        exclude_patterns=data.exclude_patterns,
        commands=commands,
    )
    
    # 如果设置为默认指令集，取消同分类下其他指令集的默认状态
    if data.is_default and data.category:
        for cs in config.command_sets:
            if cs.category == data.category and cs.id != data.id:
                cs.is_default = False
    
    config.command_sets.append(new_command_set)
    
    # 保存配置
    ConfigManager.save(config)
    
    # 重新加载路由器
    command_router = CommandRouter()
    command_router.load_from_config()
    
    return {"message": "指令集创建成功", "id": data.id}


@router.put("/{command_set_id}")
async def update_command_set(command_set_id: str, data: CommandSetUpdate):
    """更新指令集"""
    config = get_config()
    
    # 查找指令集
    target_cs = None
    for cs in config.command_sets:
        if cs.id == command_set_id:
            target_cs = cs
            break
    
    if target_cs is None:
        raise HTTPException(status_code=404, detail="指令集不存在")
    
    # 更新字段
    if data.name is not None:
        target_cs.name = data.name
    if "prefix" in data.model_fields_set:
        target_cs.prefix = data.prefix or None
    if "category" in data.model_fields_set:
        target_cs.category = data.category or None
    if data.description is not None:
        target_cs.description = data.description
    if data.is_public is not None:
        target_cs.is_public = data.is_public
    if "target_ws" in data.model_fields_set:
        target_cs.target_ws = data.target_ws
    if data.priority is not None:
        target_cs.priority = data.priority
    if data.strip_prefix is not None:
        target_cs.strip_prefix = data.strip_prefix
    if data.enabled is not None:
        target_cs.enabled = data.enabled
    if "user_access_list" in data.model_fields_set:
        target_cs.user_access_list = data.user_access_list or None
    if "group_access_list" in data.model_fields_set:
        target_cs.group_access_list = data.group_access_list or None
    if data.is_default is not None:
        target_cs.is_default = data.is_default
        # 如果设置为默认指令集，取消同分类下其他指令集的默认状态
        if data.is_default and target_cs.category:
            for cs in config.command_sets:
                if cs.category == target_cs.category and cs.id != target_cs.id:
                    cs.is_default = False
    if data.inverse_mode is not None:
        target_cs.inverse_mode = data.inverse_mode
    if data.require_prefix_in_groups is not None:
        target_cs.require_prefix_in_groups = data.require_prefix_in_groups
    if data.exclude_patterns is not None:
        target_cs.exclude_patterns = data.exclude_patterns
    if data.commands is not None:
        target_cs.commands = [
            CommandConfig(
                name=cmd.name,
                aliases=cmd.aliases,
                is_regex=cmd.is_regex,
                description=cmd.description,
                is_privileged=cmd.is_privileged,
                time_restriction=cmd.time_restriction,
                group_restriction=cmd.group_restriction,
                user_whitelist=cmd.user_whitelist,
                user_blacklist=cmd.user_blacklist,
            )
            for cmd in data.commands
        ]
    
    # 保存配置
    ConfigManager.save(config)
    
    # 重新加载路由器
    command_router = CommandRouter()
    command_router.load_from_config()
    
    return {"message": "指令集更新成功"}


@router.delete("/{command_set_id}")
async def delete_command_set(command_set_id: str):
    """删除指令集"""
    config = get_config()
    
    # 查找并删除指令集
    for i, cs in enumerate(config.command_sets):
        if cs.id == command_set_id:
            config.command_sets.pop(i)
            break
    else:
        raise HTTPException(status_code=404, detail="指令集不存在")
    
    # 保存配置
    ConfigManager.save(config)
    
    # 重新加载路由器
    command_router = CommandRouter()
    command_router.load_from_config()
    
    return {"message": "指令集删除成功"}
