#!/usr/bin/env python3
"""从本地 ArkBot、Mizuki 和 Haruki 源码同步 Postman 指令集。"""

from __future__ import annotations

import argparse
import ast
import json
import re
from pathlib import Path

import yaml


GO_STRING = re.compile(r'"(?:\\.|[^"\\])*"')

CONNECTION_ID_MIGRATIONS = {
    "8823-4uqw": "8823",
    "hrkbot-8kmo": "hrkbot",
    "mzkbot-local": "mzkbot",
    "arkbot-local": "arkbot",
    "sakurabot-6qgi": "sakurabot",
}
COMMAND_SET_ID_MIGRATIONS = {
    "hrkbot-339v": "hrkbot",
    "sakurabot-40j2": "sakurabot",
    "8823-tzcm": "8823",
    "mzkbot-local": "mzkbot",
    "arkbot-local": "arkbot",
}
CATEGORY_ID_MIGRATIONS = {"pjsk-2vd6": "pjsk"}


def go_strings(text: str) -> list[str]:
    return [json.loads(item) for item in GO_STRING.findall(text)]


def unique_groups(groups: list[list[str]]) -> list[list[str]]:
    result: list[list[str]] = []
    seen: set[tuple[str, ...]] = set()
    for group in groups:
        clean = list(dict.fromkeys(item.strip() for item in group if item.strip()))
        key = tuple(clean)
        if clean and key not in seen:
            seen.add(key)
            result.append(clean)
    return result


def haruki_commands(cloud_root: Path, client_root: Path) -> list[list[str]]:
    groups: list[list[str]] = []
    handler_root = cloud_root / "internal/pjsk/handler"
    labelled = re.compile(r"Commands:\s*\[\]string\s*\{(.*?)\}", re.S)
    for path in sorted(handler_root.glob("*.go")):
        groups.extend(go_strings(body) for body in labelled.findall(path.read_text()))

    alias_text = (handler_root / "alias.go").read_text()
    alias_calls = re.compile(
        r"newEntityAlias(?:Query|Add|Delete)Handler\(.*?\[\]string\s*\{(.*?)\}",
        re.S,
    )
    groups.extend(go_strings(body) for body in alias_calls.findall(alias_text))

    timezone_text = (
        cloud_root / "internal/pjsk/displaytime/timezone_input.go"
    ).read_text()
    aliases_match = re.search(
        r"var timeZoneAliases\s*=\s*map\[string\]string\s*\{(.*?)\n\}",
        timezone_text,
        re.S,
    )
    timezone_aliases = []
    if aliases_match:
        timezone_aliases = re.findall(r'^\s*"([^"]+)"\s*:', aliases_match.group(1), re.M)
    timezone_commands = ["/pjsk时区", "/pjsktimezone", "/pjsktz"]
    for prefix in ("/pjsktimezone", "/pjsktz"):
        timezone_commands.extend(prefix + alias for alias in sorted(timezone_aliases))
    groups.append(timezone_commands)

    birthday_base = [
        "/烤森生日取消监听",
        "/mysekai birthday unmonitor",
        "/ms生日取消监听",
        "/烤森生日监听",
        "/mysekai birthday monitor",
        "/ms生日监听",
    ]
    groups.append(
        birthday_base
        + [
            f"/{region}{command.removeprefix('/')}"
            for command in birthday_base
            for region in ("jp", "tw", "kr", "en", "cn")
        ]
    )

    groups.append(["/haruki_info", "/haruki info"])
    groups.append(["help", "/help"])
    groups.append(
        [
            "/haruki",
            "/hcbladd",
            "/hcbldel",
            "/hcblset",
            "/hcblrm",
            "/hcwladd",
            "/hcwldel",
            "/hcwlset",
            "/hcwlrm",
            "/hcmode",
            "/hccollect",
        ]
    )

    # 客户端兼容层是本地实际运行路径的一部分，纳入来源检查以避免路径写错。
    if not (client_root / "src/services/routing/service.rs").exists():
        raise FileNotFoundError(f"Haruki Client 源码不存在: {client_root}")
    return unique_groups(groups)


def seg_variants(command: str) -> list[str]:
    parts = command.replace("_", " ").split()
    return [sep.join(parts) for sep in ("", " ", "_")]


def mizuki_commands(root: Path) -> list[list[str]]:
    groups: list[list[str]] = []
    gallery_path = root / "src/plugins/gallery/__init__.py"
    gallery_text = gallery_path.read_text()
    for match in re.finditer(r"CmdHandler\(\s*(\[.*?\])\s*,", gallery_text, re.S):
        try:
            values = ast.literal_eval(match.group(1))
        except (SyntaxError, ValueError):
            continue
        if isinstance(values, list) and all(isinstance(item, str) for item in values):
            expanded = [variant for item in values for variant in seg_variants(item)]
            groups.append(["/" + item for item in expanded])

    for path in sorted((root / "src/plugins").rglob("*.py")):
        if path == gallery_path:
            continue
        try:
            tree = ast.parse(path.read_text())
        except SyntaxError:
            continue
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            if not isinstance(node.func, ast.Name) or node.func.id != "on_command":
                continue
            if not node.args or not isinstance(node.args[0], ast.Constant):
                continue
            if not isinstance(node.args[0].value, str):
                continue
            values = [node.args[0].value]
            for keyword in node.keywords:
                if keyword.arg != "aliases" or not isinstance(
                    keyword.value, (ast.Set, ast.List, ast.Tuple)
                ):
                    continue
                values.extend(
                    item.value
                    for item in keyword.value.elts
                    if isinstance(item, ast.Constant) and isinstance(item.value, str)
                )
            groups.append(["/" + item for item in values])
    return unique_groups(groups)


def command_records(groups: list[list[str]]) -> list[dict]:
    return [
        {
            "name": group[0],
            "aliases": group[1:],
            "description": "",
            "is_privileged": False,
            "group_restriction": [],
            "user_whitelist": [],
            "user_blacklist": [],
        }
        for group in groups
    ]


def prefix_collision_exclusion_patterns(
    own_groups: list[list[str]], other_groups: list[list[str]]
) -> list[str]:
    """阻止本指令集的短字面指令抢占其他指令集的长指令。"""
    own_commands = {item for group in own_groups for item in group}
    other_commands = {item for group in other_groups for item in group}
    collisions = sorted(
        {
            other
            for own in own_commands
            for other in other_commands
            if other != own and other.startswith(own)
        },
        key=lambda item: (-len(item), item),
    )
    if not collisions:
        return []
    return [r"^(?:" + "|".join(re.escape(item) for item in collisions) + ")"]


def upsert_connection(config: dict, connection: dict) -> None:
    connections = config.setdefault("connections", [])
    existing = next((item for item in connections if item["id"] == connection["id"]), None)
    if existing:
        existing.update(connection)
    else:
        connections.append(connection)


def upsert_command_set(config: dict, command_set: dict) -> None:
    command_sets = config.setdefault("command_sets", [])
    existing = next((item for item in command_sets if item["id"] == command_set["id"]), None)
    if existing:
        existing.clear()
        existing.update(command_set)
    else:
        command_sets.append(command_set)


def migrate_stable_ids(config: dict) -> None:
    """将旧的随机后缀 ID 迁移为可读且稳定的语义 ID。"""
    for connection in config.get("connections", []):
        connection["id"] = CONNECTION_ID_MIGRATIONS.get(
            connection["id"], connection["id"]
        )

    for category in config.get("categories", []):
        old_id = category["id"]
        category["id"] = CATEGORY_ID_MIGRATIONS.get(old_id, old_id)
        if category.get("name") == old_id:
            category["name"] = category["id"]
        default_id = category.get("default_command_set")
        if default_id:
            category["default_command_set"] = COMMAND_SET_ID_MIGRATIONS.get(
                default_id, default_id
            )

    for command_set in config.get("command_sets", []):
        command_set["id"] = COMMAND_SET_ID_MIGRATIONS.get(
            command_set["id"], command_set["id"]
        )
        category_id = command_set.get("category")
        if category_id:
            command_set["category"] = CATEGORY_ID_MIGRATIONS.get(
                category_id, category_id
            )
        target_ws = command_set.get("target_ws")
        if target_ws:
            command_set["target_ws"] = CONNECTION_ID_MIGRATIONS.get(
                target_ws, target_ws
            )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", type=Path, default=Path("config/config.yaml"))
    parser.add_argument("--haruki-cloud", type=Path, default=Path("/Users/deseer/project/Haruki-Cloud"))
    parser.add_argument("--haruki-client", type=Path, default=Path("/Users/deseer/project/Haruki-Client"))
    parser.add_argument("--mizuki", type=Path, default=Path("/Users/deseer/project/mizukibot/mizuki"))
    parser.add_argument("--self-id", type=int, help="上游 OneBot 握手使用的机器人 QQ")
    args = parser.parse_args()

    config = yaml.safe_load(args.config.read_text())
    migrate_stable_ids(config)
    haruki = haruki_commands(args.haruki_cloud, args.haruki_client)
    mizuki = mizuki_commands(args.mizuki)

    # 旧配置曾以 lunabout 直连同一个 Mizuki 端点；保留会造成重复连接和 403 重试。
    config["connections"] = [
        item for item in config.get("connections", []) if item.get("id") != "lunabout-um26"
    ]

    mizuki_token = ""
    mizuki_env = args.mizuki / ".env"
    if mizuki_env.exists():
        for line in mizuki_env.read_text().splitlines():
            if line.startswith("ONEBOT_ACCESS_TOKEN="):
                mizuki_token = line.split("=", 1)[1].strip().strip('"\'')
                break

    for connection in (
        {"id": "hrkbot", "name": "hrkbot", "url": "ws://host.docker.internal:8000/ws"},
        {
            "id": "mzkbot",
            "name": "mzkbot",
            "url": "ws://host.docker.internal:8088/onebot/v11/",
            "token": mizuki_token,
        },
        {"id": "arkbot", "name": "arkbot", "url": "ws://host.docker.internal:8788/onebot/v11/ws"},
    ):
        upsert_connection(
            config,
            {
                **connection,
                "token": connection.get("token", ""),
                "self_id": args.self_id,
                "enabled": True,
                "auto_reconnect": True,
                "reconnect_interval": 5,
                "allow_forward": True,
            },
        )

    gallery_exclusion = (
        r"^/(?:gall(?:[ _]|$)|看(?:所有|全部)?(?:\s|$)|上传(?:\s|$)|添加(?:\s|$)|"
        r"待审核画廊(?:\s|$)|画廊(?:待审核|审核通过|审核拒绝|群名单)(?:\s|$)|"
        r"下载(?:图包|看|画廊)(?:\s|$)|同步(?:图床|画廊图床)(?:\s|$))"
    )
    mizuki_collision_exclusions = prefix_collision_exclusion_patterns(mizuki, haruki)
    upsert_command_set(
        config,
        {
            "id": "hrkbot",
            "name": "hrkbot",
            "prefix": "hrk",
            "category": "pjsk",
            "description": "Haruki Client 本地完整指令清单",
            "is_public": True,
            "target_ws": "hrkbot",
            "priority": 100,
            # Postman 的 hrk 路由前缀由路由器消费；Haruki 原生 / 指令必须原样保留。
            "strip_prefix": False,
            "enabled": True,
            "is_default": True,
            "exclude_patterns": [gallery_exclusion],
            "commands": command_records(haruki),
        },
    )
    upsert_command_set(
        config,
        {
            "id": "mzkbot",
            "name": "mzkbot",
            "prefix": "mzk",
            "description": "Mizuki 画廊及本地零散指令",
            "is_public": True,
            "target_ws": "mzkbot",
            "priority": 200,
            "strip_prefix": False,
            "enabled": True,
            "exclude_patterns": mizuki_collision_exclusions,
            "commands": command_records(mizuki),
        },
    )
    upsert_command_set(
        config,
        {
            "id": "arkbot",
            "name": "arkbot",
            "prefix": "ark",
            "description": "ArkBot；所有群聊必须使用 ark 前缀",
            "is_public": True,
            "target_ws": "arkbot",
            "priority": 150,
            "strip_prefix": False,
            "enabled": True,
            "require_prefix_in_groups": ["@any"],
            "commands": command_records(
                [
                    ["/干员"],
                    ["/查干员", "/查"],
                    ["/技能"],
                    ["/模组"],
                    ["/敌人", "/敌对"],
                    ["/公招", "/公开招募"],
                    ["/皮肤", "/查皮肤"],
                ]
            ),
        },
    )

    args.config.write_text(
        yaml.safe_dump(config, allow_unicode=True, sort_keys=False), encoding="utf-8"
    )
    print(
        f"synced haruki={len(haruki)} definitions, "
        f"haruki_aliases={sum(len(group) for group in haruki)}, "
        f"mizuki={len(mizuki)} definitions, "
        f"mizuki_aliases={sum(len(group) for group in mizuki)}"
    )


if __name__ == "__main__":
    main()
