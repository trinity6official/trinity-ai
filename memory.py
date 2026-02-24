import json
import os
from datetime import datetime
from pathlib import Path

class TrinitySuperMemory:
    """
    Trinity's actual brain. Persistent memory that survives between responses.
    This is what makes Trinity a business partner, not just a chatbot.
    """
    
    def __init__(self, memory_file="trinity_memory.json"):
        self.memory_file = memory_file
        self.memory = self._load_or_create()
    
    def _load_or_create(self):
        """Load existing memory or create new one"""
        if os.path.exists(self.memory_file):
            with open(self.memory_file, 'r') as f:
                return json.load(f)
        
        return {
            "created": datetime.now().isoformat(),
            "last_updated": datetime.now().isoformat(),
            "operations_log": [],
            "decision_log": [],
            "learned_patterns": [],
            "current_state": {
                "working_on": None,
                "blockers": [],
                "last_successful_action": None,
                "last_successful_time": None,
                "next_step": None,
                "recovery_mode": False
            },
            "error_recovery": {
                "last_error": None,
                "last_error_time": None,
                "recovery_attempts": [],
                "rollback_points": []
            },
            "statistics": {
                "total_operations": 0,
                "successful_operations": 0,
                "failed_operations": 0,
                "success_rate": 0.0,
                "patterns_learned": 0,
                "decisions_made": 0
            }
        }
    
    def save(self):
        """Persist memory to disk"""
        self.memory["last_updated"] = datetime.now().isoformat()
        with open(self.memory_file, 'w') as f:
            json.dump(self.memory, f, indent=2)
    
    def log_operation(self, operation, tool, status, error=None, recovery=None, lesson=None):
        """Log what Trinity tried to do and what happened"""
        op_log = {
            "timestamp": datetime.now().isoformat(),
            "operation": operation,
            "tool": tool,
            "status": status,  # success, failed, partial
            "error": error,
            "recovery": recovery,
            "lesson": lesson
        }
        self.memory["operations_log"].append(op_log)
        
        # Update statistics
        self.memory["statistics"]["total_operations"] += 1
        if status == "success":
            self.memory["statistics"]["successful_operations"] += 1
        elif status == "failed":
            self.memory["statistics"]["failed_operations"] += 1
        
        self._update_success_rate()
        self.save()
        return op_log
    
    def log_decision(self, problem, options, chose, reason, outcome=None):
        """Log why Trinity made a choice"""
        decision = {
            "timestamp": datetime.now().isoformat(),
            "problem": problem,
            "options": options,
            "chose": chose,
            "reason": reason,
            "outcome": outcome
        }
        self.memory["decision_log"].append(decision)
        self.memory["statistics"]["decisions_made"] += 1
        self.save()
        return decision
    
    def learn_pattern(self, pattern, confidence, examples, action):
        """Record a pattern Trinity learned"""
        learned = {
            "timestamp": datetime.now().isoformat(),
            "pattern": pattern,
            "confidence": confidence,  # 1-10
            "examples": examples,
            "action": action,
            "times_seen": 1
        }
        
        # Check if pattern already exists
        for existing in self.memory["learned_patterns"]:
            if existing["pattern"] == pattern:
                existing["times_seen"] += 1
                existing["confidence"] = min(10, existing["confidence"] + 0.5)
                self.save()
                return existing
        
        self.memory["learned_patterns"].append(learned)
        self.memory["statistics"]["patterns_learned"] += 1
        self.save()
        return learned
    
    def get_relevant_patterns(self, context):
        """Get patterns that might help with current problem"""
        relevant = []
        for pattern in self.memory["learned_patterns"]:
            if pattern["confidence"] >= 6:  # Only use confident patterns
                relevant.append(pattern)
        return sorted(relevant, key=lambda x: x["confidence"], reverse=True)
    
    def set_working_on(self, task, blockers=None):
        """Tell Trinity what it's working on"""
        self.memory["current_state"]["working_on"] = task
        if blockers:
            self.memory["current_state"]["blockers"] = blockers
        self.save()
    
    def log_success(self, action):
        """Record successful action for recovery reference"""
        self.memory["current_state"]["last_successful_action"] = action
        self.memory["current_state"]["last_successful_time"] = datetime.now().isoformat()
        self.save()
    
    def log_error(self, error_msg):
        """Log error for recovery"""
        self.memory["error_recovery"]["last_error"] = error_msg
        self.memory["error_recovery"]["last_error_time"] = datetime.now().isoformat()
        self.memory["error_recovery"]["recovery_attempts"].append({
            "timestamp": datetime.now().isoformat(),
            "error": error_msg,
            "status": "logged"
        })
        self.save()
    
    def create_rollback_point(self, action, state):
        """Save current state before making changes"""
        rollback = {
            "timestamp": datetime.now().isoformat(),
            "action": action,
            "state": state
        }
        self.memory["error_recovery"]["rollback_points"].append(rollback)
        # Keep only last 10 rollback points
        if len(self.memory["error_recovery"]["rollback_points"]) > 10:
            self.memory["error_recovery"]["rollback_points"] = \
                self.memory["error_recovery"]["rollback_points"][-10:]
        self.save()
        return rollback
    
    def get_last_rollback(self):
        """Get last saved state for recovery"""
        if self.memory["error_recovery"]["rollback_points"]:
            return self.memory["error_recovery"]["rollback_points"][-1]
        return None
    
    def _update_success_rate(self):
        """Calculate success rate"""
        total = self.memory["statistics"]["total_operations"]
        if total > 0:
            successful = self.memory["statistics"]["successful_operations"]
            self.memory["statistics"]["success_rate"] = \
                round((successful / total) * 100, 2)
    
    def get_memory_summary(self):
        """Get Trinity's current state summary"""
        return {
            "working_on": self.memory["current_state"]["working_on"],
            "blockers": self.memory["current_state"]["blockers"],
            "last_success": self.memory["current_state"]["last_successful_action"],
            "success_rate": self.memory["statistics"]["success_rate"],
            "patterns_learned": self.memory["statistics"]["patterns_learned"],
            "recovery_mode": self.memory["current_state"]["recovery_mode"],
            "recent_operations": self.memory["operations_log"][-5:] if self.memory["operations_log"] else []
        }
    
    def get_operation_history(self, limit=10):
        """Get recent operations"""
        return self.memory["operations_log"][-limit:]
    
    def get_failed_operations(self):
        """Get all failed operations to learn from"""
        return [op for op in self.memory["operations_log"] if op["status"] == "failed"]
    
    def check_should_retry(self, operation):
        """Should Trinity retry this operation based on history?"""
        failed = self.get_failed_operations()
        for fail in failed:
            if fail["operation"] == operation:
                # Found similar failure
                if fail.get("lesson"):
                    return False, fail["lesson"]
        return True, "No previous failures"
    
    def export_brain(self):
        """Export full memory for analysis"""
        return self.memory


# Initialize Trinity's memory
trinity_memory = TrinitySuperMemory()