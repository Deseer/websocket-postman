"""指令集匹配行为测试。"""

import pytest
import asyncio
from pydantic import ValidationError
from types import SimpleNamespace
from unittest.mock import AsyncMock

from src.api.routes.command_sets import get_command_sets
from src.config import AppConfig, CommandConfig, CommandSetConfig, TimeRestriction
from src.core.permission import PermissionChecker
from src.core.parser import ParsedCommand
from src.core.router import CommandRouter
from src.core.ws_client import WebSocketConnection
from src.models.command_set import Command, CommandSet
from src.models.command_set import Category
from src.models.user import User
from scripts.migrate_stable_ids import migrate_selected_styles
from scripts.sync_local_bot_config import (
    haruki_command_pattern,
    haruki_command_records,
    migrate_stable_ids,
    prefix_collision_exclusion_patterns,
)


def test_forward_mode_keeps_literal_longest_prefix_matching():
    command_set = CommandSet(
        id="normal",
        name="Normal",
        commands=[Command(name="/a"), Command(name="/about")],
    )

    command, args, matched = command_set.find_match("/about me")

    assert command.name == "/about"
    assert args == "me"
    assert matched == "/about"


def test_forward_mode_supports_regex_and_preserves_matched_text():
    command_set = CommandSet(
        id="regex",
        name="Regex",
        commands=[Command(name=r"^/(?:ping|pong)(?:\s+\d+)?", is_regex=True)],
    )

    command, args, matched = command_set.find_match("/ping 42 extra")

    assert command.is_regex is True
    assert matched == "/ping 42"
    assert args == "extra"


def test_forward_mode_chooses_longest_actual_regex_match():
    command_set = CommandSet(
        id="regex",
        name="Regex",
        commands=[
            Command(name=r"^/添", aliases=[r"^/添加"], is_regex=True),
            Command(name=r"^/添加歌曲别名", is_regex=True),
        ],
    )

    command, args, matched = command_set.find_match("/添加歌曲别名 花里=花里实乃理")

    assert command.name == r"^/添加歌曲别名"
    assert matched == "/添加歌曲别名"
    assert args == "花里=花里实乃理"


@pytest.mark.parametrize(
    ("text", "matched", "args"),
    [
        ("/个人信息", "/个人信息", ""),
        ("/jp个人信息", "/jp个人信息", ""),
        ("/jp/个人信息", "/jp/个人信息", ""),
        ("/jp 个人信息", "/jp 个人信息", ""),
        ("jp/个人信息", "jp/个人信息", ""),
        ("jp /个人信息", "jp /个人信息", ""),
        ("/cn个人信息 参数", "/cn个人信息", "参数"),
        ("/PJSk-score 100", "/PJSk-score", "100"),
    ],
)
def test_haruki_regex_supports_server_prefix_and_preserves_arguments(
    text, matched, args
):
    record = haruki_command_records([["/个人信息", "/pjsk score"]])[0]
    command_set = CommandSet(
        id="hrkbot",
        name="HrKBot",
        commands=[Command.from_config(record)],
    )

    command, actual_args, actual_matched = command_set.find_match(text)

    assert command.is_regex is True
    assert actual_matched == matched
    assert actual_args == args


@pytest.mark.parametrize("text", ["/JP个人信息", "jp个人信息", "cn 个人信息"])
def test_haruki_regex_rejects_forms_client_cannot_strip(text):
    pattern = haruki_command_pattern(["/个人信息"])
    command_set = CommandSet(
        id="hrkbot",
        name="HrKBot",
        commands=[Command(name=pattern, is_regex=True)],
    )

    assert command_set.find_match(text) is None


def test_positive_commands_and_negative_exclusions_apply_together():
    command_set = CommandSet(
        id="mizuki",
        name="Mizuki",
        commands=[Command(name="/添加"), Command(name="/上传")],
        exclude_patterns=[r"^/(?:添加歌曲别名|上传个人信息)"],
    )

    assert command_set.find_match("/添加 大肥鱼")[0].name == "/添加"
    assert command_set.find_match("/上传 大肥鱼")[0].name == "/上传"
    assert command_set.find_match("/添加歌曲别名 花里=花里实乃理") is None
    assert command_set.find_match("/上传个人信息图片") is None


def test_cross_set_prefix_collisions_generate_exact_negative_rules():
    patterns = prefix_collision_exclusion_patterns(
        [["/添加"], ["/上传"]],
        [["/添加歌曲别名"], ["/添加角色别名"], ["/查询"]],
    )
    command_set = CommandSet(
        id="mizuki",
        name="Mizuki",
        commands=[Command(name="/添加"), Command(name="/上传")],
        exclude_patterns=patterns,
    )

    assert command_set.find_match("/添加 gallery") is not None
    assert command_set.find_match("/添加歌曲别名foo") is None
    assert command_set.find_match("/添加角色别名 foo") is None


def test_stable_id_migration_updates_config_references():
    config = {
        "connections": [{"id": "hrkbot-8kmo"}],
        "categories": [
            {
                "id": "pjsk-2vd6",
                "name": "pjsk-2vd6",
                "default_command_set": "hrkbot-339v",
            }
        ],
        "command_sets": [
            {
                "id": "hrkbot-339v",
                "category": "pjsk-2vd6",
                "target_ws": "hrkbot-8kmo",
            }
        ],
    }

    migrate_stable_ids(config)

    assert config["connections"][0]["id"] == "hrkbot"
    assert config["categories"][0] == {
        "id": "pjsk",
        "name": "pjsk",
        "default_command_set": "hrkbot",
    }
    assert config["command_sets"][0] == {
        "id": "hrkbot",
        "category": "pjsk",
        "target_ws": "hrkbot",
    }


def test_local_user_style_migration_replaces_removed_lunabot():
    assert migrate_selected_styles({"pjsk-2vd6": "lunabot-3mgm"}) == {
        "pjsk": "hrkbot"
    }


def test_inverse_mode_passes_unmatched_message_through_unchanged():
    command_set = CommandSet(
        id="inverse",
        name="Inverse",
        inverse_mode=True,
        commands=[Command(name="/blocked")],
    )

    command, args, matched = command_set.find_match("ordinary message")

    assert command.is_passthrough is True
    assert command.name == "ordinary message"
    assert args == ""
    assert matched == "ordinary message"


@pytest.mark.parametrize("text", ["/blocked", "/blocked now", "/ban 123"])
def test_inverse_mode_excludes_literal_and_regex_rules(text):
    command_set = CommandSet(
        id="inverse",
        name="Inverse",
        inverse_mode=True,
        commands=[
            Command(name="/blocked"),
            Command(name=r"^/ban(?:\s|$)", is_regex=True),
        ],
    )

    assert command_set.find_match(text) is None


def test_regex_config_rejects_invalid_or_empty_matching_patterns():
    with pytest.raises(ValidationError, match="无效的指令正则"):
        CommandConfig(name="[", is_regex=True)

    with pytest.raises(ValidationError, match="不能匹配空字符串"):
        CommandConfig(name=".*", is_regex=True)


def test_runtime_model_loads_operational_command_set_flags():
    command_set = CommandSet.from_config(
        {
            "id": "flags",
            "name": "Flags",
            "target_ws": "bot",
            "enabled": False,
            "inverse_mode": True,
            "user_access_list": "users",
            "group_access_list": "groups",
            "require_prefix_in_groups": ["@any"],
            "exclude_patterns": [r"^/gall(?:\s|$)"],
        }
    )

    assert command_set.enabled is False
    assert command_set.inverse_mode is True
    assert command_set.user_access_list == "users"
    assert command_set.group_access_list == "groups"
    assert command_set.require_prefix_in_groups == ["@any"]
    assert command_set.find_match("/gall pick") is None


def test_command_set_prefix_requirement_only_applies_to_configured_groups():
    command_set = CommandSet(
        id="ark",
        name="ArkBot",
        prefix="ark",
        require_prefix_in_groups=[10001],
    )

    assert command_set.requires_prefix(10001) is True
    assert command_set.requires_prefix(10002) is False
    assert command_set.requires_prefix(None) is False


@pytest.mark.asyncio
async def test_router_skips_unprefixed_group_command_when_prefix_is_required():
    router = CommandRouter()
    ark = CommandSet(
        id="ark",
        name="ArkBot",
        prefix="ark",
        target_ws="arkbot",
        require_prefix_in_groups=["@any"],
        commands=[Command(name="/干员")],
    )
    router._command_sets = [ark]
    router._categories = []
    router._prefix_map = {"ark": ark}
    user = User(qq_id=10001, selected_styles={})

    unprefixed = ParsedCommand(
        raw="/干员 能天使", prefix=None, command="/干员", args="能天使", is_command=True
    )
    assert await router._find_command(unprefixed, user, group_id=20001) == (
        None,
        None,
        None,
        None,
    )

    prefixed = ParsedCommand(
        raw="ark/干员 能天使", prefix="ark", command="/干员", args="能天使", is_command=True
    )
    command_set, command, args, matched = await router._find_command(
        prefixed, user, group_id=20001
    )
    assert command_set is ark
    assert command.name == "/干员"
    assert args == "能天使"
    assert matched == "/干员"


@pytest.mark.asyncio
async def test_router_falls_back_to_default_when_selected_style_is_stale():
    router = CommandRouter()
    hrk = CommandSet(
        id="hrkbot",
        name="HrKBot",
        category="pjsk",
        target_ws="hrkbot",
        is_default=True,
        commands=[Command(name="/个人信息")],
    )
    router._command_sets = [hrk]
    router._categories = [
        Category(
            id="pjsk",
            name="pjsk",
            display_name="PJSK",
            default_command_set="hrkbot",
            is_mutex=True,
        )
    ]
    router._group_sets = {"pjsk": [hrk]}
    user = User(qq_id=10001, selected_styles={"pjsk": "removed-bot"})
    parsed = ParsedCommand(
        raw="/个人信息",
        prefix=None,
        command="/个人信息",
        args="",
        is_command=True,
    )

    command_set, command, _, _ = await router._find_command(
        parsed, user, group_id=20001
    )

    assert command_set is hrk
    assert command.name == "/个人信息"


@pytest.mark.asyncio
async def test_plain_internal_commands_are_not_postman_commands_without_pm_prefix():
    router = CommandRouter()
    user = User(qq_id=10001, selected_styles={})

    for command in ("/help", "/status", "/list", "/style", "/admin"):
        plain = ParsedCommand(
            raw=command, prefix=None, command=command, args="", is_command=True
        )
        assert await router._handle_system_command(plain, user, None) is None

    prefixed = ParsedCommand(
        raw="pm/help", prefix="pm", command="/help", args="", is_command=True
    )
    result = await router._handle_system_command(prefixed, user, None)
    assert result.is_system_command is True
    assert "pm/help" in result.response


def test_command_set_config_rejects_invalid_exclusion_pattern_and_group_marker():
    with pytest.raises(ValidationError, match="无效的排除正则"):
        CommandSetConfig(
            id="bad", name="Bad", target_ws="bot", exclude_patterns=["["]
        )

    with pytest.raises(ValidationError, match="群号或 @any"):
        CommandSetConfig(
            id="bad", name="Bad", target_ws="bot", require_prefix_in_groups=["all"]
        )


@pytest.mark.asyncio
async def test_manual_disconnect_cancels_pending_reconnect():
    connection = WebSocketConnection(
        id="bot",
        name="Bot",
        url="ws://127.0.0.1:1/ws",
        reconnect_interval=0.01,
    )
    connect_spy = AsyncMock(return_value=True)
    connection.connect = connect_spy

    connection._schedule_reconnect()
    await asyncio.sleep(0)
    await connection.disconnect()
    await asyncio.sleep(0.02)

    assert connection.enabled is False
    assert connection._stopped is True
    assert connection._reconnect_task is None
    connect_spy.assert_not_awaited()


def test_command_set_access_lists_are_enforced(monkeypatch):
    config = SimpleNamespace(
        admins=[],
        access_lists=[
            SimpleNamespace(
                id="allowed-users", type="user", mode="whitelist", items=[10001]
            ),
            SimpleNamespace(
                id="blocked-groups", type="group", mode="blacklist", items=[20002]
            ),
        ],
    )
    monkeypatch.setattr("src.core.permission.get_config", lambda: config)
    checker = PermissionChecker()
    command_set = CommandSet(
        id="restricted",
        name="Restricted",
        user_access_list="allowed-users",
        group_access_list="blocked-groups",
    )

    assert checker.check_command_set_permission(User(qq_id=10001), command_set, 20001).allowed
    assert not checker.check_command_set_permission(User(qq_id=10002), command_set, 20001).allowed
    assert not checker.check_command_set_permission(User(qq_id=10001), command_set, 20002).allowed


@pytest.mark.asyncio
async def test_command_set_api_serializes_time_restriction(monkeypatch):
    config = AppConfig(
        command_sets=[
            CommandSetConfig(
                id="timed",
                name="Timed",
                target_ws="bot",
                commands=[
                    CommandConfig(
                        name="/night",
                        time_restriction=TimeRestriction(start="22:00", end="06:00"),
                    )
                ],
            )
        ]
    )
    monkeypatch.setattr("src.api.routes.command_sets.get_config", lambda: config)

    result = await get_command_sets()

    assert result[0]["commands"][0]["time_restriction"] == {
        "start": "22:00",
        "end": "06:00",
    }
