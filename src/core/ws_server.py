"""WebSocket 服务端 - 接收 NapCat 消息"""
import asyncio
import json
from typing import Any, Callable

import websockets
from websockets.server import WebSocketServerProtocol

from src.config import get_config
from src.core.router import CommandRouter, RouteResult
from src.utils.logger import logger


class NapCatWSServer:
    """NapCat WebSocket 服务端"""
    
    _instance = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance
    
    def __init__(self):
        if self._initialized:
            return
        self._server = None
        self._clients: set[WebSocketServerProtocol] = set()
        self._router = CommandRouter()
        self._running = False
        self._initialized = True
    
    async def start(self, host: str = "0.0.0.0", port: int = 8765):
        """启动 WebSocket 服务"""
        self._running = True
        self._server = await websockets.serve(
            self._handle_connection,
            host,
            port,
        )
        logger.info(f"WebSocket 服务端启动: ws://{host}:{port}")
    
    async def stop(self):
        """停止 WebSocket 服务"""
        self._running = False
        
        # 关闭所有客户端连接
        for client in list(self._clients):
            await client.close()
        
        if self._server:
            self._server.close()
            await self._server.wait_closed()
        
        logger.info("WebSocket 服务端已停止")
    
    async def _handle_connection(self, websocket: WebSocketServerProtocol):
        """处理新连接"""
        self._clients.add(websocket)
        client_info = f"{websocket.remote_address}"
        logger.info(f"NapCat 客户端连接: {client_info}")
        
        try:
            async for message in websocket:
                await self._handle_message(websocket, message)
        except websockets.ConnectionClosed:
            logger.info(f"NapCat 客户端断开: {client_info}")
        except Exception as e:
            logger.error(f"处理消息异常: {e}")
        finally:
            self._clients.discard(websocket)
    
    async def _handle_message(self, websocket: WebSocketServerProtocol, message: str):
        """处理 OneBot 消息"""
        try:
            data = json.loads(message)
            
            # 判断消息类型
            post_type = data.get("post_type")
            
            if post_type == "message":
                await self._handle_onebot_message(websocket, data)
            elif post_type == "meta_event":
                await self._handle_meta_event(data)
            elif post_type == "notice":
                pass  # 暂不处理通知
            elif post_type == "request":
                pass  # 暂不处理请求
            
        except json.JSONDecodeError:
            logger.warning(f"无效的 JSON 消息: {message[:100]}")
        except Exception as e:
            logger.error(f"处理消息失败: {e}")
    
    async def _handle_onebot_message(self, websocket: WebSocketServerProtocol, data: dict):
        """处理 OneBot 消息事件"""
        message_type = data.get("message_type")
        raw_message = data.get("raw_message", "")
        user_id = data.get("user_id", 0)
        group_id = data.get("group_id")
        
        # 获取发送者昵称
        sender = data.get("sender", {})
        nickname = sender.get("nickname", "")
        
        logger.debug(f"收到消息: [{user_id}] {raw_message[:50]}")
        
        # 获取 self_id
        self_id = data.get("self_id", 0)
        
        # 路由指令
        result = await self._router.route(
            message=raw_message,
            user_id=user_id,
            group_id=group_id,
            nickname=nickname,
            self_id=self_id,
            raw_event=data,
        )
        
        # 记录消息日志
        await self._log_message(
            user_id=user_id,
            group_id=group_id,
            command=raw_message[:256],
            result=result,
        )
        
        # 发送响应
        if result.response:
            await self._send_reply(
                websocket,
                data,
                result.response,
            )
        elif result.error_message:
            await self._send_reply(
                websocket,
                data,
                result.error_message,
            )
    
    async def _log_message(
        self,
        user_id: int,
        group_id: int | None,
        command: str,
        result: RouteResult,
    ):
        """记录消息日志到数据库"""
        from src.models.database import DatabaseManager
        from src.models.user import MessageLog
        
        try:
            async with DatabaseManager.session() as session:
                log = MessageLog(
                    user_id=user_id,
                    group_id=group_id,
                    command=command,
                    command_set_id=result.command_set.id if result.command_set else None,
                    target_ws=result.target_ws,
                    status="success" if result.success else "rejected",
                    error_message=result.error_message,
                )
                session.add(log)
                await session.commit()
        except Exception as e:
            logger.error(f"记录消息日志失败: {e}")
    
    async def _handle_meta_event(self, data: dict):
        """处理元事件"""
        meta_event_type = data.get("meta_event_type")
        
        if meta_event_type == "lifecycle":
            sub_type = data.get("sub_type")
            logger.info(f"生命周期事件: {sub_type}")
        elif meta_event_type == "heartbeat":
            pass  # 心跳
    
    async def _send_reply(
        self,
        websocket: WebSocketServerProtocol,
        original_data: dict,
        reply_message: str,
    ):
        """发送回复消息"""
        message_type = original_data.get("message_type")
        
        if message_type == "group":
            action = "send_group_msg"
            params = {
                "group_id": original_data.get("group_id"),
                "message": reply_message,
            }
        else:
            action = "send_private_msg"
            params = {
                "user_id": original_data.get("user_id"),
                "message": reply_message,
            }
        
        response = {
            "action": action,
            "params": params,
            "echo": f"reply_{original_data.get('message_id', '')}",
        }
        
        await websocket.send(json.dumps(response, ensure_ascii=False))
        logger.debug(f"发送回复: {reply_message[:50]}")
    
    async def broadcast(self, message: str):
        """广播消息到所有客户端"""
        if not self._clients:
            return
        
        # 如果是字符串且已经是 JSON，解析后重新序列化以确保格式正确
        # 如果不是，则将其序列化（通常已经是来自 Bot 的 JSON 字符串）
        tasks = [client.send(message) for client in self._clients]
        await asyncio.gather(*tasks, return_exceptions=True)
    
    @property
    def client_count(self) -> int:
        """获取客户端数量"""
        return len(self._clients)
