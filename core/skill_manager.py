import os
import importlib
import inspect as _inspect
import re
from uuid import uuid4

from core.permissions import PermissionEngine, PermissionLevel
from core.audit import ActionAuditTrail
from core.execution import ExecutionRequest, thaw_mapping
from core.trust_context import TrustLevel, get_current_trust_context


class SkillManager:
    """
    Trinity Skill Manager
    Automatically discovers and loads skills lazily
    Generates system prompt for Trinity
    Routes tool calls to correct skill
    Trinity decides which skill to use automatically
    No configuration needed
    """

    def __init__(self, gh_token=None,
                 brain_file=None, memory=None, permission_engine=None,
                 audit_trail: ActionAuditTrail | None = None, computer_controller=None):
        self.gh_token = gh_token
        self.brain_file = brain_file
        self.memory = memory
        self.permission_engine = permission_engine or PermissionEngine()
        self.audit_trail = audit_trail
        self.computer_controller = computer_controller
        self.capability_registry = None
        self._pending_actions = {}
        self._skill_cache = {}
        print("Skill Manager ready. Skills load on demand.")

    # ==========================================
    # SKILL LOADING - Lazy
    # ==========================================

    def get_skill(self, skill_name):
        """
        Load a skill by name — auto-discovers from skills/ folder.

        Any file named  skills/<skill_name>_skill.py  that contains a
        class with  name = "<skill_name>"  is loaded automatically.
        No hardcoded list needed — Trinity can create new skill files
        and they will be picked up immediately on the next call.

        Dependencies are injected by matching __init__ parameter names:
          gh_token      → self.gh_token
          brain_file    → compatibility migration path (standalone use only)
          memory        → shared MemoryService owned by the Trinity runtime
          github_skill  → self.get_skill('github')
          memory_skill  → self.get_skill('memory')
          skill_manager → self
        """
        if skill_name in self._skill_cache:
            return self._skill_cache[skill_name]

        skill_file = f"skills/{skill_name}_skill.py"
        if not os.path.exists(skill_file):
            print(f"No skill file found for: {skill_name}")
            return None

        print(f"Loading {skill_name} skill...")
        try:
            module = importlib.import_module(f"skills.{skill_name}_skill")

            # Find the class whose `name` attribute matches skill_name
            skill_class = None
            for attr in dir(module):
                obj = getattr(module, attr)
                if isinstance(obj, type) and getattr(obj, 'name', None) == skill_name:
                    skill_class = obj
                    break

            if not skill_class:
                print(f"No class with name='{skill_name}' in {skill_file}")
                return None

            # Resolve constructor dependencies by parameter name
            dep_resolvers = {
                'gh_token':     lambda: self.gh_token,
                'brain_file':   lambda: self.brain_file,
                'memory':       lambda: self.memory,
                'github_skill': lambda: self.get_skill('github'),
                'memory_skill': lambda: self.get_skill('memory'),
                'skill_manager': lambda: self,
                'computer_controller': lambda: self.computer_controller,
            }
            params = _inspect.signature(skill_class.__init__).parameters
            kwargs = {}
            for param_name in params:
                if param_name == 'self':
                    continue
                if param_name in dep_resolvers:
                    val = dep_resolvers[param_name]()
                    if val is not None:
                        kwargs[param_name] = val

            skill = skill_class(**kwargs)
            self._skill_cache[skill_name] = skill
            print(f"{skill_name} skill loaded.")
            return skill

        except Exception as e:
            print(f"Error loading {skill_name}: {str(e)}")
            return None


    def bind_capability_registry(self, registry):
        """Bind the normalized capability index owned by the Trinity runtime."""
        self.capability_registry = registry

    def _discover_skill_names(self):
        """Filesystem discovery used internally by the capability registry."""
        if not os.path.exists('skills'):
            return []
        return sorted(
            f.replace('_skill.py', '')
            for f in os.listdir('skills')
            if f.endswith('_skill.py') and not f.startswith('__')
        )

    def list_available_skills(self):
        """Return executable skill owners from the registry when it is bound."""
        if self.capability_registry is not None:
            return self.capability_registry.skill_names()
        return self._discover_skill_names()

    def reload_skill(self, skill_name):
        """
        Hot-reload a skill by evicting it from the cache and sys.modules.
        The next call to get_skill() will re-import the file from disk,
        picking up any changes made since the process started.
        """
        import sys
        self._skill_cache.pop(skill_name, None)
        sys.modules.pop(f"skills.{skill_name}_skill", None)
        print(f"[SkillManager] {skill_name} skill evicted — will reload from disk on next use.")

    def _tool_metadata(self, skill, tool_name):
        """Return declared tool metadata when a skill exposes get_tools()."""
        getter = getattr(skill, "get_tools", None)
        if not callable(getter):
            return None
        try:
            tools = getter()
        except Exception:
            return None
        if not isinstance(tools, list):
            return None
        for item in tools:
            if isinstance(item, dict) and item.get("name") == tool_name:
                return item
        return None

    def capability_requires_approval(self, skill_name, tool_name, *, skill=None):
        """Return whether execution itself is blocked on explicit approval.

        This mirrors the runtime permission gate, including the existing staging
        behavior for GitHub changes and local memory/business/debug updates.
        """
        skill = skill or self.get_skill(skill_name)
        if skill is None:
            return True
        decision = self.permission_engine.assess_tool(skill_name, tool_name)
        if decision.level == PermissionLevel.FORBIDDEN:
            return True
        result = self._permission_gate(skill_name, tool_name, skill, approved=False)
        return bool(result and result.get("needs_approval"))

    def _permission_gate(self, skill_name, tool_name, skill, approved=False):
        """Evaluate policy before executing a skill tool."""
        decision = self.permission_engine.assess_tool(skill_name, tool_name)
        if decision.level == PermissionLevel.FORBIDDEN:
            return {
                "success": False,
                "error": decision.reason,
                "permission_denied": True,
                "permission": decision.level.value,
            }
        if decision.level == PermissionLevel.HIGH_RISK and not approved:
            return {
                "success": False,
                "error": decision.reason,
                "needs_approval": True,
                "permission": decision.level.value,
            }
        if decision.level == PermissionLevel.CONFIRM and not approved:
            metadata = self._tool_metadata(skill, tool_name)
            # GitHub-style tools that declare needs_approval only stage a change;
            # the actual mutation is performed later after explicit approval.
            staging_tools = {
                "create_file", "update_file", "add_to_file", "delete_file",
                "revert_file", "create_multiple_files",
            }
            if (
                metadata
                and metadata.get("needs_approval") is True
                and skill_name == "github"
                and tool_name in staging_tools
            ):
                return None
            # Local-only convenience exemptions apply only to a verified owner.
            # Unverified sources must retain PermissionEngine trust escalation.
            if (
                skill_name in {"memory", "business", "debug"}
                and get_current_trust_context().level != TrustLevel.UNVERIFIED
            ):
                return None
            return {
                "success": False,
                "error": decision.reason,
                "needs_approval": True,
                "permission": decision.level.value,
            }
        return None

    # ==========================================
    # EXECUTE
    # ==========================================

    def execute(
        self,
        skill_name,
        tool_name,
        params=None,
        approved=False,
        context=None,
    ):
        """Compatibility wrapper around the explicit execution-request boundary."""
        return self.execute_request(
            ExecutionRequest(
                skill=skill_name,
                tool=tool_name,
                params=params or {},
                approved=approved,
                context=context or {},
            )
        )

    def execute_request(self, request: ExecutionRequest):
        """Execute one immutable request through policy, audit and capability dispatch."""
        skill_name = request.skill
        tool_name = request.tool
        params = thaw_mapping(request.params)
        approved = request.approved
        action = request.action
        decision = self.permission_engine.assess_tool(skill_name, tool_name)
        audit_metadata = (
            {"execution_context": thaw_mapping(request.context)}
            if request.context else None
        )
        action_id = None
        if self.audit_trail is not None:
            action_id = self.audit_trail.record(
                actor_type="skill",
                action=action,
                status="requested",
                permission=decision.level.value,
                approved=approved,
                params=params,
            )

        skill = self.get_skill(skill_name)
        if not skill:
            error = f"Skill {skill_name} not found"
            if self.audit_trail is not None:
                self.audit_trail.record(
                    actor_type="skill", action=action, status="failed",
                    action_id=action_id, permission=decision.level.value,
                    approved=approved, params=params, error=error,
                    metadata=audit_metadata,
                )
            return {
                'success': False,
                'error': error,
                'available_skills': self.list_available_skills()
            }

        permission_result = self._permission_gate(
            skill_name, tool_name, skill, approved=approved
        )
        if permission_result is not None:
            if permission_result.get("needs_approval"):
                approval_id = uuid4().hex[:12]
                self._pending_actions[approval_id] = request.as_pending_action(
                    approval_id, decision.level.value
                )
                permission_result["approval_id"] = approval_id
                permission_result["skill"] = skill_name
                permission_result["tool"] = tool_name
            if self.audit_trail is not None:
                status = (
                    "denied" if permission_result.get("permission_denied")
                    else "approval_required"
                )
                self.audit_trail.record(
                    actor_type="skill", action=action, status=status,
                    action_id=action_id, permission=decision.level.value,
                    approved=approved, params=params,
                    error=permission_result.get("error"),
                )
            return permission_result

        if self.audit_trail is not None:
            if approved and decision.requires_confirmation:
                self.audit_trail.record(
                    actor_type="skill", action=action, status="approved",
                    action_id=action_id, permission=decision.level.value,
                    approved=True,
                )
            self.audit_trail.record(
                actor_type="skill", action=action, status="started",
                action_id=action_id, permission=decision.level.value,
                approved=approved, params=params,
            )

        try:
            execute_signature = _inspect.signature(skill.execute)
            if "approved" in execute_signature.parameters:
                result = skill.execute(tool_name, params, approved=approved)
            else:
                result = skill.execute(tool_name, params)

            if isinstance(result, dict) and "unknown tool" in str(result.get("error", "")).lower():
                result["unknown_tool"] = True
                result["skill"] = skill_name
                result["tool"] = tool_name

            failed = (
                isinstance(result, dict)
                and bool(result.get("error"))
                and result.get("success") is not True
            ) or (
                isinstance(result, dict)
                and result.get("success") is False
            )
            if failed:
                self._log_skill_error(skill_name, tool_name, result['error'], params)
                if self.audit_trail is not None:
                    self.audit_trail.record(
                        actor_type="skill", action=action, status="failed",
                        action_id=action_id, permission=decision.level.value,
                        approved=approved, result=result,
                        error=str(result.get("error")),
                        metadata=audit_metadata,
                    )
            elif self.audit_trail is not None:
                self.audit_trail.record(
                    actor_type="skill", action=action, status="completed",
                    action_id=action_id, permission=decision.level.value,
                    approved=approved, result=result,
                    metadata=audit_metadata,
                )
            return result

        except Exception as e:
            error_msg = str(e)
            self._log_skill_error(skill_name, tool_name, error_msg, params)
            if self.audit_trail is not None:
                self.audit_trail.record(
                    actor_type="skill", action=action, status="failed",
                    action_id=action_id, permission=decision.level.value,
                    approved=approved, params=params, error=error_msg,
                    metadata=audit_metadata,
                )
            return {
                'success': False,
                'error': error_msg,
                'skill': skill_name,
                'tool': tool_name,
                'auto_debug': (
                    f"Error logged automatically. "
                    f"Trinity can use debug skill to "
                    f"analyze and fix this."
                )
            }

    def _log_skill_error(self, skill_name, tool_name,
                         error, params):
        """Log error to debug skill automatically"""
        try:
            debug_skill = self.get_skill('debug')
            if debug_skill:
                debug_skill.log_error(
                    skill=skill_name,
                    method=tool_name,
                    error=error,
                    context=str(params)[:200]
                )
        except Exception:
            pass


    # ==========================================
    # GENERIC PENDING ACTION APPROVALS
    # ==========================================

    def get_pending_actions(self):
        return {key: dict(value) for key, value in self._pending_actions.items()}

    def approve_action(self, approval_id):
        pending = self._pending_actions.pop(approval_id, None)
        if not pending:
            return {"success": False, "error": "Pending action not found"}
        return self.execute_request(
            ExecutionRequest(
                pending["skill"],
                pending["tool"],
                pending["params"],
                approved=True,
                context=pending.get("context", {}),
            )
        )

    def cancel_action(self, approval_id):
        return self._pending_actions.pop(approval_id, None) is not None

    # ==========================================
    # PENDING CHANGES
    # ==========================================

    def get_pending_changes(self):
        """Get all pending changes across all skills"""
        github_skill = self._skill_cache.get('github')
        if github_skill:
            return github_skill.get_pending_changes()
        return {}

    def commit_change(self, change_id):
        """Commit a previously staged GitHub change after explicit approval."""
        action = "github.commit_change"
        decision = self.permission_engine.assess_tool("github", "commit_change")
        action_id = None
        if self.audit_trail is not None:
            action_id = self.audit_trail.record(
                actor_type="skill", action=action, status="requested",
                permission=decision.level.value, approved=True,
                params={"change_id": change_id},
            )
            self.audit_trail.record(
                actor_type="skill", action=action, status="approved",
                action_id=action_id, permission=decision.level.value, approved=True,
            )
            self.audit_trail.record(
                actor_type="skill", action=action, status="started",
                action_id=action_id, permission=decision.level.value, approved=True,
            )

        github_skill = self._skill_cache.get('github')
        if not github_skill:
            result = (False, "GitHub skill not available")
        else:
            result = github_skill.commit_change(change_id)

        success, message = result
        if self.audit_trail is not None:
            self.audit_trail.record(
                actor_type="skill", action=action,
                status="completed" if success else "failed",
                action_id=action_id, permission=decision.level.value, approved=True,
                result={"success": success, "message": message},
                error=None if success else str(message),
            )
        return result

    def cancel_change(self, change_id):
        """Cancel a staged change and record the decision in the audit trail."""
        action = "github.cancel_change"
        github_skill = self._skill_cache.get('github')
        result = github_skill.cancel_change(change_id) if github_skill else False
        if self.audit_trail is not None:
            self.audit_trail.record(
                actor_type="skill", action=action, status="completed",
                permission="safe", approved=True,
                params={"change_id": change_id}, result={"cancelled": bool(result)},
            )
        return result

    # ==========================================
    # TRINITY PROMPT - Registry-backed
    # ==========================================

    def get_trinity_prompt(self, query=None):
        """
        Generate the skills section of Trinity's system prompt.
        When a query is provided, only include the skills relevant to that query.
        This saves tokens and keeps the LLM focused.
        """
        # Detect which skills are relevant to this query
        relevant = self._detect_relevant_skills(query) if query else None

        if self.capability_registry is not None:
            blocks = self.capability_registry.render_skill_blocks(skills=relevant)
            return self._wrap_trinity_prompt(blocks)

        # Standalone managers use the same normalized metadata path as the full runtime.
        # This prevents a second hard-coded capability catalog from drifting out of sync.
        from core.capabilities import CapabilityRegistry

        registry = CapabilityRegistry(
            self.permission_engine, skills=self
        )
        blocks = registry.render_skill_blocks(skills=relevant)
        return self._wrap_trinity_prompt(blocks)

    @staticmethod
    def _wrap_trinity_prompt(blocks):
        return f"""SKILLS AVAILABLE TO TRINITY:
Trinity automatically picks the right skill.
David never needs to mention skills directly.

{blocks}

DEBUG SKILL
Purpose: Trinity detects and fixes its own bugs, checks own configuration
Tools:
  log_error(skill_name, tool_name, error_message, params)
  analyze_error(error_message)
  read_skill_code(skill_name)
  propose_fix(skill_name, method_name, fix_description)
  test_skill_method(skill_name, tool_name, test_params)
  get_error_history(limit)
  get_error_patterns()
  get_llm_status() - Check which local AI models are active right now

WHEN TRINITY HITS AN ERROR:
1. Do not repeat the same failing call
2. Use debug.analyze_error to understand what went wrong
3. Use debug.read_skill_code to read the failing code
4. Use github.update_file to fix the code
5. Show David the fix for approval
6. After YES commit the fix
7. Try the original task again

Trinity should never hit the same error twice.

GOVERNED CAPABILITY EVOLUTION
When Trinity needs a genuinely missing capability, do not call a code-writing skill.
Emit exactly one directive so the runtime can draft an approval-gated proposal:
  TRINITY_SKILL_NEED: skill_name | one-line reason
The proposal is reviewed and explicitly approved before any skills/ file is written.

HOW TRINITY USES SKILLS:
1. David asks something
2. Trinity picks the right skill and tool
3. Trinity executes it and returns a plain-language result

CRITICAL RULES:
- Use calculator.calculate for all arithmetic — never compute in your head
- Use search_web for any current events, news, or competitor info — never make up data
- Always read a file before updating it
- Use add_to_file when adding content, update_file only when replacing
- Never commit without David saying YES
- Show a clear preview of every change before committing
- If a skill returns an error, use debug.analyze_error to classify it
- Be honest: if you don't know something, say so and offer to search for it"""

    def _detect_relevant_skills(self, query):
        """
        Return a list of relevant skill names based on the query text.
        Always includes memory. Falls back to all skills for broad queries.
        """
        if not query:
            return None

        q = query.lower()
        skills = {'memory'}  # Always useful for context

        if any(w in q for w in [
            'github', 'file', 'commit', 'code', 'repo', 'branch',
            'workflow', 'pull request', 'issue', 'push', 'read file',
        ]):
            skills.add('github')

        if any(w in q for w in [
            'review', 'bug', 'syntax', 'import', 'function', 'class',
            'quality', 'todo', 'security audit', 'vulnerability',
            'analyze code', 'check code',
        ]):
            skills.add('code')
            skills.add('github')

        if any(w in q for w in [
            'website', 'ssl', 'domain', 'http', 'trinity6.com',
            'security headers', 'online', 'offline', 'check site',
        ]):
            skills.add('web')

        if any(w in q for w in [
            'my notes', 'our notes', 'my document', 'our document',
            'my docs', 'our docs', 'personal knowledge', 'knowledge base',
            'knowledge root', 'index this', 'index folder', 'index directory',
            'refresh knowledge', 'remove knowledge root', 'runbook',
            'specification', 'architecture notes', 'design doc',
            'local file', 'local document',
        ]):
            skills.add('knowledge')

        if any(w in q for w in [
            'news', 'search', 'competitor', 'client', 'prospect',
            'market', 'cis', 'linkedin', 'find', 'research',
            'latest', 'current', 'today', 'trend',
        ]):
            skills.add('search')

        if any(w in q for w in [
            'revenue', 'client', 'pipeline', 'business', 'invoice',
            'mrr', 'outreach', 'growth', 'milestone', 'priority',
        ]):
            skills.add('business')

        if any(w in q for w in [
            'calculate', 'math', 'convert', 'how much', 'how many',
            'percent', 'total', 'cost', 'price', 'inr', 'usd',
            'formula', 'equation', 'add up', 'multiply',
        ]):
            skills.add('calculator')

        if any(w in q for w in [
            'error', 'debug', 'test', 'broken', 'fix', 'failed',
            'not working', 'crash', 'exception', 'traceback',
        ]):
            skills.add('debug')

        # If 5+ skills triggered, just send everything — query is broad
        if len(skills) >= 5:
            return None

        return sorted(skills)

    # ==========================================
    # SKILL CALL PARSER
    # ==========================================

    @staticmethod
    def _coerce_param(value: str):
        """Coerce simple numeric tool parameters while preserving ordinary strings."""
        value = value.strip()
        try:
            if value.isdigit():
                return int(value)
            if value.replace(".", "", 1).isdigit() and value.count(".") <= 1:
                return float(value)
        except (TypeError, ValueError):
            pass
        return value

    def process_skill_call(self, response_text, *, context=None):
        """Parse and execute the single supported ``SKILL_CALL: skill.tool`` format."""
        if "SKILL_CALL" not in response_text.upper():
            return None, response_text

        try:
            lines = response_text.split("\n")
            rendered: list[str] = []
            results = []
            i = 0

            while i < len(lines):
                line = lines[i]
                stripped = line.strip()
                match = re.match(
                    r"SKILL_CALL\s*:\s*([A-Za-z_][A-Za-z0-9_]*)\.([A-Za-z_][A-Za-z0-9_]*)",
                    stripped,
                    flags=re.IGNORECASE,
                )
                if match is None:
                    rendered.append(line)
                    i += 1
                    continue

                skill_name = match.group(1).lower()
                tool_name = match.group(2)
                params = {}
                i += 1

                while i < len(lines):
                    param_line = lines[i].strip()
                    if not param_line or param_line.upper().startswith("SKILL_CALL"):
                        break
                    if param_line.startswith("TRINITY_") or ":" not in param_line:
                        break
                    key, value = param_line.split(":", 1)
                    key = key.strip()
                    if " " in key and len(key) > 20:
                        break
                    params[key] = self._coerce_param(value)
                    i += 1

                result = self.execute(
                    skill_name,
                    tool_name,
                    params,
                    context=context,
                )
                results.append(result)
                rendered.append(f"[{skill_name}.{tool_name} result]")
                rendered.append(str(result))

            if results:
                return results, "\n".join(rendered)
            return None, response_text
        except Exception as exc:
            print(f"[SKILL_MANAGER] Error parsing skill call: {exc}")
            return None, response_text
