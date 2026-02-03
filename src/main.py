"""应用入口"""
import asyncio
import json
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
import uvicorn

from src.config import ConfigManager, get_config
from src.core.router import CommandRouter
from src.core.ws_client import WebSocketClientManager
from src.core.ws_server import NapCatWSServer
from src.models.database import DatabaseManager
from src.utils.logger import setup_logger, logger

# 全局实例
ws_server: NapCatWSServer | None = None
ws_client_manager: WebSocketClientManager | None = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期管理"""
    global ws_server, ws_client_manager
    
    # 启动时
    config = get_config()
    
    # 初始化日志
    setup_logger(
        log_level=config.logging.level,
        log_file=config.logging.file,
    )
    
    logger.info("正在启动 WebSocket 指令分配器...")
    
    # 初始化数据库
    await DatabaseManager.init()
    
    # 初始化路由器
    router = CommandRouter()
    router.load_from_config()
    
    # 初始化 WebSocket 客户端管理器
    ws_client_manager = WebSocketClientManager.instance()
    await ws_client_manager.init_from_config()
    
    # 设置全局消息处理器，用于将 Bot 的回复回传给 NapCat
    async def global_bot_message_handler(conn_id: str, message: str):
        # 简单透传：将 Bot 发出的所有 JSON 指令转发给所有连接的 NapCat 客户端
        if ws_server:
            logger.debug(f"回传来自 {conn_id} 的消息: {message[:100]}")
            await ws_server.broadcast(message)
            
    ws_client_manager.set_message_handler(global_bot_message_handler)
    
    await ws_client_manager.connect_all()
    
    # 启动 WebSocket 服务端
    ws_server = NapCatWSServer()
    await ws_server.start(
        host=config.server.host,
        port=config.server.ws_port,
    )
    
    logger.info("WebSocket 指令分配器启动完成!")
    
    yield
    
    # 关闭时
    logger.info("正在关闭 WebSocket 指令分配器...")
    
    if ws_server:
        await ws_server.stop()
    
    if ws_client_manager:
        await ws_client_manager.disconnect_all()
    
    await DatabaseManager.close()
    
    logger.info("WebSocket 指令分配器已关闭")


# 创建 FastAPI 应用
app = FastAPI(
    title="WebSocket 指令分配器",
    description="面向 QQBot/NapCat 的 WebSocket 指令分配器",
    version="1.0.0",
    lifespan=lifespan,
)

# CORS 配置
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 导入 API 路由
from src.api.routes import categories, command_sets, users, connections, monitor, access_lists

app.include_router(categories.router, prefix="/api/categories", tags=["分类管理"])
app.include_router(command_sets.router, prefix="/api/command-sets", tags=["指令集管理"])
app.include_router(users.router, prefix="/api/users", tags=["用户管理"])
app.include_router(connections.router, prefix="/api/connections", tags=["连接管理"])
app.include_router(monitor.router, prefix="/api/monitor", tags=["监控"])
app.include_router(access_lists.router, prefix="/api/access-lists", tags=["黑白名单"])


@app.get("/api/health")
async def health_check():
    """健康检查"""
    return {"status": "ok"}


# 日志 WebSocket 连接管理
log_ws_clients: set[WebSocket] = set()


@app.websocket("/ws/logs")
async def log_websocket(websocket: WebSocket):
    """日志实时推送 WebSocket 端点"""
    import re
    
    await websocket.accept()
    log_ws_clients.add(websocket)
    
    config = get_config()
    log_file = config.logging.file
    
    try:
        if not log_file:
            await websocket.send_json({"error": "日志文件未配置"})
            return
        
        log_path = Path(log_file)
        if not log_path.exists():
            await websocket.send_json({"error": f"日志文件不存在: {log_file}"})
            return
        
        # 日志解析正则
        pattern = r"^(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}) \| (\w+)\s+\| (.+)$"
        
        # 先发送最后 100 行历史日志
        with open(log_path, "r", encoding="utf-8") as f:
            lines = f.readlines()
            recent_lines = lines[-100:] if len(lines) > 100 else lines
            
            for line in recent_lines:
                line = line.strip()
                if not line:
                    continue
                match = re.match(pattern, line)
                if match:
                    await websocket.send_json({
                        "time": match.group(1),
                        "level": match.group(2),
                        "message": match.group(3),
                    })
                else:
                    await websocket.send_json({
                        "time": "",
                        "level": "INFO",
                        "message": line,
                    })
        
        # 然后监控新日志
        with open(log_path, "r", encoding="utf-8") as f:
            # 跳到文件末尾
            f.seek(0, 2)
            
            while True:
                line = f.readline()
                if line:
                    line = line.strip()
                    if line:
                        match = re.match(pattern, line)
                        if match:
                            await websocket.send_json({
                                "time": match.group(1),
                                "level": match.group(2),
                                "message": match.group(3),
                            })
                        else:
                            await websocket.send_json({
                                "time": "",
                                "level": "INFO",
                                "message": line,
                            })
                else:
                    await asyncio.sleep(0.5)
    
    except WebSocketDisconnect:
        pass
    except Exception as e:
        logger.error(f"日志 WebSocket 错误: {e}")
    finally:
        log_ws_clients.discard(websocket)


# 静态文件服务 - 放在 API 路由之后
from pathlib import Path

STATIC_DIR = Path(__file__).parent.parent / "static"


@app.get("/")
async def serve_root():
    """根路径返回 index.html"""
    return FileResponse(STATIC_DIR / "index.html")


# 挂载静态资源
app.mount("/assets", StaticFiles(directory=STATIC_DIR / "assets"), name="static-assets")


@app.get("/{full_path:path}")
async def serve_spa(full_path: str):
    """SPA 路由回退 - 所有未匹配的路径返回 index.html"""
    file_path = STATIC_DIR / full_path
    if file_path.exists() and file_path.is_file():
        return FileResponse(file_path)
    return FileResponse(STATIC_DIR / "index.html")


@app.get("/api/config")
async def get_config_api():
    """获取配置信息"""
    config = get_config()
    return {
        "server": {
            "host": config.server.host,
            "port": config.server.port,
            "ws_port": config.server.ws_port,
        },
        "database": {
            "url": config.database.url,
        },
        "logging": {
            "level": config.logging.level,
            "file": config.logging.file,
        },
        "final": {
            "action": config.final.action,
            "target_ws": config.final.target_ws,
            "message": config.final.message,
            "send_message": getattr(config.final, 'send_message', True),
        },
        "admins": config.admins,
        "categories_count": len(config.categories),
        "command_sets_count": len(config.command_sets),
        "connections_count": len(config.connections),
    }


from pydantic import BaseModel
from typing import Any

class ConfigUpdate(BaseModel):
    """配置更新请求"""
    server: dict | None = None
    database: dict | None = None
    logging: dict | None = None
    final: dict | None = None
    admins: list[int] | None = None


@app.put("/api/config")
async def update_config_api(data: ConfigUpdate):
    """更新配置"""
    config = get_config()
    
    if data.server:
        config.server.host = data.server.get("host", config.server.host)
        config.server.port = data.server.get("port", config.server.port)
        config.server.ws_port = data.server.get("ws_port", config.server.ws_port)
    
    if data.database:
        config.database.url = data.database.get("url", config.database.url)
    
    if data.logging:
        config.logging.level = data.logging.get("level", config.logging.level)
        config.logging.file = data.logging.get("file", config.logging.file)
    
    if data.final:
        config.final.action = data.final.get("action", config.final.action)
        config.final.target_ws = data.final.get("target_ws", config.final.target_ws)
        config.final.message = data.final.get("message", config.final.message)
        if "send_message" in data.final:
            config.final.send_message = data.final.get("send_message")
    
    if data.admins is not None:
        config.admins = data.admins
    
    ConfigManager.save(config)
    
    return {"message": "配置更新成功，请重启服务使配置生效"}


def main():
    """主函数"""
    # 加载配置
    config = ConfigManager.load()
    
    # 启动服务
    uvicorn.run(
        "src.main:app",
        host=config.server.host,
        port=config.server.port,
        reload=False,
        log_level="info",
    )


if __name__ == "__main__":
    main()
