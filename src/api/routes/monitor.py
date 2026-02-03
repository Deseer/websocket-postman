"""监控 API"""
from datetime import datetime, timedelta
from fastapi import APIRouter, Depends
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.ws_client import WebSocketClientManager
from src.core.ws_server import NapCatWSServer
from src.models.database import get_db
from src.models.user import MessageLog

router = APIRouter()


@router.get("/stats")
async def get_stats(session: AsyncSession = Depends(get_db)):
    """获取统计信息"""
    # WebSocket 连接状态
    ws_manager = WebSocketClientManager.instance()
    ws_status = ws_manager.get_status()
    
    connected_count = sum(1 for s in ws_status.values() if s.get("connected"))
    
    # 今日消息统计
    today = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
    
    result = await session.execute(
        select(func.count(MessageLog.id)).where(MessageLog.timestamp >= today)
    )
    today_messages = result.scalar_one() or 0
    
    # 成功/失败统计
    result = await session.execute(
        select(func.count(MessageLog.id)).where(
            MessageLog.timestamp >= today,
            MessageLog.status == "success",
        )
    )
    success_count = result.scalar_one() or 0
    
    result = await session.execute(
        select(func.count(MessageLog.id)).where(
            MessageLog.timestamp >= today,
            MessageLog.status == "rejected",
        )
    )
    rejected_count = result.scalar_one() or 0
    
    return {
        "connections": {
            "total": len(ws_status),
            "connected": connected_count,
        },
        "messages": {
            "today": today_messages,
            "success": success_count,
            "rejected": rejected_count,
        },
        "timestamp": datetime.now().isoformat(),
    }


@router.get("/logs")
async def get_logs(
    skip: int = 0,
    limit: int = 100,
    user_id: int | None = None,
    group_id: int | None = None,
    status: str | None = None,
    session: AsyncSession = Depends(get_db),
):
    """获取消息日志"""
    query = select(MessageLog).order_by(MessageLog.timestamp.desc())
    
    if user_id is not None:
        query = query.where(MessageLog.user_id == user_id)
    if group_id is not None:
        query = query.where(MessageLog.group_id == group_id)
    if status is not None:
        query = query.where(MessageLog.status == status)
    
    query = query.offset(skip).limit(limit)
    
    result = await session.execute(query)
    logs = result.scalars().all()
    
    return [log.to_dict() for log in logs]


@router.get("/connections")
async def get_connection_status():
    """获取连接状态"""
    ws_manager = WebSocketClientManager.instance()
    return ws_manager.get_status()


@router.get("/system-logs")
async def get_system_logs(lines: int = 200):
    """获取系统日志"""
    from pathlib import Path
    from src.config import get_config
    import re
    
    config = get_config()
    log_file = config.logging.file
    
    if not log_file:
        return []
    
    log_path = Path(log_file)
    if not log_path.exists():
        return []
    
    try:
        with open(log_path, "r", encoding="utf-8") as f:
            # 读取最后 N 行
            all_lines = f.readlines()
            recent_lines = all_lines[-lines:] if len(all_lines) > lines else all_lines
        
        # 解析日志行
        logs = []
        # 日志格式: 2026-02-02 17:07:28 | INFO     | src.config:save:198 - 配置保存成功
        pattern = r"^(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}) \| (\w+)\s+\| (.+)$"
        
        for line in recent_lines:
            line = line.strip()
            if not line:
                continue
            
            match = re.match(pattern, line)
            if match:
                logs.append({
                    "time": match.group(1),
                    "level": match.group(2),
                    "message": match.group(3),
                })
            else:
                # 非标准格式的日志行
                logs.append({
                    "time": "",
                    "level": "INFO",
                    "message": line,
                })
        
        return logs
    except Exception as e:
        return [{"time": "", "level": "ERROR", "message": f"读取日志失败: {e}"}]
