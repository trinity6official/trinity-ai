import requests
import base64
from datetime import datetime

class TrinityMonitor:
    """
    Trinity Monitoring System
    Checks everything about Trinity6 every day
    Reads directly from GitHub and web
    No stored repo data - always live and accurate
    """
    
    def __init__(self, gh_token=None):
        self.gh_token = gh_token
        self.github_headers = {}
        if gh_token:
            self.github_headers = {
                "Authorization": f"token {gh_token}"
            }
        self.results = {}
    
    # ==========================================
    # GITHUB MONITORING
    # ==========================================
    
    def check_github_repo(self, repo):
        """Check health of a GitHub repository"""
        try:
            url = f"https://api.github.com/repos/trinity6official/{repo}"
            response = requests.get(
                url,
                headers=self.github_headers,
                timeout=10
            )
            
            if response.status_code == 200:
                data = response.json()
                
                commits_url = f"https://api.github.com/repos/trinity6official/{repo}/commits?per_page=5"
                commits_response = requests.get(
                    commits_url,
                    headers=self.github_headers,
                    timeout=10
                )
                
                recent_commits = []
                if commits_response.status_code == 200:
                    commits = commits_response.json()
                    for commit in commits:
                        recent_commits.append({
                            'message': commit['commit']['message'],
                            'date': commit['commit']['author']['date'],
                            'author': commit['commit']['author']['name']
                        })
                
                workflows_url = f"https://api.github.com/repos/trinity6official/{repo}/actions/runs?per_page=3"
                workflows_response = requests.get(
                    workflows_url,
                    headers=self.github_headers,
                    timeout=10
                )
                
                recent_workflows = []
                if workflows_response.status_code == 200:
                    runs = workflows_response.json().get('workflow_runs', [])
                    for run in runs:
                        recent_workflows.append({
                            'name': run['name'],
                            'status': run['status'],
                            'conclusion': run['conclusion'],
                            'created_at': run['created_at']
                        })
                
                return {
                    'repo': repo,
                    'status': 'healthy',
                    'last_updated': data.get('updated_at'),
                    'default_branch': data.get('default_branch'),
                    'recent_commits': recent_commits,
                    'recent_workflows': recent_workflows,
                    'open_issues': data.get('open_issues_count', 0)
                }
            else:
                return {
                    'repo': repo,
                    'status': 'error',
                    'error': f"Status {response.status_code}"
                }
                
        except Exception as e:
            return {
                'repo': repo,
                'status': 'error',
                'error': str(e)
            }
    
    def check_all_repos(self):
        """Check all Trinity6 repositories"""
        repos = ['Trinity6', 'assistant', 'trinity-ai']
        results = {}
        
        for repo in repos:
            print(f"Checking {repo}...")
            results[repo] = self.check_github_repo(repo)
        
        self.results['github'] = results
        return results
    
    def get_failed_workflows(self):
        """Get any failed GitHub Actions"""
        failed = []
        github_results = self.results.get('github', {})
        
        for repo, data in github_results.items():
            workflows = data.get('recent_workflows', [])
            for wf in workflows:
                if wf.get('conclusion') == 'failure':
                    failed.append({
                        'repo': repo,
                        'workflow': wf['name'],
                        'date': wf['created_at']
                    })
        
        return failed
    
    # ==========================================
    # WEBSITE MONITORING
    # ==========================================
    
    def check_website(self, url="https://trinity6.com"):
        """Check if website is live and responding"""
        try:
            start = datetime.now()
            response = requests.get(url, timeout=10)
            end = datetime.now()
            
            response_time = (end - start).total_seconds()
            
            result = {
                'url': url,
                'status_code': response.status_code,
                'response_time_seconds': round(response_time, 2),
                'is_live': response.status_code == 200,
                'checked_at': datetime.now().isoformat()
            }
            
            self.results['website'] = result
            return result
            
        except Exception as e:
            result = {
                'url': url,
                'is_live': False,
                'error': str(e),
                'checked_at': datetime.now().isoformat()
            }
            self.results['website'] = result
            return result
    
    # ==========================================
    # SECURITY MONITORING
    # ==========================================
    
    def check_domain_expiry(self, domain="trinity6.com"):
        """Check domain expiry status"""
        try:
            import whois
            w = whois.whois(domain)
            expiry = w.expiration_date
            
            if isinstance(expiry, list):
                expiry = expiry[0]
            
            days_until_expiry = (
                expiry - datetime.now()
            ).days if expiry else None
            
            result = {
                'domain': domain,
                'expiry_date': str(expiry),
                'days_until_expiry': days_until_expiry,
                'needs_renewal': days_until_expiry < 30
                    if days_until_expiry else False
            }
            
            self.results['domain'] = result
            return result
            
        except Exception as e:
            return {
                'domain': domain,
                'error': str(e)
            }
    
    # ==========================================
    # FULL HEALTH CHECK
    # ==========================================
    
    def run_full_check(self):
        """Run complete Trinity6 health check"""
        print("\nTrinity running full health check...")
        print("=" * 50)
        
        print("Checking GitHub repositories...")
        self.check_all_repos()
        
        print("Checking website...")
        self.check_website()
        
        self.results['checked_at'] = \
            datetime.now().isoformat()
        
        print("Health check complete!")
        print("=" * 50)
        
        return self.results
    
    def get_health_summary(self):
        """Get simple health summary"""
        summary = {
            'timestamp': datetime.now().isoformat(),
            'overall': 'healthy',
            'alerts': [],
            'github': {},
            'website': {}
        }
        
        github_results = self.results.get('github', {})
        for repo, data in github_results.items():
            status = data.get('status', 'unknown')
            commits = data.get('recent_commits', [])
            last_commit = commits[0]['date'] \
                if commits else 'No commits'
            summary['github'][repo] = {
                'status': status,
                'last_commit': last_commit
            }
            if status == 'error':
                summary['alerts'].append(
                    f"GitHub repo {repo} has an error"
                )
        
        website = self.results.get('website', {})
        if website:
            summary['website'] = {
                'is_live': website.get('is_live', False),
                'response_time': website.get(
                    'response_time_seconds', 0)
            }
            if not website.get('is_live'):
                summary['alerts'].append(
                    "Website trinity6.com is down!"
                )
                summary['overall'] = 'critical'
        
        failed_workflows = self.get_failed_workflows()
        if failed_workflows:
            for wf in failed_workflows:
                summary['alerts'].append(
                    f"Failed workflow: {wf['workflow']} in {wf['repo']}"
                )
        
        if summary['alerts'] and \
           summary['overall'] != 'critical':
            summary['overall'] = 'warning'
        
        return summary
