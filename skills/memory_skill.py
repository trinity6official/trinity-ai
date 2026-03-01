import json
import os
from datetime import datetime


class MemorySkill:
    """
    Trinity Memory Skill
    Read and write Trinity's brain
    Search conversation history
    Find patterns and insights
    Log decisions and learnings
    Auto discovered by SkillManager
    """

    name = "memory"
    description = "Read and write Trinity brain, search history, log decisions and learnings"

    def __init__(self, brain_file="trinity_brain.json"):
        self.brain_file = brain_file
        self.logs_dir = "memory/daily_logs"

    def get_tools(self):
        """Returns all memory tools Trinity can use"""
        return [
            {
                "name": "read_brain",
                "description": "Read Trinity's full memory and context",
                "params": [],
                "needs_approval": False
            },
            {
                "name": "read_section",
                "description": "Read specific section of brain like david, company, knowledge",
                "params": ["section"],
                "needs_approval": False
            },
            {
                "name": "search_history",
                "description": "Search conversation history for specific topic",
                "params": ["query", "days"],
                "needs_approval": False
            },
            {
                "name": "get_recent_logs",
                "description": "Get recent daily activity logs",
                "params": ["days"],
                "needs_approval": False
            },
            {
                "name": "get_active_alerts",
                "description": "Get all active alerts",
                "params": [],
                "needs_approval": False
            },
            {
                "name": "update_david",
                "description": "Update information about David",
                "params": ["key", "value"],
                "needs_approval": False
            },
            {
                "name": "update_company",
                "description": "Update Trinity6 company information",
                "params": ["key", "value"],
                "needs_approval": False
            },
            {
                "name": "add_client",
                "description": "Add new client to pipeline",
                "params": ["name", "company", "status", "notes"],
                "needs_approval": False
            },
            {
                "name": "update_revenue",
                "description": "Update company revenue",
                "params": ["amount", "source"],
                "needs_approval": False
            },
            {
                "name": "log_decision",
                "description": "Log a decision Trinity made",
                "params": ["decision", "outcome"],
                "needs_approval": False
            },
            {
                "name": "learn",
                "description": "Add something Trinity learned",
                "params": ["category", "insight"],
                "needs_approval": False
            },
            {
                "name": "add_log",
                "description": "Add entry to daily log",
                "params": ["entry"],
                "needs_approval": False
            },
            {
                "name": "update_wellbeing",
                "description": "Update David wellbeing score",
                "params": ["score", "note"],
                "needs_approval": False
            },
            {
                "name": "get_patterns",
                "description": "Get patterns Trinity has noticed",
                "params": [],
                "needs_approval": False
            },
            {
                "name": "get_decisions",
                "description": "Get recent decisions Trinity made",
                "params": ["count"],
                "needs_approval": False
            }
        ]

    def execute(self, tool_name, params):
        """Trinity calls this to use any memory tool"""
        tool_map = {
            "read_brain": self.read_brain,
            "read_section": self.read_section,
            "search_history": self.search_history,
            "get_recent_logs": self.get_recent_logs,
            "get_active_alerts": self.get_active_alerts,
            "update_david": self.update_david,
            "update_company": self.update_company,
            "add_client": self.add_client,
            "update_revenue": self.update_revenue,
            "log_decision": self.log_decision,
            "learn": self.learn,
            "add_log": self.add_log,
            "update_wellbeing": self.update_wellbeing,
            "get_patterns": self.get_patterns,
            "get_decisions": self.get_decisions
        }

        tool = tool_map.get(tool_name)
        if not tool:
            return {"error": f"Unknown tool: {tool_name}"}

        try:
            return tool(**params)
        except Exception as e:
            return {"error": str(e)}

    # ==========================================
    # BRAIN FILE OPERATIONS
    # ==========================================

    def load_brain(self):
        """Load brain from file"""
        try:
            with open(self.brain_file, 'r') as f:
                return json.load(f)
        except Exception:
            return {}

    def save_brain(self, brain):
        """Save brain to file"""
        try:
            os.makedirs(
                os.path.dirname(self.brain_file),
                exist_ok=True
            )
            with open(self.brain_file, 'w') as f:
                json.dump(brain, f, indent=2)
            return True
        except Exception as e:
            return False

    # ==========================================
    # READ TOOLS
    # ==========================================

    def read_brain(self):
        """Read Trinity full memory"""
        brain = self.load_brain()
        return {
            'success': True,
            'brain': brain,
            'sections': list(brain.keys()),
            'last_wakeup': brain.get(
                'identity', {}
            ).get('last_wakeup'),
            'days_alive': brain.get(
                'identity', {}
            ).get('days_alive', 0)
        }

    def read_section(self, section):
        """Read specific section of brain"""
        brain = self.load_brain()
        if section not in brain:
            return {
                'success': False,
                'error': f"Section {section} not found",
                'available_sections': list(brain.keys())
            }
        return {
            'success': True,
            'section': section,
            'data': brain[section]
        }

    def search_history(self, query, days=7):
        """Search conversation history"""
        brain = self.load_brain()
        conversations = brain.get(
            'history', {}
        ).get('conversations', [])

        query_lower = query.lower()
        matches = []

        for conv in conversations:
            message = conv.get('message', '')
            if query_lower in message.lower():
                matches.append(conv)

        matches = matches[-50:]

        return {
            'success': True,
            'query': query,
            'total_matches': len(matches),
            'matches': matches[-10:]
        }

    def get_recent_logs(self, days=7):
        """Get recent daily logs"""
        brain = self.load_brain()
        logs = brain.get(
            'history', {}
        ).get('daily_logs', [])

        recent = logs[-(days * 10):]

        log_files = []
        if os.path.exists(self.logs_dir):
            log_files = sorted(
                os.listdir(self.logs_dir)
            )[-days:]

        return {
            'success': True,
            'days': days,
            'log_count': len(recent),
            'logs': recent,
            'log_files': log_files
        }

    def get_active_alerts(self):
        """Get all active alerts"""
        brain = self.load_brain()
        alerts = brain.get(
            'monitoring', {}
        ).get('alerts_active', [])

        return {
            'success': True,
            'total_alerts': len(alerts),
            'alerts': alerts
        }

    def get_patterns(self):
        """Get patterns Trinity has noticed"""
        brain = self.load_brain()
        patterns = brain.get(
            'knowledge', {}
        ).get('patterns_noticed', [])

        return {
            'success': True,
            'total_patterns': len(patterns),
            'patterns': patterns
        }

    def get_decisions(self, count=10):
        """Get recent decisions Trinity made"""
        brain = self.load_brain()
        decisions = brain.get(
            'history', {}
        ).get('decisions_made', [])

        recent = decisions[-count:]

        return {
            'success': True,
            'total_decisions': len(decisions),
            'recent_decisions': recent
        }

    # ==========================================
    # WRITE TOOLS
    # ==========================================

    def update_david(self, key, value):
        """Update David information"""
        brain = self.load_brain()

        if 'david' not in brain:
            brain['david'] = {}

        brain['david'][key] = value
        brain['david']['last_updated'] = \
            datetime.now().isoformat()

        self.save_brain(brain)

        return {
            'success': True,
            'updated': f"david.{key}",
            'value': value
        }

    def update_company(self, key, value):
        """Update company information"""
        brain = self.load_brain()

        if 'company' not in brain:
            brain['company'] = {}

        brain['company'][key] = value

        self.save_brain(brain)

        return {
            'success': True,
            'updated': f"company.{key}",
            'value': value
        }

    def add_client(self, name, company,
                    status, notes=None):
        """Add client to pipeline"""
        brain = self.load_brain()

        if 'company' not in brain:
            brain['company'] = {}
        if 'clients' not in brain['company']:
            brain['company']['clients'] = []

        client = {
            'name': name,
            'company': company,
            'status': status,
            'notes': notes or '',
            'added_date': datetime.now().isoformat()
        }

        brain['company']['clients'].append(client)
        self.save_brain(brain)

        return {
            'success': True,
            'client_added': client,
            'total_clients': len(
                brain['company']['clients']
            )
        }

    def update_revenue(self, amount, source):
        """Update company revenue"""
        brain = self.load_brain()

        if 'company' not in brain:
            brain['company'] = {}

        current = brain['company'].get('revenue', 0)
        new_total = current + float(amount)
        brain['company']['revenue'] = new_total

        self.add_log(
            f"Revenue update: +{amount} from {source}. Total: {new_total}"
        )

        self.save_brain(brain)

        return {
            'success': True,
            'added': amount,
            'source': source,
            'new_total': new_total
        }

    def log_decision(self, decision, outcome):
        """Log a decision"""
        brain = self.load_brain()

        if 'history' not in brain:
            brain['history'] = {}
        if 'decisions_made' not in brain['history']:
            brain['history']['decisions_made'] = []

        entry = {
            'timestamp': datetime.now().isoformat(),
            'decision': decision,
            'outcome': outcome
        }

        brain['history']['decisions_made'].append(entry)
        self.save_brain(brain)

        return {
            'success': True,
            'logged': entry
        }

    def learn(self, category, insight):
        """Add something Trinity learned"""
        brain = self.load_brain()

        if 'knowledge' not in brain:
            brain['knowledge'] = {
                'what_works': [],
                'what_doesnt': [],
                'patterns_noticed': [],
                'improvements_made': []
            }

        if category == 'what_works':
            if insight not in brain['knowledge']['what_works']:
                brain['knowledge']['what_works'].append(insight)
        elif category == 'what_doesnt':
            if insight not in brain['knowledge']['what_doesnt']:
                brain['knowledge']['what_doesnt'].append(insight)
        elif category == 'pattern':
            brain['knowledge']['patterns_noticed'].append({
                'timestamp': datetime.now().isoformat(),
                'pattern': insight
            })
        elif category == 'improvement':
            brain['knowledge']['improvements_made'].append({
                'timestamp': datetime.now().isoformat(),
                'improvement': insight
            })

        if 'learning' not in brain:
            brain['learning'] = {'total_interactions': 0}
        brain['learning']['total_interactions'] += 1

        self.save_brain(brain)

        return {
            'success': True,
            'learned': insight,
            'category': category
        }

    def add_log(self, entry):
        """Add entry to daily log"""
        brain = self.load_brain()

        if 'history' not in brain:
            brain['history'] = {}
        if 'daily_logs' not in brain['history']:
            brain['history']['daily_logs'] = []

        log_entry = {
            'timestamp': datetime.now().isoformat(),
            'date': datetime.now().strftime('%Y-%m-%d'),
            'entry': entry
        }

        brain['history']['daily_logs'].append(log_entry)

        os.makedirs(self.logs_dir, exist_ok=True)
        log_file = f"{self.logs_dir}/{datetime.now().strftime('%Y-%m-%d')}.json"

        daily = []
        if os.path.exists(log_file):
            with open(log_file, 'r') as f:
                daily = json.load(f)

        daily.append(log_entry)
        with open(log_file, 'w') as f:
            json.dump(daily, f, indent=2)

        self.save_brain(brain)

        return {
            'success': True,
            'logged': entry
        }

    def update_wellbeing(self, score, note=None):
        """Update David wellbeing score"""
        brain = self.load_brain()

        if 'david' not in brain:
            brain['david'] = {}

        brain['david']['wellbeing_score'] = score

        if note:
            if 'notes' not in brain['david']:
                brain['david']['notes'] = []
            brain['david']['notes'].append({
                'timestamp': datetime.now().isoformat(),
                'note': note
            })

        self.save_brain(brain)

        return {
            'success': True,
            'wellbeing_score': score,
            'note': note
        }
