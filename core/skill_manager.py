import os
import importlib
import inspect as _inspect
from uuid import uuid4
from datetime import datetime

from core.permissions import PermissionEngine, PermissionLevel
from core.audit import ActionAuditTrail
from core.execution import ExecutionRequest


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

    def load_all_skills(self):
        """
        Pre-load all skills if needed.
        Usually not required due to lazy loading.
        Only call for morning briefing or full health check.
        """
        skill_names = self.list_available_skills()
        for skill_name in skill_names:
            self.get_skill(skill_name)
        print(f"All {len(self._skill_cache)} skills loaded.")

    def list_available_skills(self):
        """Scan skills/ folder and return all discoverable skill names."""
        if not os.path.exists('skills'):
            return []
        return sorted(
            f.replace('_skill.py', '')
            for f in os.listdir('skills')
            if f.endswith('_skill.py') and not f.startswith('__')
        )

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
            # Local memory/business/debug updates do not create external side effects.
            if skill_name in {"memory", "business", "debug"}:
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

    def execute(self, skill_name, tool_name, params=None, approved=False):
        """Compatibility wrapper around the explicit execution-request boundary."""
        return self.execute_request(
            ExecutionRequest(
                skill=skill_name,
                tool=tool_name,
                params=params or {},
                approved=approved,
            )
        )

    def execute_request(self, request: ExecutionRequest):
        """Execute one immutable request through policy, audit and capability dispatch."""
        skill_name = request.skill
        tool_name = request.tool
        params = dict(request.params)
        approved = request.approved
        action = request.action
        decision = self.permission_engine.assess_tool(skill_name, tool_name)
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
                and not result.get('success', True)
                and bool(result.get('error'))
            )
            if failed:
                self.log_skill_error(skill_name, tool_name, result['error'], params)
                if self.audit_trail is not None:
                    self.audit_trail.record(
                        actor_type="skill", action=action, status="failed",
                        action_id=action_id, permission=decision.level.value,
                        approved=approved, result=result,
                        error=str(result.get("error")),
                    )
            elif self.audit_trail is not None:
                self.audit_trail.record(
                    actor_type="skill", action=action, status="completed",
                    action_id=action_id, permission=decision.level.value,
                    approved=approved, result=result,
                )
            return result

        except Exception as e:
            error_msg = str(e)
            self.log_skill_error(skill_name, tool_name, error_msg, params)
            if self.audit_trail is not None:
                self.audit_trail.record(
                    actor_type="skill", action=action, status="failed",
                    action_id=action_id, permission=decision.level.value,
                    approved=approved, params=params, error=error_msg,
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

    def log_skill_error(self, skill_name, tool_name,
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
        except:
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
                pending["skill"], pending["tool"], pending["params"], approved=True
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
    # TRINITY PROMPT - Static for speed
    # ==========================================

    def get_trinity_prompt(self, query=None):
        """
        Generate the skills section of Trinity's system prompt.
        When a query is provided, only include the skills relevant to that query.
        This saves tokens and keeps the LLM focused.
        """
        # Detect which skills are relevant to this query
        relevant = self._detect_relevant_skills(query) if query else None

        # Full skill definitions
        skill_blocks = {
            'github': """GITHUB SKILL
Purpose: Read, write, and manage code repositories
Tools:
  read_file(repo, path) - Read any file
  list_files(repo, path) - List files in a directory
  get_commits(repo, path, count) - Commit history
  get_commit_details(repo, commit_sha) - What changed in a commit
  get_workflow_runs(repo, count) - GitHub Actions status
  get_repo_info(repo) - Repository info
  get_branches(repo) - All branches
  get_issues(repo, state) - Open or closed issues
  create_file(repo, path, content, reason) - Create file [NEEDS APPROVAL]
  update_file(repo, path, content, reason) - Replace file [NEEDS APPROVAL]
  add_to_file(repo, path, content, position, reason) - Add to file [NEEDS APPROVAL]
  delete_file(repo, path, reason) - Delete file [NEEDS APPROVAL]
  revert_file(repo, path, commit_sha) - Revert to old version [NEEDS APPROVAL]
  create_multiple_files(files, reason) - Create many files [NEEDS APPROVAL]""",

            'web': """WEB SKILL
Purpose: Monitor websites, SSL, and security headers
Tools:
  check_website(url) - Is site up, response time
  check_ssl(domain) - SSL certificate status and expiry
  check_domain_expiry(domain) - Domain registration expiry
  read_webpage(url) - Read content from any webpage
  check_all_trinity6() - Full trinity6.com health check
  check_response_headers(url) - Security headers audit""",

            'memory': """MEMORY SKILL
Purpose: Read and write Trinity's brain and history
Tools:
  read_brain() - Full Trinity memory
  read_section(section) - Specific brain section
  search_history(query, days) - Search legacy conversation history
  search_sessions(query, days, limit) - Search persistent local conversation sessions
  get_recent_sessions(days, limit) - Read recent persistent conversation sessions
  get_recent_logs(days) - Recent activity logs
  get_active_alerts() - Active alerts
  update_david(key, value) - Update David info
  update_company(key, value) - Update company data
  add_client(name, company, status, notes) - Add to pipeline
  update_revenue(amount, source) - Record revenue
  log_decision(decision, outcome) - Log a decision
  learn(category, insight) - Record a learning
  add_log(entry) - Add daily log entry
  update_wellbeing(score, note) - David wellbeing score
  pin_memory(key, value) - Permanently store a critical fact (never forgotten)
  get_pinned() - Read all permanently stored facts""",

            'knowledge': """KNOWLEDGE SKILL
Purpose: Search David's approved local files and folders with source references
Tools:
  index_knowledge_path(path, recursive) - Approve and index a new local root [NEEDS APPROVAL]
  refresh_knowledge_index() - Refresh already-approved roots incrementally
  search_knowledge(query, limit) - Search indexed local knowledge
  read_knowledge_source(source_path, start_line, end_line) - Read an indexed source range
  list_knowledge_sources(limit) - List indexed local sources
  get_knowledge_status() - Knowledge index statistics
  remove_knowledge_root(path, remove_documents) - Remove an approved root from the index [NEEDS APPROVAL]""",

            'search': """SEARCH SKILL
Purpose: Real web search — no fake or hardcoded data
Tools:
  search_web(query, max_results) - DuckDuckGo search
  search_cybersecurity_news() - Live headlines from security sources
  search_cis_updates() - CIS benchmark current versions
  find_potential_clients(location, industry) - Prospect search
  research_competitor(competitor_name) - Live + baseline competitor data
  search_linkedin_prospects(role, location, industry) - LinkedIn strategy
  get_market_intelligence() - Live market intel search
  check_source(url) - Check URL accessibility and page title""",

            'code': """CODE SKILL
Purpose: Review, analyze, and audit Trinity6 code
Tools:
  review_file(repo, path) - Complete code review
  find_bugs(repo, path) - Find potential bugs
  check_python_syntax(repo, path) - Syntax check
  analyze_imports(repo, path) - Dependencies analysis
  get_functions(repo, path) - Functions and classes list
  check_code_quality(repo, path) - Quality metrics
  find_todos(repo) - Find all TODO comments
  compare_files(repo1, path1, repo2, path2) - Diff two files
  audit_security_code(repo, path) - Security vulnerability check
  get_codebase_overview(repo) - Full repo overview""",

            'business': """BUSINESS SKILL
Purpose: Track revenue, clients, and company growth
Tools:
  get_business_status() - Full health status
  get_client_pipeline() - All clients and prospects
  add_prospect(name, company, contact, notes) - Add prospect
  update_prospect_status(company, new_status, notes) - Update status
  record_revenue(amount, client, description) - Record payment
  get_weekly_priorities() - This week's priorities
  generate_invoice_details(client_name, service, amount) - Invoice
  get_growth_metrics() - Growth trends and milestones
  plan_outreach(target_count) - Weekly outreach plan
  calculate_mrr() - Monthly recurring revenue""",

            'calculator': """CALCULATOR SKILL
Purpose: Safe math — never guesses, always computes
Tools:
  calculate(expression) - Evaluate any math expression safely
  calculate_mrr(clients, price_per_client) - Monthly recurring revenue
  calculate_revenue_target(target_inr, price_per_client, months) - Clients needed
  calculate_growth_rate(current_value, previous_value) - Growth percentage
  convert_units(value, from_unit, to_unit) - Currency/data/time conversion""",

            'debug': """DEBUG SKILL
Purpose: Log errors, test skills, detect failure patterns, check LLM config
Tools:
  log_error(skill_name, tool_name, error_message, params) - Log an error
  analyze_error(error_message) - Classify error and suggest fix
  test_skill_method(skill_name, tool_name, test_params) - Actually execute and test a skill
  get_error_history(limit) - Recent error log
  get_error_patterns() - Detect recurring failures
  clear_errors() - Clear error log
  get_llm_status() - Check which local AI models are configured and active""",
        }

        if relevant is not None:
            selected = {k: skill_blocks[k] for k in relevant if k in skill_blocks}
        else:
            selected = skill_blocks

        blocks = "\n\n".join(selected.values())

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
    # CONTEXT FOR BRIEFINGS
    # ==========================================

    def get_github_context(self):
        """Get live GitHub context for briefings"""
        try:
            github_skill = self.get_skill('github')
            if not github_skill:
                return ""

            context = github_skill.get_all_repos_context()
            lines = ["LIVE GITHUB STATUS:"]

            for repo, data in context.items():
                lines.append(f"\n{repo}:")
                lines.append(
                    f"  Files: {data['total_files']}"
                )

                commits = data.get('recent_commits', [])
                if commits:
                    lines.append(
                        f"  Last commit: {commits[0]['message'][:50]}"
                    )

                workflows = data.get('recent_workflows', [])
                failed = [
                    w for w in workflows
                    if w.get('conclusion') == 'failure'
                ]
                if failed:
                    lines.append(
                        f"  FAILED workflows: {len(failed)}"
                    )

            return '\n'.join(lines)

        except Exception as e:
            return f"GitHub context error: {str(e)}"

    def get_health_summary(self):
        """Get overall system health"""
        results = {
            'checked_at': datetime.now().isoformat(),
            'skills_loaded': len(self._skill_cache),
            'skill_status': {}
        }

        for skill_name in self._skill_cache:
            results['skill_status'][skill_name] = 'active'

        try:
            web_skill = self.get_skill('web')
            if web_skill:
                website = web_skill.execute(
                    'check_website',
                    {'url': 'https://trinity6.com'}
                )
                results['website'] = website
                results['website_live'] = website.get(
                    'is_live', False
                )
        except:
            results['website_live'] = False

        try:
            memory_skill = self.get_skill('memory')
            if memory_skill:
                brain = memory_skill.read_brain()
                results['memory_active'] = brain.get(
                    'success', False
                )
                results['days_alive'] = brain.get(
                    'days_alive', 0
                )
        except:
            results['memory_active'] = False

        return results

    def get_business_summary(self):
        """Get business summary for briefings"""
        try:
            business_skill = self.get_skill('business')
            if not business_skill:
                return {}
            return business_skill.execute(
                'get_business_status', {}
            )
        except:
            return {}

    # ==========================================
    # SKILL CALL PARSER
    # ==========================================

    def process_skill_call(self, response_text):
            """
            Parse and execute SKILL_CALL blocks
            Supports both formats:
    
            Format 1 (inline - what LLM actually outputs):
            SKILL_CALL: github.read_file
            repo: Trinity6
            path: README.md
    
            Format 2 (block - old format):
            SKILL_CALL
            skill: github
            tool: read_file
            params:
            repo: Trinity6
            path: README.md
            END_SKILL_CALL
            """
            if 'SKILL_CALL' not in response_text:
                return None, response_text
    
            try:
                lines = response_text.split('\n')
                result_text = []
                all_results = []
                i = 0
    
                while i < len(lines):
                    line = lines[i]
                    stripped = line.strip()
    
                    # ── Format 1: SKILL_CALL: skill.tool ──
                    if stripped.upper().startswith('SKILL_CALL:') or stripped.upper().startswith('SKILL_CALL :'):
                        # Parse "SKILL_CALL: github.read_file"
                        call_part = stripped.split(':', 1)[1].strip()
    
                        if '.' in call_part:
                            skill_name, tool_name = call_part.split('.', 1)
                            skill_name = skill_name.strip().lower()
                            tool_name = tool_name.strip()
                        else:
                            i += 1
                            continue
    
                        # Collect parameters from following lines
                        params = {}
                        i += 1
                        while i < len(lines):
                            param_line = lines[i].strip()
    
                            # Stop at empty line, next SKILL_CALL, or non-param line
                            if not param_line:
                                break
                            if param_line.upper().startswith('SKILL_CALL'):
                                break
                            if param_line.startswith('TRINITY_'):
                                break
    
                            # Parse "key: value"
                            if ':' in param_line:
                                key, value = param_line.split(':', 1)
                                key = key.strip()
                                value = value.strip()
    
                                # Skip if key looks like a sentence
                                if ' ' in key and len(key) > 20:
                                    break
    
                                # Type conversion
                                try:
                                    if value.isdigit():
                                        value = int(value)
                                    elif value.replace('.', '').isdigit():
                                        value = float(value)
                                except:
                                    pass
    
                                params[key] = value
                            else:
                                break
    
                            i += 1
    
                        # Execute the skill call
                        result = self.execute(skill_name, tool_name, params)
                        all_results.append(result)
                        result_text.append(f"[{skill_name}.{tool_name} result]")
                        result_text.append(str(result))
                        continue
    
                    # ── Format 2: Block format with END_SKILL_CALL ──
                    elif stripped == 'SKILL_CALL':
                        skill_name = ''
                        tool_name = ''
                        params = {}
                        in_params = False
                        i += 1
    
                        while i < len(lines):
                            block_line = lines[i].strip()
    
                            if block_line == 'END_SKILL_CALL':
                                result = self.execute(
                                    skill_name, tool_name, params
                                )
                                all_results.append(result)
                                result_text.append(
                                    f"[{skill_name}.{tool_name} result]"
                                )
                                result_text.append(str(result))
                                i += 1
                                break
    
                            if block_line.startswith('skill:'):
                                skill_name = block_line.replace(
                                    'skill:', ''
                                ).strip().lower()
                            elif block_line.startswith('tool:'):
                                tool_name = block_line.replace(
                                    'tool:', ''
                                ).strip()
                            elif block_line == 'params:':
                                in_params = True
                            elif in_params and ':' in block_line:
                                parts = block_line.split(':', 1)
                                if len(parts) == 2:
                                    key = parts[0].strip()
                                    value = parts[1].strip()
                                    try:
                                        if value.isdigit():
                                            value = int(value)
                                        elif value.replace('.', '').isdigit():
                                            value = float(value)
                                    except:
                                        pass
                                    params[key] = value
    
                            i += 1
                        continue
    
                    else:
                        result_text.append(line)
    
                    i += 1
    
                if all_results:
                    return all_results, '\n'.join(result_text)
                return None, response_text
    
            except Exception as e:
                print(f"[SKILL_MANAGER] Error parsing skill call: {e}")
                return None, response_text
