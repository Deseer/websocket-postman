"""权限检查器"""
from dataclasses import dataclass
from datetime import datetime, time
from enum import Enum
from typing import Any

from src.models.command_set import Command, CommandSet
from src.models.user import User
from src.config import get_config
from src.utils.logger import logger


class PermissionResult(Enum):
    """权限检查结果"""
    ALLOWED = "allowed"
    BLACKLISTED = "blacklisted"
    NOT_WHITELISTED = "not_whitelisted"
    GROUP_RESTRICTED = "group_restricted"
    TIME_RESTRICTED = "time_restricted"
    PRIVILEGE_REQUIRED = "privilege_required"
    NOT_ALLOWED_TO_SWITCH = "not_allowed_to_switch"


@dataclass
class PermissionCheckResult:
    """权限检查结果详情"""
    allowed: bool
    reason: PermissionResult
    message: str = ""


class PermissionChecker:
    """权限检查器"""
    
    def __init__(self):
        self._admins: set[int] = set()
        self._load_admins()
    
    def _load_admins(self):
        """加载管理员列表"""
        config = get_config()
        self._admins = set(config.admins)
    
    def reload_admins(self):
        """重新加载管理员列表"""
        self._load_admins()
    
    def is_admin(self, user_id: int) -> bool:
        """检查是否为管理员"""
        return user_id in self._admins
    
    def check_command_permission(
        self,
        user: User | None,
        command: Command,
        group_id: int | None = None,
    ) -> PermissionCheckResult:
        """
        检查指令权限
        
        检查顺序：
        1. 检查用户黑名单
        2. 检查用户白名单
        3. 检查群聊限制
        4. 检查时间限制
        5. 检查特权指令权限
        """
        user_id = user.qq_id if user else 0
        
        # 管理员跳过所有检查
        if self.is_admin(user_id):
            return PermissionCheckResult(
                allowed=True,
                reason=PermissionResult.ALLOWED,
            )
        
        # 1. 检查黑名单
        if user_id in command.user_blacklist:
            return PermissionCheckResult(
                allowed=False,
                reason=PermissionResult.BLACKLISTED,
                message="你已被禁止使用此指令",
            )
        
        # 2. 检查白名单（如果有白名单，则只允许白名单内的用户）
        if command.user_whitelist and user_id not in command.user_whitelist:
            return PermissionCheckResult(
                allowed=False,
                reason=PermissionResult.NOT_WHITELISTED,
                message="你没有使用此指令的权限",
            )
        
        # 3. 检查群聊限制
        if command.group_restriction and group_id is not None:
            if group_id not in command.group_restriction:
                return PermissionCheckResult(
                    allowed=False,
                    reason=PermissionResult.GROUP_RESTRICTED,
                    message="此指令不允许在本群使用",
                )
        
        # 4. 检查时间限制
        if command.time_restriction:
            current_time = datetime.now().time()
            if not command.time_restriction.contains(current_time):
                return PermissionCheckResult(
                    allowed=False,
                    reason=PermissionResult.TIME_RESTRICTED,
                    message=f"此指令仅在 {command.time_restriction.start.strftime('%H:%M')} - {command.time_restriction.end.strftime('%H:%M')} 时段可用",
                )
        
        # 5. 检查特权指令
        if command.is_privileged:
            if user is None or not user.is_privileged:
                return PermissionCheckResult(
                    allowed=False,
                    reason=PermissionResult.PRIVILEGE_REQUIRED,
                    message="此指令需要特权才能使用",
                )
        
        return PermissionCheckResult(
            allowed=True,
            reason=PermissionResult.ALLOWED,
        )
    
    def check_style_switch_permission(
        self,
        user: User | None,
        category_allow_switch: bool,
    ) -> PermissionCheckResult:
        """
        检查用户是否可以切换某个分类下的风格
        
        Args:
            user: 用户对象
            category_allow_switch: 分类是否允许用户切换
        """
        user_id = user.qq_id if user else 0
        
        # 管理员总是可以切换
        if self.is_admin(user_id):
            return PermissionCheckResult(
                allowed=True,
                reason=PermissionResult.ALLOWED,
            )
        
        # 检查分类是否允许用户切换
        if not category_allow_switch:
            return PermissionCheckResult(
                allowed=False,
                reason=PermissionResult.NOT_ALLOWED_TO_SWITCH,
                message="此分类不允许用户切换风格，请联系管理员",
            )
        
        return PermissionCheckResult(
            allowed=True,
            reason=PermissionResult.ALLOWED,
        )
