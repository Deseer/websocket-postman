"""WebSocket 客户端管理 - 连接上游服务"""
import asyncio
from dataclasses import dataclass, field
from typing import Any, Callable

import websockets
from websockets.client import WebSocketClientProtocol

from src.config import ConnectionConfig, get_config
from src.utils.logger import logger


@dataclass
class WebSocketConnection:
    """单个 WebSocket 连接"""
    id: str
    name: str
    url: str
    token: str | None = None  # OneBot v11 认证 Token
    auto_reconnect: bool = True
    reconnect_interval: int = 5
    
    _ws: WebSocketClientProtocol | None = field(default=None, repr=False)
    _connected: bool = field(default=False, repr=False)
    _reconnecting: bool = field(default=False, repr=False)
    _message_handler: Callable | None = field(default=None, repr=False)
    _task: asyncio.Task | None = field(default=None, repr=False)
    _stopped: bool = field(default=False, repr=False)  # 用于彻底阻止重连
    _response_queue: asyncio.Queue | None = field(default=None, repr=False)  # 响应队列
    
    @property
    def connected(self) -> bool:
        return self._connected and self._ws is not None
    
    async def connect(self) -> bool:
        """连接到上游服务"""
        if self._connected:
            return True
        
        try:
            logger.info(f"正在连接: {self.name} ({self.url})")
            
            # 构建 headers - OneBot v11 协议需要这些头
            headers = {
                "User-Agent": "WebSocket-Dispatcher/1.0",
                "X-Self-ID": "0",  # 作为客户端连接，使用占位符
                "X-Client-Role": "Universal",  # 表示同时接收事件和 API 响应
            }
            
            # 如果有 Token，添加认证头（OneBot v11 协议）
            if self.token:
                headers["Authorization"] = f"Bearer {self.token}"
            
            self._ws = await websockets.connect(
                self.url,
                additional_headers=headers,
            )
            self._connected = True
            logger.info(f"连接成功: {self.name}")
            
            # 发送 OneBot v11 Lifecycle Connect 事件
            # 这是必须的，否则 NoneBot 等下游应用可能不会处理任何消息
            import time
            import json
            lifecycle_event = {
                "time": int(time.time()),
                "self_id": 0,
                "post_type": "meta_event",
                "meta_event_type": "lifecycle",
                "sub_type": "connect"
            }
            await self._ws.send(json.dumps(lifecycle_event))
            logger.info(f"已发送 lifecycle connect 事件: {self.name}")
            
            # 启动消息接收任务
            self._task = asyncio.create_task(self._receive_loop())
            return True
            
        except Exception as e:
            logger.error(f"连接失败: {self.name} - {e}")
            self._connected = False
            
            if self.auto_reconnect and not self._reconnecting:
                asyncio.create_task(self._reconnect())
            
            return False
    
    async def disconnect(self):
        """断开连接"""
        self._stopped = True  # 设置停止标志，阻止重连
        self._connected = False
        self._reconnecting = False
        
        if self._task:
            self._task.cancel()
            self._task = None
        
        if self._ws:
            await self._ws.close()
            self._ws = None
        
        logger.info(f"已断开连接: {self.name}")
    
    async def send(self, message: str | dict) -> bool:
        """发送消息"""
        if not self.connected:
            logger.warning(f"无法发送消息: {self.name} 未连接")
            return False
        
        try:
            if isinstance(message, dict):
                import json
                message = json.dumps(message, ensure_ascii=False)
            
            await self._ws.send(message)
            return True
            
        except Exception as e:
            logger.error(f"发送消息失败: {self.name} - {e}")
            return False
    
    async def send_and_wait(self, message: str | dict, timeout: float = 30.0) -> str | None:
        """发送消息并等待响应（使用响应队列避免 recv 冲突）"""
        if not self.connected:
            logger.warning(f"无法发送消息: {self.name} 未连接")
            return None
        
        # 初始化或清空响应队列
        if self._response_queue is None:
            self._response_queue = asyncio.Queue()
        else:
            # 清空旧消息
            while not self._response_queue.empty():
                try:
                    self._response_queue.get_nowait()
                except asyncio.QueueEmpty:
                    break
        
        if not await self.send(message):
            return None
        
        try:
            response = await asyncio.wait_for(self._response_queue.get(), timeout=timeout)
            return response
        except asyncio.TimeoutError:
            logger.warning(f"等待响应超时: {self.name}")
            return None
        except Exception as e:
            logger.error(f"接收响应失败: {self.name} - {e}")
            return None
    
    def set_message_handler(self, handler: Callable):
        """设置消息处理器"""
        self._message_handler = handler
    
    async def _receive_loop(self):
        """消息接收循环"""
        try:
            async for message in self._ws:
                # 如果有响应队列，将消息放入队列
                if self._response_queue is not None:
                    await self._response_queue.put(message)
                
                # 同时调用消息处理器
                if self._message_handler:
                    try:
                        await self._message_handler(self.id, message)
                    except Exception as e:
                        logger.error(f"处理消息失败: {self.name} - {e}")
        except websockets.ConnectionClosed:
            logger.warning(f"连接已关闭: {self.name}")
        except Exception as e:
            logger.error(f"接收消息失败: {self.name} - {e}")
        finally:
            self._connected = False
            if self.auto_reconnect and not self._reconnecting and not self._stopped:
                asyncio.create_task(self._reconnect())
    
    async def _reconnect(self):
        """重连"""
        if self._reconnecting:
            return
        
        self._reconnecting = True
        
        while self.auto_reconnect and not self._connected and not self._stopped:
            logger.info(f"{self.reconnect_interval} 秒后重连: {self.name}")
            await asyncio.sleep(self.reconnect_interval)
            
            if await self.connect():
                break
        
        self._reconnecting = False


class WebSocketClientManager:
    """WebSocket 客户端管理器"""
    
    _instance: "WebSocketClientManager | None" = None
    _connections: dict[str, WebSocketConnection]
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._connections = {}
        return cls._instance
    
    @classmethod
    def instance(cls) -> "WebSocketClientManager":
        return cls()
    
    async def init_from_config(self):
        """从配置初始化所有连接"""
        config = get_config()
        
        for conn_config in config.connections:
            await self.add_connection(
                conn_config.id,
                conn_config.name,
                conn_config.url,
                conn_config.token,
                conn_config.auto_reconnect,
                conn_config.reconnect_interval,
            )
    
    async def add_connection(
        self,
        id: str,
        name: str,
        url: str,
        token: str | None = None,
        auto_reconnect: bool = True,
        reconnect_interval: int = 5,
    ) -> WebSocketConnection:
        """添加连接"""
        conn = WebSocketConnection(
            id=id,
            name=name,
            url=url,
            token=token,
            auto_reconnect=auto_reconnect,
            reconnect_interval=reconnect_interval,
        )
        self._connections[id] = conn
        return conn
    
    async def connect_all(self):
        """连接所有上游服务"""
        tasks = [conn.connect() for conn in self._connections.values()]
        await asyncio.gather(*tasks, return_exceptions=True)
    
    async def disconnect_all(self):
        """断开所有连接"""
        tasks = [conn.disconnect() for conn in self._connections.values()]
        await asyncio.gather(*tasks, return_exceptions=True)
    
    def get_connection(self, id: str) -> WebSocketConnection | None:
        """获取连接"""
        return self._connections.get(id)
    
    async def remove_connection(self, id: str) -> bool:
        """移除并断开连接"""
        conn = self._connections.pop(id, None)
        if conn:
            await conn.disconnect()
            return True
        return False
    
    def get_all_connections(self) -> list[WebSocketConnection]:
        """获取所有连接"""
        return list(self._connections.values())
    
    def set_message_handler(self, handler: Callable):
        """为所有连接设置消息处理器"""
        for conn in self._connections.values():
            conn.set_message_handler(handler)
    
    async def send_to(self, connection_id: str, message: str | dict) -> bool:
        """发送消息到指定连接"""
        conn = self.get_connection(connection_id)
        if conn is None:
            logger.warning(f"连接不存在: {connection_id}")
            return False
        return await conn.send(message)
    
    async def send_and_wait(
        self,
        connection_id: str,
        message: str | dict,
        timeout: float = 30.0
    ) -> str | None:
        """发送消息并等待响应"""
        conn = self.get_connection(connection_id)
        if conn is None:
            logger.warning(f"连接不存在: {connection_id}")
            return None
        return await conn.send_and_wait(message, timeout)
    
    def get_status(self) -> dict[str, Any]:
        """获取所有连接状态"""
        return {
            conn.id: {
                "name": conn.name,
                "url": conn.url,
                "connected": conn.connected,
            }
            for conn in self._connections.values()
        }
