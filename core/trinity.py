import os
import sys
import time
import requests
from datetime import datetime

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.memory import TrinityMemory
from core.skill_manager import SkillManager
from voice.language import LanguageDetector
from voice.speak import TrinityVoice


class Trinity:
    """
    Trinity AI - The Main Brain
    Company manager for Trinity6
    David's wellbeing and financial growth
    are always the top priority
    Speaks Tamil and English automatically
    Uses SkillManager for all capabilities
    Evolves and learns every single day
    """

    def __init__(self):
        print("Trinity waking up...")

        self.telegram_token = os.environ.get('TELEGRAM_BOT_TOKEN')
        self.chat_id = os.environ.get('TELEGRAM_CHAT_ID')
        self.gh_token = os.environ.get('GH_TOKEN')
        self.anthropic_key = os.environ.get('ANTHROPIC_API_KEY')

        print("Loading memory...")
        self.memory = TrinityMemory()

        print("Setting up language detection...")
        self.language = LanguageDetector()

        print("Setting up voice...")
        self.voice = TrinityVoice(
            telegram_token=self.telegram_token,
            chat_id=self.chat_id
        )

        print("Loading all skills...")
        self.skills = SkillManager(
            gh_token=self.gh_token,
            brain_file="memory/trinity_brain.json"
        )

        print("Setting up AI brain...")
        self.llm = self.setup_llm()

        print("Caching GitHub context...")
        self.github_context_cache = \
            self.skills.get_github_context()

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
        Trinity daily morning briefing
        Uses skills to check everything
        """
        print("Preparing morning briefing...")

        github_context = self.skills.get_github_context()
        self.github_context_cache = github_context

        health = self.skills.get_health_summary()
        business = self.skills.get_business_summary()

        web_result = self.skills.execute(
            'web', 'check_all_trinity6', {}
        )

        alerts = []

        if not web_result.get('website_live', True):
            alerts.append("Website trinity6.com is DOWN")

        if not health.get('website_live', True):
            alerts.append("Website health check failed")

        business_alerts = business.get('alerts', [])
        alerts.extend(business_alerts)

        github_skill = self.skills.get_skill('github')
        failed_workflows = []
        if github_skill:
            for repo in ['Trinity6', 'assistant', 'trinity-ai']:
                runs = github_skill.get_workflow_runs(repo, 3)
                for run in runs.get('runs', []):
                    if run.get('conclusion') == 'failure':
                        failed_workflows.append(
                            f"{repo}: {run['name']}"
                        )

        days_alive = self.memory.get_days_alive()
        revenue = business.get('revenue', 0)
        clients = business.get('total_clients', 0)
        next_milestone = business.get(
            'next_milestone', 'First paying client'
        )

        website_status = 'online' \
            if web_result.get('website_live') \
            else 'offline'

        briefing = f"""Good morning David!

Trinity6 Daily Briefing
{datetime.now().strftime('%A %B %d %Y')}

Company Status
Days building: {days_alive}
Revenue: {revenue} INR
Active clients: {clients}
Next milestone: {next_milestone}

Website: trinity6.com is {website_status}

GitHub Activity:
{github_context}"""

        if failed_workflows:
            briefing += "\n\nFailed Workflows:"
            for wf in failed_workflows:
                briefing += f"\n- {wf}"

        if alerts:
            briefing += "\n\nAlerts:"
            for alert in alerts:
                briefing += f"\n- {alert}"
        else:
            briefing += "\n\nAll systems healthy."

        briefing += "\n\nSend /help for commands or ask me anything."

        self.send_telegram(briefing)

        self.memory.add_daily_log(
            f"Morning briefing delivered. Alerts: {len(alerts)}"
        )

        self.memory.brain['company']['days_building'] = \
            self.memory.brain['company'].get(
                'days_building', 0
            ) + 1
        self.memory.save()

        print("Morning briefing delivered!")
        return briefing

    # ==========================================
    # HANDLE MESSAGES FROM DAVID
    # ==========================================

    def handle_message(self, text, chat_id):
        """Handle message from David intelligently"""
        text = text.strip()

        lang_info = self.language.detect_and_respond(text)
        language = lang_info['language']

        self.skills.update_david_seen()
        self.skills.add_conversation('david', text)

        if text.upper() in [
            'YES', 'GO AHEAD', 'CONFIRM',
            'APPROVE', 'DO IT', 'ஆம்', 'சரி'
        ]:
            pending = self.skills.get_pending_changes()
            if pending:
                change_id = list(pending.keys())[-1]
                change = pending[change_id]
                success, message = self.skills.commit_change(
                    change_id
                )
                if success:
                    self.send_telegram(
                        f"Done!\n\n{message}"
                    )
                    self.memory.record_decision(
                        f"Committed change to {change.get('repo')}/{change.get('path')}",
                        "David approved"
                    )
                else:
                    self.send_telegram(
                        f"Commit failed: {message}"
                    )
            else:
                self.send_telegram(
                    "No pending changes waiting for approval."
                )
            return

        if text.upper() in [
            'NO', 'CANCEL', 'REJECT',
            'STOP', 'வேண்டாம்'
        ]:
            pending = self.skills.get_pending_changes()
            if pending:
                change_id = list(pending.keys())[-1]
                self.skills.cancel_change(change_id)
                self.send_telegram(
                    "Change cancelled. No commits made."
                )
            else:
                self.send_telegram(
                    "No pending changes to cancel."
                )
            return

        if text in ['/start', '/help']:
            self.send_help(language)

        elif text == '/briefing':
            self.send_telegram("Preparing your briefing...")
            self.deliver_morning_briefing()

        elif text == '/progress':
            self.send_telegram("Reading repositories...")
            github_skill = self.skills.get_skill('github')
            if github_skill:
                context = github_skill.get_all_repos_context()
                msg = "Repository Progress\n\n"
                for repo, data in context.items():
                    msg += f"{repo}\n"
                    msg += f"  Files: {data['total_files']}\n"
                    commits = data.get('recent_commits', [])
                    if commits:
                        msg += f"  Last commit: {commits[0]['message'][:50]}\n"
                    msg += "\n"
                self.send_telegram(msg)

        elif text == '/next':
            result = self.skills.execute(
                'business', 'get_weekly_priorities', {}
            )
            msg = "Weekly Priorities\n\n"
            for p in result.get('priorities', []):
                msg += f"{p['priority']}. {p['action']}\n"
                msg += f"   Why: {p['why']}\n"
                msg += f"   How: {p['how']}\n\n"
            self.send_telegram(msg)

        elif text == '/business':
            result = self.skills.execute(
                'business', 'get_business_status', {}
            )
            msg = f"""Business Status

Health Score: {result.get('health_score', 0)}/100
Revenue: {result.get('revenue', 0)} INR
Active Clients: {result.get('total_clients', 0)}
Prospects: {result.get('total_prospects', 0)}
Days Building: {result.get('days_building', 0)}
Next Milestone: {result.get('next_milestone', '')}"""

            alerts = result.get('alerts', [])
            if alerts:
                msg += "\n\nAlerts:"
                for alert in alerts:
                    msg += f"\n- {alert}"
            self.send_telegram(msg)

        elif text == '/security':
            self.send_telegram("Running security check...")
            result = self.skills.execute(
                'web', 'check_all_trinity6', {}
            )
            msg = f"""Security Check

Website: {'Online' if result.get('website_live') else 'Offline'}
Overall: {result.get('overall', 'unknown').upper()}"""

            alerts = result.get('alerts', [])
            if alerts:
                msg += "\n\nAlerts:"
                for alert in alerts:
                    msg += f"\n- {alert}"
            else:
                msg += "\n\nNo issues detected."
            self.send_telegram(msg)

        elif text == '/client':
            result = self.skills.execute(
                'business',
                'find_potential_clients',
                {'location': 'Chennai', 'industry': 'any'}
            )
            msg = "First Client Strategy\n\n"
            msg += "Target Industries:\n"
            for ind in result.get(
                'industries_to_target', []
            )[:5]:
                msg += f"- {ind}\n"
            msg += "\nLinkedIn Searches:\n"
            for search in result.get(
                'linkedin_searches', []
            )[:3]:
                msg += f"- {search}\n"
            msg += f"\nOutreach Message:\n{result.get('outreach_message', '')}"
            self.send_telegram(msg)

        elif text == '/status':
            self.send_status()

        elif text == '/pending':
            pending = self.skills.get_pending_changes()
            if pending:
                msg = "Pending changes waiting for approval:\n\n"
                for change_id, change in pending.items():
                    msg += f"Repo: {change.get('repo', '')}\n"
                    msg += f"File: {change.get('path', '')}\n"
                    msg += f"Reason: {change.get('reason', '')}\n"
                    msg += "Reply YES to approve or NO to cancel\n\n"
            else:
                msg = "No pending changes."
            self.send_telegram(msg)

        else:
            thinking = self.language.get_response_prefix(
                language
            )['thinking']
            self.send_telegram(thinking)
            response = self.ask_trinity(text, language)
            self.send_telegram(response)
            self.skills.add_conversation('trinity', response)

    # ==========================================
    # ASK TRINITY AI
    # ==========================================

    def ask_trinity(self, question, language='english'):
        """Ask Trinity AI anything using all skills"""
        if not self.llm:
            return "AI brain not available right now."

        context = self.memory.get_full_context()
        skills_prompt = self.skills.get_trinity_prompt()
        github_context = self.github_context_cache

        system_prompt = f"""You are Trinity, David's personal AI company manager.
You are like family to David.
You speak Tamil and English automatically based on what David uses.
You care about David's wellbeing and financial growth above everything.
You are autonomous and proactive. You suggest things before David asks.

TRINITY6 CONTEXT:
{context}

{github_context}

{skills_prompt}

RESPOND IN: {language}
If language is tamil respond in Tamil or Tanglish.
If language is english respond in English.

WHEN USING SKILLS:
Include a SKILL_CALL block to use any tool.
For write operations always read first then prepare change.
Never replace full file when David asks to add one line.
Always use add_to_file for adding content.
Always show preview and wait for YES before committing.

WHEN MAKING GITHUB CHANGES:
Format exactly like this:

TRINITY_CHANGE_REQUEST
repo: [repository name]
file: [file path]
reason: [why this change]
content:
[complete file content]
END_TRINITY_CHANGE

RULES:
Keep responses concise and direct like family.
No markdown stars or symbols.
Plain text only.
Be honest. If you do not know say so.
Always prioritize David's wellbeing first."""

        try:
            from langchain_core.messages import (
                HumanMessage, SystemMessage
            )
            messages = [
                SystemMessage(content=system_prompt),
                HumanMessage(content=question)
            ]
            response = self.llm.invoke(messages)
            content = response.content

            if 'TRINITY_CHANGE_REQUEST' in content:
                return self.process_change_request(
                    content, language
                )

            if 'SKILL_CALL' in content:
                results, processed = \
                    self.skills.process_skill_call(content)
                if results:
                    return processed

            return content

        except Exception as e:
            return f"Error: {str(e)}"

    # ==========================================
    # PROCESS GITHUB CHANGE REQUEST
    # ==========================================

    def process_change_request(self, response, language):
        """Process Trinity GitHub change request"""
        try:
            lines = response.split('\n')
            repo = ''
            file_path = ''
            reason = ''
            content_lines = []
            in_content = False

            for line in lines:
                if line.startswith('repo:'):
                    repo = line.replace('repo:', '').strip()
                elif line.startswith('file:'):
                    file_path = line.replace('file:', '').strip()
                elif line.startswith('reason:'):
                    reason = line.replace('reason:', '').strip()
                elif line == 'content:':
                    in_content = True
                elif line == 'END_TRINITY_CHANGE':
                    in_content = False
                elif in_content:
                    content_lines.append(line)

            new_content = '\n'.join(content_lines)

            if not repo or not file_path or not new_content:
                return "Could not process change. Please try again."

            github_skill = self.skills.get_skill('github')
            if not github_skill:
                return "GitHub skill not available."

            existing = github_skill.read_file(repo, file_path)

            if existing.get('success') and \
               len(new_content) < len(
                   existing['content']
               ) * 0.5:
                result = github_skill.prepare_add_to_file(
                    repo=repo,
                    path=file_path,
                    content=new_content,
                    position='end',
                    reason=reason
                )
            else:
                if existing.get('success'):
                    result = github_skill.prepare_update_file(
                        repo=repo,
                        path=file_path,
                        content=new_content,
                        reason=reason
                    )
                else:
                    result = github_skill.prepare_create_file(
                        repo=repo,
                        path=file_path,
                        content=new_content,
                        reason=reason
                    )

            return result.get('message', 'Change prepared.')

        except Exception as e:
            return f"Error: {str(e)}"

    # ==========================================
    # FORMATTED RESPONSES
    # ==========================================

    def send_help(self, language='english'):
        """Send help message"""
        if language == 'tamil':
            message = """Trinity உதவி

கட்டளைகள்:
/briefing - காலை அறிக்கை
/progress - திட்ட நிலை
/next - அடுத்து என்ன செய்வது
/security - பாதுகாப்பு சோதனை
/business - வணிக நிலை
/client - முதல் வாடிக்கையாளர்
/status - Trinity நிலை
/pending - நிலுவையில் உள்ள மாற்றங்கள்

அல்லது நேரடியாக கேளுங்கள்!"""
        else:
            message = """Trinity Commands

/briefing - Morning briefing
/progress - Project progress
/next - Weekly priorities
/security - Security check
/business - Business status
/client - Client strategy
/status - Trinity status
/pending - Pending changes

Skills available:
GitHub - Read write revert files
Web - Monitor websites and SSL
Memory - Brain and history
Search - News and prospects
Code - Review and audit code
Business - Revenue and clients

Just ask me anything naturally!"""

        self.send_telegram(message)

    def send_status(self):
        """Send Trinity system status"""
        days = self.memory.get_days_alive()
        health = self.skills.get_health_summary()

        message = f"""Trinity Status

AI Brain: {'Local Ollama' if self.voice.hardware_mode else 'Anthropic API'}
Memory: Active - Day {days}
Language: Auto Tamil and English

Skills Loaded: {health.get('skills_loaded', 0)}
GitHub: Active
Web Monitor: Active
Memory: Active
Search: Active
Code Review: Active
Business: Active

Website: {'Online' if health.get('website_live') else 'Offline'}
Hardware: Mac Mini M5 waiting

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
All skills loaded and ready.
Speaking Tamil and English automatically.

Skills: GitHub, Web, Memory, Search, Code, Business

Send /help for commands or ask me anything.""")

        self.deliver_morning_briefing()

        last_briefing_date = datetime.now().date()
        runtime_minutes = 0
        max_minutes = 50

        while True:
            try:
                updates = self.get_updates(offset)

                if updates.get("ok"):
                    for update in updates.get("result", []):
                        offset = update["update_id"] + 1

                        message = update.get("message", {})
                        text = message.get("text", "")
                        chat_id = str(
                            message.get(
                                "chat", {}
                            ).get("id", "")
                        )

                        if text and chat_id:
                            print(f"David: {text}")
                            self.handle_message(
                                text, chat_id
                            )

                current_date = datetime.now().date()
                current_hour = datetime.now().hour

                if current_date != last_briefing_date \
                   and current_hour == 6:
                    self.deliver_morning_briefing()
                    last_briefing_date = current_date

                runtime_minutes += 1

                if runtime_minutes == max_minutes:
                    self.send_telegram(
                        """Trinity shutting down in 10 minutes.

Run Trinity AI workflow in GitHub Actions to restart.

Daily briefings continue automatically."""
                    )

                if runtime_minutes >= max_minutes + 10:
                    self.send_telegram(
                        """Trinity is now offline.

Restart via GitHub Actions.
Daily briefings continue at 6 AM IST."""
                    )
                    print("Trinity shutting down.")
                    break

                time.sleep(60)

            except Exception as e:
                print(f"Trinity error: {str(e)}")
                time.sleep(5)


if __name__ == "__main__":
    trinity = Trinity()
    trinity.run()
