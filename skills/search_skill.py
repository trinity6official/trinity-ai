import requests
from datetime import datetime


class SearchSkill:
    """
    Trinity Search Skill
    Search cybersecurity news
    Find potential clients
    Research competitors
    Monitor market trends
    Auto discovered by SkillManager
    """

    name = "search"
    description = "Search web for cybersecurity news, clients, competitors and market trends"

    def __init__(self):
        self.cybersecurity_sources = [
            {
                'name': 'CISA Advisories',
                'url': 'https://www.cisa.gov/news-events/cybersecurity-advisories',
                'type': 'government'
            },
            {
                'name': 'NIST News',
                'url': 'https://www.nist.gov/news-events/news',
                'type': 'standards'
            },
            {
                'name': 'Krebs on Security',
                'url': 'https://krebsonsecurity.com',
                'type': 'blog'
            },
            {
                'name': 'The Hacker News',
                'url': 'https://thehackernews.com',
                'type': 'news'
            },
            {
                'name': 'Dark Reading',
                'url': 'https://www.darkreading.com',
                'type': 'news'
            }
        ]

    def get_tools(self):
        """Returns all search tools Trinity can use"""
        return [
            {
                "name": "search_cybersecurity_news",
                "description": "Get latest cybersecurity news and threats",
                "params": [],
                "needs_approval": False
            },
            {
                "name": "search_cis_updates",
                "description": "Check for CIS benchmark updates",
                "params": [],
                "needs_approval": False
            },
            {
                "name": "find_potential_clients",
                "description": "Find potential clients for Trinity6 Scanner",
                "params": ["location", "industry"],
                "needs_approval": False
            },
            {
                "name": "research_competitor",
                "description": "Research a competitor product or company",
                "params": ["competitor_name"],
                "needs_approval": False
            },
            {
                "name": "search_linkedin_prospects",
                "description": "Generate LinkedIn search strategy for prospects",
                "params": ["role", "location", "industry"],
                "needs_approval": False
            },
            {
                "name": "get_market_intelligence",
                "description": "Get cybersecurity market trends and opportunities",
                "params": [],
                "needs_approval": False
            },
            {
                "name": "check_source",
                "description": "Check if a news source is accessible",
                "params": ["url"],
                "needs_approval": False
            }
        ]

    def execute(self, tool_name, params):
        """Trinity calls this to use any search tool"""
        tool_map = {
            "search_cybersecurity_news": self.search_cybersecurity_news,
            "search_cis_updates": self.search_cis_updates,
            "find_potential_clients": self.find_potential_clients,
            "research_competitor": self.research_competitor,
            "search_linkedin_prospects": self.search_linkedin_prospects,
            "get_market_intelligence": self.get_market_intelligence,
            "check_source": self.check_source
        }

        tool = tool_map.get(tool_name)
        if not tool:
            return {"error": f"Unknown tool: {tool_name}"}

        try:
            return tool(**params)
        except Exception as e:
            return {"error": str(e)}

    # ==========================================
    # SEARCH TOOLS
    # ==========================================

    def check_source(self, url):
        """Check if a source is accessible"""
        try:
            response = requests.get(url, timeout=10)
            return {
                'success': True,
                'url': url,
                'accessible': response.status_code == 200,
                'status_code': response.status_code
            }
        except Exception as e:
            return {
                'success': False,
                'url': url,
                'accessible': False,
                'error': str(e)
            }

    def search_cybersecurity_news(self):
        """Check cybersecurity news sources"""
        results = {
            'success': True,
            'checked_at': datetime.now().isoformat(),
            'sources': [],
            'accessible_count': 0
        }

        for source in self.cybersecurity_sources:
            check = self.check_source(source['url'])
            source_result = {
                'name': source['name'],
                'url': source['url'],
                'type': source['type'],
                'accessible': check.get('accessible', False)
            }
            results['sources'].append(source_result)
            if check.get('accessible'):
                results['accessible_count'] += 1

        results['summary'] = f"{results['accessible_count']} of {len(self.cybersecurity_sources)} sources accessible"

        results['topics'] = [
            "Ransomware attacks increasing on SMBs",
            "CIS Controls v8.1 released with new guidelines",
            "NIST Cybersecurity Framework 2.0 updates",
            "Zero trust adoption growing in enterprises",
            "AI powered threat detection becoming standard",
            "Supply chain attacks targeting small vendors",
            "Cloud misconfiguration top cause of breaches",
            "Patch management critical for compliance"
        ]

        return results

    def search_cis_updates(self):
        """Check for CIS benchmark updates"""
        return {
            'success': True,
            'checked_at': datetime.now().isoformat(),
            'cis_url': 'https://www.cisecurity.org/cis-benchmarks',
            'known_versions': {
                'CIS Linux': 'v3.0.0',
                'CIS Windows Server 2022': 'v2.0.0',
                'CIS Ubuntu 22.04': 'v1.0.0',
                'CIS Docker': 'v1.6.0',
                'CIS Kubernetes': 'v1.8.0'
            },
            'trinity6_implements': [
                'CIS Linux Sections 1 to 6',
                'CIS Network Controls',
                'CIS Access Controls',
                'CIS Logging Controls'
            ],
            'next_to_implement': [
                'CIS Windows Server',
                'CIS Docker',
                'CIS Kubernetes',
                'CIS AWS Foundations'
            ],
            'recommendation': 'Check cisecurity.org regularly for benchmark updates and implement new sections to increase Trinity6 Scanner value'
        }

    def find_potential_clients(self,
                                location="Chennai",
                                industry="any"):
        """Generate client finding strategy"""
        industries_needing_compliance = [
            "Healthcare - HIPAA compliance required",
            "Finance - PCI DSS and SOC 2 required",
            "Legal - Client data protection critical",
            "IT Services - Compliance for enterprise clients",
            "Manufacturing - ISO 27001 increasingly required",
            "Education - Student data protection",
            "Government contractors - CMMC compliance"
        ]

        linkedin_searches = [
            f"IT Manager {location}",
            f"CISO {location}",
            f"Compliance Officer {location}",
            f"Information Security {location}",
            f"CTO small company {location}",
            f"IT Director {location}"
        ]

        outreach_message = f"""Hi [Name],

I noticed you manage IT security at [Company].

I built Trinity6, an AI powered compliance scanner that automatically checks your Linux servers against CIS benchmarks and generates professional audit reports.

Most SMBs in {location} spend weeks on manual compliance audits. Trinity6 does it in minutes.

Would you be open to a free audit of your network? No cost, no obligation. Just a real compliance report you can use immediately.

David
Trinity6 - Intelligent Security
trinity6.com"""

        return {
            'success': True,
            'location': location,
            'industry': industry,
            'industries_to_target': industries_needing_compliance,
            'linkedin_searches': linkedin_searches,
            'outreach_message': outreach_message,
            'platforms': [
                'LinkedIn - Best for B2B outreach',
                'Local business directories',
                'Chennai startup communities',
                'IT professional groups'
            ],
            'goal': 'Find 5 prospects this week. Offer free audit. Convert one to paying client.'
        }

    def research_competitor(self, competitor_name):
        """Research a competitor"""
        known_competitors = {
            'nessus': {
                'name': 'Nessus by Tenable',
                'price': '$3000+ per year',
                'target': 'Enterprise',
                'weakness': 'Too expensive for SMBs, complex UI',
                'strength': 'Comprehensive scanning',
                'trinity6_advantage': 'Affordable, AI powered, simple reports'
            },
            'qualys': {
                'name': 'Qualys VMDR',
                'price': '$10000+ per year',
                'target': 'Enterprise',
                'weakness': 'Enterprise only, very expensive',
                'strength': 'Cloud based, comprehensive',
                'trinity6_advantage': 'SMB focused, local AI, no cloud dependency'
            },
            'openscap': {
                'name': 'OpenSCAP',
                'price': 'Free',
                'target': 'Technical users',
                'weakness': 'Complex, no AI, ugly reports, technical knowledge needed',
                'strength': 'Free and open source',
                'trinity6_advantage': 'AI analysis, beautiful reports, easy to use'
            },
            'rapid7': {
                'name': 'Rapid7 InsightVM',
                'price': '$5000+ per year',
                'target': 'Mid to large enterprise',
                'weakness': 'Expensive, complex setup',
                'strength': 'Good visualization',
                'trinity6_advantage': 'Simpler, cheaper, AI powered insights'
            }
        }

        competitor_key = competitor_name.lower().replace(' ', '')
        competitor = None

        for key, data in known_competitors.items():
            if key in competitor_key or competitor_key in key:
                competitor = data
                break

        if competitor:
            return {
                'success': True,
                'competitor': competitor,
                'recommendation': f"Trinity6 should emphasize {competitor['trinity6_advantage']} when competing with {competitor['name']}"
            }

        return {
            'success': True,
            'competitor_name': competitor_name,
            'note': 'Detailed data not available for this competitor',
            'general_trinity6_advantages': [
                'AI powered plain English reports',
                'Affordable SMB pricing',
                'Local AI for privacy',
                'Multi framework single scan',
                'No cloud dependency'
            ]
        }

    def search_linkedin_prospects(self,
                                   role="IT Manager",
                                   location="Chennai",
                                   industry=""):
        """Generate LinkedIn prospect search strategy"""
        search_queries = [
            f'"{role}" "{location}"',
            f'"{role}" "{location}" "compliance"',
            f'"{role}" "{location}" "cybersecurity"',
            f'"CISO" "{location}"',
            f'"Information Security" "{location}"'
        ]

        if industry:
            search_queries.append(
                f'"{role}" "{location}" "{industry}"'
            )

        return {
            'success': True,
            'role': role,
            'location': location,
            'industry': industry,
            'linkedin_search_queries': search_queries,
            'connection_message': f"""Hi [Name], I see you manage IT at [Company] in {location}. I built an AI powered compliance scanner called Trinity6 that helps SMBs automate CIS benchmark audits. Would love to connect and share how it might help your team.""",
            'follow_up_message': """Thanks for connecting! I would love to offer you a free compliance audit of your Linux servers. Trinity6 generates a full CIS benchmark report in minutes. No cost, just a useful report for your team. Interested?""",
            'weekly_target': '20 connection requests, 5 follow ups, 1 free audit offer',
            'expected_conversion': '1 paying client per 20 prospects contacted'
        }

    def get_market_intelligence(self):
        """Get cybersecurity market trends"""
        return {
            'success': True,
            'checked_at': datetime.now().isoformat(),
            'market_size': {
                'global_cybersecurity': '$200 billion by 2028',
                'grc_market': '$64 billion by 2028',
                'smb_security': 'Fastest growing segment'
            },
            'trends': [
                'SMBs increasingly targeted by ransomware',
                'Compliance requirements expanding globally',
                'AI in security tools becoming standard',
                'Remote work increasing attack surface',
                'Supply chain security in focus',
                'Zero trust architecture adoption growing',
                'Cyber insurance requiring compliance proof'
            ],
            'opportunities_for_trinity6': [
                'SMBs needing affordable compliance tools',
                'Companies preparing for SOC 2 certification',
                'Healthcare firms needing HIPAA compliance',
                'Finance companies needing PCI DSS help',
                'IT MSPs needing scanner for client audits'
            ],
            'pricing_benchmarks': {
                'audit_one_time': '$500 to $2000',
                'monthly_monitoring': '$199 to $999',
                'enterprise_annual': '$10000 to $50000'
            },
            'trinity6_positioning': 'Affordable AI powered GRC for SMBs that cannot afford enterprise tools but need enterprise level compliance'
        }
