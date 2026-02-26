import traceback
import ast
from datetime import datetime


class DebugSkill:
    """
    Trinity Debug Skill
    Trinity detects its own errors
    Reads its own code
    Proposes fixes
    Fixes itself with David's approval
    Auto discovered by SkillManager
    """

    name = "debug"
    description = "Detect errors in Trinity skills and code, propose and apply fixes"

    def __init__(self, github_skill=None):
        self.github_skill = github_skill
        self.error_log = []

    def get_tools(self):
        return [
            {
                "name": "log_error",
                "description": "Log an error Trinity encountered",
                "params": ["skill", "method", "error", "context"],
                "needs_approval": False
            },
            {
                "name": "analyze_error",
                "description": "Analyze an error and suggest fix",
                "params": ["skill", "method", "error"],
                "needs_approval": False
            },
            {
                "name": "read_skill_code",
                "description": "Read the source code of a skill",
                "params": ["skill_name"],
                "needs_approval": False
            },
            {
                "name": "propose_fix",
                "description": "Propose a code fix for a skill method",
                "params": ["skill_name", "method_name", "fix_description"],
                "needs_approval": False
            },
            {
                "name": "get_error_history",
                "description": "Get recent errors Trinity encountered",
                "params": ["limit"],
                "needs_approval": False
            },
            {
                "name": "test_skill_method",
                "description": "Test if a skill method works correctly",
                "params": ["skill_name", "method_name", "test_params"],
                "needs_approval": False
            }
        ]

    def execute(self, tool_name, params):
        tool_map = {
            "log_error": self.log_error,
            "analyze_error": self.analyze_error,
            "read_skill_code": self.read_skill_code,
            "propose_fix": self.propose_fix,
            "get_error_history": self.get_error_history,
            "test_skill_method": self.test_skill_method
        }
        tool = tool_map.get(tool_name)
        if not tool:
            return {"error": f"Unknown tool: {tool_name}"}
        try:
            return tool(**params)
        except Exception as e:
            return {"error": str(e)}

    def log_error(self, skill, method, error, context=""):
        """Log error Trinity encountered"""
        entry = {
            'timestamp': datetime.now().isoformat(),
            'skill': skill,
            'method': method,
            'error': str(error),
            'context': context
        }
        self.error_log.append(entry)

        if len(self.error_log) > 100:
            self.error_log = self.error_log[-100:]

        return {
            'success': True,
            'logged': entry
        }

    def analyze_error(self, skill, method, error):
        """
        Analyze error and suggest what went wrong
        Trinity uses this to understand its own bugs
        """
        error_str = str(error).lower()

        analysis = {
            'skill': skill,
            'method': method,
            'error': error,
            'error_type': 'unknown',
            'likely_cause': '',
            'suggested_fix': '',
            'read_code_first': True
        }

        if 'unexpected keyword argument' in error_str:
            analysis['error_type'] = 'wrong_params'
            analysis['likely_cause'] = (
                f"Method {method} is being called with "
                f"parameters it does not accept. "
                f"The method signature does not match "
                f"how it is being called."
            )
            analysis['suggested_fix'] = (
                f"Read the source code of {skill} skill. "
                f"Check what parameters {method} actually accepts. "
                f"Update the method to accept the new params "
                f"or fix how it is being called."
            )

        elif 'not found' in error_str or 'attributeerror' in error_str:
            analysis['error_type'] = 'missing_method'
            analysis['likely_cause'] = (
                f"Method {method} does not exist in {skill} skill."
            )
            analysis['suggested_fix'] = (
                f"Read {skill} skill code. "
                f"Add the missing method or fix the name."
            )

        elif 'typeerror' in error_str:
            analysis['error_type'] = 'type_mismatch'
            analysis['likely_cause'] = (
                f"Wrong data type passed to {method}. "
                f"Expected different type than received."
            )
            analysis['suggested_fix'] = (
                f"Read {method} in {skill} skill. "
                f"Check expected types and add type validation."
            )

        elif 'keyerror' in error_str:
            analysis['error_type'] = 'missing_key'
            analysis['likely_cause'] = (
                f"Trying to access dictionary key that does not exist."
            )
            analysis['suggested_fix'] = (
                f"Use .get() instead of direct dict access. "
                f"Add key existence check before accessing."
            )

        elif 'none' in error_str:
            analysis['error_type'] = 'none_value'
            analysis['likely_cause'] = (
                f"Something returned None when a value was expected."
            )
            analysis['suggested_fix'] = (
                f"Add None check before using the value. "
                f"Handle the case where result is None."
            )

        else:
            analysis['likely_cause'] = (
                f"Read the source code to understand this error."
            )
            analysis['suggested_fix'] = (
                f"Use read_skill_code to read {skill} "
                f"then analyze the specific error."
            )

        return {
            'success': True,
            'analysis': analysis,
            'next_step': f"Use read_skill_code to read skills/{skill}.py then propose a fix"
        }

    def read_skill_code(self, skill_name):
        """Read source code of a skill file"""
        if not self.github_skill:
            return {
                'success': False,
                'error': 'GitHub skill not available'
            }

        skill_file = f"skills/{skill_name}.py"
        if not skill_name.endswith('_skill'):
            skill_file = f"skills/{skill_name}_skill.py"

        result = self.github_skill.read_file(
            'trinity-ai', skill_file
        )

        if not result.get('success'):
            result = self.github_skill.read_file(
                'trinity-ai', f"skills/{skill_name}.py"
            )

        if result.get('success'):
            content = result['content']
            lines = content.split('\n')

            return {
                'success': True,
                'skill_name': skill_name,
                'file': skill_file,
                'content': content,
                'total_lines': len(lines),
                'sha': result.get('sha')
            }

        return {
            'success': False,
            'error': f"Could not read {skill_file}",
            'tried': skill_file
        }

    def propose_fix(self, skill_name, method_name,
                    fix_description):
        """
        Propose a fix for a skill method
        Trinity describes what needs to change
        Returns guidance on how to apply fix
        """
        skill_code = self.read_skill_code(skill_name)

        if not skill_code.get('success'):
            return {
                'success': False,
                'error': f"Cannot read {skill_name} to propose fix"
            }

        content = skill_code['content']
        method_found = False
        method_lines = []
        in_method = False
        method_start = 0

        lines = content.split('\n')
        for i, line in enumerate(lines):
            if f'def {method_name}(' in line:
                method_found = True
                in_method = True
                method_start = i + 1
                method_lines.append(f"Line {i+1}: {line}")
            elif in_method:
                if line and not line.startswith(' ') \
                   and not line.startswith('\t') \
                   and 'def ' in line:
                    in_method = False
                else:
                    method_lines.append(
                        f"Line {i+1}: {line}"
                    )
                    if len(method_lines) > 30:
                        method_lines.append("...")
                        break

        return {
            'success': True,
            'skill_name': skill_name,
            'method_name': method_name,
            'method_found': method_found,
            'method_code': '\n'.join(method_lines[:20]),
            'method_start_line': method_start,
            'fix_description': fix_description,
            'next_step': (
                f"Use github_skill.update_file to fix "
                f"skills/{skill_name}_skill.py "
                f"with the corrected {method_name} method. "
                f"Read the full file first then apply fix."
            ),
            'file_sha': skill_code.get('sha')
        }

    def get_error_history(self, limit=10):
        """Get recent errors"""
        recent = self.error_log[-limit:]
        return {
            'success': True,
            'total_errors': len(self.error_log),
            'recent_errors': list(reversed(recent)),
            'most_common_skill': self.get_most_common_error_skill()
        }

    def get_most_common_error_skill(self):
        """Find which skill has most errors"""
        if not self.error_log:
            return None
        skill_counts = {}
        for entry in self.error_log:
            skill = entry.get('skill', 'unknown')
            skill_counts[skill] = \
                skill_counts.get(skill, 0) + 1
        return max(skill_counts, key=skill_counts.get)

    def test_skill_method(self, skill_name,
                           method_name, test_params):
        """Test if a skill method works"""
        return {
            'success': True,
            'skill_name': skill_name,
            'method_name': method_name,
            'test_params': test_params,
            'note': (
                f"To test: call skill_manager.execute("
                f"'{skill_name}', '{method_name}', "
                f"{test_params}) and check result"
            )
        }
