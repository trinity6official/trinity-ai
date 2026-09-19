from types import SimpleNamespace

from core.audit import ActionAuditTrail
from core.capabilities import CapabilityRegistry
from core.execution import MCPExecutionRequest
from core.mcp import MCPServerConfig, MCPServerHealth, MCPTool
from core.mcp_execution import MCPExecutionService
from core.permissions import PermissionEngine, PermissionLevel


class FakeMCP:
    def __init__(
        self,
        *,
        trust="trusted_local",
        execution_enabled=True,
        allowed_tools=("read_file",),
        result=None,
        available=True,
        result_limit_bytes=65536,
    ):
        self._config = MCPServerConfig(
            name="local-files",
            command="demo",
            trust=trust,
            execution_enabled=execution_enabled,
            allowed_tools=allowed_tools,
            result_limit_bytes=result_limit_bytes,
        )
        self.result = result if result is not None else {"content": [{"type": "text", "text": "ok"}]}
        self.available = available
        self.calls = []

    def config(self, name):
        if name != "local-files":
            raise KeyError(f"Unknown MCP server: {name}")
        return self._config

    def cached_tools(self):
        return (
            MCPTool(
                server="local-files",
                name="read_file",
                description="Read an approved file",
                input_schema={"type": "object", "properties": {"path": {"type": "string"}}},
            ),
            MCPTool(
                server="local-files",
                name="update_file",
                description="Update a file",
                input_schema={"type": "object", "properties": {"path": {}, "text": {}}},
            ),
        )

    def health(self, name):
        return MCPServerHealth(
            name=name,
            enabled=True,
            running=self.available,
            initialized=self.available,
            pid=10 if self.available else None,
            protocol_version="2025-06-18" if self.available else None,
            tool_count=2 if self.available else 0,
            last_error=None,
            stderr_tail=(),
        )

    def call_tool(self, server, tool, arguments):
        self.calls.append((server, tool, dict(arguments)))
        return self.result


def host_for(**kwargs):
    mcp = FakeMCP(**kwargs)
    permissions = PermissionEngine()
    audit = ActionAuditTrail(path=None)
    capabilities = CapabilityRegistry(permissions, mcp=mcp)
    host = SimpleNamespace(
        mcp=mcp,
        permissions=permissions,
        audit=audit,
        capabilities=capabilities,
    )
    host.mcp_execution = MCPExecutionService(host)
    return host


def test_trusted_local_read_tool_executes_without_approval():
    host = host_for()
    result = host.mcp_execution.execute("local-files", "read_file", {"path": "/tmp/a"})
    assert result["success"] is True
    assert host.mcp.calls == [("local-files", "read_file", {"path": "/tmp/a"})]


def test_untrusted_read_tool_requires_explicit_approval():
    host = host_for(trust="untrusted")
    result = host.mcp_execution.execute("local-files", "read_file", {"path": "/tmp/a"})
    assert result["needs_approval"] is True
    assert host.mcp.calls == []
    approved = host.mcp_execution.approve_action(result["approval_id"])
    assert approved["success"] is True
    assert len(host.mcp.calls) == 1


def test_mutating_tool_requires_approval_even_on_trusted_local_server():
    host = host_for(allowed_tools=("update_file",))
    result = host.mcp_execution.execute(
        "local-files", "update_file", {"path": "/tmp/a", "text": "x"}
    )
    assert result["needs_approval"] is True
    assert result["permission"] == PermissionLevel.CONFIRM.value


def test_caller_cannot_forge_preapproved_request():
    host = host_for(trust="untrusted")
    request = MCPExecutionRequest(
        "local-files", "read_file", {"path": "/tmp/a"}, approved=True
    )
    result = host.mcp_execution.execute_request(request)
    assert result["success"] is False
    assert result["permission_denied"] is True
    assert host.mcp.calls == []


def test_execution_disabled_blocks_even_safe_tool():
    host = host_for(execution_enabled=False)
    result = host.mcp_execution.execute("local-files", "read_file", {})
    assert "disabled" in result["error"].lower()
    assert host.mcp.calls == []


def test_exact_allowlist_is_required():
    host = host_for(allowed_tools=())
    result = host.mcp_execution.execute("local-files", "read_file", {})
    assert "allowlisted" in result["error"].lower()
    assert host.mcp.calls == []


def test_discovered_tool_must_be_available():
    host = host_for(available=False)
    result = host.mcp_execution.execute("local-files", "read_file", {})
    assert "unavailable" in result["error"].lower()


def test_unknown_server_is_denied():
    host = host_for()
    result = host.mcp_execution.execute("missing", "read_file", {})
    assert result["success"] is False
    assert result["permission_denied"] is True


def test_result_size_limit_is_enforced():
    host = host_for(result={"content": "x" * 100}, result_limit_bytes=32)
    result = host.mcp_execution.execute("local-files", "read_file", {})
    assert result["success"] is False
    assert "byte limit" in result["error"]


def test_server_tool_error_is_normalized_as_failure():
    host = host_for(result={"isError": True, "content": [{"text": "bad"}]})
    result = host.mcp_execution.execute("local-files", "read_file", {})
    assert result["success"] is False
    assert "tool error" in result["error"].lower()


def test_cancel_pending_action_prevents_execution():
    host = host_for(trust="untrusted")
    pending = host.mcp_execution.execute("local-files", "read_file", {})
    assert host.mcp_execution.cancel_action(pending["approval_id"]) is True
    assert host.mcp_execution.approve_action(pending["approval_id"])["success"] is False
    assert host.mcp.calls == []


def test_pending_action_snapshot_is_immutable_from_original_arguments():
    host = host_for(trust="untrusted")
    args = {"nested": {"value": 1}}
    pending = host.mcp_execution.execute("local-files", "read_file", args)
    args["nested"]["value"] = 2
    snapshot = host.mcp_execution.get_pending_actions()[pending["approval_id"]]
    assert snapshot["arguments"]["nested"]["value"] == 1


def test_process_call_parses_json_scalars_and_objects():
    host = host_for()
    execution = host.mcp_execution.process_call(
        'MCP_CALL: local-files.read_file\npath: "/tmp/a"\nlimit: 3\noptions: {"safe": true}'
    )
    assert execution.has_results
    assert host.mcp.calls[0][2] == {
        "path": "/tmp/a",
        "limit": 3,
        "options": {"safe": True},
    }


def test_process_call_without_directive_is_empty():
    host = host_for()
    result = host.mcp_execution.process_call("hello")
    assert result.has_results is False


def test_governed_descriptor_exposes_allowlisted_tool_to_conversation():
    host = host_for()
    item = host.capabilities.get("mcp:local-files.read_file")
    assert item is not None
    assert item.metadata["governance"] == "active"
    assert item.metadata["allowlisted"] is True
    assert "conversation" in item.interfaces
    assert item.permission == PermissionLevel.SAFE


def test_non_allowlisted_descriptor_stays_runtime_only():
    host = host_for()
    item = host.capabilities.get("mcp:local-files.update_file")
    assert item is not None
    assert item.interfaces == ("runtime",)
    assert item.metadata["allowlisted"] is False


def test_prompt_contains_only_governed_allowlisted_mcp_tools():
    host = host_for()
    prompt = host.capabilities.render_skill_blocks()
    assert "MCP SERVER: local-files" in prompt
    assert "read_file(path)" in prompt
    assert "update_file" not in prompt
    assert "MCP_CALL: local-files.read_file" in prompt


def test_untrusted_descriptor_marks_read_tool_for_approval():
    host = host_for(trust="untrusted")
    item = host.capabilities.get("mcp:local-files.read_file")
    assert item.execution_requires_approval is True
    assert item.permission == PermissionLevel.CONFIRM

def test_mcp_pending_action_preserves_execution_context():
    host = host_for(trust="untrusted")
    result = host.mcp_execution.execute(
        "local-files",
        "read_file",
        {"path": "/tmp/a"},
        context={"objective_id": "obj-1"},
    )
    pending = host.mcp_execution.get_pending_actions()[result["approval_id"]]
    assert pending["context"]["objective_id"] == "obj-1"
