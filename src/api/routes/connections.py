"""连接管理 API"""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from src.core.ws_client import WebSocketClientManager
from src.config import get_config, ConfigManager, ConnectionConfig

router = APIRouter()


class ConnectionCreate(BaseModel):
    """创建连接请求"""
    id: str
    name: str
    url: str
    token: str | None = None  # OneBot v11 认证 Token
    auto_reconnect: bool = True
    reconnect_interval: int = 5
    allow_forward: bool = False


class ConnectionUpdate(BaseModel):
    """更新连接请求"""
    name: str | None = None
    url: str | None = None
    token: str | None = None
    auto_reconnect: bool | None = None
    reconnect_interval: int | None = None
    allow_forward: bool | None = None


@router.get("")
async def get_connections():
    """获取所有连接状态"""
    ws_manager = WebSocketClientManager.instance()
    status = ws_manager.get_status()
    
    config = get_config()
    
    result = []
    for conn_config in config.connections:
        conn_status = status.get(conn_config.id, {})
        result.append({
            "id": conn_config.id,
            "name": conn_config.name,
            "url": conn_config.url,
            "auto_reconnect": conn_config.auto_reconnect,
            "reconnect_interval": conn_config.reconnect_interval,
            "allow_forward": getattr(conn_config, 'allow_forward', False),
            "connected": conn_status.get("connected", False),
        })
    
    return result


@router.post("")
async def create_connection(data: ConnectionCreate):
    """创建连接"""
    config = get_config()
    
    # 检查 ID 是否已存在
    for conn in config.connections:
        if conn.id == data.id:
            raise HTTPException(status_code=400, detail="连接 ID 已存在")
    
    # 添加连接配置
    new_connection = ConnectionConfig(
        id=data.id,
        name=data.name,
        url=data.url,
        token=data.token,
        auto_reconnect=data.auto_reconnect,
        reconnect_interval=data.reconnect_interval,
        allow_forward=data.allow_forward,
    )
    config.connections.append(new_connection)
    
    # 保存配置
    ConfigManager.save(config)
    
    # 添加到管理器并连接
    ws_manager = WebSocketClientManager.instance()
    conn = await ws_manager.add_connection(
        id=data.id,
        name=data.name,
        url=data.url,
        token=data.token,
        auto_reconnect=data.auto_reconnect,
        reconnect_interval=data.reconnect_interval,
    )
    await conn.connect()
    
    return {"message": "连接创建成功", "id": data.id}


@router.put("/{connection_id}")
async def update_connection(connection_id: str, data: ConnectionUpdate):
    """更新连接"""
    config = get_config()
    
    # 查找连接
    target_conn = None
    for conn in config.connections:
        if conn.id == connection_id:
            target_conn = conn
            break
    
    if target_conn is None:
        raise HTTPException(status_code=404, detail="连接不存在")
    
    # 更新字段
    if data.name is not None:
        target_conn.name = data.name
    if data.url is not None:
        target_conn.url = data.url
    if data.auto_reconnect is not None:
        target_conn.auto_reconnect = data.auto_reconnect
    if data.reconnect_interval is not None:
        target_conn.reconnect_interval = data.reconnect_interval
    if data.allow_forward is not None:
        target_conn.allow_forward = data.allow_forward
    
    # 保存配置
    ConfigManager.save(config)
    
    return {"message": "连接更新成功"}


@router.delete("/{connection_id}")
async def delete_connection(connection_id: str):
    """删除连接"""
    config = get_config()
    
    # 查找并删除连接
    for i, conn in enumerate(config.connections):
        if conn.id == connection_id:
            config.connections.pop(i)
            break
    else:
        raise HTTPException(status_code=404, detail="连接不存在")
    
    # 保存配置
    ConfigManager.save(config)
    
    # 从管理器中移除并断开连接
    ws_manager = WebSocketClientManager.instance()
    await ws_manager.remove_connection(connection_id)
    
    return {"message": "连接删除成功"}


@router.post("/{connection_id}/connect")
async def connect_connection(connection_id: str):
    """连接到上游服务"""
    ws_manager = WebSocketClientManager.instance()
    conn = ws_manager.get_connection(connection_id)
    
    if conn is None:
        raise HTTPException(status_code=404, detail="连接不存在")
    
    success = await conn.connect()
    
    if success:
        return {"message": "连接成功"}
    else:
        raise HTTPException(status_code=500, detail="连接失败")


@router.post("/{connection_id}/disconnect")
async def disconnect_connection(connection_id: str):
    """断开连接"""
    ws_manager = WebSocketClientManager.instance()
    conn = ws_manager.get_connection(connection_id)
    
    if conn is None:
        raise HTTPException(status_code=404, detail="连接不存在")
    
    await conn.disconnect()
    
    return {"message": "已断开连接"}
