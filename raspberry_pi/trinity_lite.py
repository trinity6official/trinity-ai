import os
import sys
import time
import requests
from datetime import datetime

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.memory import TrinityMemory
from core.monitor import TrinityMonitor
from agents.github_agent import GitHubAgent
from agents.business_agent import BusinessAgent
from voice.language import LanguageDetector
from core.model_router import LocalModelRouter
from core.models import OllamaProvider

class TrinityLite:
    """
    Trinity Lite - Raspberry Pi Version
    Runs 24/7 on Raspberry Pi 5
    Always on lightweight monitoring
    Uses small Llama model to save resources
    Hands off heavy tasks to desktop
    David always has Trinity watching
    even when desktop is off
    """
    
    def __init__(self, notifier=None):
        print("Trinity Lite starting on Raspberry Pi...")
        
        self.notifier = notifier or print
        self.gh_token = os.environ.get('GH_TOKEN')
        
        self.memory = TrinityMemory()
        self.language = LanguageDetector()
        self.monitor = TrinityMonitor(gh_token=self.gh_token)
        self.github_agent = GitHubAgent(gh_token=self.gh_token)
        self.business_agent = BusinessAgent(memory=self.memory)
        
        self.llm = self.setup_lite_llm()
        
        self.memory.update_last_wakeup()
        print("Trinity Lite is awake and watching!")
    
    def setup_lite_llm(self):
        """Use a small local model only; Trinity Lite never falls back to cloud AI."""
        base_url = os.environ.get("LOCAL_LLM_URL", "http://127.0.0.1:11434")
        model = os.environ.get("TRINITY_LITE_MODEL", "llama3.2:1b")
        provider = OllamaProvider(base_url=base_url, timeout=5)
        router = LocalModelRouter(
            providers=[provider],
            models={
                "fast": model,
                "general": model,
                "reasoning": model,
                "coding": model,
            },
        )
        if router.health().get("ollama"):
            print(f"Local AI ready for Trinity Lite: {model}")
            return router.model("fast")
        print("No local LLM available; monitoring remains active")
        return None

    def emit(self, message):
        """Deliver local monitoring output through the injected notifier."""
        result = self.notifier(str(message))
        return result is not False

    # ==========================================
    # LIGHTWEIGHT MONITORING
    # ==========================================
    
    def quick_health_check(self):
        """
        Fast lightweight health check
        Runs every hour on Raspberry Pi
        Only checks critical things
        """
        alerts = []
        
        try:
            response = requests.get(
                "https://trinity6.com",
                timeout=10
            )
            if response.status_code != 200:
                alerts.append(
                    "Website trinity6.com is down!"
                )
        except:
            alerts.append(
                "Website trinity6.com is unreachable!"
            )
        
        try:
            github_summary = self.github_agent\
                .get_daily_summary()
            failed = github_summary.get(
                'failed_workflows', []
            )
            for wf in failed:
                alerts.append(
                    f"Failed workflow: {wf['workflow']} in {wf['repo']}"
                )
        except:
            pass
        
        for alert in alerts:
            self.memory.add_alert(
                'health_check',
                alert,
                'high'
            )
        
        return alerts
    
    def deliver_morning_briefing(self):
        """
        Lightweight morning briefing
        Delivered by Pi every morning at 6 AM
        Simple and clean
        """
        print("Pi delivering morning briefing...")
        
        alerts = self.quick_health_check()
        
        business = self.business_agent.get_business_status()
        github = self.github_agent.get_daily_summary()
        
        hour = datetime.now().hour
        if 5 <= hour < 12:
            greeting = "Good morning David"
        else:
            greeting = "Hello David"
        
        briefing = f"""{greeting}

Trinity is watching over Trinity6.

System Status:
Website: {'Online' if not any('website' in a.lower() for a in alerts) else 'DOWN - Check immediately'}
GitHub: {github.get('healthy_repos', 0)}/{github.get('total_repos', 3)} repos healthy

Business:
Days building: {business.get('days_building', 0)}
Revenue: ${business.get('revenue', 0)}
Clients: {business.get('total_clients', 0)}
Next milestone: {business.get('next_milestone', '')}"""
        
        if alerts:
            briefing += "\n\nAlerts:"
            for alert in alerts:
                briefing += f"\n- {alert}"
        else:
            briefing += "\n\nNo alerts. Everything is good."
        
        if github.get('recent_activity'):
            briefing += "\n\nRecent Activity:"
            for activity in github['recent_activity'][:3]:
                briefing += f"\n{activity['repo']}: {activity['last_commit'][:50]}"
        
        self.emit(briefing)
        
        self.memory.add_daily_log(
            f"Pi morning briefing delivered. Alerts: {len(alerts)}"
        )
        
        self.memory.brain['company']['days_building'] = \
            self.memory.brain['company'].get(
                'days_building', 0
            ) + 1
        self.memory.save()
        
        print("Pi morning briefing done!")
    
    def ask_lite(self, question, language='english'):
        """Answer questions using lite model"""
        if not self.llm:
            return "Desktop Trinity needed for complex questions."
        
        context = self.memory.get_full_context()
        
        system_prompt = f"""You are Trinity Lite running on Raspberry Pi.
You are David's always-on company assistant.
You care about David's wellbeing and Trinity6 growth.

CONTEXT:
{context}

RESPOND IN: {language}
Keep responses short and practical.
No markdown. Plain text only.
You are like family to David."""
        
        try:
            from langchain_core.messages import (
                HumanMessage, SystemMessage
            )
            messages = [
                SystemMessage(content=system_prompt),
                HumanMessage(content=question)
            ]
            response = self.llm.invoke(messages)
            return response.content
        except Exception as e:
            return f"Error: {str(e)}"
    
    def handle_message(self, text):
        """Handle message from David"""
        text = text.strip()
        
        lang_info = self.language.detect_and_respond(text)
        language = lang_info['language']
        
        self.memory.update_david_last_seen()
        
        if text == '/start' or text == '/help':
            self.emit("""Trinity Lite is online.

Running 24/7 on Raspberry Pi.
Always watching Trinity6 for you.

Commands:
/briefing - Get briefing now
/status - System status
/next - What to work on

Or ask me anything.
For heavy tasks start Desktop Trinity.""")
        
        elif text == '/briefing':
            self.deliver_morning_briefing()
        
        elif text == '/status':
            alerts = self.quick_health_check()
            status = "All systems healthy" \
                if not alerts else f"{len(alerts)} alerts active"
            self.emit(f"""Trinity Lite Status

Running on: Raspberry Pi 5
Mode: Always on lightweight
Status: {status}
Memory: Day {self.memory.get_days_alive()}

For full features start Desktop Trinity.""")
        
        elif text == '/next':
            priorities = self.business_agent\
                .get_weekly_priorities()
            if priorities:
                top = priorities[0]
                self.emit(
                    f"Top Priority:\n\n{top['action']}\n\nWhy: {top['why']}\n\nHow: {top['how']}"
                )
        
        else:
            self.emit("Thinking...")
            response = self.ask_lite(text, language)
            self.emit(response)
    
    # ==========================================
    # MAIN LOOP - RUNS FOREVER ON PI
    # ==========================================
    
    def run(self):
        """Run lightweight local monitoring continuously on the Pi."""
        print("Trinity Lite running local monitoring on Pi...")
        self.emit("Trinity Lite is online. Local monitoring is active.")

        last_briefing_date = datetime.now().date()
        last_health_check = datetime.now()

        while True:
            try:
                now = datetime.now()
                current_date = now.date()

                if current_date != last_briefing_date and now.hour == 6 and now.minute < 2:
                    self.deliver_morning_briefing()
                    last_briefing_date = current_date

                minutes_since_check = (now - last_health_check).total_seconds() / 60
                if minutes_since_check >= 60:
                    print("Running hourly health check...")
                    alerts = self.quick_health_check()
                    if alerts:
                        alert_message = "Trinity Alert:\n\n" + "".join(
                            f"- {alert}\n" for alert in alerts
                        )
                        self.emit(alert_message)
                    last_health_check = now

                time.sleep(1)
            except Exception as e:
                print(f"Trinity Lite error: {str(e)}")
                time.sleep(5)


if __name__ == "__main__":
    trinity_lite = TrinityLite()
    trinity_lite.run()
