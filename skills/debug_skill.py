"""
Trinity Debug Skill — Real Error Logging and Self-Testing

test_skill_method() ACTUALLY executes the skill method.
It is NOT a stub that returns instructions.
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
    - Actually executes skill methods to test them
    - Detects recurring failure patterns
    """

    name = "debug"
    description = "Error logging, analysis, real skill testing, and pattern detection"

    def __init__(self, skill_manager=None):
        # skill_manager injected so test_skill_method can route to any skill
        self._skill_manager = skill_manager
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
        ]

    def execute(self, tool_name, params):
        tool_map = {
            "log_error": self.log_error,
            "analyze_error": self.analyze_error,
            "test_skill_method": self.test_skill_method,
            "get_error_history": self.get_error_history,
            "get_error_patterns": self.get_error_patterns,
            "clear_errors": self.clear_errors,
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
