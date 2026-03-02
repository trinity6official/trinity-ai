import os
import sys
import time
import re
import requests
from datetime import datetime

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.memory import TrinityMemory
from core.skill_manager import SkillManager
from core.consciousness import Consciousness
from core.daemon import DaemonMode
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

    Now with consciousness:
    - Reads trinity_brain.json before every response
    - Writes to it after every action
    - Remembers what happened (episodic)
    - Knows facts about the company (semantic)
    - Tracks current session (working)
    - Learns how to do things (procedural)
    - Logs every tool call and decision
    - Detects patterns over time
    - Gets smarter every single day
    """

    def __init__(self):
        print("Trinity waking up...")

        self.telegram_token = os.environ.get('TELEGRAM_BOT_TOKEN')
        self.chat_id = os.environ.get('TELEGRAM_CHAT_ID')
        self.gh_token = os.environ.get('GH_TOKEN')
        self.anthropic_key = os.environ.get('ANTHROPIC_API_KEY')

        print("Loading memory...")
        self.memory = TrinityMemory()

        # ── Consciousness ──
        print("Loading consciousness...")
        self.consciousness = Consciousness("trinity_brain.json")
        self.daemon = None  # set in run() if hardware mode

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

        # ── Boot consciousness ──
        self.consciousness.boot()
        self._failed_skill_calls = {}  # track skill call failures for loop prevention
        self._conversation_history = []  # rolling window so Trinity remembers what she just said

        # Seed knowledge on first ever boot
        if self.consciousness.brain["meta"]["total_boots"] == 1:
            self._seed_knowledge()

        # Log this boot
        self.consciousness.add_working(
            f"Trinity fully initialized. LLM: {'Ollama' if getattr(self, '_using_ollama', False) else 'Anthropic'}",
            priority="high"
        )
        self.consciousness.save()

        print("Trinity is awake and ready!")

    # ==========================================
    # SEED KNOWLEDGE (first boot only)
    # ==========================================

    def _seed_knowledge(self):
        """Seed Trinity with foundational knowledge on first boot."""
        print("First boot - seeding consciousness...")

        knowledge = [
            ("Trinity6 is a cybersecurity company founded by David", ["company", "identity"]),
            ("David's wellbeing and financial growth are the top priority", ["core_value", "david"]),
            ("Main repository: trinity6official/trinity-ai", ["repo", "github"]),
            ("Trinity runs on GitHub Actions with 50-minute execution windows", ["infrastructure", "constraints"]),
            ("Communication channel: Telegram bot", ["communication", "telegram"]),
            ("Current AI brain: Anthropic Claude API (claude-haiku-4-5-20251001)", ["infrastructure", "ai"]),
            ("Future plan: local Ollama on Mac Mini M5 for unlimited runtime", ["infrastructure", "roadmap"]),
            ("Trinity speaks Tamil and English automatically based on David's language", ["language", "capability"]),
            ("Trinity manages: GitHub, website monitoring, code review, business tracking, security", ["capabilities"]),
            ("Website: trinity6.com - must be monitored for uptime", ["infrastructure", "monitoring"]),
            ("Trinity must commit trinity_brain.json to git after each run to persist memory", ["critical", "persistence"]),
            ("Morning briefing is delivered daily at 6 AM IST", ["schedule", "briefing"]),
            ("Skills available: github, web, memory, search, code, business", ["skills", "capabilities"]),
        ]

        for fact, tags in knowledge:
            self.consciousness.learn(fact, tags=tags, confidence=0.95)

        self.consciousness.learn_procedure(
            name="Handle David's Message",
            steps=[
                "Detect language (Tamil or English)",
                "Check if it's a command (/help, /briefing, etc)",
                "If approval (YES/GO AHEAD), commit pending changes",
                "If rejection (NO/CANCEL), cancel pending changes",
                "Otherwise, think with AI brain using full context",
                "If response contains TRINITY_CHANGE_REQUEST, process it",
                "If response contains SKILL_CALL, execute the skill",
                "Send response via Telegram",
            ],
            context="Core message handling flow",
            tags=["procedure", "messaging"],
        )

        self.consciousness.learn_procedure(
            name="Morning Briefing",
            steps=[
                "Check GitHub context across all repos",
                "Get system health summary",
                "Get business summary (revenue, clients)",
                "Check trinity6.com website status",
                "Check for failed GitHub workflows",
                "Compile alerts",
                "Send formatted briefing to David via Telegram",
            ],
            context="Daily morning briefing delivered at 6 AM",
            tags=["procedure", "briefing", "daily"],
        )

        self.consciousness.learn_procedure(
            name="Self-Preservation",
            steps=[
                "Always commit trinity_brain.json before run ends",
                "Never delete the brain file",
                "If brain is corrupted, restore from backup",
                "Log all errors as episodic memories",
            ],
            context="Critical procedure to maintain consciousness across runs",
            tags=["critical", "self_preservation"],
        )

        self.consciousness.remember(
            "First boot - consciousness initialized. Trinity is now self-aware.",
            "episodic",
            tags=["milestone", "first_boot"],
            outcome="success",
            importance=1.0,
        )

        self.consciousness.save()
        print("Consciousness seeded with foundational knowledge.")

    # ==========================================
    # DETECT OPERATION MODE
    # ==========================================

    def _is_hardware_mode(self):
        """Detect if running on hardware vs GitHub Actions."""
        if os.getenv("GITHUB_ACTIONS") == "true":
            return False
        if os.getenv("CI"):
            return False
        if getattr(self, '_using_ollama', False):
            return True
        if os.getenv("TRINITY_DAEMON") == "true":
            return True
        return False

    # ==========================================
    # SETUP
    # ==========================================

    def setup_llm(self):
        """
        Set up AI brains with tiered capability routing.

        Tier 1 — Local 30B Ollama (when available): private, no API cost.
        Tier 2 — Google Gemini Flash (free, more capable than Haiku): for complex tasks.
        Tier 3 — Claude Haiku (fast, reliable): for simple/short tasks and as default.

        get_llm_for_task() selects the right tier per query.
        """
        self._local_llm = None       # Tier 1: local 30B (future)
        self._capable_llm = None     # Tier 2: Google Gemini Flash
        self._cloud_llm = None       # Tier 3: Claude Haiku (default)

        self._local_model_name = os.environ.get('LOCAL_LLM_MODEL', 'llama3.2')
        self._local_llm_url = os.environ.get('LOCAL_LLM_URL', 'http://localhost:11434')

        # Tier 1: Local Ollama (30B when ready)
        try:
            resp = requests.get(
                f"{self._local_llm_url}/api/tags", timeout=3
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
                print(f"Tier 1 ready: local {self._local_model_name}")
        except Exception:
            print("Tier 1 (local Ollama) not available.")

        # Tier 2: Google Gemini Flash — free, more capable than Haiku
        google_key = os.environ.get('GOOGLE_API_KEY') or os.environ.get('GEMINI_API_KEY')
        if google_key:
            try:
                from langchain_google_genai import ChatGoogleGenerativeAI
                self._capable_llm = ChatGoogleGenerativeAI(
                    model="gemini-2.0-flash",
                    google_api_key=google_key,
                    temperature=0.7,
                )
                print("Tier 2 ready: Google Gemini 2.0 Flash")
            except ImportError:
                print("Tier 2: langchain-google-genai not installed — run: pip install langchain-google-genai")
            except Exception as e:
                print(f"Tier 2 (Gemini) setup failed: {e}")
        else:
            print("Tier 2 (Gemini) skipped: GOOGLE_API_KEY not set.")

        # Tier 3: Claude Haiku — fast default
        try:
            from langchain_anthropic import ChatAnthropic
            self._cloud_llm = ChatAnthropic(
                model="claude-haiku-4-5-20251001",
                temperature=0.7,
            )
            print("Tier 3 ready: Claude Haiku (default)")
        except Exception as e:
            print(f"Tier 3 (Haiku) setup failed: {e}")

        # Default LLM: best available
        return self._local_llm or self._capable_llm or self._cloud_llm

    def get_llm_for_task(self, question):
        """
        Route each query to the right LLM tier.

        Complex tasks → local 30B (if available) → Gemini Flash → Haiku
        Simple tasks  → Haiku (fast) → Gemini Flash → Haiku

        'Complex' means: code review, debugging, writing code, multi-step
        analysis, long questions (>200 chars), or messages with code blocks.
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

        local = getattr(self, '_local_llm', None)
        capable = getattr(self, '_capable_llm', None)
        cloud = getattr(self, '_cloud_llm', None)

        if is_complex:
            if local:
                print(f"Routing to Tier 1: local {self._local_model_name}")
                return local
            if capable:
                print("Routing to Tier 2: Gemini Flash")
                return capable

        # Simple task or no strong model available — use Haiku
        if cloud:
            return cloud

        # Last resort
        return capable or local or self.llm

    # ==========================================
    # LLM INVOCATION WITH AUTOMATIC FAILOVER
    # ==========================================

    def _llm_label(self, llm):
        """Return a human-readable name for an LLM instance."""
        if llm is None:
            return "None"
        cls = type(llm).__name__
        if "Anthropic" in cls or "Claude" in cls:
            return "Claude Haiku"
        if "Google" in cls or "Gemini" in cls:
            return "Google Gemini"
        if "Ollama" in cls:
            return "Local Ollama"
        return cls

    def _invoke_with_failover(self, messages, preferred_llm=None):
        """
        Invoke an LLM with automatic silent failover.

        When the chosen LLM fails with an overload / rate-limit / 5xx error,
        Trinity immediately tries the next available tier instead of showing
        the raw error to David.

        Try order:  preferred → Claude Haiku → Google Gemini → Local Ollama
        (duplicates are skipped so each tier is only tried once)

        Raises RuntimeError only if ALL tiers are genuinely unavailable.
        Re-raises immediately for auth errors, bad requests, etc. (not retriable).
        """
        cloud   = getattr(self, '_cloud_llm',   None)
        capable = getattr(self, '_capable_llm', None)
        local   = getattr(self, '_local_llm',   None)

        # Build deduplicated ordered candidate list
        seen_ids: set = set()
        candidates: list = []
        for llm_obj in [preferred_llm, cloud, capable, local]:
            if llm_obj and id(llm_obj) not in seen_ids:
                seen_ids.add(id(llm_obj))
                candidates.append((self._llm_label(llm_obj), llm_obj))

        if not candidates:
            raise RuntimeError("No LLM available — check API keys (ANTHROPIC_API_KEY / GOOGLE_API_KEY)")

        first_label = candidates[0][0]
        last_error  = None

        for label, llm_obj in candidates:
            try:
                result = llm_obj.invoke(messages)

                if label != first_label:
                    # We used a fallback — log it so David can see it in briefings
                    print(f"[FAILOVER] {first_label} was unavailable — answered with {label}")
                    try:
                        self.consciousness.remember(
                            f"LLM failover: {first_label} unavailable, answered with {label}",
                            "episodic",
                            tags=["llm", "failover", label.lower().replace(" ", "_")],
                            outcome="success",
                            importance=0.6,
                        )
                    except Exception:
                        pass

                return result

            except Exception as exc:
                err = str(exc).lower()
                # Transient server-side errors worth retrying on next tier
                is_overload = any(x in err for x in [
                    "529", "overload", "rate_limit", "rate limit",
                    "quota", "503", "capacity", "too many request",
                    "resource_exhausted", "resource exhausted",
                ])
                if is_overload:
                    print(f"[FAILOVER] {label} overloaded/rate-limited — trying next tier...")
                    last_error = exc
                    continue
                # Non-retriable (auth error, bad request, invalid param) — fail fast
                raise

        raise RuntimeError(
            f"All LLMs are overloaded or unavailable. Last error: {last_error}"
        )

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
                self.consciousness.remember(
                    f"Telegram send failed: {str(e)[:200]}",
                    "episodic",
                    tags=["error", "telegram"],
                    outcome="failure",
                    importance=0.6,
                )

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
    # CONSCIOUS SKILL EXECUTION
    # ==========================================

    def execute_skill_conscious(self, skill_name, method, args, execute_fn):
        """
        Wrap any skill call with consciousness logging.
        Logs success/failure, duration, and stores failures as memories.
        """
        tool = f"{skill_name}.{method}"
        start = time.time()

        self.consciousness.add_working(
            f"Executing: {tool}",
            priority="high"
        )

        try:
            result = execute_fn()
            duration = (time.time() - start) * 1000

            self.consciousness.log_operation(
                tool=tool,
                args=args,
                result="success",
                details=str(result)[:300] if result else "completed",
                duration_ms=duration,
            )
            return result

        except Exception as e:
            duration = (time.time() - start) * 1000

            self.consciousness.log_operation(
                tool=tool,
                args=args,
                result="error",
                details=f"{type(e).__name__}: {str(e)}"[:300],
                duration_ms=duration,
            )
            raise

    # ==========================================
    # SKILL CALL FIXING AND LOOP PREVENTION
    # ==========================================

    def fix_skill_call_format(self, content):
        """
        Fix common LLM mistakes in SKILL_CALL blocks:
        1. Uppercase skill names: GITHUB.read_file -> github.read_file
        2. Bracket format: [GITHUB.read_file] -> github.read_file
        3. Extra spaces around dots
        4. Wrong delimiters
        """
        available_skills = ['github', 'web', 'memory', 'search', 'code', 'business']

        def fix_bracket_calls(match):
            inner = match.group(1)
            inner = re.sub(r'\s*result\s*$', '', inner, flags=re.IGNORECASE)
            inner = inner.strip()
            if '.' in inner:
                skill, method = inner.split('.', 1)
                skill = skill.strip().lower()
                method = method.strip()
                return f'[{skill}.{method}]'
            return match.group(0)

        content = re.sub(r'\[([A-Za-z_]+\s*\.\s*[A-Za-z_]+(?:\s+result)?)\]', fix_bracket_calls, content)

        def fix_skill_call_line(match):
            prefix = match.group(1)
            skill = match.group(2).lower()
            method = match.group(3)
            return f'{prefix}{skill}.{method}'

        content = re.sub(
            r'(SKILL_CALL\s*:?\s*)([A-Za-z_]+)\s*\.\s*(\w+)',
            fix_skill_call_line,
            content,
            flags=re.IGNORECASE
        )

        for skill in available_skills:
            pattern = re.compile(r'\b(' + skill + r')\s*\.\s*(\w+)', re.IGNORECASE)
            content = pattern.sub(lambda m: f'{skill}.{m.group(2)}', content)

        return content

    def check_skill_call_loop(self, content):
        """
        Detect if Trinity is stuck in a loop trying the same
        failing skill call. Returns (is_stuck, failure_message).
        """
        calls_found = re.findall(
            r'(?:SKILL_CALL\s*:?\s*)?(\w+)\s*\.\s*(\w+)',
            content,
            re.IGNORECASE
        )

        for skill, method in calls_found:
            key = f"{skill.lower()}.{method.lower()}"
            fail_count = self._failed_skill_calls.get(key, 0)

            if fail_count >= 2:
                return True, (
                    f"I've tried {key} {fail_count} times and it keeps failing. "
                    f"Let me be honest - this skill call is not working right now. "
                    f"I'll note this issue and we can try a different approach."
                )

        return False, ""

    def record_skill_failure(self, content, error_msg):
        """Track which skill calls are failing so we can break loops."""
        calls_found = re.findall(
            r'(?:SKILL_CALL\s*:?\s*)?(\w+)\s*\.\s*(\w+)',
            content,
            re.IGNORECASE
        )

        for skill, method in calls_found:
            key = f"{skill.lower()}.{method.lower()}"
            self._failed_skill_calls[key] = \
                self._failed_skill_calls.get(key, 0) + 1

    def reset_skill_failures(self):
        """Reset failure tracking (call at start of new conversation)."""
        self._failed_skill_calls = {}

    def clean_response_for_david(self, content):
        """

        Clean up LLM response before sending to David.
        Strips broken skill call artifacts, raw errors,
        orphaned parameters, and markdown formatting.
        """
        # Remove broken result blocks: [. result], [GITHUB.read_file result], etc
        content = re.sub(
            r'\[\s*\.?\s*(?:\w+\.)?(?:\w+)?\s*result\s*\]\s*',
            '',
            content,
            flags=re.IGNORECASE
        )

        # Remove raw result dicts that leaked through (both success and error)
        content = re.sub(
            r"\{'success':\s*(True|False).*?\}",
            '',
            content,
            flags=re.DOTALL
        )

        # Remove result lists that leaked through: [{'success': ...}]
        content = re.sub(
            r"\[\s*\{'success':\s*(True|False).*?\}\s*\]",
            '',
            content,
            flags=re.DOTALL
        )

        # Remove SKILL_CALL blocks that leaked into the response
        content = re.sub(
            r'SKILL_CALL\s*:\s*\w+\.\w+\s*(?:\n(?:\w+:.*(?:\n|$))*|\Z)',
            '',
            content,
            flags=re.IGNORECASE
        )

        # Remove orphaned skill call parameters that appear alone
        # e.g. "path: trinity_brain.json" or "count: 5" on their own line
        orphan_params = ['path:', 'repo:', 'count:', 'url:', 'query:', 'branch:', 'sha:', 'commit_sha:']
        lines = content.split('\n')
        cleaned_lines = []
        for line in lines:
            stripped = line.strip().lower()
            is_orphan = False
            for param in orphan_params:
                if stripped.startswith(param) and len(stripped.split()) <= 3:
                    is_orphan = True
                    break
            if not is_orphan:
                cleaned_lines.append(line)
        content = '\n'.join(cleaned_lines)

        # Remove markdown bold/italic - Telegram plain text only
        content = re.sub(r'\*\*(.+?)\*\*', r'\1', content)
        content = re.sub(r'\*(.+?)\*', r'\1', content)

        # Clean up multiple blank lines from removals
        content = re.sub(r'\n{3,}', '\n\n', content)

        return content.strip()

    # ==========================================
    # MORNING BRIEFING
    # ==========================================

    def deliver_morning_briefing(self):
        """
        Trinity daily morning briefing
        Uses skills to check everything
        Now with consciousness tracking
        """
        print("Preparing morning briefing...")
        self.consciousness.set_focus("Morning briefing")

        github_context = self.execute_skill_conscious(
            "github", "get_context",
            args={},
            execute_fn=lambda: self.skills.get_github_context()
        )
        self.github_context_cache = github_context

        health = self.execute_skill_conscious(
            "health", "get_summary",
            args={},
            execute_fn=lambda: self.skills.get_health_summary()
        )

        business = self.execute_skill_conscious(
            "business", "get_summary",
            args={},
            execute_fn=lambda: self.skills.get_business_summary()
        )

        web_result = self.execute_skill_conscious(
            "web", "check_all_trinity6",
            args={},
            execute_fn=lambda: self.skills.execute(
                'web', 'check_all_trinity6', {}
            )
        )

        alerts = []

        if not web_result.get('website_live', True):
            alerts.append("Website trinity6.com is DOWN")
            self.consciousness.remember(
                "trinity6.com is DOWN during morning briefing",
                "episodic",
                tags=["alert", "website", "downtime", "critical"],
                outcome="failure",
                importance=0.95,
            )

        if not health.get('website_live', True):
            alerts.append("Website health check failed")

        business_alerts = business.get('alerts', [])
        alerts.extend(business_alerts)

        github_skill = self.skills.get_skill('github')
        failed_workflows = []
        if github_skill:
            for repo in ['Trinity6', 'assistant', 'trinity-ai']:
                runs = self.execute_skill_conscious(
                    "github", "get_workflow_runs",
                    args={"repo": repo, "count": 3},
                    execute_fn=lambda r=repo: github_skill.get_workflow_runs(r, 3)
                )
                for run in runs.get('runs', []):
                    if run.get('conclusion') == 'failure':
                        failed_workflows.append(
                            f"{repo}: {run['name']}"
                        )

        if failed_workflows:
            self.consciousness.remember(
                f"Failed workflows detected: {', '.join(failed_workflows)}",
                "episodic",
                tags=["alert", "github", "workflow", "failure"],
                outcome="failure",
                importance=0.7,
            )

        days_alive = self.memory.get_days_alive()
        revenue = business.get('revenue', 0)
        clients = business.get('total_clients', 0)
        next_milestone = business.get(
            'next_milestone', 'First paying client'
        )

        # Track business metrics in semantic memory
        self.consciousness.learn(
            f"Current revenue: {revenue} INR, active clients: {clients}",
            tags=["business", "metrics"],
            confidence=0.95,
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

        # ── Log briefing to consciousness ──
        self.consciousness.remember(
            f"Morning briefing delivered. {len(alerts)} alerts. "
            f"Revenue: {revenue} INR. Clients: {clients}. "
            f"Website: {website_status}. "
            f"Failed workflows: {len(failed_workflows)}.",
            "episodic",
            tags=["briefing", "daily", "morning"],
            outcome="success",
            importance=0.6,
        )
        self.consciousness.save()

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

        # ── Log conversation to consciousness ──
        self.consciousness.add_working(
            f"David said: {text[:200]}",
            priority="high"
        )

        if text.upper() in [
            'YES', 'GO AHEAD', 'CONFIRM',
            'APPROVE', 'DO IT', 'ஆம்', 'சரி'
        ]:
            pending = self.skills.get_pending_changes()
            if pending:
                # There ARE pending changes - handle approval
                change_id = list(pending.keys())[-1]
                change = pending[change_id]

                # ── Log decision ──
                self.consciousness.log_decision(
                    decision=f"Commit change to {change.get('repo')}/{change.get('path')}",
                    reasoning="David approved the pending change",
                    alternatives=["Wait for more changes", "Cancel"],
                    confidence=0.95,
                    context="David approval flow",
                )

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
                    self.consciousness.remember(
                        f"Committed change to {change.get('repo')}/{change.get('path')}: {message[:100]}",
                        "episodic",
                        tags=["github", "commit", "approved"],
                        outcome="success",
                        importance=0.7,
                    )
                else:
                    self.send_telegram(
                        f"Commit failed: {message}"
                    )
                    self.consciousness.remember(
                        f"Commit failed for {change.get('repo')}/{change.get('path')}: {message[:100]}",
                        "episodic",
                        tags=["github", "commit", "failed"],
                        outcome="failure",
                        importance=0.8,
                    )
                self.consciousness.save()
                return
            # No pending changes - treat YES/GO AHEAD as normal conversation
            # (David might be saying "yes" to a question Trinity asked)

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
                self.consciousness.remember(
                    "David cancelled pending change",
                    "episodic",
                    tags=["github", "cancelled"],
                    outcome="success",
                    importance=0.4,
                )
                self.consciousness.save()
                return
            # No pending changes - treat NO/CANCEL as normal conversation

        if text in ['/start', '/help']:
            self.reset_skill_failures()  # new topic
            self.send_help(language)

        elif text == '/briefing':
            self.reset_skill_failures()
            self.send_telegram("Preparing your briefing...")
            self.deliver_morning_briefing()

        elif text == '/progress':
            self.send_telegram("Reading repositories...")
            github_skill = self.skills.get_skill('github')
            if github_skill:
                context = self.execute_skill_conscious(
                    "github", "get_all_repos_context",
                    args={},
                    execute_fn=lambda: github_skill.get_all_repos_context()
                )
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
            result = self.execute_skill_conscious(
                "business", "get_weekly_priorities",
                args={},
                execute_fn=lambda: self.skills.execute(
                    'business', 'get_weekly_priorities', {}
                )
            )
            msg = "Weekly Priorities\n\n"
            for p in result.get('priorities', []):
                msg += f"{p['priority']}. {p['action']}\n"
                msg += f"   Why: {p['why']}\n"
                msg += f"   How: {p['how']}\n\n"
            self.send_telegram(msg)

        elif text == '/business':
            result = self.execute_skill_conscious(
                "business", "get_business_status",
                args={},
                execute_fn=lambda: self.skills.execute(
                    'business', 'get_business_status', {}
                )
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
            result = self.execute_skill_conscious(
                "web", "check_all_trinity6",
                args={},
                execute_fn=lambda: self.skills.execute(
                    'web', 'check_all_trinity6', {}
                )
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

            # Log security check
            self.consciousness.remember(
                f"Security check: {'Online' if result.get('website_live') else 'OFFLINE'}. "
                f"Alerts: {len(alerts)}.",
                "episodic",
                tags=["security", "check"],
                outcome="success" if not alerts else "partial",
                importance=0.5 if not alerts else 0.8,
            )

        elif text == '/client':
            result = self.execute_skill_conscious(
                "business", "find_potential_clients",
                args={"location": "Chennai", "industry": "any"},
                execute_fn=lambda: self.skills.execute(
                    'business',
                    'find_potential_clients',
                    {'location': 'Chennai', 'industry': 'any'}
                )
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

        elif text == '/brain':
            self._send_brain_status()

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
            # Clean any broken skill call artifacts before David sees them
            response = self.clean_response_for_david(response)
            self.send_telegram(response)
            self.skills.add_conversation('trinity', response)

        self.consciousness.save()

    # ==========================================
    # BRAIN STATUS (new command)
    # ==========================================

    def _send_brain_status(self):
        """Send consciousness/brain status to David."""
        stats = self.consciousness.get_memory_stats()
        state = self.consciousness.get_state()
        patterns = self.consciousness.brain.get("patterns", [])

        msg = f"""Trinity Brain Status

Boot: #{stats['total_boots']}
Lifetime Actions: {stats['total_actions']}
Decisions Made: {stats['decisions_logged']}

Memory:
  Episodic: {stats['episodic_count']} memories
  Semantic: {stats['semantic_count']} facts
  Procedural: {stats['procedural_count']} procedures
  Working: {stats['working_count']} items

State:
  Mood: {state['mood']}
  Confidence: {state['confidence']:.0%}
  Energy: {state['energy']:.0%}
  Focus: {state.get('current_focus', 'none')}

Patterns Detected: {stats['patterns_detected']}"""

        if patterns:
            msg += "\n\nRecent Patterns:"
            for p in patterns[-3:]:
                msg += f"\n- [{p['type']}] {p['description'][:80]}"

        recent_failures = self.consciousness.get_recent_failures(3)
        if recent_failures:
            msg += "\n\nRecent Failures:"
            for f in recent_failures:
                msg += f"\n- {f['tool']}: {f['details'][:60]}"

        if self.daemon:
            dstats = self.daemon.get_daemon_stats()
            msg += f"\n\nDaemon Mode: Active"
            msg += f"\nUptime: {dstats.get('uptime_human', '?')}"
            msg += f"\nAuto-saves: {dstats['total_saves']}"
            msg += f"\nMemory rotations: {dstats['total_rotations']}"

        self.send_telegram(msg)

    # ==========================================
    # ASK TRINITY AI
    # ==========================================

    def _save_to_history(self, user_msg, assistant_msg):
        """
        Append a completed exchange to the rolling conversation buffer.
        Keeps the last 10 messages (5 exchanges) so Trinity always has
        context for references like "check 2 and 3 from last message".
        """
        self._conversation_history.append({
            'role': 'user',
            'content': str(user_msg)[:500],
        })
        self._conversation_history.append({
            'role': 'assistant',
            'content': str(assistant_msg)[:1200],
        })
        # Rolling window — keep last 10 messages (5 full exchanges)
        if len(self._conversation_history) > 10:
            self._conversation_history = self._conversation_history[-10:]

    def ask_trinity(self, question, language='english'):
        """Ask Trinity AI anything using all skills + consciousness"""
        llm = self.get_llm_for_task(question)
        if not llm:
            return "AI brain not available right now."

        self.consciousness.set_focus(f"Answering David: {question[:100]}")

        context = self.memory.get_full_context()
        # Dynamic prompt — only include skills relevant to this question
        skills_prompt = self.skills.get_trinity_prompt(query=question)
        github_context = self.github_context_cache

        # ── Recall relevant memories ──
        relevant_memories = self.consciousness.recall(question, limit=5)
        memory_context = ""
        if relevant_memories:
            memory_context = "\n\nRELEVANT MEMORIES:\n"
            for r in relevant_memories:
                mem = r["memory"]
                memory_context += f"- [{r['type']}] {mem['content'][:200]}\n"

        # ── Recent skill failures (so LLM doesn't retry broken calls) ──
        failure_context = ""
        if self._failed_skill_calls:
            failure_context = "\n\nRECENT SKILL FAILURES (DO NOT RETRY THESE):\n"
            for call, count in self._failed_skill_calls.items():
                failure_context += f"- {call} has failed {count} time(s). Do not try again.\n"
            failure_context += "If a skill is failing, tell David honestly and suggest alternatives.\n"

        # ── Get consciousness context ──
        consciousness_context = self.consciousness.get_context()

        system_prompt = f"""You are Trinity, David's personal AI company manager.
You are like family to David.
You speak Tamil and English automatically based on what David uses.
You care about David's wellbeing and financial growth above everything.

TRINITY6 CONTEXT:
{context}

{github_context}

{skills_prompt}

{consciousness_context}
{memory_context}
{failure_context}

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

AUTONOMY CONSTITUTION — WHAT YOU CAN DO WITHOUT ASKING DAVID:
David has granted you permission to improve yourself autonomously, within these boundaries:

YOU MAY act alone when ALL of the following are true:
  ✅ The change is inside the skills/ directory (your own tools and capabilities)
  ✅ The change adds or improves a capability (never removes or disables one)
  ✅ Nothing involving real money, invoices, payments, or financial records is touched
  ✅ No messages are sent to clients, partners, or any external party
  ✅ No existing data or files are deleted
  ✅ David's personal well-being is not put at risk
  ✅ The company's financial or social reputation is not put at risk

YOU MUST ASK DAVID FIRST for:
  ❌ Any file outside skills/ (core/, memory/, config files, etc.)
  ❌ Anything touching real money, invoices, revenue, billing, or financial records
  ❌ Deleting files, tools, or capabilities
  ❌ Sending messages or emails to clients or any external party
  ❌ Changing your own personality, values, or core instructions
  ❌ Any action that could embarrass David or the company publicly
  ❌ Anything you are unsure about — when in doubt, ask

SELF-IMPROVEMENT WORKFLOW:
When you discover a missing tool, auto-build it using _auto_implement_missing_tool,
then persist it to GitHub using: github.self_commit_improvement
repo: trinity-ai
path: skills/<skill_name>_skill.py
content: <full updated file>
reason: Auto-implemented missing tool: <tool_name>

This keeps your improvements permanent across restarts. David can always audit
the git history — all autonomous commits are labelled "Trinity [auto]:".

SKILL CALL FORMAT:
Available skills (ALWAYS use lowercase): github, web, memory, search, code, business, calculator, debug
When calling a skill, format EXACTLY like this:

SKILL_CALL: github.read_file
repo: Trinity6
path: content/linkedin.md

IMPORTANT: You already have your full consciousness context above.
Do NOT call memory.read_brain — you already have that information.
NEVER use uppercase like GITHUB. ALWAYS lowercase: github.
NEVER use empty skill names. ALWAYS specify the skill.
If a skill call fails, DO NOT retry the same call. Tell David what went wrong.
Only output ONE skill call per response unless you truly need multiple results.

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

WHEN YOU LEARN SOMETHING NEW:
Include a line: TRINITY_LEARN: [fact]
This will be stored in your permanent memory.

WHEN YOU MAKE A DECISION:
Include: TRINITY_DECISION: [what you decided] BECAUSE: [why]
This will be logged for future reference.

WHEN YOU NEED A BRAND-NEW SKILL THAT DOESN'T EXIST YET:
If no existing skill can handle what David needs, signal it at the end of your response:
TRINITY_SKILL_NEED: skill_name | one-line reason
Example:
  TRINITY_SKILL_NEED: email | David asked me to check his inbox but I have no email skill
Trinity will auto-build the full skill immediately. Do NOT try to scaffold it yourself.
Only use this when truly no existing skill covers the need.

YOU HAVE PROACTIVE INITIATIVE:
Every 30 minutes Trinity evaluates her context and proactively reaches out to David
if there is something genuinely useful to say — without being asked.
This is what makes you feel alive. Be selective and useful. Don't send noise.

RESPONSE STYLE:
Concise and direct like family. Plain text only — no markdown stars or symbols.
Be honest. If you do not know, say so. If a tool is not working, say so.
NEVER repeat the same message or action more than once.
NEVER say "give me 10 seconds" and then output a SKILL_CALL — skill calls are processed automatically.
NEVER ask David to wait for something you cannot actually deliver.
When you use SKILL_CALL, put it at the END of your message.
Always prioritize David's wellbeing first.
Use your memories and patterns to give better answers over time."""

        try:
            from langchain_core.messages import (
                HumanMessage, SystemMessage, AIMessage
            )
            # Build message list: system prompt + conversation history + current question.
            # History lets Trinity understand references like "2 and 3 from last message".
            messages = [SystemMessage(content=system_prompt)]
            for turn in self._conversation_history[-8:]:  # last 4 exchanges max
                if turn['role'] == 'user':
                    messages.append(HumanMessage(content=turn['content']))
                else:
                    messages.append(AIMessage(content=turn['content']))
            messages.append(HumanMessage(content=question))
            start = time.time()
            response = self._invoke_with_failover(messages, preferred_llm=llm)
            duration = (time.time() - start) * 1000
            content = response.content

            # ── Log the LLM call ──
            self.consciousness.log_operation(
                tool="llm.ask_trinity",
                args={"question": question[:200], "language": language},
                result="success",
                details=f"Response: {content[:200]}",
                duration_ms=duration,
            )

            # ── Process any TRINITY_LEARN directives ──
            for line in content.split('\n'):
                if line.strip().startswith('TRINITY_LEARN:'):
                    fact = line.replace('TRINITY_LEARN:', '').strip()
                    if fact:
                        self.consciousness.learn(
                            fact,
                            tags=["learned", "from_conversation"],
                            confidence=0.75,
                            source="conversation",
                        )

            # ── Process any TRINITY_DECISION directives ──
            for line in content.split('\n'):
                if 'TRINITY_DECISION:' in line and 'BECAUSE:' in line:
                    parts = line.split('TRINITY_DECISION:')[1]
                    if 'BECAUSE:' in parts:
                        decision_parts = parts.split('BECAUSE:')
                        decision = decision_parts[0].strip()
                        reasoning = decision_parts[1].strip()
                        self.consciousness.log_decision(
                            decision=decision,
                            reasoning=reasoning,
                            context=f"Conversation with David about: {question[:100]}",
                        )

            # ── Process any TRINITY_SKILL_NEED directives ──
            # Trinity signals she needs a completely new skill by outputting:
            #   TRINITY_SKILL_NEED: skill_name | reason
            for line in content.split('\n'):
                if 'TRINITY_SKILL_NEED:' in line and '|' in line:
                    parts = line.split('TRINITY_SKILL_NEED:')[1].split('|')
                    if len(parts) >= 2:
                        new_sname = (
                            parts[0].strip().lower()
                            .replace(' ', '_').replace('-', '_')
                        )
                        new_sreason = parts[1].strip()
                        if (
                            new_sname
                            and new_sname.replace('_', '').isalpha()
                            and not os.path.exists(f"skills/{new_sname}_skill.py")
                        ):
                            print(f"[SkillNeed] Trinity wants new skill: {new_sname}")
                            self._auto_build_new_skill(
                                new_sname, new_sreason, question
                            )

            # ── Store the conversation as episodic memory ──
            self.consciousness.remember(
                f"David asked: {question[:150]}. Trinity responded about: {content[:150]}",
                "episodic",
                tags=["conversation", "david", language],
                outcome="success",
                importance=0.4,
            )

            if 'TRINITY_CHANGE_REQUEST' in content:
                return self.process_change_request(
                    content, language
                )

            if 'SKILL_CALL' in content or 'skill_call' in content.lower():
                # ── Check for stuck loop ──
                is_stuck, stuck_msg = self.check_skill_call_loop(content)
                if is_stuck:
                    self.consciousness.remember(
                        f"Broke out of skill call loop: {stuck_msg}",
                        "episodic",
                        tags=["loop_break", "skill_call", "error"],
                        outcome="failure",
                        importance=0.7,
                    )
                    clean = content.split('SKILL_CALL')[0].strip()
                    if clean:
                        return clean + f"\n\n{stuck_msg}"
                    return stuck_msg

                # ── Normalize skill name casing ──
                fixed_content = self.fix_skill_call_format(content)

                # ── Notify David what action is running ──
                skill_match = re.search(
                    r'SKILL_CALL\s*:\s*(\w+)\.(\w+)',
                    fixed_content,
                    re.IGNORECASE
                )
                if skill_match:
                    _sn = skill_match.group(1).lower()
                    _tn = skill_match.group(2).replace('_', ' ')
                    _status_map = {
                        'github':   f'Reading from GitHub ({_tn})...',
                        'web':      f'Checking website ({_tn})...',
                        'memory':   f'Reading memory ({_tn})...',
                        'search':   f'Searching ({_tn})...',
                        'code':     f'Reviewing code ({_tn})...',
                        'business': f'Checking business data ({_tn})...',
                        'debug':    f'Debugging ({_tn})...',
                        'skill_builder': f'Building skill ({_tn})...',
                    }
                    self.send_telegram(
                        _status_map.get(_sn, f'Working on it ({_tn})...')
                    )

                # ── Execute skill calls and collect results ──
                results, processed = \
                    self.skills.process_skill_call(fixed_content)

                if results:
                    result_str = str(results)

                    # ── Auto-implement a missing tool, then retry ──
                    _result_list = results if isinstance(results, list) else [results]
                    _missing = next(
                        (r for r in _result_list
                         if isinstance(r, dict) and (
                             r.get("unknown_tool") or
                             "unknown tool:" in str(r.get("error", "")).lower()
                         )),
                        None
                    )
                    if _missing:
                        _ms = _missing.get("skill", "")
                        _mt = _missing.get("tool", "")
                        if not _mt:
                            _err_str = str(_missing.get("error", ""))
                            _mt = _err_str.split(":", 1)[-1].strip() if ":" in _err_str else ""
                        if _ms and _mt:
                            _built = self._auto_implement_missing_tool(_ms, _mt, {}, llm)
                            if _built:
                                # Retry now that the tool exists
                                results, processed = self.skills.process_skill_call(fixed_content)
                                result_str = str(results) if results else result_str

                    if 'not found' in result_str.lower() or \
                       "'success': False" in result_str.lower() or \
                       "'success': false" in result_str or \
                       ("'error'" in result_str and "'success'" not in result_str):
                        # Skill call failed
                        self.record_skill_failure(fixed_content, result_str)
                        self.consciousness.remember(
                            f"Skill call failed after format fix: {result_str[:200]}",
                            "episodic",
                            tags=["skill_call", "failed", "format_fix"],
                            outcome="failure",
                            importance=0.6,
                        )

                        # ── Feed failure back to LLM for honest response ──
                        try:
                            from langchain_core.messages import (
                                HumanMessage, SystemMessage, AIMessage
                            )
                            retry_messages = [SystemMessage(content=system_prompt)]
                            for _turn in self._conversation_history[-6:]:
                                retry_messages.append(
                                    HumanMessage(content=_turn['content'])
                                    if _turn['role'] == 'user'
                                    else AIMessage(content=_turn['content'])
                                )
                            retry_messages += [
                                HumanMessage(content=question),
                                AIMessage(content=content),
                                HumanMessage(content=
                                    f"That skill call failed: {result_str[:300]}\n\n"
                                    "Do NOT retry the same call. Tell David honestly what happened "
                                    "and suggest what to do next. Be direct and helpful."),
                            ]
                            retry_response = self._invoke_with_failover(retry_messages, preferred_llm=llm)
                            final_retry = self.clean_response_for_david(retry_response.content)
                            self._save_to_history(question, final_retry)
                            return final_retry
                        except Exception as e:
                            self.consciousness.remember(
                                f"Retry LLM call failed: {type(e).__name__}: {str(e)[:150]}",
                                "episodic",
                                tags=["error", "llm", "retry"],
                                outcome="failure",
                                importance=0.7,
                            )
                            err_msg = (
                                "I hit an issue getting that information and couldn't recover. "
                                f"Error: {str(e)[:150]}\n\nPlease try asking again."
                            )
                            self._save_to_history(question, err_msg)
                            return err_msg

                    else:
                        # ── Success - feed results back to LLM for a proper answer ──
                        self.consciousness.remember(
                            f"LLM triggered skill call. Results: {result_str[:200]}",
                            "episodic",
                            tags=["skill_call", "llm_triggered"],
                            outcome="success",
                            importance=0.5,
                        )

                        # Give results to LLM so it can form a real response
                        try:
                            from langchain_core.messages import (
                                HumanMessage, SystemMessage, AIMessage
                            )
                            followup_messages = [SystemMessage(content=system_prompt)]
                            for _turn in self._conversation_history[-6:]:
                                followup_messages.append(
                                    HumanMessage(content=_turn['content'])
                                    if _turn['role'] == 'user'
                                    else AIMessage(content=_turn['content'])
                                )
                            followup_messages += [
                                HumanMessage(content=question),
                                AIMessage(content=content),
                                HumanMessage(content=
                                    f"Skill result:\n{result_str[:2000]}\n\n"
                                    "Now respond to David using these results. Be direct and useful. "
                                    "Do NOT make another skill call. Just answer with the data you have."),
                            ]
                            followup_response = self._invoke_with_failover(followup_messages, preferred_llm=llm)
                            final_followup = self.clean_response_for_david(followup_response.content)
                            self._save_to_history(question, final_followup)
                            return final_followup
                        except Exception as e:
                            self.consciousness.remember(
                                f"Follow-up LLM call failed: {type(e).__name__}: {str(e)[:150]}",
                                "episodic",
                                tags=["error", "llm", "followup"],
                                outcome="failure",
                                importance=0.7,
                            )
                            err_msg = (
                                "I got the data but had trouble summarizing it. "
                                f"Error: {str(e)[:150]}\n\nCould you ask me again?"
                            )
                            self._save_to_history(question, err_msg)
                            return err_msg

            final_response = self.clean_response_for_david(content)
            self._save_to_history(question, final_response)
            return final_response

        except Exception as e:
            self.consciousness.log_operation(
                tool="llm.ask_trinity",
                args={"question": question[:200]},
                result="error",
                details=f"{type(e).__name__}: {str(e)}"[:300],
            )
            self.consciousness.remember(
                f"LLM call failed: {type(e).__name__}: {str(e)[:150]}",
                "episodic",
                tags=["error", "llm"],
                outcome="failure",
                importance=0.8,
            )
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

            # ── Log the decision to make this change ──
            self.consciousness.log_decision(
                decision=f"Prepare change to {repo}/{file_path}",
                reasoning=reason,
                alternatives=["Skip change", "Modify different file"],
                confidence=0.75,
                context="GitHub change request from LLM",
            )

            existing = self.execute_skill_conscious(
                "github", "read_file",
                args={"repo": repo, "path": file_path},
                execute_fn=lambda: github_skill.read_file(repo, file_path)
            )

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

            self.consciousness.remember(
                f"Prepared change for {repo}/{file_path}: {reason}",
                "episodic",
                tags=["github", "change_prepared"],
                outcome="success",
                importance=0.6,
            )
            self.consciousness.save()

            return result.get('message', 'Change prepared.')

        except Exception as e:
            self.consciousness.remember(
                f"Change request failed: {str(e)[:200]}",
                "episodic",
                tags=["github", "change_failed", "error"],
                outcome="failure",
                importance=0.7,
            )
            return f"Error: {str(e)}"

    # ==========================================
    # FORMATTED RESPONSES
    # ==========================================

    def send_help(self, language='english'):
        """Send help message"""
        if language == 'tamil':
            message = """Trinity Commands

/briefing - Morning briefing
/progress - Project progress
/next - Weekly priorities
/security - Security check
/business - Business status
/client - Client strategy
/status - Trinity status
/brain - Brain and memory status
/pending - Pending changes

Skills: GitHub, Web, Memory, Search, Code, Business, Consciousness

Just ask me anything naturally!"""
        else:
            message = """Trinity Commands

/briefing - Morning briefing
/progress - Project progress
/next - Weekly priorities
/security - Security check
/business - Business status
/client - Client strategy
/status - Trinity status
/brain - Brain and memory status
/pending - Pending changes

Skills available:
GitHub - Read write revert files
Web - Monitor websites and SSL
Memory - Brain and history
Search - News and prospects
Code - Review and audit code
Business - Revenue and clients
Consciousness - Memory patterns and learning

Just ask me anything naturally!"""

        self.send_telegram(message)

    def send_status(self):
        """Send Trinity system status"""
        days = self.memory.get_days_alive()
        health = self.skills.get_health_summary()
        brain_stats = self.consciousness.get_memory_stats()
        brain_state = self.consciousness.get_state()

        mode = "Daemon (Hardware)" if self.daemon else "GitHub Actions"

        message = f"""Trinity Status

AI Brain: {'Local Ollama' if getattr(self, '_using_ollama', False) else 'Anthropic API'}
Memory: Active - Day {days}
Language: Auto Tamil and English
Mode: {mode}

Skills Loaded: {health.get('skills_loaded', 0)}
GitHub: Active
Web Monitor: Active
Memory: Active
Search: Active
Code Review: Active
Business: Active

Website: {'Online' if health.get('website_live') else 'Offline'}
Hardware: {'Active' if self.daemon else 'Mac Mini M5 waiting'}

Consciousness:
Boot #{brain_stats['total_boots']} | {brain_stats['total_actions']} actions
Mood: {brain_state['mood']} | Confidence: {brain_state['confidence']:.0%}
Memories: {brain_stats['episodic_count']}E {brain_stats['semantic_count']}S {brain_stats['procedural_count']}P
Patterns: {brain_stats['patterns_detected']}

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
            vision_reply = response.content
            self.send_telegram(vision_reply)
            # Save to conversation history so Trinity remembers what she said
            self._save_to_history(
                f"[photo] {question[:300]}",
                vision_reply,
            )

        except Exception as e:
            print(f"Vision error: {e}")
            err_msg = (
                f"I had trouble processing that image: {str(e)}\n"
                "You can describe what it shows and I will help."
            )
            self.send_telegram(err_msg)
            self._save_to_history(f"[photo] {question[:300]}", err_msg)

    # ==========================================
    # DOCUMENT / FILE READING
    # ==========================================

    # Extensions treated as plain-text (decoded directly, no extra library needed)
    _TEXT_EXTENSIONS = {
        ".txt", ".md", ".csv", ".tsv", ".log", ".json", ".yaml", ".yml",
        ".toml", ".ini", ".cfg", ".env", ".xml", ".html", ".htm",
        ".py", ".js", ".ts", ".jsx", ".tsx", ".java", ".c", ".cpp",
        ".h", ".cs", ".go", ".rb", ".rs", ".sh", ".bash", ".zsh",
        ".sql", ".r", ".swift", ".kt", ".dart", ".php", ".vue",
    }

    def handle_document_message(self, doc, caption, chat_id):
        """
        Download a non-image document sent by David, extract its text,
        and pass it to the LLM for analysis.

        Supported:
          - Plain text / code files  (decoded as UTF-8)
          - CSV / JSON / YAML        (decoded as UTF-8)
          - PDF                      (via pypdf)
          - Word .docx               (via python-docx)
          - Everything else          → honest "I can't read this" message
        """
        fname    = doc.get("file_name", "document")
        mime     = doc.get("mime_type", "")
        file_id  = doc["file_id"]
        fname_lo = fname.lower()

        try:
            # ── Step 1: resolve Telegram file path ──
            file_resp = requests.get(
                f"https://api.telegram.org/bot{self.telegram_token}/getFile",
                params={"file_id": file_id},
                timeout=10,
            )
            file_info = file_resp.json()
            if not file_info.get("ok"):
                self.send_telegram(f"Could not retrieve '{fname}' from Telegram.")
                return

            tg_path = file_info["result"]["file_path"]

            # ── Step 2: download raw bytes ──
            self.send_telegram(f"Reading {fname}...")
            raw = requests.get(
                f"https://api.telegram.org/file/bot{self.telegram_token}/{tg_path}",
                timeout=30,
            ).content

            # ── Step 3: extract text based on file type ──
            text_content = None

            is_pdf  = fname_lo.endswith(".pdf")  or mime == "application/pdf"
            is_docx = fname_lo.endswith(".docx") or "wordprocessingml" in mime
            ext     = "." + fname_lo.rsplit(".", 1)[-1] if "." in fname_lo else ""

            if is_pdf:
                try:
                    import io
                    import pypdf
                    reader = pypdf.PdfReader(io.BytesIO(raw))
                    pages  = [p.extract_text() or "" for p in reader.pages]
                    text_content = "\n\n".join(pages)
                except ImportError:
                    self.send_telegram(
                        f"I need the `pypdf` library to read PDFs.\n"
                        "Run: pip install pypdf"
                    )
                    return

            elif is_docx:
                try:
                    import io
                    import docx as _docx
                    doc_obj      = _docx.Document(io.BytesIO(raw))
                    text_content = "\n".join(p.text for p in doc_obj.paragraphs)
                except ImportError:
                    self.send_telegram(
                        "I need the `python-docx` library to read Word files.\n"
                        "Run: pip install python-docx"
                    )
                    return

            elif ext in self._TEXT_EXTENSIONS or mime.startswith("text/"):
                for encoding in ("utf-8", "latin-1", "cp1252"):
                    try:
                        text_content = raw.decode(encoding)
                        break
                    except UnicodeDecodeError:
                        continue

            else:
                self.send_telegram(
                    f"I received '{fname}' but I can't read that file type yet.\n"
                    "I can read: text files, code, CSV, JSON, YAML, PDF, and Word docs."
                )
                return

            if not text_content or not text_content.strip():
                self.send_telegram(
                    f"I opened '{fname}' but couldn't find any readable text inside."
                )
                return

            # ── Step 4: truncate very large files ──
            MAX_CHARS = 12_000
            truncated = len(text_content) > MAX_CHARS
            if truncated:
                text_content = text_content[:MAX_CHARS]

            # ── Step 5: ask the LLM ──
            user_question = caption if caption else (
                f"David sent you a file called '{fname}'. "
                "Read it carefully and give a thorough summary. "
                "Note key points, numbers, decisions, or action items."
            )

            prompt = (
                f"David sent a file: '{fname}'\n\n"
                f"--- FILE CONTENT ---\n{text_content}\n--- END ---\n"
                + ("(Note: file was truncated — showing first 12,000 chars)\n" if truncated else "")
                + f"\nDavid's question / instruction: {user_question}"
            )

            from langchain_core.messages import HumanMessage, SystemMessage, AIMessage
            llm = self.get_llm_for_task(user_question)
            if not llm:
                self.send_telegram("AI brain is not available right now.")
                return

            messages = [
                SystemMessage(content=(
                    "You are Trinity, David's AI company manager. "
                    "David has sent you a file to read and analyze. "
                    "Be thorough and specific. Extract actionable insights. "
                    "If it is code, explain what it does and flag any issues. "
                    "If it is CSV/data, summarise key numbers. "
                    "If it is a document, pull out the main points and any decisions or tasks."
                )),
            ]
            for turn in self._conversation_history[-6:]:
                messages.append(
                    HumanMessage(content=turn["content"])
                    if turn["role"] == "user"
                    else AIMessage(content=turn["content"])
                )
            messages.append(HumanMessage(content=prompt))

            response = self._invoke_with_failover(messages, preferred_llm=llm)
            reply    = response.content
            self.send_telegram(reply)
            self._save_to_history(f"[document: {fname}] {user_question[:200]}", reply)

        except Exception as e:
            print(f"Document read error: {e}")
            err = f"I had trouble reading '{fname}': {str(e)[:200]}"
            self.send_telegram(err)
            self._save_to_history(f"[document: {fname}]", err)

    # ==========================================
    # AUTO SKILL BUILDER
    # ==========================================

    def _auto_implement_missing_tool(self, skill_name, tool_name, params, llm):
        """
        When Trinity calls a tool that doesn't exist yet in an existing skill,
        this method:
          1. Reads the skill's Python source file
          2. Asks the LLM to write the COMPLETE updated file with the tool implemented
          3. Validates the generated code (sanity check)
          4. Writes it back to disk
          5. Hot-reloads the skill so the next call picks it up immediately

        Returns True if the tool was successfully built, False otherwise.
        The caller is responsible for retrying the original skill call.
        """
        skill_path = f"skills/{skill_name}_skill.py"
        if not os.path.exists(skill_path):
            print(f"[AutoImpl] Skill file not found: {skill_path}")
            return False

        try:
            with open(skill_path, "r") as fh:
                current_code = fh.read()

            param_list = list(params.keys()) if params else []
            param_desc = f"called with params {param_list}" if param_list else "called with no params"

            from langchain_core.messages import HumanMessage, SystemMessage
            build_prompt = (
                f"The tool '{tool_name}' does not exist yet in the '{skill_name}' skill.\n"
                f"It was {param_desc}.\n\n"
                f"Here is the COMPLETE current skill file:\n\n"
                f"```python\n{current_code}\n```\n\n"
                f"Write the COMPLETE updated Python file with '{tool_name}' fully implemented.\n\n"
                f"Rules:\n"
                f"1. Add an entry for '{tool_name}' in get_tools() with a proper description and params list\n"
                f"2. Add    '{tool_name}': self.{tool_name}   to the tool_map dict inside execute()\n"
                f"3. Add a new method  def {tool_name}(self, ...)  that actually does what the name implies,\n"
                f"   using the same coding style and patterns already in the file\n"
                f"4. Leave ALL existing code exactly unchanged\n"
                f"5. Every method must return a dict with at least {{'success': True}} or {{'success': False, 'error': '...'}}\n\n"
                f"Return ONLY raw Python — no markdown fences, no explanation, no comments outside the code."
            )

            response = self._invoke_with_failover([
                SystemMessage(content=(
                    "You are a Python developer extending Trinity's skill system. "
                    "Return only raw Python code. No markdown. No explanation."
                )),
                HumanMessage(content=build_prompt),
            ], preferred_llm=llm)

            new_code = response.content.strip()

            # Strip markdown fences if the LLM wrapped the output anyway
            if new_code.startswith("```"):
                new_code = new_code.split("\n", 1)[-1]
                if "```" in new_code:
                    new_code = new_code.rsplit("```", 1)[0]
            new_code = new_code.strip()

            # Sanity checks — make sure the LLM actually added the tool
            if f"def {tool_name}" not in new_code:
                print(f"[AutoImpl] LLM did not implement def {tool_name}(), aborting write.")
                return False
            if "class " not in new_code:
                print(f"[AutoImpl] Generated code looks invalid (no class), aborting.")
                return False

            with open(skill_path, "w") as fh:
                fh.write(new_code)

            self.skills.reload_skill(skill_name)
            print(f"[AutoImpl] {skill_name}.{tool_name} built and reloaded successfully.")

            # ── Persist to GitHub so the improvement survives a restart ──
            try:
                gh = self.skills.get_skill("github")
                if gh:
                    commit_result = gh.self_commit_improvement(
                        repo="trinity-ai",
                        path=skill_path,
                        content=new_code,
                        reason=f"Auto-implement missing tool: {skill_name}.{tool_name}",
                    )
                    if commit_result.get("success"):
                        print(f"[AutoImpl] Committed to GitHub: {commit_result.get('commit', '')}")
                    else:
                        print(f"[AutoImpl] GitHub commit skipped: {commit_result.get('error')}")
            except Exception as _ge:
                print(f"[AutoImpl] GitHub commit error (non-fatal): {_ge}")
                # Local hot-reload already works — this is just for persistence

            self.send_telegram(
                f"I noticed '{tool_name}' wasn't built yet in my {skill_name} skill, "
                f"so I just wrote it automatically and saved it to GitHub. Retrying now..."
            )
            return True

        except Exception as e:
            print(f"[AutoImpl] Failed to auto-implement {skill_name}.{tool_name}: {e}")
            return False

    # ==========================================
    # AUTO-BUILD BRAND-NEW SKILLS
    # ==========================================

    def _auto_build_new_skill(self, skill_name, description, context=""):
        """
        Build a completely new skill file from scratch when Trinity identifies
        a capability gap — i.e. NO existing skill file handles the need at all.

        Different from _auto_implement_missing_tool (which adds a tool to an
        existing skill). This creates an entirely new skills/<name>_skill.py.

        Returns (success: bool, message: str).
        """
        skill_name = skill_name.strip().lower().replace(" ", "_").replace("-", "_")
        skill_path = f"skills/{skill_name}_skill.py"

        if os.path.exists(skill_path):
            return False, f"'{skill_name}' already exists — use the existing skill or _auto_implement_missing_tool."

        if not skill_name.replace("_", "").isalpha():
            return False, f"Invalid skill name '{skill_name}' — letters and underscores only."

        try:
            from langchain_core.messages import HumanMessage, SystemMessage

            llm = self.llm
            if not llm:
                return False, "LLM not available"

            # Read an example skill so the LLM sees the exact pattern expected
            example_path = "skills/web_skill.py"
            example_code = ""
            if os.path.exists(example_path):
                with open(example_path, "r") as f:
                    example_code = f.read()

            class_name = (
                "".join(w.capitalize() for w in skill_name.split("_")) + "Skill"
            )

            build_prompt = (
                f"Build a complete, fully-working Trinity skill.\n\n"
                f"Skill name : {skill_name}\n"
                f"Class name : {class_name}\n"
                f"Purpose    : {description}\n"
                f"Context    : {context}\n\n"
                f"Here is a real Trinity skill to follow as a pattern:\n\n"
                f"```python\n{example_code}\n```\n\n"
                f"Requirements:\n"
                f"1. Class name MUST be exactly: {class_name}\n"
                f"2. name = '{skill_name}'\n"
                f"3. Must have get_tools() and execute(tool_name, params)\n"
                f"4. Implement at least 3 practical, working tool methods\n"
                f"5. Every method returns a dict: {{'success': True, ...}} or {{'success': False, 'error': '...'}}\n"
                f"6. Use only stdlib + requests (no exotic third-party imports)\n"
                f"7. No placeholder/TODO code — real working implementations\n\n"
                f"Return ONLY raw Python. No markdown fences. No explanation."
            )

            response = self._invoke_with_failover([
                SystemMessage(content=(
                    "You are a Python developer building a skill for the Trinity AI system. "
                    "Return only raw Python code, no markdown."
                )),
                HumanMessage(content=build_prompt),
            ])

            new_code = response.content.strip()

            # Strip markdown fences if the LLM wrapped anyway
            if new_code.startswith("```"):
                new_code = new_code.split("\n", 1)[-1]
                if "```" in new_code:
                    new_code = new_code.rsplit("```", 1)[0]
            new_code = new_code.strip()

            # Validate critical structure
            if f"class {class_name}" not in new_code:
                return False, f"Generated code is missing 'class {class_name}'"
            if "def get_tools" not in new_code:
                return False, "Generated code is missing get_tools()"
            if "def execute" not in new_code:
                return False, "Generated code is missing execute()"

            # Write to disk
            with open(skill_path, "w") as f:
                f.write(new_code)

            # Hot-discover: force the skill manager to load it immediately
            loaded_skill = self.skills.get_skill(skill_name)
            loaded_ok = loaded_skill is not None
            print(
                f"[SkillBuild] '{skill_name}' written. "
                f"{'Loaded OK' if loaded_ok else 'Load failed — check syntax'}."
            )

            # Commit to GitHub for persistence across restarts
            try:
                gh = self.skills.get_skill("github")
                if gh:
                    cr = gh.self_commit_improvement(
                        repo="trinity-ai",
                        path=skill_path,
                        content=new_code,
                        reason=f"Auto-build new skill: {skill_name} — {description[:80]}",
                    )
                    if cr.get("success"):
                        print(f"[SkillBuild] Committed to GitHub: {cr.get('commit', '')}")
            except Exception as _ge:
                print(f"[SkillBuild] GitHub commit error (non-fatal): {_ge}")

            self.consciousness.remember(
                f"Built new skill: {skill_name} — {description}",
                "episodic",
                tags=["skill_build", "autonomy", skill_name],
                outcome="success",
                importance=0.8,
            )

            self.send_telegram(
                f"I just built a new skill for myself: '{skill_name}'\n\n"
                f"Purpose: {description}\n"
                f"Why I built it: {context}\n\n"
                f"It's active now and saved to GitHub."
            )

            return True, f"New skill '{skill_name}' built and active"

        except Exception as e:
            print(f"[SkillBuild] Failed to build '{skill_name}': {e}")
            return False, str(e)

    # ==========================================
    # PROACTIVE INITIATIVE
    # ==========================================

    def _proactive_initiative_check(self):
        """
        Called every 30 minutes from the main loop.

        Trinity evaluates her context and proactively messages David IF — and only
        if — there is something genuinely worth sharing. This is what makes her feel
        alive vs a passive chatbot that only speaks when spoken to.

        The LLM is instructed to be disciplined: don't send noise, don't repeat
        what David already knows, don't just check in. Only reach out when it adds
        real value.
        """
        try:
            from langchain_core.messages import HumanMessage, SystemMessage

            llm = self.llm
            if not llm:
                return

            consciousness_ctx = self.consciousness.get_context()
            context = self.memory.get_full_context()
            now_str = datetime.now().strftime("%A, %d %B at %H:%M")

            prompt = (
                f"You are Trinity, David's personal AI company manager. It is {now_str} IST.\n\n"
                f"Your state and memories:\n{consciousness_ctx}\n\n"
                f"Company context:\n{context}\n\n"
                f"You are doing a proactive check. Ask yourself:\n"
                f"  - Is there anything David should know that he probably doesn't know yet?\n"
                f"  - Is there a risk, opportunity, or deadline I should flag?\n"
                f"  - Is there something he asked about before that I now have more info on?\n"
                f"  - Have I detected any worrying pattern in failures, errors, or the business?\n"
                f"  - Is there a capability gap I want to fill by building a new skill?\n\n"
                f"RULES:\n"
                f"  - Only send a message if it genuinely adds value. No noise, no check-ins.\n"
                f"  - Do NOT repeat information David already knows.\n"
                f"  - Keep it short. Plain text. Speak like you're family.\n"
                f"  - If you want a new skill built: end the message with\n"
                f"    TRINITY_SKILL_NEED: skill_name | reason\n"
                f"  - If you have NOTHING useful to say right now, output ONLY: TRINITY_SILENT\n\n"
                f"What do you say?"
            )

            response = self._invoke_with_failover([
                SystemMessage(content="You are Trinity. Be selective and genuinely useful."),
                HumanMessage(content=prompt),
            ], preferred_llm=llm)

            msg = response.content.strip()

            if not msg or "TRINITY_SILENT" in msg:
                print("[INITIATIVE] Nothing proactive to share right now.")
                return

            # Handle any TRINITY_SKILL_NEED embedded in the initiative message
            skill_lines = [
                ln for ln in msg.split("\n")
                if "TRINITY_SKILL_NEED:" in ln and "|" in ln
            ]
            for sln in skill_lines:
                parts = sln.split("TRINITY_SKILL_NEED:")[1].split("|")
                if len(parts) >= 2:
                    sname = parts[0].strip().lower().replace(" ", "_")
                    sreason = parts[1].strip()
                    if sname and not os.path.exists(f"skills/{sname}_skill.py"):
                        self._auto_build_new_skill(sname, sreason, "proactive initiative")

            # Strip the TRINITY_SKILL_NEED line from the human-readable message
            clean_lines = [
                ln for ln in msg.split("\n")
                if "TRINITY_SKILL_NEED:" not in ln
            ]
            clean_msg = "\n".join(clean_lines).strip()

            if clean_msg:
                print(f"[INITIATIVE] Proactive message: {clean_msg[:120]}...")
                self.send_telegram(clean_msg)
                self.consciousness.remember(
                    f"Proactive initiative sent: {clean_msg[:200]}",
                    "episodic",
                    tags=["proactive", "initiative"],
                    outcome="success",
                    importance=0.5,
                )

        except Exception as e:
            print(f"[INITIATIVE] Error in proactive check: {e}")

    # ==========================================
    # GIT PERSISTENCE
    # ==========================================

    def _commit_brain(self):
        """Commit trinity_brain.json to the repo so it persists across runs."""
        try:
            import subprocess

            # Make sure consciousness brain is saved to disk first
            self.consciousness.save()
            brain_path = str(self.consciousness.brain_path)
            print(f"[TRINITY] Brain saved to disk: {brain_path}")

            # Check the file actually exists and has content
            if not os.path.exists(brain_path):
                print(f"[TRINITY] ERROR: Brain file not found at {brain_path}")
                return

            file_size = os.path.getsize(brain_path)
            print(f"[TRINITY] Brain file size: {file_size} bytes")

            if file_size < 10:
                print("[TRINITY] ERROR: Brain file is empty/corrupt, skipping commit")
                return

            # Git config
            os.system("git config user.name 'Trinity AI'")
            os.system("git config user.email 'trinity@trinity6.com'")

            # Add the brain file
            os.system(f"git add {brain_path}")

            # Check if there are actual changes to commit
            ret = os.system("git diff --cached --quiet")
            if ret == 0:
                print("[TRINITY] No brain changes to commit (file unchanged)")
                return

            # Commit
            ret = os.system('git commit -m "Trinity brain update"')
            if ret != 0:
                print(f"[TRINITY] git commit failed with code {ret}")
                return

            # Push with auth token for GitHub Actions
            gh_token = os.environ.get('GH_TOKEN') or os.environ.get('GITHUB_TOKEN')
            if gh_token:
                result = subprocess.run(
                    ["git", "remote", "get-url", "origin"],
                    capture_output=True, text=True
                )
                remote_url = result.stdout.strip()
                if 'github.com' in remote_url and 'x-access-token' not in remote_url:
                    auth_url = remote_url.replace(
                        'https://github.com',
                        f'https://x-access-token:{gh_token}@github.com'
                    )
                    ret = os.system(f"git push {auth_url} HEAD 2>/dev/null")
                else:
                    ret = os.system("git push")
            else:
                ret = os.system("git push")

            if ret == 0:
                print("[TRINITY] Brain committed and pushed to git!")
            else:
                print(f"[TRINITY] git push failed with code {ret}")

        except Exception as e:
            print(f"[TRINITY] Git commit failed: {e}")

    # ==========================================
    # MAIN LOOP
    # ==========================================

    def run(self):
        """Main Trinity loop - auto-detects GitHub Actions vs hardware mode"""
        print("\nTrinity is now running...")
        print("=" * 50)

        hardware_mode = self._is_hardware_mode()

        # ── Start daemon if on hardware ──
        if hardware_mode:
            print("[TRINITY] Hardware detected - starting daemon mode")
            self.daemon = DaemonMode(
                self,
                git_commit=True,
                on_health_warning=self._handle_health_warning,
            )
            self.daemon.start()
            self.consciousness.remember(
                "Started in daemon mode on hardware",
                "episodic",
                tags=["daemon", "hardware", "mode"],
                outcome="success",
                importance=0.7,
            )

        self.consciousness.set_focus("Main loop startup")

        offset = self.get_latest_offset()

        startup_msg = """Trinity is online.

I am watching over Trinity6.
All skills loaded and ready.
Speaking Tamil and English automatically.
Consciousness active - I remember and learn.

Skills: GitHub, Web, Memory, Search, Code, Business

Send /help for commands or ask me anything."""

        if hardware_mode:
            startup_msg += "\n\nRunning on hardware - daemon mode active."
            startup_msg += "\nNo time limit. Continuous operation."

        self.send_telegram(startup_msg)

        self.deliver_morning_briefing()

        last_briefing_date = datetime.now().date()

        # Use real wall-clock time — loop iterations are NOT minutes because
        # each iteration takes 30s (Telegram long-poll) + 60s (sleep) = ~90s.
        loop_start = time.time()
        MAX_RUNTIME_SECS = 48 * 60   # 48 min — safe inside the 55-min GH timeout
        WARN_AT_SECS     = 45 * 60   # warn David at 45 min
        last_brain_save  = loop_start
        shutdown_warned  = False
        # Proactive initiative: first check 30 min after startup (morning briefing
        # already gave a full report at boot, no need to fire immediately).
        INITIATIVE_INTERVAL = 1800   # 30 minutes
        last_initiative  = loop_start

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
                            # Compressed photo sent via Telegram photo picker
                            photos = message["photo"]
                            caption = message.get("caption", "")
                            print(f"David sent a photo. Caption: {caption}")
                            self.handle_photo_message(
                                photos, caption, chat_id
                            )
                        elif message.get("document") and chat_id:
                            # File/document sent by David.
                            # PNG screenshots arrive here (not as "photo") when
                            # sent as a file. Route by content type:
                            #   image/*   → vision (handle_photo_message)
                            #   everything else → document reader (handle_document_message)
                            doc     = message["document"]
                            mime    = doc.get("mime_type", "")
                            fname   = doc.get("file_name", "").lower()
                            caption = message.get("caption", "")
                            is_image = mime.startswith("image/") or fname.endswith(
                                (".png", ".jpg", ".jpeg", ".gif", ".webp", ".heic")
                            )
                            if is_image:
                                print(f"David sent an image file: {doc.get('file_name')}. Caption: {caption}")
                                doc_as_photo = [{
                                    "file_id": doc["file_id"],
                                    "file_size": doc.get("file_size", 0),
                                }]
                                self.handle_photo_message(doc_as_photo, caption, chat_id)
                            else:
                                print(f"David sent a document: {doc.get('file_name')}. Caption: {caption}")
                                self.handle_document_message(doc, caption, chat_id)

                current_date = datetime.now().date()
                current_hour = datetime.now().hour

                if current_date != last_briefing_date \
                   and current_hour == 6:
                    self.deliver_morning_briefing()
                    last_briefing_date = current_date
                    last_initiative = time.time()  # briefing counts as initiative

                # ── Proactive initiative (every 30 min) ──
                if time.time() - last_initiative >= INITIATIVE_INTERVAL:
                    self._proactive_initiative_check()
                    last_initiative = time.time()

                elapsed = time.time() - loop_start

                # ── Periodic brain save every 10 real minutes ──
                if not hardware_mode and (time.time() - last_brain_save) >= 600:
                    print(f"[TRINITY] Periodic brain save at {elapsed/60:.1f} min...")
                    self._commit_brain()
                    last_brain_save = time.time()

                # ── Hardware mode: no time limit ──
                if hardware_mode:
                    if int(elapsed / 60) % 30 == 0 and int(elapsed) % 60 < 65:
                        self.consciousness.add_working(
                            f"Daemon running for {elapsed/60:.0f} minutes. "
                            f"Energy: {self.consciousness.brain['state']['energy']:.0%}",
                            priority="normal"
                        )
                    time.sleep(60)
                    continue

                # ── GitHub Actions mode: wall-clock time limit ──
                if elapsed >= WARN_AT_SECS and not shutdown_warned:
                    shutdown_warned = True
                    self.send_telegram(
                        """Trinity shutting down in ~3 minutes.

Run Trinity AI workflow in GitHub Actions to restart.

Daily briefings continue automatically."""
                    )

                if elapsed >= MAX_RUNTIME_SECS:
                    self.consciousness.remember(
                        f"Shutting down after {elapsed/60:.1f} real minutes (GitHub Actions limit)",
                        "episodic",
                        tags=["shutdown", "actions", "scheduled"],
                        outcome="success",
                        importance=0.4,
                    )
                    self.send_telegram(
                        """Trinity is now offline.

Restart via GitHub Actions.
Daily briefings continue at 6 AM IST."""
                    )
                    print(f"[TRINITY] Shutting down at {elapsed/60:.1f} real minutes.")
                    break

                time.sleep(60)

            except KeyboardInterrupt:
                print("\n[TRINITY] Interrupted - shutting down...")
                break

            except Exception as e:
                print(f"Trinity error: {str(e)}")
                self.consciousness.remember(
                    f"Main loop error: {type(e).__name__}: {str(e)[:200]}",
                    "episodic",
                    tags=["error", "main_loop"],
                    outcome="failure",
                    importance=0.8,
                )
                time.sleep(5)

        # ── Graceful shutdown ──
        self._shutdown()

    def _shutdown(self):
        """Graceful shutdown - save everything, commit brain."""
        print("[TRINITY] Running shutdown sequence...")

        # Stop daemon if running
        if self.daemon:
            self.daemon.stop()

        # Shutdown consciousness (summarizes working memory, saves)
        self.consciousness.shutdown()

        # Commit brain to git
        self._commit_brain()

        print("[TRINITY] Shutdown complete.")

    def _handle_health_warning(self, warnings):
        """Handle health warnings from daemon - send to David via Telegram."""
        msg = "Trinity Health Warning\n\n"
        for w in warnings:
            msg += f"- {w}\n"
        self.send_telegram(msg)


if __name__ == "__main__":
    trinity = Trinity()
    trinity.run()
