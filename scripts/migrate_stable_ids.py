#!/usr/bin/env python3
"""迁移本地 SQLite 中引用的旧随机后缀配置 ID。"""

from __future__ import annotations

import argparse
import json
import sqlite3
from datetime import datetime
from pathlib import Path

from scripts.sync_local_bot_config import (
    CATEGORY_ID_MIGRATIONS,
    COMMAND_SET_ID_MIGRATIONS,
    CONNECTION_ID_MIGRATIONS,
)


STYLE_ID_MIGRATIONS = {
    **COMMAND_SET_ID_MIGRATIONS,
    "lunabot-3mgm": "hrkbot",
}


def migrate_selected_styles(styles: dict[str, str] | None) -> dict[str, str]:
    migrated: dict[str, str] = {}
    for category_id, style_id in (styles or {}).items():
        migrated[CATEGORY_ID_MIGRATIONS.get(category_id, category_id)] = (
            STYLE_ID_MIGRATIONS.get(style_id, style_id)
        )
    return migrated


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--database", type=Path, default=Path("data/dispatcher.db"))
    args = parser.parse_args()

    backup_dir = args.database.parent / "backups"
    backup_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    backup_path = backup_dir / f"{args.database.name}.{timestamp}.bak"
    # SQLite 在线备份会包含 WAL 中已提交的数据，避免直接复制活动数据库不一致。
    with sqlite3.connect(args.database) as source, sqlite3.connect(
        backup_path
    ) as backup:
        source.backup(backup)

    with sqlite3.connect(args.database) as connection:
        rows = connection.execute(
            "SELECT qq_id, selected_styles, allowed_switch_groups FROM users"
        ).fetchall()
        for qq_id, styles_json, groups_json in rows:
            styles = migrate_selected_styles(json.loads(styles_json or "{}"))
            groups = [
                CATEGORY_ID_MIGRATIONS.get(item, item)
                for item in json.loads(groups_json or "[]")
            ]
            connection.execute(
                "UPDATE users SET selected_styles = ?, allowed_switch_groups = ? "
                "WHERE qq_id = ?",
                (json.dumps(styles, ensure_ascii=False), json.dumps(groups), qq_id),
            )

        for old_id, new_id in COMMAND_SET_ID_MIGRATIONS.items():
            connection.execute(
                "UPDATE message_logs SET command_set_id = ? WHERE command_set_id = ?",
                (new_id, old_id),
            )
        for old_id, new_id in CONNECTION_ID_MIGRATIONS.items():
            connection.execute(
                "UPDATE message_logs SET target_ws = ? WHERE target_ws = ?",
                (new_id, old_id),
            )

    print(f"migrated local database; backup={backup_path}")


if __name__ == "__main__":
    main()
