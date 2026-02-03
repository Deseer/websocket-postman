"""指令解析器"""
import re
from dataclasses import dataclass
from typing import Any


@dataclass
class ParsedCommand:
    """解析后的指令"""
    raw: str                          # 原始消息
    prefix: str | None                # 指令集前缀（如果有）
    command: str                      # 指令名（如 /chat）
    args: str                         # 指令参数
    is_command: bool                  # 是否为指令
    
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
        self.command_prefixes = set(command_prefixes or [])
    
    def update_prefixes(self, prefixes: list[str]):
        """更新有效的指令集前缀"""
        self.command_prefixes = set(prefixes)
    
    def parse(self, message: str) -> ParsedCommand:
        """
        解析消息
        
        支持两种格式：
        1. 带前缀：可爱风格:/chat 你好
        2. 普通指令：/chat 你好
        """
        message = message.strip()
        
        # 尝试匹配带前缀的格式
        prefix_match = self.PREFIX_PATTERN.match(message)
        if prefix_match:
            potential_prefix = prefix_match.group(1).strip()
            command = prefix_match.group(2)
            args = prefix_match.group(3).strip()
            
            # 验证前缀是否有效
            if potential_prefix in self.command_prefixes:
                return ParsedCommand(
                    raw=message,
                    prefix=potential_prefix,
                    command=command,
                    args=args,
                    is_command=True,
                )
        
        # 尝试匹配普通指令格式
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
        system_commands = {
            "/help", "/status", "/list", "/style", "/admin"
        }
        return command.split()[0] if command else "" in system_commands
