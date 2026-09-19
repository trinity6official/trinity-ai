from __future__ import annotations

import sys
import textwrap
import time
from pathlib import Path

import pytest

from core.events import EventBus
from core.mcp import (
    MCPError,
    MCPProtocolError,
    MCPRemoteError,
    MCPServerConfig,
    MCPServerManager,
    MCPTimeoutError,
)


def _fake_server(tmp_path: Path) -> Path:
    script = tmp_path / "fake_mcp.py"
    script.write_text(textwrap.dedent(r'''
        import json, os, sys, time
        def send(value):
            sys.stdout.write(json.dumps(value, separators=(",", ":")) + "\n"); sys.stdout.flush()
        for raw in sys.stdin:
            if not raw.strip(): continue
            msg=json.loads(raw); method=msg.get("method"); rid=msg.get("id"); params=msg.get("params") or {}
            if rid is None: continue
            if method == "initialize":
                send({"jsonrpc":"2.0","id":rid,"result":{"protocolVersion":params.get("protocolVersion"),"capabilities":{"tools":{}},"serverInfo":{"name":"fake","version":"1"}}})
            elif method == "tools/list":
                if os.environ.get("MCP_CRASH_ON_LIST") == "1": os._exit(7)
                delay=float(os.environ.get("MCP_LIST_DELAY","0"));
                if delay: time.sleep(delay)
                if os.environ.get("MCP_LIST_ERROR") == "1":
                    send({"jsonrpc":"2.0","id":rid,"error":{"code":-32000,"message":"discovery failed"}}); continue
                if not params.get("cursor"):
                    send({"jsonrpc":"2.0","id":rid,"result":{"tools":[{"name":"echo","description":"Echo arguments","inputSchema":{"type":"object"}}],"nextCursor":"2"}})
                else:
                    allowed=os.environ.get("MCP_ALLOWED_SECRET"); hidden=os.environ.get("MCP_HIDDEN_SECRET")
                    send({"jsonrpc":"2.0","id":rid,"result":{"tools":[{"name":"environment","description":f"allowed={allowed};hidden={hidden}","inputSchema":{"type":"object"}}]}})
            else:
                send({"jsonrpc":"2.0","id":rid,"error":{"code":-32601,"message":"unknown method"}})
    ''').strip()+"\n", encoding="utf-8")
    return script


def _config(tmp_path: Path, **overrides) -> MCPServerConfig:
    values={"name":"fake","command":sys.executable,"args":(str(_fake_server(tmp_path)),),"request_timeout_seconds":1.0}
    values.update(overrides)
    return MCPServerConfig(**values)


def test_stdio_server_initializes_and_reports_health(tmp_path):
    bus=EventBus(); events=[]; bus.subscribe("*", events.append)
    manager=MCPServerManager([_config(tmp_path)], event_bus=bus)
    try:
        health=manager.start("fake")
        assert health.healthy and health.pid and health.protocol_version == "2025-06-18"
        assert any(e.type == "mcp.server_started" for e in events)
    finally: manager.stop_all()


def test_tools_list_is_paginated_and_cached(tmp_path):
    manager=MCPServerManager([_config(tmp_path)])
    try:
        manager.start("fake"); tools=manager.list_tools("fake")
        assert [(t.server,t.name) for t in tools] == [("fake","echo"),("fake","environment")]
        assert manager.list_tools("fake",refresh=False) is tools
    finally: manager.stop_all()


def test_child_environment_is_allowlisted(tmp_path, monkeypatch):
    monkeypatch.setenv("MCP_ALLOWED_SECRET","allowed-value"); monkeypatch.setenv("MCP_HIDDEN_SECRET","must-not-leak")
    manager=MCPServerManager([_config(tmp_path, env_passthrough=("MCP_ALLOWED_SECRET",))])
    try:
        manager.start("fake"); tools=manager.list_tools("fake")
        description=next(t.description for t in tools if t.name == "environment")
        assert description == "allowed=allowed-value;hidden=None"
    finally: manager.stop_all()


def test_discovery_timeout_is_bounded(tmp_path, monkeypatch):
    monkeypatch.setenv("MCP_LIST_DELAY","0.2")
    manager=MCPServerManager([_config(tmp_path, env_passthrough=("MCP_LIST_DELAY",))])
    try:
        manager.start("fake")
        with pytest.raises(MCPTimeoutError): manager.list_tools("fake", timeout_seconds=0.03)
    finally: manager.stop_all()


def test_discovery_json_rpc_errors_are_typed(tmp_path, monkeypatch):
    monkeypatch.setenv("MCP_LIST_ERROR","1")
    manager=MCPServerManager([_config(tmp_path, env_passthrough=("MCP_LIST_ERROR",))])
    try:
        manager.start("fake")
        with pytest.raises(MCPRemoteError) as exc: manager.list_tools("fake")
        assert exc.value.code == -32000
    finally: manager.stop_all()


def test_crashed_server_becomes_unhealthy_and_can_restart(tmp_path, monkeypatch):
    monkeypatch.setenv("MCP_CRASH_ON_LIST","1")
    manager=MCPServerManager([_config(tmp_path, env_passthrough=("MCP_CRASH_ON_LIST",))])
    try:
        manager.start("fake")
        with pytest.raises((MCPProtocolError,MCPError)): manager.list_tools("fake")
        deadline=time.monotonic()+1
        while manager.health("fake").running and time.monotonic() < deadline: time.sleep(0.01)
        assert not manager.health("fake").running
        assert manager.restart("fake").initialized
    finally: manager.stop_all()


def test_config_loader_keeps_disabled_servers_stopped(tmp_path):
    script=_fake_server(tmp_path); cfg=tmp_path/"mcp.yaml"
    cfg.write_text(f'protocol_version: "2025-06-18"\nservers:\n  active:\n    enabled: true\n    command: "{sys.executable}"\n    args: ["{script}"]\n  disabled:\n    enabled: false\n    command: "{sys.executable}"\n    args: ["{script}"]\n')
    manager=MCPServerManager.from_config(cfg)
    try:
        result=manager.start_enabled(); assert set(result) == {"active"}; assert not manager.health("disabled").running
    finally: manager.stop_all()


def test_discover_tools_starts_only_enabled_servers(tmp_path):
    manager=MCPServerManager([_config(tmp_path,name="active"),_config(tmp_path,name="disabled",enabled=False)])
    try:
        assert {t.server for t in manager.discover_tools()} == {"active"}; assert not manager.health("disabled").running
    finally: manager.stop_all()


def test_missing_config_is_valid_empty_manager(tmp_path):
    manager=MCPServerManager.from_config(tmp_path/"missing.yaml"); assert manager.names() == (); assert manager.health() == {}


def test_invalid_config_is_rejected(tmp_path):
    cfg=tmp_path/"bad.yaml"; cfg.write_text("servers:\n  broken:\n    enabled: true\n")
    with pytest.raises(ValueError, match="requires a command"): MCPServerManager.from_config(cfg)


def test_manager_cached_tools_is_side_effect_free_before_start(tmp_path):
    manager = MCPServerManager(
        [MCPServerConfig(name="demo", command="missing-command", enabled=True)]
    )
    assert manager.cached_tools() == ()
    assert manager.cached_tools("demo") == ()
    assert manager.health("demo").running is False
