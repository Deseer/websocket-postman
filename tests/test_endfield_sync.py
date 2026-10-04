from pathlib import Path

import pytest

from scripts.sync_endfield_bot import command_records, command_set
from src.core.parser import CommandParser
from src.core.router import CommandRouter
from src.models.command_set import Command, CommandSet
from src.models.user import User


@pytest.fixture
def source():
    return Path(__file__).parent / "fixtures/endfieldbot"


@pytest.mark.parametrize("short,args,canonical", [
    ("/干员", "莱万汀 9", "/终末地 干员"),
    ("/角色", "女管理员", "/终末地 角色"),
    ("/武器", "黯色火炬", "/终末地 武器"),
    ("/敌人列表", "虬兽", "/终末地 敌人列表"),
    ("/基质规划", "智识提升+灼热伤害提升+附术 世界等级6", "/终末地 基质规划"),
    ("/地图", "枢纽区 宝箱", "/终末地 地图"),
    ("/插图", "莱万汀 3", "/终末地 插图"),
    ("/help", "", "/终末地 帮助"),
    ("/ef", "武器 黯色火炬", "/终末地"),
])
def test_endfield_normalizes_short_commands_without_losing_arguments(source, short, args, canonical):
    cs = CommandSet.from_config(command_set(source))
    matched, actual_args, _ = cs.find_match(f"{short} {args}".strip())
    # Explicit /ef 武器 can match a longer native alias too; both preserve upstream intent.
    forwarded = f"{matched.name} {actual_args}".strip()
    assert forwarded == f"{canonical} {args}".strip()


@pytest.mark.asyncio
async def test_ef_prefix_isolated_from_ark_and_bare_group_commands(source, monkeypatch):
    ef = CommandSet.from_config(command_set(source))
    ark = CommandSet(id="arkbot", name="arkbot", prefix="ark", target_ws="arkbot",
                     require_prefix_in_groups=["@any"], commands=[Command(name="/地图")])
    router = CommandRouter()
    monkeypatch.setattr(router, "_command_sets", [ef, ark])
    monkeypatch.setattr(router, "_categories", [])
    monkeypatch.setattr(router, "_prefix_map", {"ef": ef, "ark": ark})
    parser = CommandParser(["ef", "ark"])
    user = User(qq_id=1, selected_styles={})
    for text, expected in [("ef/地图 枢纽区", "endfieldbot"),
                           ("ark/地图 JT8-3", "arkbot"),
                           ("/地图 枢纽区", None), ("/help", None)]:
        cs, *_ = await router._find_command(parser.parse(text), user, group_id=1)
        assert (cs.id if cs else None) == expected


def test_every_upstream_alias_is_included(source):
    records = command_records(source)
    assert len(records) == 15
    assert command_set(source)["require_prefix_in_groups"] == ["@any"]
    assert any("/武器基质" in record["aliases"] for record in records)
