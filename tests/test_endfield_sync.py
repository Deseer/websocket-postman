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


@pytest.mark.parametrize("short,args,expected", [
    ("/干员", "莱万汀 9", "/干员 莱万汀 9"),
    ("/角色", "女管理员", "/角色 女管理员"),
    ("/武器", "黯色火炬", "/武器 黯色火炬"),
    ("/敌人列表", "虬兽", "/敌人列表 虬兽"),
    ("/基质规划", "智识提升+灼热伤害提升+附术 世界等级6", "/基质规划 智识提升+灼热伤害提升+附术 世界等级6"),
    ("/地图", "枢纽区 宝箱", "/地图 枢纽区 宝箱"),
    ("/插图", "莱万汀 3", "/插图 莱万汀 3"),
    ("/终末地 状态", "导电 4", "/状态 导电 4"),
    ("/help", "", "/帮助"),
    ("/ef", "武器 黯色火炬", "/武器 黯色火炬"),
])
def test_endfield_normalizes_short_commands_without_losing_arguments(source, short, args, expected):
    cs = CommandSet.from_config(command_set(source))
    matched, actual_args, _ = cs.find_match(f"{short} {args}".strip())
    # Every routing alias is normalized to syntax understood by EndfieldBot.
    forwarded = f"{matched.name} {actual_args}".strip()
    assert forwarded == expected


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
    assert len(records) == 16
    assert command_set(source)["require_prefix_in_groups"] == ["@any"]
    assert any(record["name"] == "/武器基质" for record in records)
