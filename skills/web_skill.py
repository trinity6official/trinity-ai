import requests
import socket
import ssl
from datetime import datetime


class WebSkill:
    """
    Trinity Web Skill
    Monitor websites, check SSL certificates,
    read webpage content, check response times
    Auto discovered by SkillManager
    """

    name = "web"
    description = "Monitor websites, check uptime, SSL certificates and response times"

    def __init__(self):
        self.monitored_sites = [
            "https://trinity6.com"
        ]

    def get_tools(self):
        """Returns all web tools Trinity can use"""
        return [
            {
                "name": "check_website",
                "description": "Check if website is up and response time",
                "params": ["url"],
                "needs_approval": False
            },
            {
                "name": "check_ssl",
                "description": "Check SSL certificate validity and expiry",
                "params": ["domain"],
                "needs_approval": False
            },
            {
                "name": "check_domain_expiry",
                "description": "Check when domain expires",
                "params": ["domain"],
                "needs_approval": False
            },
            {
                "name": "read_webpage",
                "description": "Read and extract text content from webpage",
                "params": ["url"],
                "needs_approval": False
            },
            {
                "name": "check_all_trinity6",
                "description": "Full health check of all Trinity6 web properties",
                "params": [],
                "needs_approval": False
            },
            {
                "name": "check_response_headers",
                "description": "Check security headers of a website",
                "params": ["url"],
                "needs_approval": False
            }
        ]

    def execute(self, tool_name, params):
        """Trinity calls this to use any web tool"""
        tool_map = {
            "check_website": self.check_website,
            "check_ssl": self.check_ssl,
            "check_domain_expiry": self.check_domain_expiry,
            "read_webpage": self.read_webpage,
            "check_all_trinity6": self.check_all_trinity6,
            "check_response_headers": self.check_response_headers
        }

        tool = tool_map.get(tool_name)
        if not tool:
            return {"error": f"Unknown tool: {tool_name}"}

        try:
            return tool(**params)
        except Exception as e:
            return {"error": str(e)}

    # ==========================================
    # WEB TOOLS
    # ==========================================

    def check_website(self, url="https://trinity6.com"):
        """Check if website is up and measure response time"""
        try:
            start = datetime.now()
            response = requests.get(url, timeout=10)
            end = datetime.now()

            response_time = (end - start).total_seconds()

            status = "online"
            if response.status_code != 200:
                status = f"error_{response.status_code}"

            return {
                'success': True,
                'url': url,
                'status': status,
                'status_code': response.status_code,
                'response_time_seconds': round(response_time, 2),
                'is_live': response.status_code == 200,
                'checked_at': datetime.now().isoformat()
            }

        except requests.exceptions.ConnectionError:
            return {
                'success': False,
                'url': url,
                'status': 'offline',
                'is_live': False,
                'error': 'Connection refused',
                'checked_at': datetime.now().isoformat()
            }
        except requests.exceptions.Timeout:
            return {
                'success': False,
                'url': url,
                'status': 'timeout',
                'is_live': False,
                'error': 'Request timed out',
                'checked_at': datetime.now().isoformat()
            }
        except Exception as e:
            return {
                'success': False,
                'url': url,
                'status': 'error',
                'is_live': False,
                'error': str(e),
                'checked_at': datetime.now().isoformat()
            }

    def check_ssl(self, domain="trinity6.com"):
        """Check SSL certificate validity and expiry"""
        try:
            context = ssl.create_default_context()
            conn = context.wrap_socket(
                socket.socket(socket.AF_INET),
                server_hostname=domain
            )
            conn.settimeout(5)
            conn.connect((domain, 443))
            cert = conn.getpeercert()
            conn.close()

            expire_date = datetime.strptime(
                cert['notAfter'],
                '%b %d %H:%M:%S %Y %Z'
            )

            days_until_expiry = (
                expire_date - datetime.now()
            ).days

            status = 'valid'
            if days_until_expiry < 7:
                status = 'critical'
            elif days_until_expiry < 30:
                status = 'warning'

            return {
                'success': True,
                'domain': domain,
                'valid': True,
                'status': status,
                'expires': str(expire_date),
                'days_until_expiry': days_until_expiry,
                'needs_renewal': days_until_expiry < 30,
                'issuer': dict(x[0] for x in cert.get('issuer', []))
            }

        except ssl.SSLError as e:
            return {
                'success': False,
                'domain': domain,
                'valid': False,
                'status': 'invalid',
                'error': f"SSL Error: {str(e)}"
            }
        except Exception as e:
            return {
                'success': False,
                'domain': domain,
                'valid': False,
                'error': str(e)
            }

    def check_domain_expiry(self, domain="trinity6.com"):
        """Check when domain registration expires"""
        try:
            import whois
            w = whois.whois(domain)
            expiry = w.expiration_date

            if isinstance(expiry, list):
                expiry = expiry[0]

            days_until_expiry = (
                expiry - datetime.now()
            ).days if expiry else None

            return {
                'success': True,
                'domain': domain,
                'expiry_date': str(expiry),
                'days_until_expiry': days_until_expiry,
                'needs_renewal': days_until_expiry < 30
                    if days_until_expiry else False,
                'registrar': w.registrar
            }

        except Exception as e:
            return {
                'success': False,
                'domain': domain,
                'error': str(e)
            }

    def read_webpage(self, url):
        """Read and extract text content from webpage"""
        try:
            headers = {
                'User-Agent': 'Mozilla/5.0 Trinity6 Monitor'
            }
            response = requests.get(
                url, headers=headers, timeout=10
            )

            if response.status_code != 200:
                return {
                    'success': False,
                    'url': url,
                    'error': f"Status {response.status_code}"
                }

            content = response.text

            try:
                from bs4 import BeautifulSoup
                soup = BeautifulSoup(content, 'html.parser')

                for script in soup(["script", "style"]):
                    script.decompose()

                text = soup.get_text()
                lines = (
                    line.strip() for line in text.splitlines()
                )
                chunks = (
                    phrase.strip()
                    for line in lines
                    for phrase in line.split("  ")
                )
                text = '\n'.join(
                    chunk for chunk in chunks if chunk
                )

                return {
                    'success': True,
                    'url': url,
                    'title': soup.title.string
                        if soup.title else '',
                    'text': text[:3000],
                    'full_length': len(text)
                }

            except ImportError:
                return {
                    'success': True,
                    'url': url,
                    'text': content[:3000],
                    'note': 'BeautifulSoup not installed. Raw HTML returned.'
                }

        except Exception as e:
            return {
                'success': False,
                'url': url,
                'error': str(e)
            }

    def check_response_headers(self, url):
        """Check security headers of website"""
        try:
            response = requests.get(url, timeout=10)
            headers = dict(response.headers)

            security_headers = {
                'Strict-Transport-Security': headers.get(
                    'Strict-Transport-Security', 'Missing'
                ),
                'X-Frame-Options': headers.get(
                    'X-Frame-Options', 'Missing'
                ),
                'X-Content-Type-Options': headers.get(
                    'X-Content-Type-Options', 'Missing'
                ),
                'Content-Security-Policy': headers.get(
                    'Content-Security-Policy', 'Missing'
                ),
                'X-XSS-Protection': headers.get(
                    'X-XSS-Protection', 'Missing'
                )
            }

            missing = [
                k for k, v in security_headers.items()
                if v == 'Missing'
            ]

            score = (
                (len(security_headers) - len(missing)) /
                len(security_headers) * 100
            )

            return {
                'success': True,
                'url': url,
                'security_headers': security_headers,
                'missing_headers': missing,
                'security_score': round(score),
                'recommendations': [
                    f"Add {h} header" for h in missing
                ]
            }

        except Exception as e:
            return {
                'success': False,
                'url': url,
                'error': str(e)
            }

    def check_all_trinity6(self):
        """Full health check of all Trinity6 properties"""
        results = {
            'checked_at': datetime.now().isoformat(),
            'overall': 'healthy',
            'properties': {}
        }

        website = self.check_website("https://trinity6.com")
        results['properties']['website'] = website

        ssl_check = self.check_ssl("trinity6.com")
        results['properties']['ssl'] = ssl_check

        headers = self.check_response_headers(
            "https://trinity6.com"
        )
        results['properties']['security_headers'] = headers

        alerts = []

        if not website.get('is_live'):
            alerts.append("Website trinity6.com is DOWN")
            results['overall'] = 'critical'

        elif website.get('response_time_seconds', 0) > 3:
            alerts.append(
                f"Website slow: {website['response_time_seconds']}s response time"
            )
            results['overall'] = 'warning'

        if not ssl_check.get('valid'):
            alerts.append("SSL certificate is invalid")
            results['overall'] = 'critical'

        elif ssl_check.get('days_until_expiry', 999) < 30:
            alerts.append(
                f"SSL expires in {ssl_check['days_until_expiry']} days"
            )
            if results['overall'] != 'critical':
                results['overall'] = 'warning'

        results['alerts'] = alerts
        return results
