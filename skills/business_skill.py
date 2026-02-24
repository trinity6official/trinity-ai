from datetime import datetime


class BusinessSkill:
    """
    Trinity Business Skill
    Track revenue and clients
    Generate business insights
    Monitor Trinity6 growth
    Plan sales strategy
    Auto discovered by SkillManager
    """

    name = "business"
    description = "Track revenue, clients, business health and growth strategy for Trinity6"

    def __init__(self, memory_skill=None):
        self.memory_skill = memory_skill

    def get_tools(self):
        """Returns all business tools Trinity can use"""
        return [
            {
                "name": "get_business_status",
                "description": "Get full business health status",
                "params": [],
                "needs_approval": False
            },
            {
                "name": "get_client_pipeline",
                "description": "Get all clients and prospects in pipeline",
                "params": [],
                "needs_approval": False
            },
            {
                "name": "add_prospect",
                "description": "Add new prospect to pipeline",
                "params": ["name", "company", "contact", "notes"],
                "needs_approval": False
            },
            {
                "name": "update_prospect_status",
                "description": "Update status of a prospect",
                "params": ["company", "new_status", "notes"],
                "needs_approval": False
            },
            {
                "name": "record_revenue",
                "description": "Record new revenue received",
                "params": ["amount", "client", "description"],
                "needs_approval": False
            },
            {
                "name": "get_weekly_priorities",
                "description": "Get this weeks business priorities",
                "params": [],
                "needs_approval": False
            },
            {
                "name": "generate_invoice_details",
                "description": "Generate invoice details for a client",
                "params": ["client_name", "service", "amount"],
                "needs_approval": False
            },
            {
                "name": "get_growth_metrics",
                "description": "Get Trinity6 growth metrics and trends",
                "params": [],
                "needs_approval": False
            },
            {
                "name": "plan_outreach",
                "description": "Generate outreach plan for this week",
                "params": ["target_count"],
                "needs_approval": False
            },
            {
                "name": "calculate_mrr",
                "description": "Calculate monthly recurring revenue",
                "params": [],
                "needs_approval": False
            }
        ]

    def execute(self, tool_name, params):
        """Trinity calls this to use any business tool"""
        tool_map = {
            "get_business_status": self.get_business_status,
            "get_client_pipeline": self.get_client_pipeline,
            "add_prospect": self.add_prospect,
            "update_prospect_status": self.update_prospect_status,
            "record_revenue": self.record_revenue,
            "get_weekly_priorities": self.get_weekly_priorities,
            "generate_invoice_details": self.generate_invoice_details,
            "get_growth_metrics": self.get_growth_metrics,
            "plan_outreach": self.plan_outreach,
            "calculate_mrr": self.calculate_mrr
        }

        tool = tool_map.get(tool_name)
        if not tool:
            return {"error": f"Unknown tool: {tool_name}"}

        try:
            return tool(**params)
        except Exception as e:
            return {"error": str(e)}

    # ==========================================
    # HELPER
    # ==========================================

    def get_brain(self):
        """Get brain data via memory skill"""
        if self.memory_skill:
            result = self.memory_skill.read_brain()
            if result.get('success'):
                return result['brain']
        return {}

    def save_to_brain(self, key, value):
        """Save data via memory skill"""
        if self.memory_skill:
            return self.memory_skill.update_company(key, value)
        return False

    # ==========================================
    # BUSINESS TOOLS
    # ==========================================

    def get_business_status(self):
        """Get full business health status"""
        brain = self.get_brain()
        company = brain.get('company', {})

        revenue = company.get('revenue', 0)
        clients = company.get('clients', [])
        days_building = company.get('days_building', 0)
        current_phase = company.get('current_phase', 'Building')

        active_clients = [
            c for c in clients
            if c.get('status') == 'active'
        ]
        prospects = [
            c for c in clients
            if c.get('status') == 'prospect'
        ]
        completed = [
            c for c in clients
            if c.get('status') == 'completed'
        ]

        health_score = 100

        if revenue == 0 and days_building > 30:
            health_score -= 30
        elif revenue == 0 and days_building > 14:
            health_score -= 15

        if not active_clients:
            health_score -= 20

        if not prospects:
            health_score -= 10

        alerts = []
        if revenue == 0 and days_building > 7:
            alerts.append(
                "No revenue yet. Focus on getting first client."
            )
        if not prospects:
            alerts.append(
                "No prospects in pipeline. Start outreach today."
            )
        if days_building > 60 and not active_clients:
            alerts.append(
                "Building for 60 days without a client. Reassess strategy."
            )

        return {
            'success': True,
            'health_score': max(0, health_score),
            'revenue': revenue,
            'days_building': days_building,
            'current_phase': current_phase,
            'total_clients': len(active_clients),
            'total_prospects': len(prospects),
            'completed_projects': len(completed),
            'next_milestone': company.get(
                'next_milestone', 'First paying client'
            ),
            'alerts': alerts,
            'products': company.get('products', {}),
            'checked_at': datetime.now().isoformat()
        }

    def get_client_pipeline(self):
        """Get all clients and prospects"""
        brain = self.get_brain()
        clients = brain.get('company', {}).get('clients', [])

        pipeline = {
            'prospects': [],
            'in_discussion': [],
            'free_audit': [],
            'active': [],
            'completed': [],
            'lost': []
        }

        for client in clients:
            status = client.get('status', 'prospect')
            if status in pipeline:
                pipeline[status].append(client)
            else:
                pipeline['prospects'].append(client)

        return {
            'success': True,
            'total_in_pipeline': len(clients),
            'pipeline': pipeline,
            'summary': {
                'prospects': len(pipeline['prospects']),
                'in_discussion': len(pipeline['in_discussion']),
                'free_audit': len(pipeline['free_audit']),
                'active': len(pipeline['active']),
                'completed': len(pipeline['completed'])
            }
        }

    def add_prospect(self, name, company,
                      contact='', notes=''):
        """Add new prospect to pipeline"""
        if self.memory_skill:
            result = self.memory_skill.add_client(
                name=name,
                company=company,
                status='prospect',
                notes=f"Contact: {contact}. {notes}"
            )
            return {
                'success': True,
                'added': {
                    'name': name,
                    'company': company,
                    'status': 'prospect',
                    'contact': contact,
                    'notes': notes
                },
                'message': f"Added {name} from {company} as prospect"
            }

        return {
            'success': False,
            'error': 'Memory skill not available'
        }

    def update_prospect_status(self, company,
                                new_status, notes=''):
        """Update prospect status in pipeline"""
        brain = self.get_brain()
        clients = brain.get(
            'company', {}
        ).get('clients', [])

        updated = False
        for client in clients:
            if company.lower() in \
               client.get('company', '').lower():
                client['status'] = new_status
                client['last_updated'] = \
                    datetime.now().isoformat()
                if notes:
                    client['notes'] = client.get(
                        'notes', ''
                    ) + f"\n{notes}"
                updated = True
                break

        if updated:
            if self.memory_skill:
                self.memory_skill.update_company(
                    'clients', clients
                )
            return {
                'success': True,
                'company': company,
                'new_status': new_status,
                'message': f"Updated {company} to {new_status}"
            }

        return {
            'success': False,
            'error': f"Company {company} not found in pipeline"
        }

    def record_revenue(self, amount, client,
                        description=''):
        """Record new revenue"""
        if self.memory_skill:
            result = self.memory_skill.update_revenue(
                amount=float(amount),
                source=client
            )

            self.memory_skill.add_log(
                f"Revenue recorded: ${amount} from {client}. {description}"
            )

            return {
                'success': True,
                'amount': amount,
                'client': client,
                'description': description,
                'new_total': result.get('new_total', 0),
                'message': f"Recorded ${amount} from {client}"
            }

        return {
            'success': False,
            'error': 'Memory skill not available'
        }

    def get_weekly_priorities(self):
        """Get this weeks business priorities"""
        brain = self.get_brain()
        company = brain.get('company', {})

        revenue = company.get('revenue', 0)
        clients = company.get('clients', [])
        days = company.get('days_building', 0)

        active = [
            c for c in clients
            if c.get('status') == 'active'
        ]
        prospects = [
            c for c in clients
            if c.get('status') == 'prospect'
        ]

        priorities = []

        if revenue == 0:
            priorities.append({
                'priority': 1,
                'action': 'Get first paying client',
                'why': 'Zero revenue is the biggest risk',
                'how': 'Offer free audit to 5 prospects this week. Convert one to paid.',
                'time_needed': '2 to 3 hours'
            })

        if not prospects:
            priorities.append({
                'priority': 2,
                'action': 'Build prospect pipeline',
                'why': 'No prospects means no future clients',
                'how': 'Search LinkedIn for IT Managers in Chennai. Send 10 connection requests.',
                'time_needed': '1 hour'
            })

        priorities.append({
            'priority': len(priorities) + 1,
            'action': 'Post on LinkedIn',
            'why': 'Build Trinity6 brand and attract inbound leads',
            'how': 'Share one cybersecurity insight post with real value',
            'time_needed': '30 minutes'
        })

        priorities.append({
            'priority': len(priorities) + 1,
            'action': 'Upload YouTube Short',
            'why': 'Video content builds trust faster',
            'how': 'Record 60 second tip about CIS benchmarks or compliance',
            'time_needed': '1 hour'
        })

        if days > 7:
            priorities.append({
                'priority': len(priorities) + 1,
                'action': 'Review and improve Trinity6 Scanner',
                'why': 'Better product means easier sales',
                'how': 'Add one new feature or improve existing report quality',
                'time_needed': '2 hours'
            })

        return {
            'success': True,
            'week': datetime.now().strftime('%Y Week %W'),
            'total_priorities': len(priorities),
            'priorities': priorities,
            'focus': priorities[0]['action'] if priorities else 'Keep building'
        }

    def generate_invoice_details(self, client_name,
                                  service, amount):
        """Generate invoice details"""
        invoice_number = f"T6-{datetime.now().strftime('%Y%m%d')}-001"

        return {
            'success': True,
            'invoice': {
                'invoice_number': invoice_number,
                'date': datetime.now().strftime('%B %d %Y'),
                'due_date': 'Due on receipt',
                'from': {
                    'company': 'Trinity6',
                    'website': 'trinity6.com',
                    'email': 'trinity6official@gmail.com'
                },
                'to': {
                    'client': client_name
                },
                'service': service,
                'amount': float(amount),
                'currency': 'INR',
                'payment_methods': [
                    'UPI',
                    'Bank Transfer',
                    'Razorpay'
                ],
                'notes': 'Thank you for choosing Trinity6 for your cybersecurity needs.'
            },
            'message': f"Invoice {invoice_number} generated for {client_name}"
        }

    def get_growth_metrics(self):
        """Get Trinity6 growth metrics"""
        brain = self.get_brain()
        company = brain.get('company', {})
        history = brain.get('history', {})

        revenue = company.get('revenue', 0)
        days = company.get('days_building', 0)
        clients = company.get('clients', [])

        logs = history.get('daily_logs', [])
        decisions = history.get('decisions_made', [])

        weekly_revenue = revenue / max(1, days / 7)

        return {
            'success': True,
            'metrics': {
                'days_building': days,
                'total_revenue': revenue,
                'weekly_average_revenue': round(weekly_revenue, 2),
                'total_clients': len([
                    c for c in clients
                    if c.get('status') == 'active'
                ]),
                'total_prospects': len([
                    c for c in clients
                    if c.get('status') == 'prospect'
                ]),
                'total_log_entries': len(logs),
                'total_decisions': len(decisions),
                'revenue_per_day': round(
                    revenue / max(1, days), 2
                )
            },
            'milestones': {
                'first_revenue': revenue > 0,
                'first_client': len([
                    c for c in clients
                    if c.get('status') == 'active'
                ]) > 0,
                'ten_prospects': len(clients) >= 10,
                'monthly_revenue_10k': revenue >= 10000
            },
            'next_milestone': self.get_next_milestone(
                revenue, clients
            )
        }

    def get_next_milestone(self, revenue, clients):
        """Determine next business milestone"""
        active = [
            c for c in clients
            if c.get('status') == 'active'
        ]
        prospects = [
            c for c in clients
            if c.get('status') == 'prospect'
        ]

        if revenue == 0:
            return "Get first paying client"
        elif len(active) < 3:
            return "Reach 3 active clients"
        elif revenue < 10000:
            return "Reach 10000 INR monthly revenue"
        elif revenue < 50000:
            return "Reach 50000 INR monthly revenue"
        elif len(active) < 10:
            return "Reach 10 active clients"
        else:
            return "Scale to 100000 INR monthly revenue"

    def plan_outreach(self, target_count=10):
        """Generate outreach plan for the week"""
        days = ['Monday', 'Tuesday', 'Wednesday',
                'Thursday', 'Friday']

        per_day = max(1, target_count // len(days))

        plan = []
        for day in days:
            plan.append({
                'day': day,
                'actions': [
                    f"Send {per_day} LinkedIn connection requests to IT Managers in Chennai",
                    "Follow up with previous connections",
                    "Engage with one cybersecurity post"
                ],
                'target_connections': per_day
            })

        return {
            'success': True,
            'weekly_target': target_count,
            'per_day': per_day,
            'plan': plan,
            'templates': {
                'connection_request': """Hi [Name], I see you manage IT security at [Company]. I built Trinity6, an AI powered compliance scanner for SMBs. Would love to connect.""",
                'follow_up': """Thanks for connecting [Name]. Would you be open to a free compliance audit of your servers? Trinity6 generates a full CIS benchmark report in minutes. No cost, just useful insights.""",
                'free_audit_offer': """Hi [Name], I would love to offer [Company] a completely free security audit. Trinity6 will scan your Linux servers and give you a professional compliance report. Takes 30 minutes. Interested?"""
            },
            'expected_results': {
                'connections_accepted': f"{target_count // 3} to {target_count // 2}",
                'responses': f"{target_count // 5} to {target_count // 3}",
                'free_audits': f"1 to 3",
                'conversions': "0 to 1 paying client"
            }
        }

    def calculate_mrr(self):
        """Calculate monthly recurring revenue"""
        brain = self.get_brain()
        clients = brain.get('company', {}).get('clients', [])
        total_revenue = brain.get(
            'company', {}
        ).get('revenue', 0)

        active = [
            c for c in clients
            if c.get('status') == 'active'
        ]

        estimated_mrr = len(active) * 500

        return {
            'success': True,
            'total_revenue_ever': total_revenue,
            'active_clients': len(active),
            'estimated_mrr': estimated_mrr,
            'estimated_arr': estimated_mrr * 12,
            'to_reach_targets': {
                'mrr_10000': max(
                    0, 10000 - estimated_mrr
                ),
                'mrr_50000': max(
                    0, 50000 - estimated_mrr
                ),
                'clients_needed_for_10k_mrr': max(
                    0, 20 - len(active)
                )
            },
            'note': 'Based on estimated 500 INR per active client per month'
        }
