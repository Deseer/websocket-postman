"""配置加载模块"""
import os
from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, Field
from pydantic_settings import BaseSettings

from src.utils.logger import logger


class TimeRestriction(BaseModel):
    """时间限制配置"""
    start: str = "00:00"
    end: str = "23:59"


class CommandConfig(BaseModel):
    """单个指令配置"""
    name: str
    aliases: list[str] = Field(default_factory=list)
    description: str = ""
    is_privileged: bool = False
    time_restriction: TimeRestriction | None = None
    group_restriction: list[int] = Field(default_factory=list)
    user_whitelist: list[int] = Field(default_factory=list)
    user_blacklist: list[int] = Field(default_factory=list)


class CommandSetConfig(BaseModel):
    """指令集配置"""
    id: str
    name: str
    prefix: str | None = None
    category: str | None = None
    description: str = ""
    is_public: bool = False
    target_ws: str
    priority: int = 0
    strip_prefix: bool = False
    enabled: bool = True  # 启用开关
    user_access_list: str | None = None  # 用户黑白名单 ID
    group_access_list: str | None = None  # 群聊黑白名单 ID
    is_default: bool = False  # 是否为分类默认指令集
    commands: list[CommandConfig] = Field(default_factory=list)


class CategoryConfig(BaseModel):
    """分类配置"""
    id: str
    name: str
    display_name: str
    description: str = ""
    icon: str = ""
    order: int = 0
    enabled: bool = True  # 启用开关
    allow_user_switch: bool = True  # 是否允许用户切换此分类下的指令集
    default_command_set: str | None = None  # 默认使用的指令集ID
    is_mutex: bool = True  # 此分类下的指令集是否互斥（单选）


class AccessListConfig(BaseModel):
    """黑白名单配置"""
    id: str
    name: str
    type: str  # "user" | "group"
    mode: str  # "whitelist" | "blacklist"
    items: list[int] = Field(default_factory=list)


class ConnectionConfig(BaseModel):
    """WebSocket 连接配置"""
    id: str
    name: str
    url: str
    token: str | None = None  # OneBot v11 认证 Token
    auto_reconnect: bool = True
    reconnect_interval: int = 5
    allow_forward: bool = False  # 是否允许此连接主动发起消息并转发


class FinalConfig(BaseModel):
    """Final 规则配置"""
    action: str = "reject"  # reject / allow / forward
    target_ws: str | None = None
    message: str = "未知指令"
    send_message: bool = True  # 是否发送拒绝消息


class ServerConfig(BaseModel):
    """服务器配置"""
    host: str = "0.0.0.0"
    port: int = 8080
    ws_port: int = 8765


class DatabaseConfig(BaseModel):
    """数据库配置"""
    url: str = "sqlite+aiosqlite:///./data/dispatcher.db"


class LoggingConfig(BaseModel):
    """日志配置"""
    level: str = "INFO"
    file: str | None = None


class AppConfig(BaseModel):
    """应用总配置"""
    server: ServerConfig = Field(default_factory=ServerConfig)
    database: DatabaseConfig = Field(default_factory=DatabaseConfig)
    logging: LoggingConfig = Field(default_factory=LoggingConfig)
    categories: list[CategoryConfig] = Field(default_factory=list)
    connections: list[ConnectionConfig] = Field(default_factory=list)
    command_sets: list[CommandSetConfig] = Field(default_factory=list)
    access_lists: list[AccessListConfig] = Field(default_factory=list)
    final: FinalConfig = Field(default_factory=FinalConfig)
    admins: list[int] = Field(default_factory=list)


class ConfigManager:
    """配置管理器"""
    
    _instance: "ConfigManager | None" = None
    _config: AppConfig | None = None
    _config_path: Path | None = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
    
    @classmethod
    def load(cls, config_path: str | Path | None = None) -> AppConfig:
        """加载配置文件"""
        instance = cls()
        
        if config_path is None:
            # 默认配置路径
            config_path = Path("config/config.yaml")
            if not config_path.exists():
                config_path = Path("config/config.example.yaml")
        
        config_path = Path(config_path)
        instance._config_path = config_path
        
        if not config_path.exists():
            logger.warning(f"配置文件不存在: {config_path}, 使用默认配置")
            instance._config = AppConfig()
            return instance._config
        
        try:
            with open(config_path, "r", encoding="utf-8") as f:
                config_data = yaml.safe_load(f)
            
            instance._config = AppConfig(**config_data)
            logger.info(f"配置加载成功: {config_path}")
            
        except Exception as e:
            logger.error(f"配置加载失败: {e}")
            instance._config = AppConfig()
        
        return instance._config
    
    @classmethod
    def get(cls) -> AppConfig:
        """获取当前配置"""
        instance = cls()
        if instance._config is None:
            return cls.load()
        return instance._config
    
    @classmethod
    def reload(cls) -> AppConfig:
        """重新加载配置"""
        instance = cls()
        if instance._config_path:
            return cls.load(instance._config_path)
        return cls.load()
    
    @classmethod
    def save(cls, config: AppConfig | None = None) -> bool:
        """保存配置到文件"""
        instance = cls()
        if config:
            instance._config = config
        
        if instance._config is None or instance._config_path is None:
            logger.error("无法保存配置: 配置未初始化")
            return False
        
        try:
            # 使用 exclude_defaults 减少冗余，exclude_none 去除 null 值
            config_dict = instance._config.model_dump(
                exclude_defaults=True,
                exclude_none=True,
            )
            
            # 确保必要的顶级键存在
            for key in ['server', 'database', 'logging', 'categories', 
                        'connections', 'command_sets', 'final', 'admins']:
                if key not in config_dict:
                    if key in ['categories', 'connections', 'command_sets', 'admins']:
                        config_dict[key] = []
                    else:
                        config_dict[key] = {}
            
            with open(instance._config_path, "w", encoding="utf-8") as f:
                yaml.dump(
                    config_dict, 
                    f, 
                    allow_unicode=True, 
                    default_flow_style=False,
                    sort_keys=False,  # 保持字段顺序
                )
            
            logger.info(f"配置保存成功: {instance._config_path}")
            return True
            
        except Exception as e:
            logger.error(f"配置保存失败: {e}")
            return False


# 便捷函数
def get_config() -> AppConfig:
    """获取配置的便捷函数"""
    return ConfigManager.get()
