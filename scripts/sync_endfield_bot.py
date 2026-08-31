"""只热更新 EndfieldBot；不运行会重写其他 bot 的全量同步。"""

import argparse
import ast
import json
import tomllib
import urllib.request
from pathlib import Path


def command_records(source: Path) -> list[dict]:
    tree = ast.parse((source / "src/endfieldbot/commands.py").read_text())
    aliases = None
    for node in tree.body:
        if isinstance(node, ast.Assign) and any(
            isinstance(target, ast.Name) and target.id == "ALIASES"
            for target in node.targets
        ):
            aliases = ast.literal_eval(node.value)
    if not isinstance(aliases, dict) or not aliases:
        raise ValueError("EndfieldBot ALIASES 未找到，停止同步")
    records = []
    for alias, action in aliases.items():
        if not isinstance(alias, str) or not isinstance(action, str):
            raise ValueError("EndfieldBot ALIASES 格式无效")
        records.append({
            "name": f"/终末地 {alias}",
            "aliases": [f"/{alias}", f"/zmd {alias}", f"/ef {alias}"],
            "description": f"EndfieldBot: {action}",
            "is_regex": False,
        })
    # 短指令规范化为上游原生命令，不要求开启 short_commands。
    help_record = next(record for record in records if record["name"] == "/终末地 帮助")
    help_record["aliases"].append("/help")
    records.append({"name": "/终末地", "aliases": ["/zmd", "/ef"], "is_regex": False})
    return records


def command_set(source: Path) -> dict:
    return {
        "id": "endfieldbot", "name": "endfieldbot", "prefix": "ef",
        "description": "终末地资料；群聊必须使用 ef 前缀",
        "is_public": True, "target_ws": "endfieldbot", "priority": 150,
        "strip_prefix": False, "enabled": True,
        "require_prefix_in_groups": ["@any"],
        "commands": command_records(source),
    }


def api(base: str, path: str, method="GET", body=None):
    payload = json.dumps(body).encode() if body is not None else None
    request = urllib.request.Request(base + path, data=payload, method=method,
                                     headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(request, timeout=20) as response:
        return json.load(response)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, default=Path("/Users/deseer/project/EndfieldBot"))
    parser.add_argument("--postman", default="http://127.0.0.1:7200")
    args = parser.parse_args()
    settings = tomllib.loads((args.source / "config.local.toml").read_text())["bot"]
    token = settings.get("token", "")
    if len(token) < 16:
        raise ValueError("EndfieldBot token 缺失或过短")
    ready = api("http://127.0.0.1:8792", "/readyz")
    if not ready.get("data_ready"):
        raise RuntimeError("EndfieldBot 素材未就绪")
    desired = command_set(args.source)
    connections = api(args.postman, "/api/connections")
    existing = next((c for c in connections if c["id"] == "endfieldbot"), None)
    self_id = next((c["self_id"] for c in connections if c.get("self_id")), None)
    if not self_id:
        raise RuntimeError("Postman 没有可复用的 OneBot self_id，停止接入")
    connection = {
        "id": "endfieldbot", "name": "endfieldbot",
        "url": "ws://host.docker.internal:8792/onebot/v11/ws",
        "token": token, "self_id": self_id,
        "enabled": True, "auto_reconnect": True,
        "reconnect_interval": 5, "allow_forward": True,
    }
    # 同步明确启用本 bot；其他连接、禁用状态与指令集一律不写。
    api(args.postman, "/api/connections" + ("/endfieldbot" if existing else ""),
        "PUT" if existing else "POST", connection)
    current = api(args.postman, "/api/connections")
    if not next(c for c in current if c["id"] == "endfieldbot")["connected"]:
        api(args.postman, "/api/connections/endfieldbot/disconnect", "POST")
        raise RuntimeError("OneBot 连接失败，已停止重连，未发布指令")
    sets = api(args.postman, "/api/command-sets")
    exists = any(item["id"] == "endfieldbot" for item in sets)
    api(args.postman, "/api/command-sets" + ("/endfieldbot" if exists else ""),
        "PUT" if exists else "POST", desired)
    print(f"EndfieldBot connected; {len(desired['commands'])} command records; prefix=ef")


if __name__ == "__main__":
    main()
