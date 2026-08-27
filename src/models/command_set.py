"""指令集相关数据模型（内存中的运行时模型）"""

import re
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
    is_regex: bool = False
    description: str = ""
    is_privileged: bool = False
    time_restriction: TimeRange | None = None
    group_restriction: list[int] = field(default_factory=list)
    user_whitelist: list[int | str] = field(default_factory=list)
    user_blacklist: list[int | str] = field(default_factory=list)
    is_passthrough: bool = False
    _compiled_regexes: dict[str, re.Pattern[str]] = field(
        default_factory=dict, init=False, repr=False
    )

    def __post_init__(self):
        if self.is_regex:
            self._compiled_regexes = {
                matcher: re.compile(matcher) for matcher in [self.name, *self.aliases]
            }

    def match_regex(self, matcher: str, text: str) -> re.Match[str] | None:
        """使用预编译正则从消息开头匹配。"""
        return self._compiled_regexes[matcher].match(text)

    @classmethod
    def from_config(cls, config: dict[str, Any]) -> "Command":
        """从配置创建"""
        return cls(
            name=config["name"],
            aliases=config.get("aliases", []),
            is_regex=config.get("is_regex", False),
            description=config.get("description", ""),
            is_privileged=config.get("is_privileged", False),
            time_restriction=TimeRange.from_config(config.get("time_restriction")),
            group_restriction=config.get("group_restriction", []),
            user_whitelist=config.get("user_whitelist", []),
            user_blacklist=config.get("user_blacklist", []),
        )

    def matches(self, cmd_name: str) -> bool:
        """检查指令名是否匹配"""
        if self.is_regex:
            return any(
                self.match_regex(pattern, cmd_name)
                for pattern in [self.name, *self.aliases]
            )
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
    is_default: bool = False
    enabled: bool = True
    user_access_list: str | None = None
    group_access_list: str | None = None
    inverse_mode: bool = False
    require_prefix_in_groups: list[int | str] = field(default_factory=list)
    exclude_patterns: list[str] = field(default_factory=list)
    commands: list[Command] = field(default_factory=list)
    _compiled_exclude_patterns: list[re.Pattern[str]] = field(
        default_factory=list, init=False, repr=False
    )

    def __post_init__(self):
        self._compiled_exclude_patterns = [
            re.compile(pattern) for pattern in self.exclude_patterns
        ]

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
            is_default=config.get("is_default", False),
            enabled=config.get("enabled", True),
            user_access_list=config.get("user_access_list"),
            group_access_list=config.get("group_access_list"),
            inverse_mode=config.get("inverse_mode", False),
            require_prefix_in_groups=config.get("require_prefix_in_groups", []),
            exclude_patterns=config.get("exclude_patterns", []),
            commands=commands,
        )

    def requires_prefix(self, group_id: int | None) -> bool:
        """群聊是否必须显式使用该指令集前缀；私聊不受影响。"""
        if group_id is None:
            return False
        return "@any" in self.require_prefix_in_groups or group_id in self.require_prefix_in_groups

    def find_command(self, cmd_name: str) -> Command | None:
        """查找指令"""
        for cmd in self.commands:
            if cmd.matches(cmd_name):
                return cmd
        return None

    _CQ_AT_QQ_PATTERN = re.compile(r"qq=([^,\]]+)")
    _PLACEHOLDER_PATTERN = re.compile(r"@(any|self)")
    _CQ_AT_OR_TEXT_AT_PATTERN = r"(?:\[CQ:at,[^\]]*?\]|@\S+)"
    _CQ_SELF_OR_LITERAL_PATTERN = r"(?:\[CQ:at,[^\]]*?\]|@self|@\S+)"

    @classmethod
    def _extract_qq_from_cq_at(cls, token: str) -> str | None:
        """从 CQ at 码中提取 qq 参数"""
        match = cls._CQ_AT_QQ_PATTERN.search(token)
        if match:
            return match.group(1)
        return None

    @classmethod
    def _match_with_placeholders(
        cls,
        matcher: str,
        text: str,
        self_id: int = 0,
    ) -> int | None:
        """支持 @any/@self 占位符的前缀匹配，返回匹配长度"""
        parts: list[str] = []
        self_groups: list[str] = []

        last_end = 0
        self_group_idx = 0
        previous_was_placeholder = False
        for placeholder_match in cls._PLACEHOLDER_PATTERN.finditer(matcher):
            literal_segment = matcher[last_end : placeholder_match.start()]
            if literal_segment:
                # 兼容 @self/xxx 与 @self /xxx 两种写法
                if previous_was_placeholder and literal_segment[0] in {"/", "#"}:
                    parts.append(r"\s*")
                parts.append(re.escape(literal_segment))

            placeholder_type = placeholder_match.group(1)

            if placeholder_type == "any":
                parts.append(cls._CQ_AT_OR_TEXT_AT_PATTERN)
            else:
                group_name = f"self_at_{self_group_idx}"
                parts.append(
                    fr"(?P<{group_name}>{cls._CQ_SELF_OR_LITERAL_PATTERN})"
                )
                self_groups.append(group_name)
                self_group_idx += 1

            previous_was_placeholder = True
            last_end = placeholder_match.end()

        tail_segment = matcher[last_end:]
        if tail_segment:
            # 兼容 @self/xxx 与 @self /xxx 两种写法
            if previous_was_placeholder and tail_segment[0] in {"/", "#"}:
                parts.append(r"\s*")
            parts.append(re.escape(tail_segment))

        pattern = re.compile("^" + "".join(parts))
        match = pattern.match(text)
        if not match:
            return None

        # @self 必须匹配到当前 bot（self_id）或显式字面量 @self
        expected_self_id = str(self_id)
        for group_name in self_groups:
            token = match.group(group_name)
            if token == "@self":
                continue
            if token.startswith("@"):
                # 纯文本 @昵称 无法从原文稳定还原 qq，按 @self 处理
                continue
            qq = cls._extract_qq_from_cq_at(token)
            if qq is None or qq != expected_self_id:
                return None

        return match.end()

    def find_match(
        self,
        text: str,
        self_id: int = 0,
    ) -> tuple[Command, str, str] | None:
        """
        在文本开头寻找匹配的指令（最长前缀匹配，支持 @any/@self 占位符）
        返回: (匹配的指令, 剩余参数, 实际匹配到的指令文本)
        """
        if not text:
            return None

        if any(pattern.match(text) for pattern in self._compiled_exclude_patterns):
            return None

        if self.inverse_mode:
            # 反向模式中 commands 是排除规则；未命中的消息原样透传。
            for cmd in self.commands:
                if cmd.is_regex:
                    if any(
                        cmd.match_regex(pattern, text)
                        for pattern in [cmd.name, *cmd.aliases]
                    ):
                        return None
                    continue
                if any(text.startswith(matcher) for matcher in [cmd.name, *cmd.aliases]):
                    return None

            passthrough = Command(name=text, is_passthrough=True)
            return passthrough, "", text

        # 收集所有可能的匹配项（名称和别名）
        all_matchers: list[tuple[str, Command]] = []
        for cmd in self.commands:
            all_matchers.append((cmd.name, cmd))
            for alias in cmd.aliases:
                all_matchers.append((alias, cmd))

        # 按匹配词长度降序排列，确保「最长匹配」
        all_matchers.sort(key=lambda x: len(x[0]), reverse=True)

        best_match: tuple[int, Command, str, str] | None = None
        for name, cmd in all_matchers:
            if cmd.is_regex:
                match = cmd.match_regex(name, text)
                if not match:
                    continue
                matched_text = match.group(0)
                args = text[match.end() :].strip()
                candidate = (len(matched_text), cmd, args, matched_text)
                if best_match is None or candidate[0] > best_match[0]:
                    best_match = candidate
                continue

            if "@any" in name or "@self" in name:
                match_len = self._match_with_placeholders(name, text, self_id=self_id)
                if match_len is None:
                    continue

                matched_text = text[:match_len]
                args = text[match_len:].strip()
                candidate = (match_len, cmd, args, matched_text)
                if best_match is None or candidate[0] > best_match[0]:
                    best_match = candidate
                continue

            if text.startswith(name):
                # 匹配成功，提取参数（去掉匹配到的指令名，并清除首尾空格）
                args = text[len(name) :].strip()
                candidate = (len(name), cmd, args, name)
                if best_match is None or candidate[0] > best_match[0]:
                    best_match = candidate

        if best_match is None:
            return None
        _, command, args, matched_text = best_match
        return command, args, matched_text


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
    enabled: bool = True

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
            enabled=config.get("enabled", True),
        )
