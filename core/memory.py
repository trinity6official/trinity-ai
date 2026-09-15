import json
import os
from datetime import datetime
from pathlib import Path

from core.memory_store import MemoryStore

class TrinityMemory:
    """
    Trinity Memory System
    Reads and writes to trinity_brain.json
    Only stores what GitHub cannot tell us
    Repository details read directly from GitHub
    """
    
    def __init__(self, brain_file="memory/trinity_brain.json", memory_root=None, db_path=None):
        self.brain_file = brain_file
        self.brain = self.load()
        # Keep the legacy JSON compatibility layer while new durable memories are
        # written to SQLite + Markdown. Tests/custom paths get an isolated vault.
        root = Path(memory_root) if memory_root else Path(brain_file).parent
        if str(root) in ("", "."):
            root = Path("memory") if brain_file == "memory/trinity_brain.json" else Path(".")
        self.store = MemoryStore(root=root, db_path=db_path)
        self.store.import_legacy_brain(self.brain)

    def load(self):
        """Load Trinity's brain from file"""
        try:
            with open(self.brain_file, 'r') as f:
                brain = json.load(f)
                print("Trinity memory loaded successfully")
                return brain
        except FileNotFoundError:
            print("No memory file found. Starting fresh.")
            return {}
        except Exception as e:
            print(f"Memory load error: {str(e)}")
            return {}

    def save(self):
        """Save Trinity's brain to file"""
        try:
            parent = os.path.dirname(self.brain_file)
            if parent:
                os.makedirs(parent, exist_ok=True)
            with open(self.brain_file, 'w') as f:
                json.dump(self.brain, f, indent=2)
            print("Trinity memory saved")
        except Exception as e:
            print(f"Memory save error: {str(e)}")

    def update_last_wakeup(self):
        """Record when Trinity last woke up"""
        if 'identity' not in self.brain:
            self.brain['identity'] = {
                'name': 'Trinity',
                'version': '1.0',
                'born': '2026-02-22',
                'days_alive': 0,
                'last_wakeup': None,
                'core_mission': "David's wellbeing and financial growth"
            }
        self.brain['identity']['last_wakeup'] = \
            datetime.now().isoformat()
        self.brain['identity']['days_alive'] = \
            self.brain['identity'].get('days_alive', 0) + 1
        self.save()
    
    def update_david_last_seen(self):
        """Record when David last interacted"""
        if 'david' not in self.brain:
            self.brain['david'] = {}
        self.brain['david']['last_seen'] = \
            datetime.now().isoformat()
        self.save()
    
    def add_daily_log(self, log_entry):
        """Add entry to daily log"""
        self.brain.setdefault('history', {}).setdefault('daily_logs', [])

        entry = {
            'timestamp': datetime.now().isoformat(),
            'date': datetime.now().strftime('%Y-%m-%d'),
            'entry': log_entry
        }
        self.brain['history']['daily_logs'].append(entry)
        self.store.add_daily_entry(log_entry, entry['timestamp'])
        
        logs_dir = "memory/daily_logs"
        os.makedirs(logs_dir, exist_ok=True)
        log_file = f"{logs_dir}/{datetime.now().strftime('%Y-%m-%d')}.json"
        
        daily_entries = []
        if os.path.exists(log_file):
            with open(log_file, 'r') as f:
                daily_entries = json.load(f)
        
        daily_entries.append(entry)
        with open(log_file, 'w') as f:
            json.dump(daily_entries, f, indent=2)
        
        self.save()
    
    def add_alert(self, alert_type, message, severity="medium"):
        """Record an alert sent to David"""
        self.brain.setdefault('history', {}).setdefault('alerts_sent', [])
        self.brain.setdefault('monitoring', {}).setdefault('alerts_active', [])

        alert = {
            'timestamp': datetime.now().isoformat(),
            'type': alert_type,
            'message': message,
            'severity': severity
        }
        self.brain['history']['alerts_sent'].append(alert)
        self.brain['monitoring']['alerts_active'].append(alert)
        self.save()
    
    def clear_alert(self, alert_type):
        """Clear resolved alert"""
        if 'monitoring' not in self.brain:
            return
        self.brain['monitoring']['alerts_active'] = [
            a for a in self.brain['monitoring']['alerts_active']
            if a['type'] != alert_type
        ]
        self.save()
    
    def update_monitoring_status(self, key, value):
        """Update monitoring status"""
        if 'monitoring' not in self.brain:
            self.brain['monitoring'] = {}
        self.brain['monitoring'][key] = value
        self.brain['monitoring']['last_check'] = \
            datetime.now().isoformat()
        self.save()
    
    def record_decision(self, decision, outcome):
        """Record a decision Trinity made"""
        self.brain.setdefault('history', {}).setdefault('decisions_made', [])

        entry = {
            'timestamp': datetime.now().isoformat(),
            'decision': decision,
            'outcome': outcome
        }
        self.brain['history']['decisions_made'].append(entry)
        self.store.remember(
            f"{decision} — Outcome: {outcome}", kind="decision",
            category="trinity", importance=0.85, metadata=entry
        )
        self.save()
    
    def learn(self, category, insight):
        """Add something Trinity learned"""
        if 'knowledge' not in self.brain:
            self.brain['knowledge'] = {
                'what_works': [],
                'what_doesnt': [],
                'patterns_noticed': []
            }
        
        if category == 'what_works':
            if insight not in self.brain['knowledge']['what_works']:
                self.brain['knowledge']['what_works'].append(insight)
        elif category == 'what_doesnt':
            if insight not in self.brain['knowledge']['what_doesnt']:
                self.brain['knowledge']['what_doesnt'].append(insight)
        elif category == 'pattern':
            self.brain['knowledge']['patterns_noticed'].append({
                'timestamp': datetime.now().isoformat(),
                'pattern': insight
            })
        
        if 'learning' not in self.brain:
            self.brain['learning'] = {'total_interactions': 0}
        self.brain['learning']['total_interactions'] += 1
        self.save()
    
    def update_wellbeing(self, score, note=None):
        """Update David's wellbeing score"""
        if 'david' not in self.brain:
            self.brain['david'] = {}
        self.brain['david']['wellbeing_score'] = score
        if note:
            if 'notes' not in self.brain['david']:
                self.brain['david']['notes'] = []
            self.brain['david']['notes'].append({
                'timestamp': datetime.now().isoformat(),
                'note': note
            })
        self.save()
    
    def get_recent_logs(self, days=7):
        """Get logs from the last N days"""
        if 'history' not in self.brain:
            return []
        logs = self.brain['history'].get('daily_logs', [])
        return logs[-days*10:] if logs else []
    
    def get_active_alerts(self):
        """Get all active alerts"""
        if 'monitoring' not in self.brain:
            return []
        return self.brain['monitoring'].get('alerts_active', [])
    
    def get_company_summary(self):
        """Get quick company summary"""
        company = self.brain.get('company', {})
        return {
            'name': company.get('name'),
            'phase': company.get('current_phase'),
            'next_milestone': company.get('next_milestone'),
            'revenue': company.get('revenue', 0),
            'clients': len(company.get('clients', [])),
            'days_building': company.get('days_building', 0)
        }
    
    def get_david_summary(self):
        """Get quick David summary"""
        david = self.brain.get('david', {})
        return {
            'wellbeing_score': david.get('wellbeing_score', 100),
            'last_seen': david.get('last_seen'),
            'stress_indicators': david.get('stress_indicators', [])
        }
    
    def add_conversation(self, role, message):
        """Store conversation history"""
        if 'history' not in self.brain:
            self.brain['history'] = {'conversations': []}
        if 'conversations' not in self.brain['history']:
            self.brain['history']['conversations'] = []
        
        entry = {
            'timestamp': datetime.now().isoformat(),
            'role': role,
            'message': message
        }
        conversations = self.brain['history']['conversations']
        conversations.append(entry)
        
        if len(conversations) > 100:
            self.brain['history']['conversations'] = \
                conversations[-100:]
        
        self.save()
    
    def remember(self, content, kind="semantic", category="general", importance=0.5, metadata=None):
        """Store a durable memory in Trinity's local SQLite/Markdown vault."""
        return self.store.remember(
            content, kind=kind, category=category, importance=importance, metadata=metadata
        )

    def recall(self, query, limit=10, kind=None):
        """Recall relevant durable memories from the local store."""
        return self.store.search(query, limit=limit, kind=kind)

    def recent_memories(self, limit=10):
        return self.store.recent(limit=limit)

    def get_days_alive(self):
        """Get how many days Trinity has been running"""
        if 'identity' not in self.brain:
            return 0
        return self.brain['identity'].get('days_alive', 0)
    
    def get_full_context(self):
        """
        Get full context for AI prompting
        Does NOT include repo details
        Those are read directly from GitHub
        """
        return json.dumps({
            'david': self.brain.get('david', {}),
            'company': self.brain.get('company', {}),
            'knowledge': self.brain.get('knowledge', {}),
            'monitoring': self.brain.get('monitoring', {}),
            'recent_logs': self.get_recent_logs(3)
        }, indent=2)
