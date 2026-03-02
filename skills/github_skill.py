import requests
import base64
from datetime import datetime


class GitHubSkill:
    """
    Trinity GitHub Skill
    Everything Trinity needs to work with GitHub
    Read, write, create, delete, revert files
    Monitor repos, commits, workflows
    Auto discovered by SkillManager
    """

    name = "github"
    description = "Complete GitHub operations for all Trinity6 repositories"

    def __init__(self, gh_token=None):
        self.gh_token = gh_token
        self.org = "trinity6official"
        self.repos = ["Trinity6", "assistant", "trinity-ai"]
        self.headers = {}
        self.pending_changes = {}
        if gh_token:
            self.headers = {
                "Authorization": f"token {gh_token}",
                "Accept": "application/vnd.github.v3+json"
            }

    def get_tools(self):
        """
        Returns all tools Trinity can use
        SkillManager reads this automatically
        Trinity knows exactly what it can do
        """
        return [
            {
                "name": "read_file",
                "description": "Read any file from any Trinity6 repository",
                "params": ["repo", "path"],
                "needs_approval": False
            },
            {
                "name": "read_file_at_commit",
                "description": "Read a file as it was at a specific commit",
                "params": ["repo", "path", "commit_sha"],
                "needs_approval": False
            },
            {
                "name": "list_files",
                "description": "List all files in a repository or folder",
                "params": ["repo", "path"],
                "needs_approval": False
            },
            {
                "name": "get_commits",
                "description": "Get commit history for a repo or file",
                "params": ["repo", "path", "count"],
                "needs_approval": False
            },
            {
                "name": "get_commit_details",
                "description": "Get details of a specific commit",
                "params": ["repo", "commit_sha"],
                "needs_approval": False
            },
            {
                "name": "get_workflow_runs",
                "description": "Get GitHub Actions workflow run status",
                "params": ["repo", "count"],
                "needs_approval": False
            },
            {
                "name": "get_repo_info",
                "description": "Get repository information and stats",
                "params": ["repo"],
                "needs_approval": False
            },
            {
                "name": "get_branches",
                "description": "List all branches in a repository",
                "params": ["repo"],
                "needs_approval": False
            },
            {
                "name": "get_issues",
                "description": "Get open or closed issues",
                "params": ["repo", "state"],
                "needs_approval": False
            },
            {
                "name": "create_file",
                "description": "Create a new file in a repository",
                "params": ["repo", "path", "content", "reason"],
                "needs_approval": True
            },
            {
                "name": "update_file",
                "description": "Update existing file content",
                "params": ["repo", "path", "content", "reason"],
                "needs_approval": True
            },
            {
                "name": "add_to_file",
                "description": "Add content to existing file without replacing",
                "params": ["repo", "path", "content", "position", "reason"],
                "needs_approval": True
            },
            {
                "name": "delete_file",
                "description": "Delete a file from repository",
                "params": ["repo", "path", "reason"],
                "needs_approval": True
            },
            {
                "name": "revert_file",
                "description": "Revert a file to a previous commit version",
                "params": ["repo", "path", "commit_sha"],
                "needs_approval": True
            },
            {
                "name": "create_multiple_files",
                "description": "Create multiple files at once",
                "params": ["files", "reason"],
                "needs_approval": True
            },
            {
                "name": "self_commit_improvement",
                "description": (
                    "Commit a self-improvement directly to GitHub — no David approval needed. "
                    "ONLY allowed for files inside the skills/ directory. "
                    "Use this when Trinity auto-builds or improves her own tools."
                ),
                "params": ["repo", "path", "content", "reason"],
                "needs_approval": False
            }
        ]

    def execute(self, tool_name, params):
        """
        Trinity calls this to use any GitHub tool
        Routes to correct method automatically
        """
        tool_map = {
            "read_file": self.read_file,
            "read_file_at_commit": self.read_file_at_commit,
            "list_files": self.list_files,
            "get_commits": self.get_commits,
            "get_commit_details": self.get_commit_details,
            "get_workflow_runs": self.get_workflow_runs,
            "get_repo_info": self.get_repo_info,
            "get_branches": self.get_branches,
            "get_issues": self.get_issues,
            "create_file": self.prepare_create_file,
            "update_file": self.prepare_update_file,
            "add_to_file": self.prepare_add_to_file,
            "delete_file": self.prepare_delete_file,
            "revert_file": self.prepare_revert_file,
            "create_multiple_files": self.prepare_create_multiple_files,
            "self_commit_improvement": self.self_commit_improvement
        }

        tool = tool_map.get(tool_name)
        if not tool:
            return {"error": f"Unknown tool: {tool_name}"}

        try:
            return tool(**params)
        except Exception as e:
            return {"error": str(e)}

    # ==========================================
    # GITHUB API CALLER
    # ==========================================

    def call_github(self, method, endpoint, data=None):
        """Universal GitHub API caller"""
        url = f"https://api.github.com{endpoint}"
        try:
            if method == 'GET':
                response = requests.get(
                    url, headers=self.headers, timeout=10
                )
            elif method == 'PUT':
                response = requests.put(
                    url, headers=self.headers,
                    json=data, timeout=15
                )
            elif method == 'POST':
                response = requests.post(
                    url, headers=self.headers,
                    json=data, timeout=15
                )
            elif method == 'DELETE':
                response = requests.delete(
                    url, headers=self.headers,
                    json=data, timeout=15
                )
            return response
        except Exception as e:
            return None

    # ==========================================
    # READ TOOLS - No approval needed
    # ==========================================

    def read_file(self, repo, path, ref='main'):
        """Read any file from any repo"""
        response = self.call_github(
            'GET',
            f"/repos/{self.org}/{repo}/contents/{path}?ref={ref}"
        )
        if response and response.status_code == 200:
            data = response.json()
            content = base64.b64decode(
                data['content']
            ).decode('utf-8')
            return {
                'success': True,
                'content': content,
                'sha': data['sha'],
                'path': path,
                'repo': repo
            }
        return {
            'success': False,
            'error': f"Could not read {repo}/{path}"
        }

    def read_file_at_commit(self, repo, path, commit_sha):
        """Read file as it was at specific commit"""
        return self.read_file(repo, path, ref=commit_sha)

    def list_files(self, repo, path=''):
        """List all files in repo or folder"""
        response = self.call_github(
            'GET',
            f"/repos/{self.org}/{repo}/git/trees/main?recursive=1"
        )
        if response and response.status_code == 200:
            tree = response.json().get('tree', [])
            files = [
                item['path'] for item in tree
                if item['type'] == 'blob'
            ]
            if path:
                files = [f for f in files if f.startswith(path)]
            return {
                'success': True,
                'files': files,
                'total': len(files)
            }
        return {'success': False, 'files': [], 'total': 0}

    def get_commits(self, repo, path=None, count=10):
        """Get commit history"""
        endpoint = f"/repos/{self.org}/{repo}/commits?per_page={count}"
        if path:
            endpoint += f"&path={path}"
        response = self.call_github('GET', endpoint)
        if response and response.status_code == 200:
            commits = response.json()
            return {
                'success': True,
                'commits': [{
                    'sha': c['sha'],
                    'short_sha': c['sha'][:7],
                    'message': c['commit']['message'],
                    'author': c['commit']['author']['name'],
                    'date': c['commit']['author']['date']
                } for c in commits]
            }
        return {'success': False, 'commits': []}

    def get_commit_details(self, repo, commit_sha):
        """Get details of specific commit"""
        response = self.call_github(
            'GET',
            f"/repos/{self.org}/{repo}/commits/{commit_sha}"
        )
        if response and response.status_code == 200:
            data = response.json()
            return {
                'success': True,
                'sha': data['sha'],
                'short_sha': data['sha'][:7],
                'message': data['commit']['message'],
                'author': data['commit']['author']['name'],
                'date': data['commit']['author']['date'],
                'files_changed': [
                    f['filename']
                    for f in data.get('files', [])
                ]
            }
        return {
            'success': False,
            'error': f"Commit {commit_sha} not found"
        }

    def get_workflow_runs(self, repo, count=5):
        """Get GitHub Actions runs"""
        response = self.call_github(
            'GET',
            f"/repos/{self.org}/{repo}/actions/runs?per_page={count}"
        )
        if response and response.status_code == 200:
            runs = response.json().get('workflow_runs', [])
            return {
                'success': True,
                'runs': [{
                    'name': r['name'],
                    'status': r['status'],
                    'conclusion': r['conclusion'],
                    'created_at': r['created_at'],
                    'url': r['html_url']
                } for r in runs]
            }
        return {'success': False, 'runs': []}

    def get_repo_info(self, repo):
        """Get repository information"""
        response = self.call_github(
            'GET', f"/repos/{self.org}/{repo}"
        )
        if response and response.status_code == 200:
            data = response.json()
            return {
                'success': True,
                'name': data['name'],
                'description': data.get('description'),
                'default_branch': data['default_branch'],
                'last_updated': data['updated_at'],
                'open_issues': data['open_issues_count'],
                'visibility': data['visibility']
            }
        return {'success': False, 'error': 'Repo not found'}

    def get_branches(self, repo):
        """Get all branches"""
        response = self.call_github(
            'GET', f"/repos/{self.org}/{repo}/branches"
        )
        if response and response.status_code == 200:
            return {
                'success': True,
                'branches': [b['name'] for b in response.json()]
            }
        return {'success': False, 'branches': []}

    def get_issues(self, repo, state='open'):
        """Get repository issues"""
        response = self.call_github(
            'GET',
            f"/repos/{self.org}/{repo}/issues?state={state}"
        )
        if response and response.status_code == 200:
            issues = response.json()
            return {
                'success': True,
                'issues': [{
                    'number': i['number'],
                    'title': i['title'],
                    'state': i['state'],
                    'created': i['created_at']
                } for i in issues]
            }
        return {'success': False, 'issues': []}

    def get_all_repos_context(self):
        """Get full context of all repositories"""
        context = {}
        for repo in self.repos:
            files = self.list_files(repo)
            commits = self.get_commits(repo, count=3)
            workflows = self.get_workflow_runs(repo, count=3)
            context[repo] = {
                'total_files': files.get('total', 0),
                'recent_commits': commits.get('commits', []),
                'recent_workflows': workflows.get('runs', [])
            }
        return context

    # ==========================================
    # WRITE TOOLS - Need David's approval
    # ==========================================

    def generate_change_id(self):
        """Generate unique change ID"""
        return f"change_{datetime.now().strftime('%Y%m%d%H%M%S')}"

    def generate_preview(self, old_content,
                          new_content, path, is_new):
        """Generate human readable change preview"""
        if is_new:
            lines = new_content.split('\n')[:5]
            preview = '\n'.join(lines)
            total = len(new_content.split('\n'))
            return f"NEW FILE: {path}\n\nFirst 5 lines:\n{preview}\n\nTotal lines: {total}"

        if old_content == new_content:
            return "No changes detected."

        old_lines = old_content.split('\n')
        new_lines = new_content.split('\n')
        changes = []
        max_lines = max(len(old_lines), len(new_lines))

        for i in range(max_lines):
            old = old_lines[i] if i < len(old_lines) else None
            new = new_lines[i] if i < len(new_lines) else None
            if old != new:
                if old and new:
                    changes.append(
                        f"Line {i+1} changed:\n  Before: {old}\n  After:  {new}"
                    )
                elif old is None:
                    changes.append(f"Line {i+1} added: {new}")
                else:
                    changes.append(f"Line {i+1} removed: {old}")

        if not changes:
            return "No visible changes."

        preview = '\n\n'.join(changes[:3])
        if len(changes) > 3:
            preview += f"\n\n... and {len(changes) - 3} more changes"

        return preview

    def stage_change(self, change_type, repo, path,
                      new_content, reason,
                      file_sha=None, is_new=False,
                      old_content=None):
        """Stage any change for approval"""
        change_id = self.generate_change_id()
        preview = self.generate_preview(
            old_content, new_content, path, is_new
        )

        self.pending_changes[change_id] = {
            'type': change_type,
            'repo': repo,
            'path': path,
            'new_content': new_content,
            'old_content': old_content,
            'file_sha': file_sha,
            'reason': reason,
            'is_new': is_new,
            'preview': preview,
            'created_at': datetime.now().isoformat(),
            'status': 'pending'
        }

        return change_id, preview

    def prepare_create_file(self, repo, path,
                             content, reason):
        """Stage new file creation for approval"""
        existing = self.read_file(repo, path)
        if existing.get('success'):
            return {
                'success': False,
                'error': f"File already exists. Use update_file instead."
            }

        change_id, preview = self.stage_change(
            'create', repo, path, content,
            reason, is_new=True
        )

        return {
            'success': True,
            'needs_approval': True,
            'change_id': change_id,
            'preview': preview,
            'message': f"Ready to create {repo}/{path}\n\n{preview}\n\nReply YES to create or NO to cancel."
        }

    def prepare_update_file(self, repo, path,
                             content, reason):
        """Stage file update for approval"""
        existing = self.read_file(repo, path)
        if not existing.get('success'):
            return {
                'success': False,
                'error': f"File not found. Use create_file instead."
            }

        change_id, preview = self.stage_change(
            'update', repo, path, content, reason,
            file_sha=existing['sha'],
            old_content=existing['content']
        )

        return {
            'success': True,
            'needs_approval': True,
            'change_id': change_id,
            'preview': preview,
            'message': f"Ready to update {repo}/{path}\n\n{preview}\n\nReply YES to update or NO to cancel."
        }

    def prepare_add_to_file(self, repo, path,
                             content, position='end',
                             reason=''):
        """Add content to file without replacing existing"""
        existing = self.read_file(repo, path)
        if not existing.get('success'):
            return self.prepare_create_file(
                repo, path, content, reason
            )

        current = existing['content']

        if position == 'end':
            new_content = current.rstrip() + '\n\n' + content
        elif position == 'start':
            new_content = content + '\n\n' + current
        else:
            try:
                lines = current.split('\n')
                lines.insert(int(position), content)
                new_content = '\n'.join(lines)
            except:
                new_content = current.rstrip() + '\n\n' + content

        change_id, preview = self.stage_change(
            'update', repo, path, new_content,
            reason or f"Add content to {path}",
            file_sha=existing['sha'],
            old_content=current
        )

        return {
            'success': True,
            'needs_approval': True,
            'change_id': change_id,
            'preview': preview,
            'message': f"Ready to add content to {repo}/{path}\n\n{preview}\n\nReply YES to confirm or NO to cancel."
        }

    def prepare_delete_file(self, repo, path, reason):
        """Stage file deletion for approval"""
        existing = self.read_file(repo, path)
        if not existing.get('success'):
            return {
                'success': False,
                'error': "File not found."
            }

        change_id = self.generate_change_id()
        self.pending_changes[change_id] = {
            'type': 'delete',
            'repo': repo,
            'path': path,
            'file_sha': existing['sha'],
            'reason': reason,
            'preview': f"DELETE: {repo}/{path}",
            'created_at': datetime.now().isoformat(),
            'status': 'pending'
        }

        return {
            'success': True,
            'needs_approval': True,
            'change_id': change_id,
            'preview': f"DELETE FILE: {repo}/{path}",
            'message': f"Ready to DELETE {repo}/{path}\n\nThis cannot be undone easily.\n\nReply YES to delete or NO to cancel."
        }

    def prepare_revert_file(self, repo, path, commit_sha):
        """Revert file to specific commit version"""
        old_version = self.read_file_at_commit(
            repo, path, commit_sha
        )
        if not old_version.get('success'):
            return {
                'success': False,
                'error': f"Could not find {path} at commit {commit_sha}"
            }

        commit_info = self.get_commit_details(repo, commit_sha)
        reason = f"Revert {path} to commit {commit_sha}"
        if commit_info.get('success'):
            reason += f" - {commit_info['message']}"

        current = self.read_file(repo, path)
        current_content = current.get('content') if current.get('success') else None
        current_sha = current.get('sha') if current.get('success') else None

        change_id, preview = self.stage_change(
            'update', repo, path,
            old_version['content'], reason,
            file_sha=current_sha,
            old_content=current_content
        )

        return {
            'success': True,
            'needs_approval': True,
            'change_id': change_id,
            'preview': preview,
            'message': f"Ready to revert {repo}/{path} to commit {commit_sha}\n\n{preview}\n\nReply YES to revert or NO to cancel."
        }

    def prepare_create_multiple_files(self, files, reason):
        """
        Stage multiple file creations for approval
        files = [{'repo': '', 'path': '', 'content': ''}]
        """
        change_id = self.generate_change_id()
        previews = []

        for file_info in files:
            preview = f"CREATE: {file_info['repo']}/{file_info['path']}"
            previews.append(preview)

        self.pending_changes[change_id] = {
            'type': 'create_multiple',
            'files': files,
            'reason': reason,
            'preview': '\n'.join(previews),
            'created_at': datetime.now().isoformat(),
            'status': 'pending'
        }

        preview_text = '\n'.join(previews)
        return {
            'success': True,
            'needs_approval': True,
            'change_id': change_id,
            'preview': preview_text,
            'message': f"Ready to create {len(files)} files:\n\n{preview_text}\n\nReply YES to create all or NO to cancel."
        }

    # ==========================================
    # COMMIT APPROVED CHANGES
    # ==========================================

    def commit_change(self, change_id):
        """Execute approved change"""
        change = self.pending_changes.get(change_id)
        if not change or change['status'] != 'pending':
            return False, "Change not found or already processed."

        try:
            if change['type'] == 'delete':
                success, message = self.commit_delete(change)

            elif change['type'] == 'create_multiple':
                success, message = self.commit_multiple(change)

            else:
                success, message = self.commit_file(change)

            if success:
                self.pending_changes[change_id]['status'] = 'committed'

            return success, message

        except Exception as e:
            return False, f"Error: {str(e)}"

    def commit_file(self, change):
        """Commit single file create or update"""
        content_encoded = base64.b64encode(
            change['new_content'].encode('utf-8')
        ).decode('utf-8')

        payload = {
            'message': f"Trinity: {change['reason']}",
            'content': content_encoded,
            'branch': 'main'
        }

        if change.get('file_sha'):
            payload['sha'] = change['file_sha']

        response = self.call_github(
            'PUT',
            f"/repos/{self.org}/{change['repo']}/contents/{change['path']}",
            data=payload
        )

        if response and response.status_code in [200, 201]:
            return True, f"Done! {change['type'].title()}d {change['repo']}/{change['path']}"
        else:
            error = response.json().get('message', 'Unknown') if response else 'No response'
            return False, f"Failed: {error}"

    def commit_delete(self, change):
        """Commit file deletion"""
        payload = {
            'message': f"Trinity: {change['reason']}",
            'sha': change['file_sha'],
            'branch': 'main'
        }

        response = self.call_github(
            'DELETE',
            f"/repos/{self.org}/{change['repo']}/contents/{change['path']}",
            data=payload
        )

        if response and response.status_code == 200:
            return True, f"Deleted {change['repo']}/{change['path']}"
        return False, "Delete failed"

    def commit_multiple(self, change):
        """Commit multiple files one by one"""
        results = []
        failed = []

        for file_info in change['files']:
            existing = self.read_file(
                file_info['repo'], file_info['path']
            )

            content_encoded = base64.b64encode(
                file_info['content'].encode('utf-8')
            ).decode('utf-8')

            payload = {
                'message': f"Trinity: {change['reason']} - {file_info['path']}",
                'content': content_encoded,
                'branch': 'main'
            }

            if existing.get('success'):
                payload['sha'] = existing['sha']

            response = self.call_github(
                'PUT',
                f"/repos/{self.org}/{file_info['repo']}/contents/{file_info['path']}",
                data=payload
            )

            if response and response.status_code in [200, 201]:
                results.append(file_info['path'])
            else:
                failed.append(file_info['path'])

        if failed:
            return False, f"Created {len(results)} files. Failed: {', '.join(failed)}"

        return True, f"Successfully created {len(results)} files:\n" + '\n'.join(results)

    def cancel_change(self, change_id):
        """Cancel pending change"""
        if change_id in self.pending_changes:
            self.pending_changes[change_id]['status'] = 'cancelled'
            return True
        return False

    def get_pending_changes(self):
        """Get all pending approvals"""
        return {
            k: v for k, v in self.pending_changes.items()
            if v['status'] == 'pending'
        }

    # ==========================================
    # AUTONOMOUS SELF-IMPROVEMENT (no approval)
    # ==========================================

    def self_commit_improvement(self, repo, path, content, reason):
        """
        Commit a self-improvement change directly — no staging, no David approval.

        GUARDRAILS (enforced in code, not just policy):
          - Path must be inside skills/  (Trinity's own capability files)
          - Will never touch core/, memory/, or any non-skill file
          - Content must be non-empty

        Used when Trinity auto-builds a missing tool or improves her own skills.
        All autonomous commits are clearly labelled "Trinity [auto]:" in git history
        so David can always audit what she did.
        """
        # ── Hard guardrail: only skills/ directory ──
        clean_path = path.lstrip("/").replace("\\", "/")
        if not clean_path.startswith("skills/"):
            return {
                "success": False,
                "error": (
                    f"Autonomous commits are only allowed inside skills/. "
                    f"'{path}' is outside that boundary — ask David for approval."
                )
            }

        if not content or not content.strip():
            return {"success": False, "error": "Content is empty — nothing to commit."}

        # Get current SHA so GitHub accepts the update
        existing = self.read_file(repo, clean_path)
        file_sha = existing.get("sha") if existing.get("success") else None

        content_encoded = base64.b64encode(
            content.encode("utf-8")
        ).decode("utf-8")

        payload = {
            "message": f"Trinity [auto]: {reason}",
            "content": content_encoded,
            "branch": "main",
        }
        if file_sha:
            payload["sha"] = file_sha

        response = self.call_github(
            "PUT",
            f"/repos/{self.org}/{repo}/contents/{clean_path}",
            data=payload,
        )

        if response and response.status_code in [200, 201]:
            return {
                "success": True,
                "message": f"Self-improvement committed: {repo}/{clean_path}",
                "reason": reason,
                "commit": response.json().get("commit", {}).get("sha", "")[:7],
            }

        error = "No response from GitHub"
        if response:
            try:
                error = response.json().get("message", f"HTTP {response.status_code}")
            except Exception:
                error = f"HTTP {response.status_code}"
        return {"success": False, "error": f"GitHub commit failed: {error}"}
