"""指令解析器"""

import re
from dataclasses import dataclass


@dataclass
class ParsedCommand:
    """解析后的指令"""

    raw: str  # 原始消息
    prefix: str | None  # 指令集前缀（如果有）
    command: str  # 指令名（如 /chat）
    args: str  # 指令参数
    is_command: bool  # 是否为指令

    @property
    def full_command(self) -> str:
        """完整指令（包含前缀）"""
        if self.prefix:
            return f"{self.prefix}:{self.command}"
        return self.command


class CommandParser:
    """指令解析器"""

    # 指令前缀正则：可爱风格:/chat 你好
    PREFIX_PATTERN = re.compile(r"^(.+?):(/\S+)(.*)$")

    # 普通指令正则：/chat 你好
    COMMAND_PATTERN = re.compile(r"^(/\S+)(.*)$")

    def __init__(self, command_prefixes: list[str] | None = None):
        """
        初始化解析器

        Args:
            command_prefixes: 有效的指令集前缀列表
        """
        self.command_prefixes = sorted(
            list(set(command_prefixes or [])), key=len, reverse=True
        )
        self._regen_pattern()

    def update_prefixes(self, prefixes: list[str]):
        """更新有效的指令集前缀"""
        self.command_prefixes = sorted(list(set(prefixes)), key=len, reverse=True)
        self._regen_pattern()

    def _regen_pattern(self):
        """重新生成带前缀的正则"""
        if not self.command_prefixes:
            self._combined_pattern = None
            return

        # 构造正则：^(前缀1|前缀2|...)([:\s]*)(/\S+)(.*)$
        # prefix 后面可以接可选的冒号或空格
        prefixes_esc = [re.escape(p) for p in self.command_prefixes]
        pattern_str = f"^({'|'.join(prefixes_esc)})([:\\s]*)(/\\S+)(.*)$"
        self._combined_pattern = re.compile(pattern_str)

    def parse(self, message: str) -> ParsedCommand:
        """
        解析消息

        支持：
        1. 已注册前缀：skr/chat, skr:/chat, skr /chat
        2. 普通指令：/chat
        """
        message = message.strip()

        # 1. 优先尝试匹配已注册的前缀
        if self._combined_pattern:
            match = self._combined_pattern.match(message)
            if match:
                return ParsedCommand(
                    raw=message,
                    prefix=match.group(1),
                    command=match.group(3),
                    args=match.group(4).strip(),
                    is_command=True,
                )

        # 2. 尝试匹配普通指令格式
        cmd_match = self.COMMAND_PATTERN.match(message)
        if cmd_match:
            command = cmd_match.group(1)
            args = cmd_match.group(2).strip()

            return ParsedCommand(
                raw=message,
                prefix=None,
                command=command,
                args=args,
                is_command=True,
            )

        # 不是指令
        return ParsedCommand(
            raw=message,
            prefix=None,
            command="",
            args=message,
            is_command=False,
        )

    def is_system_command(self, command: str) -> bool:
        """检查是否为系统内置指令"""
        system_commands = {"/help", "/status", "/list", "/style", "/admin"}
        return command.split()[0] if command else "" in system_commands
