"""用户管理 API"""
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.database import get_db
from src.models.user import User

router = APIRouter()


class UserUpdate(BaseModel):
    """更新用户请求"""
    nickname: str | None = None
    is_admin: bool | None = None
    is_privileged: bool | None = None
    selected_styles: dict[str, str] | None = None
    allowed_switch_groups: list[str] | None = None


@router.get("")
async def get_users(
    skip: int = 0,
    limit: int = 100,
    session: AsyncSession = Depends(get_db),
):
    """获取用户列表"""
    result = await session.execute(
        select(User).offset(skip).limit(limit)
    )
    users = result.scalars().all()
    
    return [user.to_dict() for user in users]


@router.get("/{user_id}")
async def get_user(
    user_id: int,
    session: AsyncSession = Depends(get_db),
):
    """获取指定用户"""
    result = await session.execute(
        select(User).where(User.qq_id == user_id)
    )
    user = result.scalar_one_or_none()
    
    if user is None:
        raise HTTPException(status_code=404, detail="用户不存在")
    
    return user.to_dict()


@router.put("/{user_id}")
async def update_user(
    user_id: int,
    data: UserUpdate,
    session: AsyncSession = Depends(get_db),
):
    """更新用户"""
    result = await session.execute(
        select(User).where(User.qq_id == user_id)
    )
    user = result.scalar_one_or_none()
    
    if user is None:
        # 创建新用户
        user = User(qq_id=user_id)
        session.add(user)
    
    # 更新字段
    if data.nickname is not None:
        user.nickname = data.nickname
    if data.is_admin is not None:
        user.is_admin = data.is_admin
    if data.is_privileged is not None:
        user.is_privileged = data.is_privileged
    if data.selected_styles is not None:
        user.selected_styles = data.selected_styles
    if data.allowed_switch_groups is not None:
        user.allowed_switch_groups = data.allowed_switch_groups
    
    await session.commit()
    
    return {"message": "用户更新成功"}


@router.post("/{user_id}/allow-group/{group}")
async def allow_user_switch_group(
    user_id: int,
    group: str,
    session: AsyncSession = Depends(get_db),
):
    """允许用户切换某互斥组"""
    result = await session.execute(
        select(User).where(User.qq_id == user_id)
    )
    user = result.scalar_one_or_none()
    
    if user is None:
        user = User(qq_id=user_id, allowed_switch_groups=[])
        session.add(user)
    
    groups = list(user.allowed_switch_groups or [])
    if group not in groups:
        groups.append(group)
        user.allowed_switch_groups = groups
    
    await session.commit()
    
    return {"message": f"已允许用户切换 {group}"}


@router.delete("/{user_id}/allow-group/{group}")
async def deny_user_switch_group(
    user_id: int,
    group: str,
    session: AsyncSession = Depends(get_db),
):
    """禁止用户切换某互斥组"""
    result = await session.execute(
        select(User).where(User.qq_id == user_id)
    )
    user = result.scalar_one_or_none()
    
    if user is None:
        raise HTTPException(status_code=404, detail="用户不存在")
    
    groups = list(user.allowed_switch_groups or [])
    if group in groups:
        groups.remove(group)
        user.allowed_switch_groups = groups
    
    await session.commit()
    
    return {"message": f"已禁止用户切换 {group}"}


@router.post("/{user_id}/style/{group}/{style_id}")
async def set_user_style(
    user_id: int,
    group: str,
    style_id: str,
    session: AsyncSession = Depends(get_db),
):
    """为用户设置风格"""
    result = await session.execute(
        select(User).where(User.qq_id == user_id)
    )
    user = result.scalar_one_or_none()
    
    if user is None:
        user = User(qq_id=user_id, selected_styles={})
        session.add(user)
    
    styles = dict(user.selected_styles or {})
    styles[group] = style_id
    user.selected_styles = styles
    
    await session.commit()
    
    return {"message": f"已为用户设置 {group} 风格为 {style_id}"}
