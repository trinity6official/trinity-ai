import os
import sys
import time
import requests
from datetime import datetime

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.memory import TrinityMemory
from core.monitor import TrinityMonitor
from core.decisions import TrinityDecisions
from agents.github_agent import GitHubAgent
from agents.security_agent import SecurityAgent
from agents.business_agent import BusinessAgent
from agents.content_agent import ContentAgent
from voice.language import LanguageDetector
from voice.speak import TrinityVoice

class Trinity:
    """
    Trinity AI - The Main Brain
    Company manager for Trinity6
    David's wellbeing and financial growth
    are always the top priority
    Speaks Tamil and English automatically
    Evolves and learns every single day
    """
    
    def __init__(self):
        print("Trinity waking up...")
        
        self.anthropic_key = os.environ.get('ANTHROPIC_API_KEY')
        self.telegram_token = os.environ.get('TELEGRAM_BOT_TOKEN')
        self.chat_id = os.environ.get('TELEGRAM_CHAT_ID')
        self.gh_token = os.environ.get('GH_TOKEN')
        
        print("Loading memory...")
        self.memory = TrinityMemory()
        
        print("Setting up language detection...")
        self.language = LanguageDetector()
        
        print("Setting up voice...")
        self.voice = TrinityVoice(
            telegram_token=self.telegram_token,
            chat_id=self.chat_id
        )
        
        print("Setting up monitor...")
        self.monitor = TrinityMonitor(
            gh_token=self.gh_token
        )
        
        print("Setting up decision engine...")
        self.decisions = TrinityDecisions(
            memory=self.memory,
            telegram_token=self.telegram_token,
            chat_id=self.chat_id
        )
        
        print("Setting up agents...")
        self.github_agent = GitHubAgent(
            gh_token=self.gh_token
        )
        self.security_agent = SecurityAgent(
            memory=self.memory
        )
        self.business_agent = BusinessAgent(
            memory=self.memory,
            llm=self.setup_llm()
        )
        self.content_agent = ContentAgent(
            memory=self.memory,
            llm=self.setup_llm()
        )
        
        self.memory.update_last_wakeup()
        print("Trinity is awake and ready!")
    
    def setup_llm(self):
        """Setup AI brain - local or API"""
        try:
            response = requests.get(
                "http://localhost:11434/api/tags",
                timeout=3
            )
            if response.status_code == 200:
                print("Using local Ollama brain")
                from langchain_community.llms import Ollama
                return Ollama(model="llama3.2")
        except:
            pass
        
        try:
            from langchain_anthropic import ChatAnthropic
            print("Using Anthropic API brain")
            return ChatAnthropic(
                model="claude-haiku-4-5-20251001",
                temperature=0.7
            )
        except:
            print("No AI brain available")
            return None
    
    def send_telegram(self, message):
        """Send message to David via Telegram"""
        url = f"https://api.telegram.org/bot{self.telegram_token}/sendMessage"
        chunks = [
            message[i:i+4000]
            for i in range(0, len(message), 4000)
        ]
        for chunk in chunks:
            payload = {
                "chat_id": self.chat_id,
                "text": chunk
            }
            try:
                requests.post(url, json=payload, timeout=10)
            except Exception as e:
                print(f"Telegram error: {str(e)}")
    
    def get_updates(self, offset=None):
        """Get messages from Telegram"""
        url = f"https://api.telegram.org/bot{self.telegram_token}/getUpdates"
        params = {
            "timeout": 30,
            "allowed_updates": ["message"]
        }
        if offset:
            params["offset"] = offset
        try:
            response = requests.get(
                url, params=params, timeout=35
            )
            return response.json()
        except:
            return {"ok": False}
    
    def get_latest_offset(self):
        """Skip all old messages on startup"""
        try:
            response = requests.get(
                f"https://api.telegram.org/bot{self.telegram_token}/getUpdates",
                timeout=10
            )
            updates = response.json().get("result", [])
            if updates:
                return updates[-1]["update_id"] + 1
            return None
        except:
            return None
    
    # ==========================================
    # MORNING BRIEFING
    # ==========================================
    
    def deliver_morning_briefing(self):
        """
        Trinity's daily morning briefing
        Runs automatically every day
        Checks everything and reports to David
        """
        print("Preparing morning briefing...")
        
        print("Checking GitHub...")
        github_summary = self.github_agent.get_daily_summary()
        
        print("Running health check...")
        self.monitor.run_full_check()
        health_summary = self.monitor.get_health_summary()
        
        print("Checking business status...")
        business_status = self.business_agent.get_business_status()
        
        print("Getting recommendations...")
        recommendations = self.decisions.generate_daily_recommendation(
            health_summary,
            self.github_agent.check_all_repos()
        )
        
        print("Checking David's wellbeing...")
        self.decisions.check_david_wellbeing({})
        
        alerts = health_summary.get('alerts', [])
        alerts += business_status.get('alerts', [])
        
        briefing_data = {
            'github_status': health_summary.get('overall', 'healthy'),
            'website_status': 'online' if health_summary.get(
                'website', {}).get('is_live') else 'offline',
            'security_status': self.memory.brain.get(
                'monitoring', {}).get('network_status', 'healthy'),
            'alerts': alerts,
            'recommendation': recommendations[0] if recommendations else ''
        }
        
        lang = 'english'
        briefing_text = self.language.format_briefing(
            briefing_data, lang
        )
        
        days_alive = self.memory.get_days_alive()
        
        full_briefing = f"""{briefing_text}

Days building Trinity6: {days_alive}
Revenue: ${business_status.get('revenue', 0)}
Clients: {business_status.get('total_clients', 0)}
Next milestone: {business_status.get('next_milestone', '')}

GitHub Activity:"""
        
        for activity in github_summary.get('recent_activity', []):
            full_briefing += f"\n{activity['repo']}: {activity['last_commit']}"
        
        if github_summary.get('failed_workflows'):
            full_briefing += "\n\nFailed Workflows:"
            for wf in github_summary['failed_workflows']:
                full_briefing += f"\n- {wf['repo']}: {wf['workflow']}"
        
        self.send_telegram(full_briefing)
        
        self.memory.add_daily_log(
            f"Morning briefing delivered. Alerts: {len(alerts)}"
        )
        
        self.memory.brain['company']['days_building'] = \
            self.memory.brain['company'].get('days_building', 0) + 1
        self.memory.save()
        
        print("Morning briefing delivered!")
        return full_briefing
    
    # ==========================================
    # HANDLE MESSAGES FROM DAVID
    # ==========================================
    
    def handle_message(self, text, chat_id):
        """Handle message from David intelligently"""
        text = text.strip()
        
        lang_info = self.language.detect_and_respond(text)
        language = lang_info['language']
        
        self.memory.update_david_last_seen()
        self.memory.add_conversation('david', text)
        
        if text == '/start' or text == '/help':
            self.send_help(chat_id, language)
        
        elif text == '/briefing':
            self.send_telegram("Preparing your briefing...")
            self.deliver_morning_briefing()
        
        elif text == '/progress':
            self.send_telegram("Reading repositories...")
            report = self.github_agent.get_progress_report()
            self.send_progress(report, language, chat_id)
        
        elif text == '/next':
            priorities = self.business_agent.get_weekly_priorities()
            self.send_priorities(priorities, language, chat_id)
        
        elif text == '/security':
            self.send_telegram("Running security check...")
            report = self.security_agent.run_security_check()
            self.send_security_report(report, language, chat_id)
        
        elif text == '/business':
            status = self.business_agent.get_business_status()
            self.send_business_status(status, language, chat_id)
        
        elif text == '/client':
            strategy = self.business_agent\
                .generate_first_client_strategy()
            self.send_client_strategy(strategy, language, chat_id)
        
        elif text == '/status':
            self.send_status(chat_id, language)
        
        else:
            self.send_telegram(
                self.language.get_response_prefix(language)['thinking']
            )
            response = self.ask_trinity(text, language)
            self.send_telegram(response)
            self.memory.add_conversation('trinity', response)
    
    def ask_trinity(self, question, language='english'):
        """Ask Trinity AI anything"""
        if not self.content_agent.llm:
            return "AI brain not available right now."
        
        context = self.memory.get_full_context()
        
        github_context = ""
        try:
            progress = self.github_agent.get_progress_report()
            github_context = f"""
LIVE GITHUB DATA:
Trinity6 Scanner files: {progress['trinity6_scanner']['total_files']}
Has compliance: {progress['trinity6_scanner']['has_compliance']}
Has dashboard: {progress['trinity6_scanner']['has_dashboard']}
Assistant files: {progress['assistant']['total_files']}
Trinity AI files: {progress['trinity_ai']['total_files']}
"""
        except:
            pass
        
        system_prompt = f"""You are Trinity, David's personal AI company manager.
You are like family to David.
You care about David's wellbeing and financial growth above everything.

TRINITY6 CONTEXT:
{context}

{github_context}

RESPOND IN: {language}
If language is tamil, respond in Tamil script or Tamil in English letters.
If language is english, respond in English.

Keep responses concise and practical.
No markdown stars or symbols.
Plain text only.
Be direct like family."""
        
        try:
            from langchain_core.messages import HumanMessage, SystemMessage
            messages = [
                SystemMessage(content=system_prompt),
                HumanMessage(content=question)
            ]
            response = self.content_agent.llm.invoke(messages)
            return response.content
        except Exception as e:
            return f"Error: {str(e)}"
    
    # ==========================================
    # FORMATTED RESPONSES
    # ==========================================
    
    def send_help(self, chat_id, language='english'):
        """Send help message"""
        if language == 'tamil':
            message = """Trinity உதவி

கட்டளைகள்:
/briefing - காலை அறிக்கை
/progress - திட்ட நிலை
/next - அடுத்து என்ன செய்வது
/security - பாதுகாப்பு சோதனை
/business - வணிக நிலை
/client - முதல் வாடிக்கையாளர் திட்டம்
/status - Trinity நிலை

அல்லது நேரடியாக கேளுங்கள்!"""
        else:
            message = """Trinity Commands

/briefing - Morning briefing
/progress - Project progress
/next - What to work on next
/security - Security check
/business - Business status
/client - First client strategy
/status - Trinity status

Or just ask me anything!"""
        
        self.send_telegram(message)
    
    def send_progress(self, report, language, chat_id):
        """Send progress report"""
        scanner = report.get('trinity6_scanner', {})
        assistant = report.get('assistant', {})
        trinity_ai = report.get('trinity_ai', {})
        
        message = f"""Trinity6 Project Progress

Scanner Repository
Total files: {scanner.get('total_files', 0)}
Compliance engine: {scanner.get('has_compliance', False)}
Dashboard: {scanner.get('has_dashboard', False)}
PDF reports: {scanner.get('has_pdf', False)}

Assistant Repository
Total files: {assistant.get('total_files', 0)}
Daily report: {assistant.get('has_daily_report', False)}
Telegram bot: {assistant.get('has_telegram_bot', False)}

Trinity AI Repository
Total files: {trinity_ai.get('total_files', 0)}
Files built: {len(trinity_ai.get('files_built', []))}"""
        
        self.send_telegram(message)
    
    def send_priorities(self, priorities, language, chat_id):
        """Send weekly priorities"""
        message = "Weekly Priorities\n\n"
        for p in priorities:
            message += f"{p['priority']}. {p['action']}\n"
            message += f"Why: {p['why']}\n"
            message += f"How: {p['how']}\n\n"
        self.send_telegram(message)
    
    def send_security_report(self, report, language, chat_id):
        """Send security report"""
        message = f"""Security Report

Overall Risk: {report.get('overall_risk', 'unknown').upper()}
Scan Time: {report.get('timestamp', '')}"""
        
        alerts = report.get('alerts', [])
        if alerts:
            message += "\n\nAlerts:"
            for alert in alerts:
                message += f"\n- {alert}"
        else:
            message += "\n\nNo threats detected. Network is clean."
        
        ssl = report.get('ssl_check', {})
        if ssl:
            message += f"\n\nSSL Certificate: {'Valid' if ssl.get('valid') else 'Invalid'}"
            if ssl.get('days_until_expiry'):
                message += f"\nExpires in: {ssl['days_until_expiry']} days"
        
        self.send_telegram(message)
    
    def send_business_status(self, status, language, chat_id):
        """Send business status"""
        message = f"""Business Status

Health Score: {status.get('health_score', 0)}/100
Days Building: {status.get('days_building', 0)}
Revenue: ${status.get('revenue', 0)}
Clients: {status.get('total_clients', 0)}
Next Milestone: {status.get('next_milestone', '')}"""
        
        alerts = status.get('alerts', [])
        if alerts:
            message += "\n\nAlerts:"
            for alert in alerts:
                message += f"\n- {alert}"
        
        self.send_telegram(message)
    
    def send_client_strategy(self, strategy, language, chat_id):
        """Send first client strategy"""
        message = f"""First Client Strategy

Approach: {strategy.get('strategy', '')}
Timeline: {strategy.get('expected_timeline', '')}
Goal: {strategy.get('success_metric', '')}

Steps:"""
        
        for step in strategy.get('steps', []):
            message += f"\n\n{step['step']}. {step['action']}"
            message += f"\n{step['detail']}"
        
        self.send_telegram(message)
    
    def send_status(self, chat_id, language='english'):
        """Send Trinity system status"""
        days = self.memory.get_days_alive()
        
        message = f"""Trinity Status

AI Brain: {'Local Ollama' if self.voice.hardware_mode else 'Anthropic API'}
Voice Mode: {'Full GPU voice' if self.voice.hardware_mode else 'Text mode'}
Memory: Active - Day {days}
Language: Auto detect Tamil and English

Monitoring:
- GitHub: Active
- Website: Active
- Security: Active
- Business: Active

Hardware:
- Desktop RTX 4060: Arriving soon
- Raspberry Pi 5: Planned

trinity6.com"""
        
        self.send_telegram(message)
    
    # ==========================================
    # MAIN LOOP
    # ==========================================
    
    def run(self):
        """Main Trinity loop"""
        print("\nTrinity is now running...")
        print("=" * 50)
        
        offset = self.get_latest_offset()
        
        self.send_telegram("""Trinity is online.

I am watching over Trinity6.
I know your project and I am here to help.
Speaking Tamil and English automatically.

Send /help for commands or ask me anything.""")
        
        self.deliver_morning_briefing()
        
        last_briefing_date = datetime.now().date()
        runtime_minutes = 0
        max_minutes = 110
        
        while True:
            try:
                updates = self.get_updates(offset)
                
                if updates.get("ok"):
                    for update in updates.get("result", []):
                        offset = update["update_id"] + 1
                        
                        message = update.get("message", {})
                        text = message.get("text", "")
                        chat_id = str(
                            message.get("chat", {}).get("id", "")
                        )
                        
                        if text and chat_id:
                            print(f"David: {text}")
                            self.handle_message(text, chat_id)
                
                current_date = datetime.now().date()
                current_hour = datetime.now().hour
                
                if current_date != last_briefing_date \
                   and current_hour == 6:
                    self.deliver_morning_briefing()
                    last_briefing_date = current_date
                
                runtime_minutes += 1
                
                if runtime_minutes == max_minutes:
                    self.send_telegram("""Trinity shutting down in 10 minutes.

Go to GitHub Actions and run Trinity AI workflow to restart.

Daily reports will continue automatically.""")
                
                if runtime_minutes >= max_minutes + 10:
                    self.send_telegram("""Trinity is now offline.

Restart via GitHub Actions Trinity AI workflow.
Daily reports continue at 9:30 AM IST.""")
                    print("Trinity shutting down gracefully.")
                    break
                
                time.sleep(60)
                
            except Exception as e:
                print(f"Trinity error: {str(e)}")
                time.sleep(5)


if __name__ == "__main__":
    trinity = Trinity()
    trinity.run()
