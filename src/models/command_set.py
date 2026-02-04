"""指令集相关数据模型（内存中的运行时模型）"""

from dataclasses import dataclass, field
from datetime import time
from typing import Any


@dataclass
class TimeRange:
    """时间范围"""

    start: time
    end: time

    @classmethod
    def from_config(cls, config: dict[str, str] | None) -> "TimeRange | None":
        """从配置创建"""
        if config is None:
            return None

        start_parts = config.get("start", "00:00").split(":")
        end_parts = config.get("end", "23:59").split(":")

        return cls(
            start=time(int(start_parts[0]), int(start_parts[1])),
            end=time(int(end_parts[0]), int(end_parts[1])),
        )

    def contains(self, t: time) -> bool:
        """检查时间是否在范围内"""
        if self.start <= self.end:
            return self.start <= t <= self.end
        else:
            # 跨午夜的情况
            return t >= self.start or t <= self.end


@dataclass
class Command:
    """指令"""

    name: str
    aliases: list[str] = field(default_factory=list)
    description: str = ""
    is_privileged: bool = False
    time_restriction: TimeRange | None = None
    group_restriction: list[int] = field(default_factory=list)
    user_whitelist: list[int] = field(default_factory=list)
    user_blacklist: list[int] = field(default_factory=list)

    @classmethod
    def from_config(cls, config: dict[str, Any]) -> "Command":
        """从配置创建"""
        return cls(
            name=config["name"],
            aliases=config.get("aliases", []),
            description=config.get("description", ""),
            is_privileged=config.get("is_privileged", False),
            time_restriction=TimeRange.from_config(config.get("time_restriction")),
            group_restriction=config.get("group_restriction", []),
            user_whitelist=config.get("user_whitelist", []),
            user_blacklist=config.get("user_blacklist", []),
        )

    def matches(self, cmd_name: str) -> bool:
        """检查指令名是否匹配"""
        if cmd_name == self.name:
            return True
        return cmd_name in self.aliases


@dataclass
class CommandSet:
    """指令集"""

    id: str
    name: str
    prefix: str | None = None
    category: str | None = None
    description: str = ""
    is_public: bool = False
    target_ws: str = ""
    priority: int = 0
    strip_prefix: bool = False
    commands: list[Command] = field(default_factory=list)

    @classmethod
    def from_config(cls, config: dict[str, Any]) -> "CommandSet":
        """从配置创建"""
        commands = [Command.from_config(cmd) for cmd in config.get("commands", [])]

        return cls(
            id=config["id"],
            name=config["name"],
            prefix=config.get("prefix"),
            category=config.get("category"),
            description=config.get("description", ""),
            is_public=config.get("is_public", False),
            target_ws=config.get("target_ws", ""),
            priority=config.get("priority", 0),
            strip_prefix=config.get("strip_prefix", False),
            commands=commands,
        )

    def find_command(self, cmd_name: str) -> Command | None:
        """查找指令"""
        for cmd in self.commands:
            if cmd.matches(cmd_name):
                return cmd
        return None

    def find_match(self, text: str) -> tuple[Command, str] | None:
        """
        在文本开头寻找匹配的指令（最长前缀匹配）
        返回: (匹配的指令, 剩余的参数)
        """
        if not text:
            return None

        # 收集所有可能的匹配项（名称和别名）
        all_matchers: list[tuple[str, Command]] = []
        for cmd in self.commands:
            all_matchers.append((cmd.name, cmd))
            for alias in cmd.aliases:
                all_matchers.append((alias, cmd))

        # 按匹配词长度降序排列，确保「最长匹配」
        all_matchers.sort(key=lambda x: len(x[0]), reverse=True)

        for name, cmd in all_matchers:
            if text.startswith(name):
                # 匹配成功，提取参数（去掉匹配到的指令名，并清除首尾空格）
                args = text[len(name) :].strip()
                return cmd, args
        return None


@dataclass
class Category:
    """分类"""

    id: str
    name: str
    display_name: str
    description: str = ""
    icon: str = ""
    order: int = 0
    allow_user_switch: bool = True  # 是否允许用户切换此分类下的指令集
    default_command_set: str | None = None  # 默认使用的指令集ID
    is_mutex: bool = True  # 此分类下的指令集是否互斥

    @classmethod
    def from_config(cls, config: dict[str, Any]) -> "Category":
        """从配置创建"""
        return cls(
            id=config["id"],
            name=config["name"],
            display_name=config.get("display_name", config["name"]),
            description=config.get("description", ""),
            icon=config.get("icon", ""),
            order=config.get("order", 0),
            allow_user_switch=config.get("allow_user_switch", True),
            default_command_set=config.get("default_command_set"),
            is_mutex=config.get("is_mutex", True),
        )
