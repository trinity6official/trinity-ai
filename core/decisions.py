from datetime import datetime
from typing import Callable

from core.permissions import PermissionEngine, PermissionLevel

class TrinityDecisions:
    """
    Trinity Decision Engine
    Decides what Trinity can do alone
    versus what needs David's approval
    David's wellbeing and financial growth
    are always the top priority
    """
    
    def __init__(self, memory, telegram_token=None, chat_id=None, notifier: Callable[[str], object] | None = None):
        self.memory = memory
        self.telegram_token = telegram_token
        self.chat_id = chat_id
        self.notifier = notifier
        self.pending_approvals = []
        self.permissions = PermissionEngine()
    
    # ==========================================
    # CORE DECISION LOGIC
    # ==========================================
    
    def can_act_alone(self, action_type):
        """Check if Trinity can act without David."""
        return self.permissions.assess_action(action_type).level == PermissionLevel.SAFE

    def needs_approval(self, action_type):
        """Check if a known action explicitly requires David's approval."""
        return action_type in self.permissions.CONFIRM_ACTIONS

    def never_do(self, action_type):
        """Check whether policy forbids an action entirely."""
        return self.permissions.assess_action(action_type).level == PermissionLevel.FORBIDDEN

    # ==========================================
    # APPROVAL SYSTEM
    # ==========================================
    
    def request_approval(self, action, description,
                          impact, cost=None):
        """
        Ask David for approval before acting
        Sends Telegram message and waits
        """
        approval_id = f"approval_{datetime.now().strftime('%Y%m%d%H%M%S%f')}"
        
        message = f"""Trinity needs your approval.

Action: {action}
Description: {description}
Impact: {impact}"""
        
        if cost:
            message += f"\nCost: {cost}"
        
        message += f"""

Reply with:
YES - to approve
NO - to reject
ID: {approval_id}"""
        
        self.send_telegram(message)
        
        self.pending_approvals.append({
            'id': approval_id,
            'action': action,
            'description': description,
            'impact': impact,
            'cost': cost,
            'requested_at': datetime.now().isoformat(),
            'status': 'pending'
        })
        
        self.memory.record_decision(
            f"Requested approval for: {action}",
            "Pending David's response"
        )
        
        return approval_id
    
    def check_approval_response(self, approval_id):
        """Check if David responded to approval request"""
        for approval in self.pending_approvals:
            if approval['id'] == approval_id:
                return approval.get('status', 'pending')
        return 'not_found'
    
    # ==========================================
    # WELLBEING CHECKS
    # ==========================================
    
    def check_david_wellbeing(self, context):
        """
        Monitor David's wellbeing
        This is Trinity's top priority
        """
        indicators = []
        
        last_seen = self.memory.brain['david'].get(
            'last_seen'
        )
        
        if last_seen:
            last_seen_dt = datetime.fromisoformat(last_seen)
            hours_since = (
                datetime.now() - last_seen_dt
            ).total_seconds() / 3600
            
            if hours_since > 20:
                indicators.append(
                    "David has not been seen for over 20 hours"
                )
        
        days_alive = self.memory.get_days_alive()
        if days_alive > 0 and days_alive % 7 == 0:
            indicators.append(
                "David has been working for 7 days straight. Rest is important."
            )
        
        if indicators:
            self.memory.update_wellbeing(
                80,
                "Wellbeing indicators detected"
            )
            
            message = "David I noticed something.\n\n"
            for indicator in indicators:
                message += f"- {indicator}\n"
            message += "\nYour wellbeing is Trinity's top priority. Please take care of yourself."
            
            self.send_telegram(message)
        
        return indicators
    
    # ==========================================
    # FINANCIAL MONITORING
    # ==========================================
    
    def check_financial_health(self):
        """Monitor financial status and alerts"""
        alerts = []
        
        revenue = self.memory.brain['company'].get(
            'revenue', 0
        )
        
        if revenue == 0:
            days = self.memory.get_days_alive()
            if days > 30:
                alerts.append(
                    "Trinity6 has no revenue yet after 30 days. Time to focus on getting first client."
                )
        
        return alerts
    
    # ==========================================
    # SMART RECOMMENDATIONS
    # ==========================================
    
    def generate_daily_recommendation(self,
                                       health_summary,
                                       github_data):
        """
        Generate what David should focus on today
        Based on current status and roadmap
        """
        recommendations = []
        
        if health_summary.get('overall') == 'critical':
            recommendations.append(
                "URGENT: Website is down. Fix this first."
            )
        
        failed_workflows = []
        for repo, data in github_data.items():
            for wf in data.get('recent_workflows', []):
                if wf.get('conclusion') == 'failure':
                    failed_workflows.append(repo)
        
        if failed_workflows:
            recommendations.append(
                f"Fix failed GitHub Actions in: {', '.join(failed_workflows)}"
            )
        
        company = self.memory.brain.get('company', {})
        phase = company.get('current_phase', '')
        
        if 'Phase 2' in phase:
            recommendations.append(
                "Phase 2 is complete. Consider starting Phase 3 Windows support or focus on getting first client."
            )
        
        revenue = company.get('revenue', 0)
        if revenue == 0:
            recommendations.append(
                "No revenue yet. Reaching out to potential clients should be a priority."
            )
        
        hardware = self.memory.brain.get('hardware', {})
        desktop = hardware.get('desktop', {})
        if desktop.get('status') == 'arriving_soon':
            recommendations.append(
                "Hardware arriving soon. Prepare the macOS, Ollama, permissions and Trinity Doctor checklist."
            )
        
        if not recommendations:
            recommendations.append(
                "Everything looks good. Continue building Phase 3 or focus on client outreach."
            )
        
        return recommendations
    
    # ==========================================
    # TELEGRAM
    # ==========================================
    
    def send_telegram(self, message):
        """Compatibility notification method; transport remains optional and external."""
        if self.notifier is not None:
            return self.notifier(message)
        if not (self.telegram_token and self.chat_id):
            return False
        from core.channels.telegram import TelegramChannel

        return TelegramChannel(self.telegram_token, self.chat_id).send(message)

    def log_decision(self, action, reasoning, outcome):
        """Log every decision Trinity makes"""
        self.memory.record_decision(
            f"{action} - Reasoning: {reasoning}",
            outcome
        )
