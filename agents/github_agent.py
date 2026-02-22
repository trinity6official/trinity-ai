import os
import requests
import base64
from datetime import datetime

class GitHubAgent:
    """
    Trinity GitHub Agent
    Monitors all Trinity6 repositories
    Reads everything live from GitHub API
    Never stores repo data in memory
    """
    
    def __init__(self, gh_token=None):
        self.gh_token = gh_token
        self.headers = {}
        if gh_token:
            self.headers = {
                "Authorization": f"token {gh_token}"
            }
        self.org = "trinity6official"
        self.repos = [
            "Trinity6",
            "assistant",
            "trinity-ai"
        ]
    
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
                runs = response.json().get(
                    'workflow_runs', []
                )
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
                content = response.json().get('content', '')
                return base64.b64decode(content).decode('utf-8')
            return None
        except Exception as e:
            print(f"Error reading file: {str(e)}")
            return None
    
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
        """
        Analyze repositories and report
        Trinity6 project progress
        """
        trinity6_files = self.get_repo_structure('Trinity6')
        assistant_files = self.get_repo_structure('assistant')
        trinity_ai_files = self.get_repo_structure('trinity-ai')
        
        trinity6_readme = self.get_file_content(
            'Trinity6', 'README.md'
        )
        
        report = {
            'timestamp': datetime.now().isoformat(),
            'trinity6_scanner': {
                'total_files': len(trinity6_files),
                'has_compliance': any(
                    'compliance' in f
                    for f in trinity6_files
                ),
                'has_scanner': any(
                    'scanner' in f
                    for f in trinity6_files
                ),
                'has_dashboard': any(
                    'dashboard' in f
                    for f in trinity6_files
                ),
                'has_pdf': any(
                    'pdf' in f
                    for f in trinity6_files
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
