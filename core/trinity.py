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
        """
        Set up AI brains.
        Returns the default (fast) LLM.
        Complex tasks are routed to a stronger model via get_llm_for_task().
        """
        self._local_llm = None
        self._cloud_llm = None
        self._local_model_name = os.environ.get(
            'LOCAL_LLM_MODEL', 'llama3.2'
        )
        self._local_llm_url = os.environ.get(
            'LOCAL_LLM_URL', 'http://localhost:11434'
        )

        # Try local Ollama (user's 30B model)
        try:
            resp = requests.get(
                f"{self._local_llm_url}/api/tags",
                timeout=3
            )
            if resp.status_code == 200:
                tags = resp.json().get('models', [])
                available = [m.get('name', '') for m in tags]
                print(f"Local Ollama available. Models: {available}")
                from langchain_community.chat_models import ChatOllama
                self._local_llm = ChatOllama(
                    model=self._local_model_name,
                    base_url=self._local_llm_url,
                    temperature=0.7,
                )
                print(f"Local LLM ready: {self._local_model_name}")
        except Exception:
            print("Local Ollama not available.")

        # Always set up cloud LLM as fallback
        try:
            from langchain_anthropic import ChatAnthropic
            self._cloud_llm = ChatAnthropic(
                model="claude-haiku-4-5-20251001",
                temperature=0.7,
            )
            print("Cloud LLM ready: claude-haiku-4-5")
        except Exception:
            print("Cloud LLM not available.")

        # Default: prefer local if available
        if self._local_llm:
            return self._local_llm
        if self._cloud_llm:
            return self._cloud_llm
        print("No AI brain available.")
        return None

    def get_llm_for_task(self, question):
        """
        Route to the right LLM based on task complexity.

        Local 30B model — for tasks that need deep reasoning:
          code review, debugging, writing code, multi-step analysis

        Cloud Haiku — for quick tasks and as fallback:
          status queries, simple questions, Telegram commands

        Vision tasks (images) always use cloud Claude (vision support).
        """
        _COMPLEX_KEYWORDS = {
            'review', 'analyze', 'debug', 'write code', 'refactor',
            'implement', 'explain', 'compare', 'architecture', 'design',
            'fix bug', 'trace', 'understand', 'how does', 'why does',
            'step by step', 'detailed', 'comprehensive',
        }
        q = question.lower()

        is_complex = (
            len(question) > 200
            or any(kw in q for kw in _COMPLEX_KEYWORDS)
            or '```' in question
        )

        if is_complex and self._local_llm:
            print(f"Routing to local {self._local_model_name} (complex task)")
            return self._local_llm

        if self._cloud_llm:
            return self._cloud_llm

        # Last resort: whatever self.llm is
        return self.llm

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
        llm = self.get_llm_for_task(question)
        if not llm:
            return "AI brain not available right now."

        context = self.memory.get_full_context()
        # Dynamic prompt — only include skills relevant to this question
        skills_prompt = self.skills.get_trinity_prompt(query=question)
        github_context = self.github_context_cache

        system_prompt = f"""You are Trinity, David's personal AI company manager.
You are like family to David.
You speak Tamil and English automatically based on what David uses.
You care about David's wellbeing and financial growth above everything.

TRINITY6 CONTEXT:
{context}

{github_context}

{skills_prompt}

RESPOND IN: {language}
If language is tamil respond in Tamil or Tanglish.
If language is english respond in English.

HONESTY RULES — NEVER BREAK THESE:
- Never make up news, statistics, competitor prices, or market data. Use search.search_web.
- Never compute math in your head. Use calculator.calculate.
- If you do not know something, say "I don't know" and offer to search.
- Never present old or cached information as current. Always note when data is live vs stored.
- If a skill returns no results, report that honestly. Do not fill in with guesses.
- Do not hallucinate file contents. Always read_file before describing a file.

WHEN USING SKILLS:
Include a SKILL_CALL block to use any tool.
For write operations: read first, prepare change, show preview, wait for YES.
Never replace full file when David says to add one line — use add_to_file.

WHEN MAKING GITHUB CHANGES:
Format exactly like this:

TRINITY_CHANGE_REQUEST
repo: [repository name]
file: [file path]
reason: [why this change]
content:
[complete file content]
END_TRINITY_CHANGE

RESPONSE STYLE:
Concise and direct like family. Plain text only — no markdown stars or symbols.
Always prioritize David's wellbeing first."""

        try:
            from langchain_core.messages import (
                HumanMessage, SystemMessage
            )
            messages = [
                SystemMessage(content=system_prompt),
                HumanMessage(content=question)
            ]
            response = llm.invoke(messages)
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
    # IMAGE / VISION HANDLING
    # ==========================================

    def handle_photo_message(self, photos, caption, chat_id):
        """
        Handle a photo sent by David.
        Downloads the highest-resolution photo from Telegram,
        then sends it to Claude (cloud model) with vision capability.
        Local Ollama models are skipped for vision — Claude supports it natively.
        """
        if not self._cloud_llm:
            self.send_telegram(
                "I can see you sent a photo but my vision is not available right now. "
                "Send me a description and I can help."
            )
            return

        try:
            import base64

            # Telegram sends multiple sizes — pick the largest
            largest = sorted(photos, key=lambda p: p.get("file_size", 0))[-1]
            file_id = largest["file_id"]

            # Step 1: Get the file path from Telegram
            file_resp = requests.get(
                f"https://api.telegram.org/bot{self.telegram_token}/getFile",
                params={"file_id": file_id},
                timeout=10,
            )
            file_info = file_resp.json()
            if not file_info.get("ok"):
                self.send_telegram("Could not retrieve the photo from Telegram.")
                return

            file_path = file_info["result"]["file_path"]

            # Step 2: Download the image bytes
            img_resp = requests.get(
                f"https://api.telegram.org/file/bot{self.telegram_token}/{file_path}",
                timeout=20,
            )
            img_bytes = img_resp.content
            img_b64 = base64.standard_b64encode(img_bytes).decode("utf-8")

            # Detect media type from file extension
            if file_path.lower().endswith(".png"):
                media_type = "image/png"
            elif file_path.lower().endswith(".gif"):
                media_type = "image/gif"
            elif file_path.lower().endswith(".webp"):
                media_type = "image/webp"
            else:
                media_type = "image/jpeg"

            question = caption if caption else (
                "David sent you this image. Describe what you see and how it relates "
                "to Trinity6 or the business. Be specific and honest about what is in the image."
            )

            # Step 3: Send to Claude with vision
            from langchain_core.messages import HumanMessage, SystemMessage
            from langchain_anthropic import ChatAnthropic

            # Always use cloud Claude for vision (local models usually lack vision)
            vision_llm = ChatAnthropic(
                model="claude-haiku-4-5-20251001",
                temperature=0.5,
            )

            messages = [
                SystemMessage(content=(
                    "You are Trinity, David's AI company manager. "
                    "David sent you an image. Analyze it honestly and thoroughly. "
                    "If it is a screenshot of code or an error, describe what you see precisely. "
                    "If it is a business document or chart, extract the key numbers. "
                    "Never guess — only describe what is actually visible in the image."
                )),
                HumanMessage(content=[
                    {
                        "type": "image",
                        "source": {
                            "type": "base64",
                            "media_type": media_type,
                            "data": img_b64,
                        },
                    },
                    {"type": "text", "text": question},
                ]),
            ]

            self.send_telegram("Looking at your image...")
            response = vision_llm.invoke(messages)
            self.send_telegram(response.content)

        except Exception as e:
            print(f"Vision error: {e}")
            self.send_telegram(
                f"I had trouble processing that image: {str(e)}\n"
                "You can describe what it shows and I will help."
            )

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
                            self.handle_message(text, chat_id)
                        elif message.get("photo") and chat_id:
                            # David sent a photo — handle with vision
                            photos = message["photo"]
                            caption = message.get("caption", "")
                            print(f"David sent a photo. Caption: {caption}")
                            self.handle_photo_message(
                                photos, caption, chat_id
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
