"""用户数据模型"""
from datetime import datetime
from typing import Any

from sqlalchemy import JSON, Boolean, DateTime, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column

from src.models.database import Base


class User(Base):
    """用户表"""
    __tablename__ = "users"
    
    qq_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    nickname: Mapped[str] = mapped_column(String(64), default="")
    is_admin: Mapped[bool] = mapped_column(Boolean, default=False)
    is_privileged: Mapped[bool] = mapped_column(Boolean, default=False)
    
    # 用户选择的风格 {"bot_style": "style-cute", "music_style": "netease"}
    selected_styles: Mapped[dict[str, str]] = mapped_column(
        JSON, default=dict
    )
    
    # 管理员允许用户自由切换的互斥组
    allowed_switch_groups: Mapped[list[str]] = mapped_column(
        JSON, default=list
    )
    
    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now()
    )
    
    def to_dict(self) -> dict[str, Any]:
        """转换为字典"""
        return {
            "qq_id": self.qq_id,
            "nickname": self.nickname,
            "is_admin": self.is_admin,
            "is_privileged": self.is_privileged,
            "selected_styles": self.selected_styles,
            "allowed_switch_groups": self.allowed_switch_groups,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }


class MessageLog(Base):
    """消息日志表"""
    __tablename__ = "message_logs"
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(Integer, index=True)
    group_id: Mapped[int | None] = mapped_column(Integer, nullable=True, index=True)
    command: Mapped[str] = mapped_column(String(256))
    command_set_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    target_ws: Mapped[str | None] = mapped_column(String(64), nullable=True)
    status: Mapped[str] = mapped_column(String(32))  # success / rejected / error
    error_message: Mapped[str | None] = mapped_column(String(512), nullable=True)
    timestamp: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), index=True
    )
    
    def to_dict(self) -> dict[str, Any]:
        """转换为字典"""
        return {
            "id": self.id,
            "user_id": self.user_id,
            "group_id": self.group_id,
            "command": self.command,
            "command_set_id": self.command_set_id,
            "target_ws": self.target_ws,
            "status": self.status,
            "error_message": self.error_message,
            "timestamp": self.timestamp.isoformat() if self.timestamp else None,
        }
