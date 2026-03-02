"""
Trinity Debug Skill — Real Error Logging, Self-Testing, and Self-Healing

test_skill_method() ACTUALLY executes the skill method — not a stub.
read_skill_code() and propose_fix() let Trinity read and fix its own code.
"""
import time
import traceback
from collections import Counter
from datetime import datetime


class DebugSkill:
    """
    Real debugging and self-healing capabilities.
    - Logs errors with full context
    - Classifies error types with fix suggestions
    - Actually executes skill methods to test them (not a stub)
    - Detects recurring failure patterns
    - Reads its own skill source code via GitHub
    - Proposes fixes for broken methods
    """

    name = "debug"
    description = "Error logging, analysis, real skill testing, pattern detection, and self-healing"

    def __init__(self, skill_manager=None, github_skill=None):
        self._skill_manager = skill_manager   # for test_skill_method execution
        self.github_skill = github_skill       # for read_skill_code / propose_fix
        self._error_log = []
        self._MAX_ERRORS = 200

    def get_tools(self):
        return [
            {
                "name": "log_error",
                "description": "Log an error with skill name, tool name, and message",
                "params": ["skill_name", "tool_name", "error_message", "params"],
                "needs_approval": False,
            },
            {
                "name": "analyze_error",
                "description": "Classify an error and suggest a concrete fix",
                "params": ["error_message"],
                "needs_approval": False,
            },
            {
                "name": "read_skill_code",
                "description": "Read the source code of a skill file via GitHub",
                "params": ["skill_name"],
                "needs_approval": False,
            },
            {
                "name": "propose_fix",
                "description": "Read a method and propose a fix — returns code + next_step",
                "params": ["skill_name", "method_name", "fix_description"],
                "needs_approval": False,
            },
            {
                "name": "test_skill_method",
                "description": (
                    "Actually execute a skill method with test params "
                    "and return the real result + timing"
                ),
                "params": ["skill_name", "tool_name", "test_params"],
                "needs_approval": False,
            },
            {
                "name": "get_error_history",
                "description": "Return recent errors from the log",
                "params": ["limit"],
                "needs_approval": False,
            },
            {
                "name": "get_error_patterns",
                "description": "Detect which skills and tools fail most often",
                "params": [],
                "needs_approval": False,
            },
            {
                "name": "clear_errors",
                "description": "Clear the in-memory error log",
                "params": [],
                "needs_approval": False,
            },
            {
                "name": "get_llm_status",
                "description": "Check which AI brain tiers are configured and available right now",
                "params": [],
                "needs_approval": False,
            },
        ]

    def execute(self, tool_name, params):
        tool_map = {
            "log_error": self.log_error,
            "analyze_error": self.analyze_error,
            "read_skill_code": self.read_skill_code,
            "propose_fix": self.propose_fix,
            "test_skill_method": self.test_skill_method,
            "get_error_history": self.get_error_history,
            "get_error_patterns": self.get_error_patterns,
            "clear_errors": self.clear_errors,
            "get_llm_status": self.get_llm_status,
        }
        tool = tool_map.get(tool_name)
        if not tool:
            return {"error": f"Unknown tool: {tool_name}", "success": False}
        try:
            return tool(**params)
        except TypeError as e:
            return {"error": f"Wrong params for {tool_name}: {e}", "success": False}
        except Exception as e:
            return {"error": str(e), "success": False}

    # ==========================================
    # TOOLS
    # ==========================================

    def log_error(self, skill_name, tool_name, error_message, params=None):
        """Log an error with full context."""
        entry = {
            "timestamp": datetime.now().isoformat(),
            "skill": skill_name,
            "tool": tool_name,
            "error": str(error_message),
            "params": params or {},
        }
        self._error_log.append(entry)
        if len(self._error_log) > self._MAX_ERRORS:
            self._error_log = self._error_log[-self._MAX_ERRORS:]
        return {
            "success": True,
            "logged": entry,
            "total_errors": len(self._error_log),
        }

    def analyze_error(self, error_message):
        """Classify error type and give a concrete fix suggestion."""
        msg = str(error_message).lower()

        patterns = [
            {
                "keywords": ["importerror", "modulenotfounderror", "no module named"],
                "type": "ImportError",
                "cause": "Missing Python package or wrong import path",
                "fix": (
                    "Check requirements.txt. "
                    "Run: pip install <package_name>. "
                    "Verify the import path matches the actual file location."
                ),
            },
            {
                "keywords": ["keyerror"],
                "type": "KeyError",
                "cause": "Dictionary key does not exist in the data",
                "fix": (
                    "Use .get(key, default) instead of [key]. "
                    "Log the full dict before accessing to see available keys."
                ),
            },
            {
                "keywords": ["typeerror", "unexpected keyword argument", "takes", "argument"],
                "type": "TypeError",
                "cause": "Wrong argument types or count passed to function",
                "fix": (
                    "Check the function signature. "
                    "Make sure all required params are provided and types match."
                ),
            },
            {
                "keywords": ["attributeerror"],
                "type": "AttributeError",
                "cause": "Object does not have the expected attribute or method",
                "fix": (
                    "Check if the object is None before accessing attributes. "
                    "Verify the skill loaded correctly. "
                    "Check the exact attribute name."
                ),
            },
            {
                "keywords": ["connectionerror", "timeout", "connection refused", "network"],
                "type": "NetworkError",
                "cause": "Network request failed",
                "fix": (
                    "Check internet connectivity. "
                    "Verify the URL/endpoint is correct. "
                    "Add retry logic with exponential backoff."
                ),
            },
            {
                "keywords": ["401", "403", "unauthorized", "forbidden"],
                "type": "AuthError",
                "cause": "Authentication or permission failure",
                "fix": (
                    "Check API tokens and environment variables. "
                    "Verify the token has the required permissions. "
                    "Check if the token has expired."
                ),
            },
            {
                "keywords": ["404", "not found"],
                "type": "NotFoundError",
                "cause": "Resource does not exist at the given path",
                "fix": (
                    "Verify the file or endpoint path. "
                    "Check if the resource was moved or deleted."
                ),
            },
            {
                "keywords": ["zerodivisionerror", "division by zero"],
                "type": "ZeroDivisionError",
                "cause": "Division by zero in arithmetic",
                "fix": "Add guard: if denominator == 0: handle_zero_case()",
            },
            {
                "keywords": ["jsondecodeerror", "invalid json", "json"],
                "type": "JSONError",
                "cause": "Invalid JSON received or produced",
                "fix": (
                    "Log the raw response before parsing. "
                    "Wrap json.loads() in try/except. "
                    "Check if the API returned an error page instead of JSON."
                ),
            },
            {
                "keywords": ["filenotfounderror", "no such file"],
                "type": "FileNotFoundError",
                "cause": "File or directory does not exist",
                "fix": (
                    "Check the path. "
                    "Use os.makedirs(dir, exist_ok=True) before writing. "
                    "Verify working directory."
                ),
            },
        ]

        matched = None
        for pattern in patterns:
            if any(kw in msg for kw in pattern["keywords"]):
                matched = pattern
                break

        if not matched:
            matched = {
                "type": "UnknownError",
                "cause": "Could not classify this error automatically",
                "fix": (
                    "Add more logging around the failing code. "
                    "Print the full traceback. "
                    "Isolate the failing line by adding print() before each operation."
                ),
            }

        return {
            "success": True,
            "error_message": error_message,
            "error_type": matched["type"],
            "likely_cause": matched["cause"],
            "fix_suggestion": matched["fix"],
            "analyzed_at": datetime.now().isoformat(),
        }

    def test_skill_method(self, skill_name, tool_name, test_params=None):
        """
        ACTUALLY execute a skill method.
        Returns the real result, execution time, and pass/fail status.
        This is not a stub — it calls the real code.
        """
        if test_params is None:
            test_params = {}

        if not self._skill_manager:
            return {
                "success": False,
                "error": (
                    "DebugSkill needs skill_manager to test skills. "
                    "Instantiate with: DebugSkill(skill_manager=skill_manager_instance)"
                ),
                "skill": skill_name,
                "tool": tool_name,
            }

        start = time.time()
        try:
            result = self._skill_manager.execute(skill_name, tool_name, test_params)
            duration_ms = int((time.time() - start) * 1000)

            # Determine if the result indicates failure
            failed = (
                result is None
                or (isinstance(result, dict) and "error" in result)
                or (isinstance(result, dict) and result.get("success") is False)
            )

            return {
                "success": True,
                "test_passed": not failed,
                "skill": skill_name,
                "tool": tool_name,
                "params_used": test_params,
                "result": result,
                "duration_ms": duration_ms,
                "tested_at": datetime.now().isoformat(),
            }

        except Exception as e:
            duration_ms = int((time.time() - start) * 1000)
            tb = traceback.format_exc()
            # Auto-log the failure
            self.log_error(skill_name, tool_name, str(e), test_params)
            return {
                "success": False,
                "test_passed": False,
                "skill": skill_name,
                "tool": tool_name,
                "params_used": test_params,
                "error": str(e),
                "traceback": tb,
                "duration_ms": duration_ms,
                "tested_at": datetime.now().isoformat(),
            }

    def get_error_history(self, limit=20):
        """Return the most recent errors from the log."""
        limit = int(limit) if limit else 20
        recent = self._error_log[-limit:]
        return {
            "success": True,
            "total_errors": len(self._error_log),
            "showing": len(recent),
            "errors": recent,
        }

    def get_error_patterns(self):
        """Detect recurring error patterns from the log."""
        if not self._error_log:
            return {
                "success": True,
                "patterns": [],
                "note": "No errors logged yet.",
            }

        skill_tool = Counter(
            f"{e['skill']}.{e['tool']}" for e in self._error_log
        )
        error_types = Counter(
            e["error"].split(":")[0].strip() for e in self._error_log
        )
        recurring = [
            {"skill_tool": k, "count": v}
            for k, v in skill_tool.most_common(5)
            if v >= 2
        ]

        return {
            "success": True,
            "total_errors": len(self._error_log),
            "recurring_failures": recurring,
            "top_error_types": dict(error_types.most_common(5)),
            "most_failing": skill_tool.most_common(1)[0][0] if skill_tool else None,
        }

    def clear_errors(self):
        """Clear the in-memory error log."""
        count = len(self._error_log)
        self._error_log.clear()
        return {"success": True, "cleared": count}

    def get_llm_status(self):
        """
        Check which AI brain tiers are configured and available right now.
        Checks env vars and pings local Ollama — no API calls to cloud providers.
        """
        import os
        import requests as _requests

        tiers = {}

        # Tier 1: Local Ollama
        local_url = os.environ.get('LOCAL_LLM_URL', 'http://localhost:11434')
        local_model = os.environ.get('LOCAL_LLM_MODEL', 'llama3.2')
        try:
            resp = _requests.get(f"{local_url}/api/tags", timeout=2)
            if resp.status_code == 200:
                models = [m.get('name', '') for m in resp.json().get('models', [])]
                tiers['tier1_local_ollama'] = {
                    'available': True,
                    'model': local_model,
                    'all_models': models,
                    'status': 'ready',
                }
            else:
                tiers['tier1_local_ollama'] = {'available': False, 'status': 'ollama running but returned error'}
        except Exception:
            tiers['tier1_local_ollama'] = {
                'available': False,
                'model': local_model,
                'status': 'not running',
                'action': 'Start Ollama on your machine to enable this tier',
            }

        # Tier 2: Google Gemini Flash
        google_key = os.environ.get('GOOGLE_API_KEY') or os.environ.get('GEMINI_API_KEY')
        tiers['tier2_google_gemini'] = {
            'available': bool(google_key),
            'model': 'gemini-2.0-flash',
            'key_var': 'GOOGLE_API_KEY or GEMINI_API_KEY',
            'status': 'ready — free tier, more capable than Haiku' if google_key else 'not configured',
            'action': None if google_key else 'Add GOOGLE_API_KEY to GitHub Actions secrets (get from aistudio.google.com)',
        }

        # Tier 3: Claude Haiku (default)
        anthropic_key = os.environ.get('ANTHROPIC_API_KEY')
        tiers['tier3_claude_haiku'] = {
            'available': bool(anthropic_key),
            'model': 'claude-haiku-4-5-20251001',
            'key_var': 'ANTHROPIC_API_KEY',
            'status': 'ready — default for simple tasks' if anthropic_key else 'not configured',
        }

        active_tiers = [k for k, v in tiers.items() if v['available']]
        return {
            'success': True,
            'tiers': tiers,
            'active_tiers': active_tiers,
            'current_default': (
                'tier1_local_ollama' if tiers['tier1_local_ollama']['available']
                else 'tier2_google_gemini' if tiers['tier2_google_gemini']['available']
                else 'tier3_claude_haiku' if tiers['tier3_claude_haiku']['available']
                else 'none — no LLM configured!'
            ),
            'recommendation': (
                'All good!' if len(active_tiers) >= 2
                else 'Add GOOGLE_API_KEY for a more capable free model for complex tasks'
            ),
        }

    def read_skill_code(self, skill_name):
        """Read source code of a skill file via GitHub (requires github_skill)."""
        if not self.github_skill:
            return {
                "success": False,
                "error": "github_skill not available — inject it via DebugSkill(github_skill=...)",
            }
        skill_file = f"skills/{skill_name}_skill.py"
        result = self.github_skill.read_file("trinity-ai", skill_file)
        if not result.get("success"):
            # Try without _skill suffix
            result = self.github_skill.read_file("trinity-ai", f"skills/{skill_name}.py")
        if result.get("success"):
            content = result["content"]
            return {
                "success": True,
                "skill_name": skill_name,
                "file": skill_file,
                "content": content,
                "total_lines": len(content.split("\n")),
                "sha": result.get("sha"),
            }
        return {"success": False, "error": f"Could not read {skill_file}"}

    def propose_fix(self, skill_name, method_name, fix_description):
        """
        Locate a method in a skill file and describe how to fix it.
        Returns the method's current code + guidance on next steps.
        """
        skill_code = self.read_skill_code(skill_name)
        if not skill_code.get("success"):
            return {"success": False, "error": f"Cannot read {skill_name} to propose fix"}

        content = skill_code["content"]
        method_found = False
        method_lines = []
        in_method = False
        method_start = 0

        for i, line in enumerate(content.split("\n")):
            if f"def {method_name}(" in line:
                method_found = True
                in_method = True
                method_start = i + 1
                method_lines.append(f"Line {i+1}: {line}")
            elif in_method:
                if line and not line.startswith((" ", "\t")) and "def " in line:
                    in_method = False
                else:
                    method_lines.append(f"Line {i+1}: {line}")
                    if len(method_lines) > 30:
                        method_lines.append("...")
                        break

        return {
            "success": True,
            "skill_name": skill_name,
            "method_name": method_name,
            "method_found": method_found,
            "method_code": "\n".join(method_lines[:20]),
            "method_start_line": method_start,
            "fix_description": fix_description,
            "next_step": (
                f"Use github_skill.update_file to fix "
                f"skills/{skill_name}_skill.py with the corrected {method_name} method. "
                "Read the full file first, then apply the fix."
            ),
            "file_sha": skill_code.get("sha"),
        }
