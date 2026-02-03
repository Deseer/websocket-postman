"""黑白名单管理 API"""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from src.config import get_config, ConfigManager

router = APIRouter()


class AccessListCreate(BaseModel):
    """创建黑白名单请求"""
    id: str
    name: str
    type: str  # "user" | "group"
    mode: str  # "whitelist" | "blacklist"
    items: list[int] = Field(default_factory=list)


class AccessListUpdate(BaseModel):
    """更新黑白名单请求"""
    name: str | None = None
    type: str | None = None
    mode: str | None = None
    items: list[int] | None = None


@router.get("")
async def get_access_lists():
    """获取所有黑白名单"""
    config = get_config()
    return [
        {
            "id": al.id,
            "name": al.name,
            "type": al.type,
            "mode": al.mode,
            "items": al.items,
        }
        for al in config.access_lists
    ]


@router.get("/conflicts")
async def check_conflicts():
    """检查冲突：同一用户/群同时出现在黑白名单中"""
    config = get_config()
    conflicts = []
    
    # 按类型分组
    user_lists = [al for al in config.access_lists if al.type == "user"]
    group_lists = [al for al in config.access_lists if al.type == "group"]
    
    # 检查用户名单冲突
    for i, list1 in enumerate(user_lists):
        for list2 in user_lists[i+1:]:
            if list1.mode != list2.mode:  # 一白一黑才可能冲突
                common = set(list1.items) & set(list2.items)
                if common:
                    conflicts.append({
                        "type": "user",
                        "list1": {"id": list1.id, "name": list1.name, "mode": list1.mode},
                        "list2": {"id": list2.id, "name": list2.name, "mode": list2.mode},
                        "items": list(common),
                    })
    
    # 检查群聊名单冲突
    for i, list1 in enumerate(group_lists):
        for list2 in group_lists[i+1:]:
            if list1.mode != list2.mode:
                common = set(list1.items) & set(list2.items)
                if common:
                    conflicts.append({
                        "type": "group",
                        "list1": {"id": list1.id, "name": list1.name, "mode": list1.mode},
                        "list2": {"id": list2.id, "name": list2.name, "mode": list2.mode},
                        "items": list(common),
                    })
    
    return {"has_conflicts": len(conflicts) > 0, "conflicts": conflicts}


@router.get("/{access_list_id}")
async def get_access_list(access_list_id: str):
    """获取单个黑白名单"""
    config = get_config()
    for al in config.access_lists:
        if al.id == access_list_id:
            return {
                "id": al.id,
                "name": al.name,
                "type": al.type,
                "mode": al.mode,
                "items": al.items,
            }
    raise HTTPException(status_code=404, detail="黑白名单不存在")


@router.post("")
async def create_access_list(data: AccessListCreate):
    """创建黑白名单"""
    config = get_config()
    
    # 检查 ID 是否已存在
    for al in config.access_lists:
        if al.id == data.id:
            raise HTTPException(status_code=400, detail="黑白名单 ID 已存在")
    
    # 验证类型和模式
    if data.type not in ("user", "group"):
        raise HTTPException(status_code=400, detail="type 必须是 'user' 或 'group'")
    if data.mode not in ("whitelist", "blacklist"):
        raise HTTPException(status_code=400, detail="mode 必须是 'whitelist' 或 'blacklist'")
    
    # 添加到配置
    from src.config import AccessListConfig
    new_list = AccessListConfig(
        id=data.id,
        name=data.name,
        type=data.type,
        mode=data.mode,
        items=data.items,
    )
    config.access_lists.append(new_list)
    ConfigManager.save()
    
    return {"id": data.id, "message": "创建成功"}


@router.put("/{access_list_id}")
async def update_access_list(access_list_id: str, data: AccessListUpdate):
    """更新黑白名单"""
    config = get_config()
    
    for al in config.access_lists:
        if al.id == access_list_id:
            if data.name is not None:
                al.name = data.name
            if data.type is not None:
                if data.type not in ("user", "group"):
                    raise HTTPException(status_code=400, detail="type 必须是 'user' 或 'group'")
                al.type = data.type
            if data.mode is not None:
                if data.mode not in ("whitelist", "blacklist"):
                    raise HTTPException(status_code=400, detail="mode 必须是 'whitelist' 或 'blacklist'")
                al.mode = data.mode
            if data.items is not None:
                al.items = data.items
            
            ConfigManager.save()
            return {"message": "更新成功"}
    
    raise HTTPException(status_code=404, detail="黑白名单不存在")


@router.delete("/{access_list_id}")
async def delete_access_list(access_list_id: str):
    """删除黑白名单"""
    config = get_config()
    
    # 检查是否被指令集引用
    for cs in config.command_sets:
        if cs.user_access_list == access_list_id or cs.group_access_list == access_list_id:
            raise HTTPException(
                status_code=400, 
                detail=f"该黑白名单正在被指令集 '{cs.name}' 使用，请先解除关联"
            )
    
    for i, al in enumerate(config.access_lists):
        if al.id == access_list_id:
            config.access_lists.pop(i)
            ConfigManager.save()
            return {"message": "删除成功"}
    
    raise HTTPException(status_code=404, detail="黑白名单不存在")
