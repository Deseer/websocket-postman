"""指令集管理 API"""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from src.core.router import CommandRouter
from src.config import get_config, ConfigManager, CommandSetConfig, CommandConfig

router = APIRouter()


class CommandCreate(BaseModel):
    """创建指令请求"""
    name: str
    aliases: list[str] = Field(default_factory=list)
    description: str = ""
    is_privileged: bool = False
    time_restriction: dict | None = None
    group_restriction: list[int] = Field(default_factory=list)
    user_whitelist: list[int] = Field(default_factory=list)
    user_blacklist: list[int] = Field(default_factory=list)


class CommandSetCreate(BaseModel):
    """创建指令集请求"""
    id: str
    name: str
    prefix: str | None = None
    category: str | None = None
    description: str = ""
    is_public: bool = False
    target_ws: str
    priority: int = 0
    strip_prefix: bool = False
    enabled: bool = True
    user_access_list: str | None = None
    group_access_list: str | None = None
    is_default: bool = False
    commands: list[CommandCreate] = Field(default_factory=list)


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
    commands: list[CommandCreate] | None = None


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
            "commands": [
                {
                    "name": cmd.name,
                    "aliases": cmd.aliases,
                    "description": cmd.description,
                    "is_privileged": cmd.is_privileged,
                    "time_restriction": {
                        "start": cmd.time_restriction.start.strftime("%H:%M"),
                        "end": cmd.time_restriction.end.strftime("%H:%M"),
                    } if cmd.time_restriction else None,
                    "group_restriction": cmd.group_restriction,
                    "user_whitelist": cmd.user_whitelist,
                    "user_blacklist": cmd.user_blacklist,
                }
                for cmd in cs.commands
            ],
        })
    
    return result


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
        "commands": [
            {
                "name": cmd.name,
                "aliases": cmd.aliases,
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
    if data.prefix is not None:
        target_cs.prefix = data.prefix
    if data.category is not None:
        target_cs.category = data.category
    if data.description is not None:
        target_cs.description = data.description
    if data.is_public is not None:
        target_cs.is_public = data.is_public
    if data.target_ws is not None:
        target_cs.target_ws = data.target_ws
    if data.priority is not None:
        target_cs.priority = data.priority
    if data.strip_prefix is not None:
        target_cs.strip_prefix = data.strip_prefix
    if data.enabled is not None:
        target_cs.enabled = data.enabled
    if data.user_access_list is not None:
        target_cs.user_access_list = data.user_access_list if data.user_access_list else None
    if data.group_access_list is not None:
        target_cs.group_access_list = data.group_access_list if data.group_access_list else None
    if data.is_default is not None:
        from src.utils.logger import logger
        logger.info(f"Setting is_default for {target_cs.id}: {data.is_default}")
        target_cs.is_default = data.is_default
        # 如果设置为默认指令集，取消同分类下其他指令集的默认状态
        if data.is_default and target_cs.category:
            for cs in config.command_sets:
                if cs.category == target_cs.category and cs.id != target_cs.id:
                    cs.is_default = False
        logger.info(f"After setting, target_cs.is_default = {target_cs.is_default}")
    if data.commands is not None:
        target_cs.commands = [
            CommandConfig(
                name=cmd.name,
                aliases=cmd.aliases,
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


@router.get("/groups/mutual-exclusive")
async def get_mutual_exclusive_groups():
    """获取所有互斥组"""
    command_router = CommandRouter()
    groups = command_router.get_mutual_exclusive_groups()
    
    return {
        group: [
            {"id": cs.id, "name": cs.name}
            for cs in sets
        ]
        for group, sets in groups.items()
    }
