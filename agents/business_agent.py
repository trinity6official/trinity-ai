import requests
from datetime import datetime

class BusinessAgent:
    """
    Trinity Business Intelligence Agent
    Monitors Trinity6 business health
    Tracks clients, revenue, opportunities
    Researches market and competitors
    Helps David grow Trinity6
    """
    
    def __init__(self, memory=None, llm=None):
        self.memory = memory
        self.llm = llm
    
    # ==========================================
    # BUSINESS HEALTH
    # ==========================================
    
    def get_business_status(self):
        """Get current business health"""
        if not self.memory:
            return {}
        
        company = self.memory.brain.get('company', {})
        david = self.memory.brain.get('david', {})
        
        days_building = company.get('days_building', 0)
        revenue = company.get('revenue', 0)
        clients = company.get('clients', [])
        next_milestone = company.get('next_milestone', '')
        
        health_score = 100
        alerts = []
        
        if revenue == 0 and days_building > 30:
            health_score -= 20
            alerts.append(
                "No revenue after 30 days. Prioritise client outreach."
            )
        
        if len(clients) == 0:
            health_score -= 10
            alerts.append(
                "No clients yet. First client is the most important milestone."
            )
        
        return {
            'timestamp': datetime.now().isoformat(),
            'health_score': health_score,
            'days_building': days_building,
            'revenue': revenue,
            'total_clients': len(clients),
            'clients': clients,
            'next_milestone': next_milestone,
            'alerts': alerts,
            'financial_goals': david.get(
                'financial_goals', []
            )
        }
    
    def get_client_pipeline(self):
        """Get client pipeline status"""
        if not self.memory:
            return {}
        
        clients = self.memory.brain['company'].get(
            'clients', []
        )
        
        pipeline = {
            'prospect': [],
            'in_discussion': [],
            'active': [],
            'completed': []
        }

        for client in clients:
            status = client.get('status', 'prospect')
            if status in pipeline:
                pipeline[status].append(client)
        
        return pipeline
    
    def add_client(self, name, company,
                    status, notes=None):
        """Add new client to pipeline"""
        if not self.memory:
            return
        
        client = {
            'name': name,
            'company': company,
            'status': status,
            'notes': notes or '',
            'added_date': datetime.now().isoformat()
        }
        
        self.memory.brain['company']['clients'].append(
            client
        )
        self.memory.save()
        
        self.memory.add_daily_log(
            f"New client added to pipeline: {name} from {company}"
        )
        
        return client
    
    def update_revenue(self, amount, source):
        """Update company revenue"""
        if not self.memory:
            return
        
        current = self.memory.brain['company'].get(
            'revenue', 0
        )
        self.memory.brain['company']['revenue'] = \
            current + amount
        
        self.memory.add_daily_log(
            f"Revenue update: +{amount} from {source}. Total: {current + amount}"
        )
        
        self.memory.save()
    
    # ==========================================
    # MARKET INTELLIGENCE
    # ==========================================
    
    def get_cybersecurity_news(self):
        """Get latest cybersecurity news"""
        news_sources = [
            {
                'name': 'CISA Alerts',
                'url': 'https://www.cisa.gov/news-events/cybersecurity-advisories',
                'type': 'government'
            },
            {
                'name': 'NIST News',
                'url': 'https://www.nist.gov/news-events/news',
                'type': 'standards'
            }
        ]
        
        news = []
        for source in news_sources:
            try:
                response = requests.get(
                    source['url'],
                    timeout=10
                )
                if response.status_code == 200:
                    news.append({
                        'source': source['name'],
                        'url': source['url'],
                        'status': 'accessible',
                        'type': source['type']
                    })
            except Exception as e:
                news.append({
                    'source': source['name'],
                    'status': 'error',
                    'error': str(e)
                })
        
        return news
    
    def analyze_market_opportunity(self):
        """Analyze Trinity6 market opportunity"""
        analysis = {
            'timestamp': datetime.now().isoformat(),
            'target_market': 'Small and Medium Businesses',
            'problem': 'Manual GRC compliance is expensive and complex',
            'solution': 'Trinity6 automated AI powered compliance scanning',
            'competitors': {
                'Nessus': {
                    'price': '$3000+ per year',
                    'weakness': 'Too expensive for SMBs'
                },
                'Qualys': {
                    'price': '$10000+ per year',
                    'weakness': 'Enterprise focused'
                },
                'OpenSCAP': {
                    'price': 'Free',
                    'weakness': 'Too complex, no AI, ugly reports'
                }
            },
            'trinity6_advantage': [
                'AI powered analysis in plain English',
                'Affordable SMB pricing',
                'Local AI for data privacy',
                'Beautiful professional reports',
                'Multi framework single scan',
                'Network discovery built in'
            ],
            'pricing': {
                'standard': '$199 per month',
                'enterprise': '$999 per month',
                'audit': '$500 per audit'
            },
            'target_clients': [
                'Small businesses needing compliance',
                'Startups preparing for SOC 2',
                'Companies needing CIS benchmark audits',
                'IT managers needing automated scanning'
            ]
        }
        
        return analysis
    
    # ==========================================
    # RECOMMENDATIONS
    # ==========================================
    
    def get_weekly_priorities(self):
        """Get recommended priorities for the week"""
        priorities = []
        
        if not self.memory:
            return priorities
        
        company = self.memory.brain.get('company', {})
        revenue = company.get('revenue', 0)
        clients = company.get('clients', [])
        days = company.get('days_building', 0)
        phase = company.get('current_phase', '')
        
        if revenue == 0:
            priorities.append({
                'priority': 1,
                'action': 'Get first paying client',
                'why': 'Revenue validates your product and funds growth',
                'how': 'Offer free audit to 2-3 SMBs. Turn results into case study.'
            })
        
        if 'Phase 2' in phase:
            priorities.append({
                'priority': 2,
                'action': 'Start Phase 3 Windows support',
                'why': 'Most enterprise clients run Windows servers',
                'how': 'Build Windows CIS benchmark YAML files first'
            })
        
        if days > 14 and len(clients) == 0:
            priorities.append({
                'priority': 3,
                'action': 'LinkedIn outreach to potential clients',
                'why': 'Your product is ready. Time to find customers.',
                'how': 'Search LinkedIn for IT managers and compliance officers at SMBs'
            })
        
        priorities.append({
            'priority': len(priorities) + 1,
            'action': 'Post daily content on LinkedIn',
            'why': 'Builds Trinity6 brand and attracts clients',
            'how': 'Use daily AI generated posts from assistant repository'
        })
        
        return priorities
    
    def generate_first_client_strategy(self):
        """Strategy for getting first client"""
        return {
            'strategy': 'Free Audit Approach',
            'steps': [
                {
                    'step': 1,
                    'action': 'Identify 5 local SMBs',
                    'detail': 'Look for businesses that handle sensitive data like healthcare, finance, legal'
                },
                {
                    'step': 2,
                    'action': 'Offer free CIS benchmark audit',
                    'detail': 'No cost to them. You get case study and testimonial.'
                },
                {
                    'step': 3,
                    'action': 'Run Trinity6 scanner on their network',
                    'detail': 'Deliver professional PDF report with findings'
                },
                {
                    'step': 4,
                    'action': 'Present findings to decision maker',
                    'detail': 'Show executive summary. Highlight risks. Propose monthly monitoring.'
                },
                {
                    'step': 5,
                    'action': 'Convert to paying client',
                    'detail': 'Offer Standard Plan at $199/month for ongoing monitoring'
                }
            ],
            'expected_timeline': '4-6 weeks to first paying client',
            'success_metric': 'One paying client at $199/month'
        }
    
    def get_daily_business_brief(self):
        """Get complete daily business briefing"""
        status = self.get_business_status()
        pipeline = self.get_client_pipeline()
        priorities = self.get_weekly_priorities()
        
        return {
            'timestamp': datetime.now().isoformat(),
            'business_status': status,
            'client_pipeline': pipeline,
            'weekly_priorities': priorities,
            'market_opportunity': self.analyze_market_opportunity()
        }
