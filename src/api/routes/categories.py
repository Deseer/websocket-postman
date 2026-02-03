"""分类管理 API"""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from src.core.router import CommandRouter
from src.config import get_config, ConfigManager

router = APIRouter()


class CategoryCreate(BaseModel):
    """创建分类请求"""
    id: str
    name: str
    display_name: str
    description: str = ""
    icon: str = ""
    order: int = 0
    enabled: bool = True
    allow_user_switch: bool = True
    default_command_set: str | None = None
    is_mutex: bool = True


class CategoryUpdate(BaseModel):
    """更新分类请求"""
    name: str | None = None
    display_name: str | None = None
    description: str | None = None
    icon: str | None = None
    order: int | None = None
    enabled: bool | None = None
    allow_user_switch: bool | None = None
    default_command_set: str | None = None
    is_mutex: bool | None = None


@router.get("")
async def get_categories():
    """获取所有分类"""
    command_router = CommandRouter()
    categories = command_router.get_categories()
    
    return [
        {
            "id": cat.id,
            "name": cat.name,
            "display_name": cat.display_name,
            "description": cat.description,
            "icon": cat.icon,
            "order": cat.order,
            "enabled": getattr(cat, 'enabled', True),
            "allow_user_switch": cat.allow_user_switch,
            "default_command_set": cat.default_command_set,
            "is_mutex": cat.is_mutex,
        }
        for cat in sorted(categories, key=lambda c: c.order)
    ]


@router.post("")
async def create_category(data: CategoryCreate):
    """创建分类"""
    config = get_config()
    
    # 检查 ID 是否已存在
    for cat in config.categories:
        if cat.id == data.id:
            raise HTTPException(status_code=400, detail="分类 ID 已存在")
    
    # 添加分类
    from src.config import CategoryConfig
    new_category = CategoryConfig(
        id=data.id,
        name=data.name,
        display_name=data.display_name,
        description=data.description,
        icon=data.icon,
        order=data.order,
        enabled=data.enabled,
        allow_user_switch=data.allow_user_switch,
        default_command_set=data.default_command_set,
        is_mutex=data.is_mutex,
    )
    config.categories.append(new_category)
    
    # 保存配置
    ConfigManager.save(config)
    
    # 重新加载路由器
    command_router = CommandRouter()
    command_router.load_from_config()
    
    return {"message": "分类创建成功", "id": data.id}


@router.put("/{category_id}")
async def update_category(category_id: str, data: CategoryUpdate):
    """更新分类"""
    config = get_config()
    
    # 查找分类
    target_category = None
    for cat in config.categories:
        if cat.id == category_id:
            target_category = cat
            break
    
    if target_category is None:
        raise HTTPException(status_code=404, detail="分类不存在")
    
    # 更新字段
    if data.name is not None:
        target_category.name = data.name
    if data.display_name is not None:
        target_category.display_name = data.display_name
    if data.description is not None:
        target_category.description = data.description
    if data.icon is not None:
        target_category.icon = data.icon
    if data.order is not None:
        target_category.order = data.order
    if data.enabled is not None:
        target_category.enabled = data.enabled
    if data.allow_user_switch is not None:
        target_category.allow_user_switch = data.allow_user_switch
    if data.default_command_set is not None:
        target_category.default_command_set = data.default_command_set
    if data.is_mutex is not None:
        target_category.is_mutex = data.is_mutex
    
    # 保存配置
    ConfigManager.save(config)
    
    # 重新加载路由器
    command_router = CommandRouter()
    command_router.load_from_config()
    
    return {"message": "分类更新成功"}


@router.delete("/{category_id}")
async def delete_category(category_id: str):
    """删除分类"""
    config = get_config()
    
    # 查找并删除分类
    for i, cat in enumerate(config.categories):
        if cat.id == category_id:
            config.categories.pop(i)
            break
    else:
        raise HTTPException(status_code=404, detail="分类不存在")
    
    # 保存配置
    ConfigManager.save(config)
    
    # 重新加载路由器
    command_router = CommandRouter()
    command_router.load_from_config()
    
    return {"message": "分类删除成功"}
