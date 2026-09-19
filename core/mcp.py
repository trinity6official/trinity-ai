"""Dependency-light Model Context Protocol (MCP) stdio foundation for Trinity.

PR #14 intentionally owns transport, configured local-server lifecycle, health,
and tool discovery only. Discovered tools are metadata at this stage; execution
is added later behind Trinity governance rather than exposed directly here.
"""
from __future__ import annotations

import json
import os
import queue
import subprocess
import threading
import time
from collections import deque
from dataclasses import dataclass, field
from pathlib import Path
from types import MappingProxyType
from typing import Any, Mapping, Sequence

import yaml

from core.events import EventBus


DEFAULT_MCP_PROTOCOL_VERSION = "2025-06-18"
DEFAULT_REQUEST_TIMEOUT_SECONDS = 15.0
_ENV_BASE_KEYS = (
    "PATH", "HOME", "TMPDIR", "TEMP", "TMP", "LANG", "LC_ALL",
    "USER", "LOGNAME", "SHELL", "SYSTEMROOT", "WINDIR", "PATHEXT", "COMSPEC",
)


class MCPError(RuntimeError):
    """Base error for Trinity's MCP transport."""


class MCPTimeoutError(MCPError):
    """Raised when an MCP request exceeds its configured deadline."""


class MCPProtocolError(MCPError):
    """Raised when an MCP peer violates the JSON-RPC/MCP contract."""


class MCPRemoteError(MCPError):
    """Raised for JSON-RPC error responses returned by an MCP server."""

    def __init__(self, code: int | None, message: str, data: Any = None) -> None:
        super().__init__(f"MCP error {code}: {message}")
        self.code = code
        self.message = message
        self.data = data


@dataclass(frozen=True)
class MCPServerConfig:
    name: str
    command: str
    args: tuple[str, ...] = ()
    enabled: bool = True
    cwd: str | None = None
    env_passthrough: tuple[str, ...] = ()
    request_timeout_seconds: float = DEFAULT_REQUEST_TIMEOUT_SECONDS
    protocol_version: str = DEFAULT_MCP_PROTOCOL_VERSION

    def __post_init__(self) -> None:
        name = str(self.name).strip()
        command = str(self.command).strip()
        if not name:
            raise ValueError("MCP server name is required")
        if not command:
            raise ValueError(f"MCP server {name!r} requires a command")
        timeout = float(self.request_timeout_seconds)
        if timeout <= 0:
            raise ValueError(f"MCP server {name!r} timeout must be positive")
        object.__setattr__(self, "name", name)
        object.__setattr__(self, "command", command)
        object.__setattr__(self, "args", tuple(str(v) for v in self.args))
        object.__setattr__(self, "env_passthrough", tuple(str(v) for v in self.env_passthrough))
        object.__setattr__(self, "request_timeout_seconds", timeout)
        object.__setattr__(self, "protocol_version", str(self.protocol_version).strip())

    @classmethod
    def from_mapping(
        cls,
        name: str,
        value: Mapping[str, Any],
        *,
        default_protocol_version: str = DEFAULT_MCP_PROTOCOL_VERSION,
    ) -> "MCPServerConfig":
        args = value.get("args", ()) or ()
        env_passthrough = value.get("env_passthrough", ()) or ()
        if not isinstance(args, Sequence) or isinstance(args, (str, bytes)):
            raise ValueError(f"MCP server {name!r} args must be a list")
        if not isinstance(env_passthrough, Sequence) or isinstance(env_passthrough, (str, bytes)):
            raise ValueError(f"MCP server {name!r} env_passthrough must be a list")
        cwd = value.get("cwd")
        return cls(
            name=str(name),
            command=str(value.get("command", "")),
            args=tuple(str(v) for v in args),
            enabled=bool(value.get("enabled", True)),
            cwd=str(cwd).strip() if cwd else None,
            env_passthrough=tuple(str(v).strip() for v in env_passthrough if str(v).strip()),
            request_timeout_seconds=float(
                value.get("request_timeout_seconds", DEFAULT_REQUEST_TIMEOUT_SECONDS)
            ),
            protocol_version=str(
                value.get("protocol_version", default_protocol_version)
                or default_protocol_version
            ),
        )


@dataclass(frozen=True)
class MCPTool:
    server: str
    name: str
    description: str = ""
    input_schema: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "server", str(self.server).strip())
        object.__setattr__(self, "name", str(self.name).strip())
        object.__setattr__(self, "description", str(self.description or ""))
        object.__setattr__(self, "input_schema", MappingProxyType(dict(self.input_schema or {})))


@dataclass(frozen=True)
class MCPServerHealth:
    name: str
    enabled: bool
    running: bool
    initialized: bool
    pid: int | None
    protocol_version: str | None
    tool_count: int
    last_error: str | None
    stderr_tail: tuple[str, ...]

    @property
    def healthy(self) -> bool:
        return self.enabled and self.running and self.initialized and not self.last_error


class MCPStdioClient:
    """One serialized MCP JSON-RPC client over line-delimited stdio."""

    def __init__(
        self,
        config: MCPServerConfig,
        *,
        event_bus: EventBus | None = None,
        environ: Mapping[str, str] | None = None,
    ) -> None:
        self.config = config
        self.event_bus = event_bus
        self.environ = dict(os.environ if environ is None else environ)
        self.process: subprocess.Popen[str] | None = None
        self.initialized = False
        self.negotiated_protocol_version: str | None = None
        self.server_info: dict[str, Any] = {}
        self.last_error: str | None = None
        self.tools_cache: tuple[MCPTool, ...] = ()
        self._stderr_tail: deque[str] = deque(maxlen=20)
        self._inbox: queue.Queue[tuple[str, Any]] = queue.Queue()
        self._request_lock = threading.Lock()
        self._write_lock = threading.Lock()
        self._next_id = 1
        self._stopping = threading.Event()

    @property
    def running(self) -> bool:
        process = self.process
        return process is not None and process.poll() is None

    def _emit(self, event_type: str, **payload: Any) -> None:
        if self.event_bus is not None:
            self.event_bus.publish(event_type, server=self.config.name, **payload)

    def _child_environment(self) -> dict[str, str]:
        child = {k: self.environ[k] for k in _ENV_BASE_KEYS if k in self.environ}
        for key in self.config.env_passthrough:
            if key in self.environ:
                child[key] = self.environ[key]
        return child

    def start(self) -> MCPServerHealth:
        if self.running and self.initialized:
            return self.health()
        if self.running:
            self.stop()
        self.last_error = None
        self.initialized = False
        self.negotiated_protocol_version = None
        self.server_info = {}
        self.tools_cache = ()
        self._stopping.clear()
        self._drain_inbox()

        command = [self.config.command, *self.config.args]
        cwd = Path(self.config.cwd).expanduser().resolve() if self.config.cwd else None
        try:
            self.process = subprocess.Popen(
                command,
                cwd=str(cwd) if cwd else None,
                env=self._child_environment(),
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                encoding="utf-8",
                errors="replace",
                bufsize=1,
            )
        except Exception as exc:
            self.last_error = f"{type(exc).__name__}: {exc}"
            self._emit("mcp.server_failed", error=self.last_error)
            raise MCPError(f"Unable to start MCP server {self.config.name}: {exc}") from exc

        threading.Thread(
            target=self._reader_loop,
            name=f"mcp-{self.config.name}-stdout",
            daemon=True,
        ).start()
        threading.Thread(
            target=self._stderr_loop,
            name=f"mcp-{self.config.name}-stderr",
            daemon=True,
        ).start()

        try:
            result = self._request(
                "initialize",
                {
                    "protocolVersion": self.config.protocol_version,
                    "capabilities": {},
                    "clientInfo": {"name": "trinity-ai", "version": "1.0"},
                },
            )
            if not isinstance(result, Mapping):
                raise MCPProtocolError("initialize result must be an object")
            protocol = str(result.get("protocolVersion", "")).strip()
            if not protocol:
                raise MCPProtocolError("initialize result omitted protocolVersion")
            info = result.get("serverInfo", {}) or {}
            if not isinstance(info, Mapping):
                raise MCPProtocolError("initialize serverInfo must be an object")
            self.negotiated_protocol_version = protocol
            self.server_info = dict(info)
            self._notify("notifications/initialized", {})
            self.initialized = True
            self._emit(
                "mcp.server_started",
                pid=self.process.pid if self.process else None,
                protocol_version=protocol,
            )
            return self.health()
        except Exception as exc:
            self.last_error = str(exc)
            self._emit("mcp.server_failed", error=self.last_error)
            self.stop()
            raise

    def stop(self, *, grace_seconds: float = 2.0) -> None:
        process = self.process
        if process is None:
            return
        self._stopping.set()
        try:
            if process.stdin is not None:
                process.stdin.close()
        except Exception:
            pass
        if process.poll() is None:
            process.terminate()
            try:
                process.wait(timeout=max(0.1, grace_seconds))
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=max(0.1, grace_seconds))
        self.process = None
        self.initialized = False
        self._emit("mcp.server_stopped")

    def restart(self) -> MCPServerHealth:
        self.stop()
        return self.start()

    def list_tools(
        self,
        *,
        refresh: bool = True,
        timeout_seconds: float | None = None,
    ) -> tuple[MCPTool, ...]:
        if not self.initialized:
            raise MCPError(f"MCP server {self.config.name} is not initialized")
        if self.tools_cache and not refresh:
            return self.tools_cache

        tools: list[MCPTool] = []
        cursor: str | None = None
        for _page in range(100):
            params = {"cursor": cursor} if cursor else {}
            result = self._request("tools/list", params, timeout_seconds=timeout_seconds)
            if not isinstance(result, Mapping):
                raise MCPProtocolError("tools/list result must be an object")
            raw_tools = result.get("tools", [])
            if not isinstance(raw_tools, list):
                raise MCPProtocolError("tools/list tools must be a list")
            for raw in raw_tools:
                if not isinstance(raw, Mapping):
                    raise MCPProtocolError("tool descriptor must be an object")
                name = str(raw.get("name", "")).strip()
                if not name:
                    raise MCPProtocolError("tool descriptor omitted name")
                schema = raw.get("inputSchema", {}) or {}
                if not isinstance(schema, Mapping):
                    raise MCPProtocolError(f"tool {name} inputSchema must be an object")
                tools.append(
                    MCPTool(
                        server=self.config.name,
                        name=name,
                        description=str(raw.get("description", "") or ""),
                        input_schema=dict(schema),
                    )
                )
            cursor_value = result.get("nextCursor")
            cursor = str(cursor_value) if cursor_value else None
            if not cursor:
                self.tools_cache = tuple(tools)
                self._emit("mcp.tools_discovered", tool_count=len(tools))
                return self.tools_cache
        raise MCPProtocolError("tools/list exceeded 100 pages")

    def health(self) -> MCPServerHealth:
        process = self.process
        running = self.running
        if process is not None and not running and self.last_error is None and not self._stopping.is_set():
            self.last_error = f"MCP server exited with code {process.returncode}"
        return MCPServerHealth(
            name=self.config.name,
            enabled=self.config.enabled,
            running=running,
            initialized=bool(running and self.initialized),
            pid=process.pid if running and process is not None else None,
            protocol_version=self.negotiated_protocol_version,
            tool_count=len(self.tools_cache),
            last_error=self.last_error,
            stderr_tail=tuple(self._stderr_tail),
        )

    def _notify(self, method: str, params: Mapping[str, Any] | None = None) -> None:
        message: dict[str, Any] = {"jsonrpc": "2.0", "method": method}
        if params is not None:
            message["params"] = dict(params)
        self._write_message(message)

    def _request(
        self,
        method: str,
        params: Mapping[str, Any] | None = None,
        *,
        timeout_seconds: float | None = None,
    ) -> Any:
        timeout = float(
            self.config.request_timeout_seconds
            if timeout_seconds is None
            else timeout_seconds
        )
        if timeout <= 0:
            raise ValueError("timeout_seconds must be positive")
        if not self.running:
            raise MCPError(f"MCP server {self.config.name} is not running")

        with self._request_lock:
            request_id = self._next_id
            self._next_id += 1
            message: dict[str, Any] = {
                "jsonrpc": "2.0",
                "id": request_id,
                "method": method,
            }
            if params is not None:
                message["params"] = dict(params)
            self._write_message(message)

            deadline = time.monotonic() + timeout
            while True:
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    error = f"MCP request timed out: {self.config.name}.{method}"
                    self.last_error = error
                    self._emit("mcp.request_timeout", method=method)
                    raise MCPTimeoutError(error)
                try:
                    kind, payload = self._inbox.get(timeout=remaining)
                except queue.Empty as exc:
                    error = f"MCP request timed out: {self.config.name}.{method}"
                    self.last_error = error
                    self._emit("mcp.request_timeout", method=method)
                    raise MCPTimeoutError(error) from exc
                if kind == "transport_error":
                    self.last_error = str(payload)
                    raise MCPProtocolError(str(payload))
                response = payload
                if not isinstance(response, Mapping):
                    raise MCPProtocolError("MCP response must be an object")
                if response.get("id") != request_id:
                    continue
                if "error" in response:
                    error = response.get("error") or {}
                    if not isinstance(error, Mapping):
                        raise MCPProtocolError("JSON-RPC error must be an object")
                    raise MCPRemoteError(
                        error.get("code"),
                        str(error.get("message", "unknown error")),
                        error.get("data"),
                    )
                if "result" not in response:
                    raise MCPProtocolError("JSON-RPC response omitted result/error")
                return response.get("result")

    def _write_message(self, message: Mapping[str, Any]) -> None:
        process = self.process
        if process is None or process.poll() is not None or process.stdin is None:
            raise MCPError(f"MCP server {self.config.name} is not writable")
        line = json.dumps(dict(message), separators=(",", ":"), ensure_ascii=False)
        with self._write_lock:
            try:
                process.stdin.write(line + "\n")
                process.stdin.flush()
            except (BrokenPipeError, OSError) as exc:
                self.last_error = f"MCP stdin failed: {exc}"
                raise MCPError(self.last_error) from exc

    def _reader_loop(self) -> None:
        process = self.process
        stdout = process.stdout if process is not None else None
        if stdout is None:
            self._inbox.put(("transport_error", "MCP stdout is unavailable"))
            return
        try:
            for raw_line in stdout:
                line = raw_line.strip()
                if not line:
                    continue
                try:
                    message = json.loads(line)
                except json.JSONDecodeError as exc:
                    self._inbox.put((
                        "transport_error",
                        f"Invalid MCP JSON from {self.config.name}: {exc}",
                    ))
                    continue
                if not isinstance(message, dict):
                    self._inbox.put(("transport_error", "MCP message must be a JSON object"))
                    continue
                if "method" in message:
                    if "id" in message:
                        self._reject_server_request(message)
                    else:
                        self._emit(
                            "mcp.notification",
                            method=str(message.get("method", "")),
                            params=message.get("params"),
                        )
                    continue
                self._inbox.put(("response", message))
        finally:
            if not self._stopping.is_set():
                code = process.poll() if process is not None else None
                self._inbox.put((
                    "transport_error",
                    f"MCP server {self.config.name} stdout closed (exit={code})",
                ))

    def _reject_server_request(self, message: Mapping[str, Any]) -> None:
        try:
            self._write_message({
                "jsonrpc": "2.0",
                "id": message.get("id"),
                "error": {
                    "code": -32601,
                    "message": "Trinity MCP client does not advertise server-request capabilities",
                },
            })
        except MCPError:
            pass

    def _stderr_loop(self) -> None:
        process = self.process
        stderr = process.stderr if process is not None else None
        if stderr is None:
            return
        for raw_line in stderr:
            line = raw_line.rstrip("\r\n")
            if line:
                self._stderr_tail.append(line[:1000])

    def _drain_inbox(self) -> None:
        while True:
            try:
                self._inbox.get_nowait()
            except queue.Empty:
                return


class MCPServerManager:
    """Own configured MCP server lifecycle and discovery only."""

    def __init__(
        self,
        configs: Sequence[MCPServerConfig] = (),
        *,
        event_bus: EventBus | None = None,
        environ: Mapping[str, str] | None = None,
    ) -> None:
        configs = tuple(configs)
        self.event_bus = event_bus
        self.environ = dict(os.environ if environ is None else environ)
        self._configs = {config.name: config for config in configs}
        if len(self._configs) != len(configs):
            raise ValueError("Duplicate MCP server names are not allowed")
        self._clients: dict[str, MCPStdioClient] = {}

    @classmethod
    def from_environment(
        cls,
        *,
        event_bus: EventBus | None = None,
        environ: Mapping[str, str] | None = None,
    ) -> "MCPServerManager":
        env = dict(os.environ if environ is None else environ)
        default = Path(__file__).resolve().parent.parent / "config" / "mcp_servers.yaml"
        path = Path(env.get("TRINITY_MCP_CONFIG", str(default))).expanduser()
        return cls.from_config(path, event_bus=event_bus, environ=env)

    @classmethod
    def from_config(
        cls,
        path: str | Path,
        *,
        event_bus: EventBus | None = None,
        environ: Mapping[str, str] | None = None,
    ) -> "MCPServerManager":
        path = Path(path).expanduser()
        if not path.exists():
            return cls((), event_bus=event_bus, environ=environ)
        raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        if not isinstance(raw, Mapping):
            raise ValueError("MCP configuration root must be a mapping")
        protocol = str(raw.get("protocol_version", DEFAULT_MCP_PROTOCOL_VERSION))
        servers = raw.get("servers", {}) or {}
        if not isinstance(servers, Mapping):
            raise ValueError("MCP servers must be a mapping keyed by server name")
        configs = [
            MCPServerConfig.from_mapping(
                str(name),
                value if isinstance(value, Mapping) else {},
                default_protocol_version=protocol,
            )
            for name, value in servers.items()
        ]
        return cls(configs, event_bus=event_bus, environ=environ)

    def names(self) -> tuple[str, ...]:
        return tuple(sorted(self._configs))

    def config(self, name: str) -> MCPServerConfig:
        try:
            return self._configs[name]
        except KeyError as exc:
            raise KeyError(f"Unknown MCP server: {name}") from exc

    def _client(self, name: str) -> MCPStdioClient:
        config = self.config(name)
        client = self._clients.get(name)
        if client is None:
            client = MCPStdioClient(config, event_bus=self.event_bus, environ=self.environ)
            self._clients[name] = client
        return client

    def start(self, name: str) -> MCPServerHealth:
        return self._client(name).start()

    def start_enabled(self) -> dict[str, MCPServerHealth]:
        """Start enabled servers and cache their advertised tool metadata."""
        result: dict[str, MCPServerHealth] = {}
        for name in self.names():
            if not self._configs[name].enabled:
                continue
            client = self._client(name)
            try:
                client.start()
                client.list_tools(refresh=True)
                result[name] = client.health()
            except MCPError as exc:
                client.last_error = str(exc)
                result[name] = client.health()
        return result

    def stop(self, name: str) -> None:
        client = self._clients.get(name)
        if client is not None:
            client.stop()

    def stop_all(self) -> None:
        for name in tuple(self._clients):
            self.stop(name)

    def restart(self, name: str) -> MCPServerHealth:
        return self._client(name).restart()

    def health(self, name: str | None = None) -> MCPServerHealth | dict[str, MCPServerHealth]:
        if name is None:
            return {server: self.health(server) for server in self.names()}  # type: ignore[return-value]
        client = self._clients.get(name)
        if client is not None:
            return client.health()
        config = self.config(name)
        return MCPServerHealth(
            name=name,
            enabled=config.enabled,
            running=False,
            initialized=False,
            pid=None,
            protocol_version=None,
            tool_count=0,
            last_error=None,
            stderr_tail=(),
        )

    def list_tools(
        self,
        name: str,
        *,
        refresh: bool = True,
        timeout_seconds: float | None = None,
    ) -> tuple[MCPTool, ...]:
        return self._client(name).list_tools(
            refresh=refresh,
            timeout_seconds=timeout_seconds,
        )

    def cached_tools(self, name: str | None = None) -> tuple[MCPTool, ...]:
        """Return already-discovered tool metadata without process or I/O side effects."""
        if name is not None:
            self.config(name)
            client = self._clients.get(name)
            return tuple(client.tools_cache) if client is not None else ()

        tools: list[MCPTool] = []
        for server in self.names():
            client = self._clients.get(server)
            if client is not None:
                tools.extend(client.tools_cache)
        return tuple(tools)

    def discover_tools(self, *, refresh: bool = True) -> tuple[MCPTool, ...]:
        """Explicit discovery helper; unlike cached_tools this may perform I/O."""
        tools: list[MCPTool] = []
        for name in self.names():
            if not self._configs[name].enabled:
                continue
            client = self._client(name)
            if not client.running:
                client.start()
            tools.extend(client.list_tools(refresh=refresh))
        return tuple(tools)
