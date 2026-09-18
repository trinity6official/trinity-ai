from core.memory import MemoryService


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

    def __init__(self, brain_file=None, memory=None):
        self.memory = memory or MemoryService(
            brain_file=brain_file or MemoryService.DEFAULT_LEGACY_BRAIN
        )
        # Compatibility attribute for older tests/integrations.  It is a
        # migration/export path, not this skill's persistence owner.
        self.brain_file = str(brain_file or self.memory.brain_file)

    def _session_store(self):
        return self.memory.store

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
                "name": "search_sessions",
                "description": "Search persistent local Trinity conversation sessions",
                "params": ["query", "days", "limit"],
                "needs_approval": False
            },
            {
                "name": "get_recent_sessions",
                "description": "Read recent persistent Trinity conversation sessions",
                "params": ["days", "limit"],
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
            },
            {
                "name": "pin_memory",
                "description": (
                    "Permanently store a critical fact that should never be forgotten "
                    "(e.g. client names, pricing decisions, key facts about David)"
                ),
                "params": ["key", "value"],
                "needs_approval": False
            },
            {
                "name": "get_pinned",
                "description": "Read all permanently pinned memories",
                "params": [],
                "needs_approval": False
            }
        ]

    def execute(self, tool_name, params):
        """Trinity calls this to use any memory tool"""
        tool_map = {
            "read_brain": self.read_brain,
            "read_section": self.read_section,
            "search_history": self.search_history,
            "search_sessions": self.search_sessions,
            "get_recent_sessions": self.get_recent_sessions,
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
            "get_decisions": self.get_decisions,
            "pin_memory": self.pin_memory,
            "get_pinned": self.get_pinned,
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
        """Read the authoritative structured state owned by MemoryService."""
        return self.memory.brain

    def save_brain(self, brain):
        """Persist structured state through MemoryService."""
        if not isinstance(brain, dict):
            return False
        self.memory.brain = brain
        self.memory.save()
        return True

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
        """Search authoritative persistent conversation history."""
        records = self._session_store().search_conversations(
            str(query or ""),
            days=int(days) if days is not None else None,
            limit=10,
        )
        matches = [self._session_payload(record) for record in records]

        return {
            'success': True,
            'query': query,
            'total_matches': len(matches),
            'matches': matches[-10:]
        }

    @staticmethod
    def _session_payload(record):
        return {"id": record.id, "session_id": record.session_id, "user": record.user_text, "assistant": record.assistant_text,
                "created_at": record.created_at, "metadata": record.metadata}

    def search_sessions(self, query, days=30, limit=10):
        records = self._session_store().search_conversations(str(query or ""), days=int(days) if days is not None else None, limit=int(limit))
        return {"success": True, "query": query, "total_matches": len(records), "matches": [self._session_payload(r) for r in records]}

    def get_recent_sessions(self, days=7, limit=20):
        records = self._session_store().recent_conversations(days=int(days) if days is not None else None, limit=int(limit))
        return {"success": True, "days": days, "count": len(records), "sessions": [self._session_payload(r) for r in records]}

    def get_recent_logs(self, days=7):
        """Get recent daily logs"""
        recent = self.memory.get_recent_logs(int(days))
        daily_dir = self.memory.store.vault / "daily"
        log_files = [path.name for path in sorted(daily_dir.glob("*.md"))[-int(days):]]

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
        self.memory.update_david(key, value)

        return {
            'success': True,
            'updated': f"david.{key}",
            'value': value
        }

    def update_company(self, key, value):
        """Update company information"""
        self.memory.update_company(key, value)

        return {
            'success': True,
            'updated': f"company.{key}",
            'value': value
        }

    def add_client(self, name, company,
                    status, notes=None):
        """Add client to pipeline"""
        client = self.memory.add_client(name, company, status, notes)
        clients = self.memory.brain.get('company', {}).get('clients', [])

        return {
            'success': True,
            'client_added': client,
            'total_clients': len(clients)
        }

    def update_revenue(self, amount, source):
        """Update company revenue"""
        new_total = self.memory.update_revenue(amount, source)

        return {
            'success': True,
            'added': amount,
            'source': source,
            'new_total': new_total
        }

    def log_decision(self, decision, outcome):
        """Log a decision"""
        self.memory.record_decision(decision, outcome)
        entry = self.memory.brain['history']['decisions_made'][-1]

        return {
            'success': True,
            'logged': entry
        }

    def learn(self, category, insight):
        """Add something Trinity learned"""
        self.memory.learn(category, insight)

        return {
            'success': True,
            'learned': insight,
            'category': category
        }

    def add_log(self, entry):
        """Add entry to daily log"""
        self.memory.add_daily_log(entry)

        return {
            'success': True,
            'logged': entry
        }

    def update_wellbeing(self, score, note=None):
        """Update David wellbeing score"""
        self.memory.update_wellbeing(score, note)

        return {
            'success': True,
            'wellbeing_score': score,
            'note': note
        }

    # ==========================================
    # PERMANENT MEMORY — NEVER FORGOTTEN
    # ==========================================

    def pin_memory(self, key, value):
        """
        Permanently store a critical fact.
        Pinned memories are never pruned, never decay, never expire.
        Use for: client names, pricing, key decisions, David's preferences.
        """
        self.memory.pin_memory(key, value)
        pinned = self.memory.get_pinned()

        return {
            'success': True,
            'pinned_key': key,
            'pinned_value': value,
            'total_pinned': len(pinned),
        }

    def get_pinned(self):
        """Read all permanently pinned memories."""
        pinned = self.memory.get_pinned()
        return {
            'success': True,
            'total_pinned': len(pinned),
            'pinned': pinned,
        }
