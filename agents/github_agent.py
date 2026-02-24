import os
import requests
import base64
from datetime import datetime

class GitHubAgent:
    """
    Trinity GitHub Agent
    Monitors all Trinity6 repositories
    Reads everything live from GitHub API
    Can create and update files with approval
    Never stores repo data in memory
    """
    
    def __init__(self, gh_token=None):
        self.gh_token = gh_token
        self.headers = {}
        if gh_token:
            self.headers = {
                "Authorization": f"token {gh_token}",
                "Accept": "application/vnd.github.v3+json"
            }
        self.org = "trinity6official"
        self.repos = [
            "Trinity6",
            "assistant",
            "trinity-ai"
        ]
        self.pending_changes = {}
    
    # ==========================================
    # REPOSITORY CHECKS
    # ==========================================
    
    def get_repo_info(self, repo):
        """Get basic repository information"""
        try:
            url = f"https://api.github.com/repos/{self.org}/{repo}"
            response = requests.get(
                url,
                headers=self.headers,
                timeout=10
            )
            if response.status_code == 200:
                return response.json()
            return None
        except Exception as e:
            print(f"Error getting repo info: {str(e)}")
            return None
    
    def get_recent_commits(self, repo, count=5):
        """Get recent commits from repository"""
        try:
            url = f"https://api.github.com/repos/{self.org}/{repo}/commits?per_page={count}"
            response = requests.get(
                url,
                headers=self.headers,
                timeout=10
            )
            if response.status_code == 200:
                commits = response.json()
                return [{
                    'message': c['commit']['message'],
                    'author': c['commit']['author']['name'],
                    'date': c['commit']['author']['date'],
                    'sha': c['sha'][:7]
                } for c in commits]
            return []
        except Exception as e:
            print(f"Error getting commits: {str(e)}")
            return []
    
    def get_workflow_runs(self, repo, count=3):
        """Get recent GitHub Actions runs"""
        try:
            url = f"https://api.github.com/repos/{self.org}/{repo}/actions/runs?per_page={count}"
            response = requests.get(
                url,
                headers=self.headers,
                timeout=10
            )
            if response.status_code == 200:
                runs = response.json().get('workflow_runs', [])
                return [{
                    'name': r['name'],
                    'status': r['status'],
                    'conclusion': r['conclusion'],
                    'created_at': r['created_at'],
                    'html_url': r['html_url']
                } for r in runs]
            return []
        except Exception as e:
            print(f"Error getting workflows: {str(e)}")
            return []
    
    def get_file_content(self, repo, path):
        """Read a file from repository"""
        try:
            url = f"https://api.github.com/repos/{self.org}/{repo}/contents/{path}"
            response = requests.get(
                url,
                headers=self.headers,
                timeout=10
            )
            if response.status_code == 200:
                data = response.json()
                content = base64.b64decode(
                    data['content']
                ).decode('utf-8')
                return content, data['sha']
            return None, None
        except Exception as e:
            print(f"Error reading file: {str(e)}")
            return None, None
    
    def get_repo_structure(self, repo):
        """Get all files in repository"""
        try:
            url = f"https://api.github.com/repos/{self.org}/{repo}/git/trees/main?recursive=1"
            response = requests.get(
                url,
                headers=self.headers,
                timeout=10
            )
            if response.status_code == 200:
                tree = response.json().get('tree', [])
                return [
                    item['path']
                    for item in tree
                    if item['type'] == 'blob'
                ]
            return []
        except Exception as e:
            print(f"Error getting structure: {str(e)}")
            return []
    
    # ==========================================
    # WRITE CAPABILITY - WITH APPROVAL
    # ==========================================
    
    def prepare_file_update(self, repo, path,
                             new_content, reason):
        """
        Prepare a file change for David's approval
        Shows preview before committing anything
        Returns change_id for tracking
        """
        change_id = f"change_{datetime.now().strftime('%Y%m%d%H%M%S')}"
        
        existing_content, file_sha = self.get_file_content(
            repo, path
        )
        
        preview = self.generate_diff_preview(
            existing_content,
            new_content,
            path
        )
        
        self.pending_changes[change_id] = {
            'repo': repo,
            'path': path,
            'new_content': new_content,
            'file_sha': file_sha,
            'reason': reason,
            'is_new_file': existing_content is None,
            'preview': preview,
            'created_at': datetime.now().isoformat(),
            'status': 'pending'
        }
        
        return change_id, preview
    
    def generate_diff_preview(self, old_content,
                               new_content, path):
        """Generate human readable preview of changes"""
        if old_content is None:
            lines = new_content.split('\n')[:10]
            preview = '\n'.join(lines)
            if len(new_content.split('\n')) > 10:
                preview += f"\n... and {len(new_content.split(chr(10))) - 10} more lines"
            return f"NEW FILE: {path}\n\nFirst 10 lines:\n{preview}"
        
        old_lines = old_content.split('\n')
        new_lines = new_content.split('\n')
        
        changes = []
        for i, (old, new) in enumerate(
            zip(old_lines, new_lines)
        ):
            if old != new:
                changes.append(
                    f"Line {i+1}:\n  Before: {old}\n  After:  {new}"
                )
        
        if len(new_lines) > len(old_lines):
            for i in range(len(old_lines), len(new_lines)):
                changes.append(
                    f"Line {i+1} added: {new_lines[i]}"
                )
        elif len(old_lines) > len(new_lines):
            for i in range(len(new_lines), len(old_lines)):
                changes.append(
                    f"Line {i+1} removed: {old_lines[i]}"
                )
        
        if not changes:
            return "No differences detected."
        
        preview = '\n\n'.join(changes[:5])
        if len(changes) > 5:
            preview += f"\n\n... and {len(changes) - 5} more changes"
        
        return preview
    
    def commit_change(self, change_id,
                       commit_message=None):
        """
        Commit an approved change to GitHub
        Only called after David says YES
        """
        change = self.pending_changes.get(change_id)
        if not change:
            return False, "Change not found"
        
        if change['status'] != 'pending':
            return False, f"Change already {change['status']}"
        
        try:
            url = f"https://api.github.com/repos/{self.org}/{change['repo']}/contents/{change['path']}"
            
            if not commit_message:
                commit_message = f"Trinity: {change['reason']}"
            
            content_encoded = base64.b64encode(
                change['new_content'].encode('utf-8')
            ).decode('utf-8')
            
            payload = {
                'message': commit_message,
                'content': content_encoded,
                'branch': 'main'
            }
            
            if change['file_sha']:
                payload['sha'] = change['file_sha']
            
            response = requests.put(
                url,
                headers=self.headers,
                json=payload,
                timeout=15
            )
            
            if response.status_code in [200, 201]:
                self.pending_changes[change_id]['status'] = \
                    'committed'
                return True, f"Successfully committed to {change['repo']}/{change['path']}"
            else:
                error = response.json().get('message', 'Unknown error')
                return False, f"Commit failed: {error}"
                
        except Exception as e:
            return False, f"Error: {str(e)}"
    
    def cancel_change(self, change_id):
        """Cancel a pending change"""
        if change_id in self.pending_changes:
            self.pending_changes[change_id]['status'] = \
                'cancelled'
            return True
        return False
    
    def create_new_file(self, repo, path,
                         content, reason):
        """Prepare a new file for approval"""
        return self.prepare_file_update(
            repo, path, content, reason
        )
    
    def get_pending_changes(self):
        """Get all pending changes waiting for approval"""
        return {
            k: v for k, v in self.pending_changes.items()
            if v['status'] == 'pending'
        }
    
    # ==========================================
    # ANALYSIS
    # ==========================================
    
    def check_all_repos(self):
        """Full check of all repositories"""
        results = {}
        
        for repo in self.repos:
            print(f"Checking {repo}...")
            
            info = self.get_repo_info(repo)
            commits = self.get_recent_commits(repo)
            workflows = self.get_workflow_runs(repo)
            structure = self.get_repo_structure(repo)
            
            failed_workflows = [
                w for w in workflows
                if w.get('conclusion') == 'failure'
            ]
            
            last_commit_date = None
            if commits:
                last_commit_date = commits[0]['date']
            
            results[repo] = {
                'status': 'healthy' if info else 'error',
                'last_updated': info.get('updated_at') if info else None,
                'total_files': len(structure),
                'recent_commits': commits,
                'recent_workflows': workflows,
                'failed_workflows': failed_workflows,
                'last_commit_date': last_commit_date,
                'open_issues': info.get('open_issues_count', 0) if info else 0
            }
        
        return results
    
    def get_daily_summary(self):
        """Get daily GitHub activity summary"""
        results = self.check_all_repos()
        
        summary = {
            'timestamp': datetime.now().isoformat(),
            'total_repos': len(self.repos),
            'healthy_repos': 0,
            'failed_workflows': [],
            'recent_activity': [],
            'alerts': []
        }
        
        for repo, data in results.items():
            if data['status'] == 'healthy':
                summary['healthy_repos'] += 1
            
            for wf in data.get('failed_workflows', []):
                summary['failed_workflows'].append({
                    'repo': repo,
                    'workflow': wf['name'],
                    'date': wf['created_at']
                })
                summary['alerts'].append(
                    f"Failed workflow in {repo}: {wf['name']}"
                )
            
            commits = data.get('recent_commits', [])
            if commits:
                summary['recent_activity'].append({
                    'repo': repo,
                    'last_commit': commits[0]['message'],
                    'date': commits[0]['date'],
                    'author': commits[0]['author']
                })
        
        return summary
    
    def get_progress_report(self):
        """Analyze repositories and report progress"""
        trinity6_files = self.get_repo_structure('Trinity6')
        assistant_files = self.get_repo_structure('assistant')
        trinity_ai_files = self.get_repo_structure('trinity-ai')
        
        trinity6_readme, _ = self.get_file_content(
            'Trinity6', 'README.md'
        )
        
        report = {
            'timestamp': datetime.now().isoformat(),
            'trinity6_scanner': {
                'total_files': len(trinity6_files),
                'has_compliance': any(
                    'compliance' in f for f in trinity6_files
                ),
                'has_scanner': any(
                    'scanner' in f for f in trinity6_files
                ),
                'has_dashboard': any(
                    'dashboard' in f for f in trinity6_files
                ),
                'has_pdf': any(
                    'pdf' in f for f in trinity6_files
                ),
                'readme': trinity6_readme[:500]
                    if trinity6_readme else None
            },
            'assistant': {
                'total_files': len(assistant_files),
                'has_daily_report': any(
                    'trinity6_assistant' in f
                    for f in assistant_files
                ),
                'has_telegram_bot': any(
                    'telegram_bot' in f
                    for f in assistant_files
                )
            },
            'trinity_ai': {
                'total_files': len(trinity_ai_files),
                'files_built': trinity_ai_files
            }
        }
        
        return report
