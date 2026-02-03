"""数据库连接和会话管理"""
from contextlib import asynccontextmanager
from pathlib import Path
from typing import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

from src.config import get_config
from src.utils.logger import logger


class Base(DeclarativeBase):
    """SQLAlchemy 基类"""
    pass


class DatabaseManager:
    """数据库管理器"""
    
    _instance: "DatabaseManager | None" = None
    _engine = None
    _session_factory = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
    
    @classmethod
    async def init(cls, db_url: str | None = None):
        """初始化数据库连接"""
        instance = cls()
        
        if db_url is None:
            config = get_config()
            db_url = config.database.url
        
        # 确保数据目录存在
        if "sqlite" in db_url:
            db_path = db_url.split("///")[-1]
            Path(db_path).parent.mkdir(parents=True, exist_ok=True)
        
        instance._engine = create_async_engine(
            db_url,
            echo=False,
            future=True,
        )
        
        instance._session_factory = async_sessionmaker(
            instance._engine,
            class_=AsyncSession,
            expire_on_commit=False,
        )
        
        # 创建所有表
        async with instance._engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        
        logger.info(f"数据库初始化完成: {db_url}")
    
    @classmethod
    async def close(cls):
        """关闭数据库连接"""
        instance = cls()
        if instance._engine:
            await instance._engine.dispose()
            logger.info("数据库连接已关闭")
    
    @classmethod
    @asynccontextmanager
    async def session(cls) -> AsyncGenerator[AsyncSession, None]:
        """获取数据库会话"""
        instance = cls()
        if instance._session_factory is None:
            await cls.init()
        
        async with instance._session_factory() as session:
            try:
                yield session
                await session.commit()
            except Exception:
                await session.rollback()
                raise


# 便捷函数
async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """获取数据库会话的依赖注入函数"""
    async with DatabaseManager.session() as session:
        yield session
