import os
import ast
import re
from datetime import datetime


class CodeSkill:
    """
    Trinity Code Skill
    Review code in repositories
    Find bugs and issues
    Suggest improvements
    Check code quality
    Understand Trinity6 codebase
    Auto discovered by SkillManager
    """

    name = "code"
    description = "Review code, find bugs, suggest improvements and understand Trinity6 codebase"

    def __init__(self, github_skill=None):
        self.github_skill = github_skill
        self.trinity6_repos = [
            "Trinity6",
            "assistant",
            "trinity-ai"
        ]

    def get_tools(self):
        """Returns all code tools Trinity can use"""
        return [
            {
                "name": "review_file",
                "description": "Review a specific code file for issues",
                "params": ["repo", "path"],
                "needs_approval": False
            },
            {
                "name": "find_bugs",
                "description": "Find potential bugs in a file",
                "params": ["repo", "path"],
                "needs_approval": False
            },
            {
                "name": "check_python_syntax",
                "description": "Check Python file for syntax errors",
                "params": ["repo", "path"],
                "needs_approval": False
            },
            {
                "name": "analyze_imports",
                "description": "Analyze imports and dependencies in a file",
                "params": ["repo", "path"],
                "needs_approval": False
            },
            {
                "name": "get_functions",
                "description": "List all functions and classes in a file",
                "params": ["repo", "path"],
                "needs_approval": False
            },
            {
                "name": "check_code_quality",
                "description": "Check overall code quality metrics",
                "params": ["repo", "path"],
                "needs_approval": False
            },
            {
                "name": "find_todos",
                "description": "Find all TODO and FIXME comments in repo",
                "params": ["repo"],
                "needs_approval": False
            },
            {
                "name": "compare_files",
                "description": "Compare two files and find differences",
                "params": ["repo1", "path1", "repo2", "path2"],
                "needs_approval": False
            },
            {
                "name": "audit_security_code",
                "description": "Audit code for security vulnerabilities",
                "params": ["repo", "path"],
                "needs_approval": False
            },
            {
                "name": "get_codebase_overview",
                "description": "Get overview of entire Trinity6 codebase",
                "params": ["repo"],
                "needs_approval": False
            }
        ]

    def execute(self, tool_name, params):
        """Trinity calls this to use any code tool"""
        tool_map = {
            "review_file": self.review_file,
            "find_bugs": self.find_bugs,
            "check_python_syntax": self.check_python_syntax,
            "analyze_imports": self.analyze_imports,
            "get_functions": self.get_functions,
            "check_code_quality": self.check_code_quality,
            "find_todos": self.find_todos,
            "compare_files": self.compare_files,
            "audit_security_code": self.audit_security_code,
            "get_codebase_overview": self.get_codebase_overview
        }

        tool = tool_map.get(tool_name)
        if not tool:
            return {"error": f"Unknown tool: {tool_name}"}

        try:
            return tool(**params)
        except Exception as e:
            return {"error": str(e)}

    # ==========================================
    # HELPER - Read file via GitHub skill
    # ==========================================

    def read_code_file(self, repo, path):
        """Read file content via GitHub skill"""
        if self.github_skill:
            result = self.github_skill.read_file(repo, path)
            if result.get('success'):
                return result['content']
        return None

    # ==========================================
    # CODE ANALYSIS TOOLS
    # ==========================================

    def check_python_syntax(self, repo, path):
        """Check Python file for syntax errors"""
        content = self.read_code_file(repo, path)
        if not content:
            return {
                'success': False,
                'error': f"Could not read {repo}/{path}"
            }

        try:
            ast.parse(content)
            return {
                'success': True,
                'repo': repo,
                'path': path,
                'syntax_valid': True,
                'message': 'No syntax errors found'
            }
        except SyntaxError as e:
            return {
                'success': True,
                'repo': repo,
                'path': path,
                'syntax_valid': False,
                'error': str(e),
                'line': e.lineno,
                'message': f"Syntax error on line {e.lineno}: {e.msg}"
            }

    def get_functions(self, repo, path):
        """List all functions and classes in file"""
        content = self.read_code_file(repo, path)
        if not content:
            return {
                'success': False,
                'error': f"Could not read {repo}/{path}"
            }

        try:
            tree = ast.parse(content)
            functions = []
            classes = []

            for node in ast.walk(tree):
                if isinstance(node, ast.FunctionDef):
                    args = [
                        arg.arg for arg in node.args.args
                    ]
                    docstring = ast.get_docstring(node)
                    functions.append({
                        'name': node.name,
                        'line': node.lineno,
                        'args': args,
                        'has_docstring': docstring is not None,
                        'docstring': docstring[:100]
                            if docstring else None
                    })
                elif isinstance(node, ast.ClassDef):
                    methods = [
                        n.name for n in ast.walk(node)
                        if isinstance(n, ast.FunctionDef)
                    ]
                    classes.append({
                        'name': node.name,
                        'line': node.lineno,
                        'methods': methods,
                        'method_count': len(methods)
                    })

            return {
                'success': True,
                'repo': repo,
                'path': path,
                'total_functions': len(functions),
                'total_classes': len(classes),
                'functions': functions,
                'classes': classes
            }

        except Exception as e:
            return {
                'success': False,
                'error': str(e)
            }

    def analyze_imports(self, repo, path):
        """Analyze imports and dependencies"""
        content = self.read_code_file(repo, path)
        if not content:
            return {
                'success': False,
                'error': f"Could not read {repo}/{path}"
            }

        try:
            tree = ast.parse(content)
            imports = []
            from_imports = []

            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    for alias in node.names:
                        imports.append(alias.name)
                elif isinstance(node, ast.ImportFrom):
                    module = node.module or ''
                    names = [
                        alias.name for alias in node.names
                    ]
                    from_imports.append({
                        'from': module,
                        'imports': names
                    })

            standard_libs = [
                'os', 'sys', 'json', 'time', 'datetime',
                'collections', 're', 'math', 'random',
                'string', 'io', 'ast', 'ssl', 'socket',
                'subprocess', 'threading', 'pathlib'
            ]

            third_party = [
                i for i in imports
                if i not in standard_libs
            ]

            return {
                'success': True,
                'repo': repo,
                'path': path,
                'total_imports': len(imports) + len(from_imports),
                'direct_imports': imports,
                'from_imports': from_imports,
                'third_party_dependencies': third_party,
                'standard_library': [
                    i for i in imports
                    if i in standard_libs
                ]
            }

        except Exception as e:
            return {
                'success': False,
                'error': str(e)
            }

    def find_bugs(self, repo, path):
        """Find potential bugs in Python file"""
        content = self.read_code_file(repo, path)
        if not content:
            return {
                'success': False,
                'error': f"Could not read {repo}/{path}"
            }

        potential_bugs = []
        lines = content.split('\n')

        for i, line in enumerate(lines, 1):
            stripped = line.strip()

            if 'except:' in stripped and \
               'except Exception' not in stripped:
                potential_bugs.append({
                    'line': i,
                    'type': 'Bare except',
                    'code': stripped,
                    'suggestion': 'Use except Exception as e instead of bare except'
                })

            if '== None' in stripped or '!= None' in stripped:
                potential_bugs.append({
                    'line': i,
                    'type': 'None comparison',
                    'code': stripped,
                    'suggestion': 'Use is None or is not None instead'
                })

            if 'print(' in stripped and \
               i < len(lines) - 5:
                potential_bugs.append({
                    'line': i,
                    'type': 'Debug print statement',
                    'code': stripped,
                    'suggestion': 'Consider using logging instead of print'
                })

            if 'TODO' in stripped or 'FIXME' in stripped or \
               'HACK' in stripped:
                potential_bugs.append({
                    'line': i,
                    'type': 'Unresolved TODO',
                    'code': stripped,
                    'suggestion': 'This needs attention'
                })

            if 'password' in stripped.lower() and \
               '=' in stripped and \
               '"' in stripped:
                potential_bugs.append({
                    'line': i,
                    'type': 'Possible hardcoded credential',
                    'code': 'Line hidden for security',
                    'suggestion': 'Use environment variables for credentials'
                })

        syntax_check = self.check_python_syntax(repo, path)

        return {
            'success': True,
            'repo': repo,
            'path': path,
            'syntax_valid': syntax_check.get('syntax_valid', False),
            'total_issues': len(potential_bugs),
            'potential_bugs': potential_bugs,
            'overall': 'clean' if not potential_bugs else 'needs review'
        }

    def check_code_quality(self, repo, path):
        """Check overall code quality"""
        content = self.read_code_file(repo, path)
        if not content:
            return {
                'success': False,
                'error': f"Could not read {repo}/{path}"
            }

        lines = content.split('\n')
        total_lines = len(lines)
        blank_lines = sum(1 for l in lines if not l.strip())
        comment_lines = sum(
            1 for l in lines if l.strip().startswith('#')
        )
        code_lines = total_lines - blank_lines - comment_lines

        long_lines = [
            i+1 for i, l in enumerate(lines)
            if len(l) > 100
        ]

        try:
            tree = ast.parse(content)
            functions = [
                n for n in ast.walk(tree)
                if isinstance(n, ast.FunctionDef)
            ]
            functions_with_docs = [
                f for f in functions
                if ast.get_docstring(f)
            ]
            doc_coverage = (
                len(functions_with_docs) /
                len(functions) * 100
            ) if functions else 100

        except:
            functions = []
            doc_coverage = 0

        quality_score = 100

        if long_lines:
            quality_score -= min(20, len(long_lines) * 2)
        if doc_coverage < 50:
            quality_score -= 20
        if code_lines > 500:
            quality_score -= 10

        return {
            'success': True,
            'repo': repo,
            'path': path,
            'metrics': {
                'total_lines': total_lines,
                'code_lines': code_lines,
                'blank_lines': blank_lines,
                'comment_lines': comment_lines,
                'long_lines': long_lines[:5],
                'total_functions': len(functions),
                'documentation_coverage': round(doc_coverage),
                'quality_score': quality_score
            },
            'rating': 'excellent' if quality_score >= 80
                else 'good' if quality_score >= 60
                else 'needs improvement'
        }

    def find_todos(self, repo):
        """Find all TODO and FIXME comments"""
        if not self.github_skill:
            return {
                'success': False,
                'error': 'GitHub skill not available'
            }

        files_result = self.github_skill.list_files(repo)
        if not files_result.get('success'):
            return {
                'success': False,
                'error': 'Could not list files'
            }

        python_files = [
            f for f in files_result['files']
            if f.endswith('.py')
        ]

        all_todos = []

        for file_path in python_files[:10]:
            content = self.read_code_file(repo, file_path)
            if not content:
                continue

            for i, line in enumerate(
                content.split('\n'), 1
            ):
                if any(
                    keyword in line
                    for keyword in ['TODO', 'FIXME', 'HACK', 'XXX']
                ):
                    all_todos.append({
                        'file': file_path,
                        'line': i,
                        'content': line.strip()
                    })

        return {
            'success': True,
            'repo': repo,
            'total_todos': len(all_todos),
            'todos': all_todos
        }

    def audit_security_code(self, repo, path):
        """Audit code for security issues"""
        content = self.read_code_file(repo, path)
        if not content:
            return {
                'success': False,
                'error': f"Could not read {repo}/{path}"
            }

        security_issues = []
        lines = content.split('\n')

        dangerous_patterns = [
            {
                'pattern': r'eval\s*\(',
                'issue': 'Use of eval()',
                'severity': 'high',
                'suggestion': 'eval() can execute arbitrary code. Avoid it.'
            },
            {
                'pattern': r'exec\s*\(',
                'issue': 'Use of exec()',
                'severity': 'high',
                'suggestion': 'exec() can execute arbitrary code. Avoid it.'
            },
            {
                'pattern': r'shell\s*=\s*True',
                'issue': 'Shell injection risk',
                'severity': 'high',
                'suggestion': 'Use shell=False and pass args as list'
            },
            {
                'pattern': r'pickle\.loads',
                'issue': 'Unsafe deserialization',
                'severity': 'medium',
                'suggestion': 'pickle.loads can execute code. Use JSON instead.'
            },
            {
                'pattern': r'requests\.get.*verify\s*=\s*False',
                'issue': 'SSL verification disabled',
                'severity': 'medium',
                'suggestion': 'Never disable SSL verification in production'
            },
            {
                'pattern': r'md5|sha1',
                'issue': 'Weak cryptographic hash',
                'severity': 'low',
                'suggestion': 'Use SHA-256 or stronger'
            }
        ]

        for i, line in enumerate(lines, 1):
            for check in dangerous_patterns:
                if re.search(
                    check['pattern'], line, re.IGNORECASE
                ):
                    security_issues.append({
                        'line': i,
                        'issue': check['issue'],
                        'severity': check['severity'],
                        'code': line.strip(),
                        'suggestion': check['suggestion']
                    })

        high = [
            s for s in security_issues
            if s['severity'] == 'high'
        ]
        medium = [
            s for s in security_issues
            if s['severity'] == 'medium'
        ]
        low = [
            s for s in security_issues
            if s['severity'] == 'low'
        ]

        overall_risk = 'low'
        if high:
            overall_risk = 'high'
        elif medium:
            overall_risk = 'medium'

        return {
            'success': True,
            'repo': repo,
            'path': path,
            'overall_risk': overall_risk,
            'total_issues': len(security_issues),
            'high_severity': len(high),
            'medium_severity': len(medium),
            'low_severity': len(low),
            'issues': security_issues,
            'is_secure': len(security_issues) == 0
        }

    def review_file(self, repo, path):
        """Complete review of a code file"""
        syntax = self.check_python_syntax(repo, path)
        functions = self.get_functions(repo, path)
        bugs = self.find_bugs(repo, path)
        quality = self.check_code_quality(repo, path)
        security = self.audit_security_code(repo, path)

        recommendations = []

        if not syntax.get('syntax_valid'):
            recommendations.append(
                f"Fix syntax error on line {syntax.get('line')}"
            )

        if bugs.get('total_issues', 0) > 0:
            recommendations.append(
                f"Fix {bugs['total_issues']} potential bugs"
            )

        if quality.get('metrics', {}).get(
            'documentation_coverage', 100
        ) < 50:
            recommendations.append(
                "Add docstrings to functions"
            )

        if security.get('high_severity', 0) > 0:
            recommendations.append(
                f"Fix {security['high_severity']} high severity security issues immediately"
            )

        overall = 'good'
        if not syntax.get('syntax_valid') or \
           security.get('overall_risk') == 'high':
            overall = 'needs immediate attention'
        elif bugs.get('total_issues', 0) > 5 or \
             quality.get('quality_score', 100) < 60:
            overall = 'needs improvement'

        return {
            'success': True,
            'repo': repo,
            'path': path,
            'overall': overall,
            'syntax': syntax,
            'functions': functions,
            'bugs': bugs,
            'quality': quality,
            'security': security,
            'recommendations': recommendations
        }

    def compare_files(self, repo1, path1,
                       repo2, path2):
        """Compare two files"""
        content1 = self.read_code_file(repo1, path1)
        content2 = self.read_code_file(repo2, path2)

        if not content1 or not content2:
            return {
                'success': False,
                'error': 'Could not read one or both files'
            }

        lines1 = content1.split('\n')
        lines2 = content2.split('\n')

        differences = []
        max_lines = max(len(lines1), len(lines2))

        for i in range(min(max_lines, 100)):
            l1 = lines1[i] if i < len(lines1) else None
            l2 = lines2[i] if i < len(lines2) else None
            if l1 != l2:
                differences.append({
                    'line': i + 1,
                    'file1': l1,
                    'file2': l2
                })

        return {
            'success': True,
            'file1': f"{repo1}/{path1}",
            'file2': f"{repo2}/{path2}",
            'file1_lines': len(lines1),
            'file2_lines': len(lines2),
            'total_differences': len(differences),
            'differences': differences[:20],
            'are_identical': len(differences) == 0
        }

    def get_codebase_overview(self, repo):
        """Get overview of entire codebase"""
        if not self.github_skill:
            return {
                'success': False,
                'error': 'GitHub skill not available'
            }

        files_result = self.github_skill.list_files(repo)
        if not files_result.get('success'):
            return {
                'success': False,
                'error': 'Could not list files'
            }

        all_files = files_result['files']
        python_files = [f for f in all_files if f.endswith('.py')]
        yaml_files = [f for f in all_files if f.endswith('.yaml') or f.endswith('.yml')]
        json_files = [f for f in all_files if f.endswith('.json')]
        html_files = [f for f in all_files if f.endswith('.html')]

        folders = set()
        for f in all_files:
            parts = f.split('/')
            if len(parts) > 1:
                folders.add(parts[0])

        return {
            'success': True,
            'repo': repo,
            'total_files': len(all_files),
            'file_types': {
                'python': len(python_files),
                'yaml': len(yaml_files),
                'json': len(json_files),
                'html': len(html_files),
                'other': len(all_files) - len(python_files) - len(yaml_files) - len(json_files) - len(html_files)
            },
            'folders': list(folders),
            'python_files': python_files,
            'all_files': all_files
        }
