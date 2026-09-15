import os
import sys
import time
from datetime import datetime

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.memory import TrinityMemory
from core.skill_manager import SkillManager
from core.consciousness import Consciousness
from core.daemon import DaemonMode  # compatibility alias for existing integrations/tests
from core.memory_store import MemoryStore
from core.memory_pipeline import ConversationMemoryPipeline
from core.channels import TelegramChannel
from core.ai_service import LocalAIService, build_local_ai_from_environment
from core.orchestrator import MessageKind, MessageOrchestrator
from core.events import EventBus
from core.audit import ActionAuditTrail
from core.notifications import NotificationService
from core.permissions import PermissionEngine
from core.awareness import AwarenessEngine
from core.presence import PresenceEngine
from core.presence_web import PresenceServer
from core.vision import LocalVisionService
from core.perception import PerceptionService
from core.proactive import ProactiveEngine
from core.commands import CommandHandler
from core.computer import ComputerController
from core.agent_bootstrap import build_default_agent_registry
from core.persistence import StatePersistence
from core.runtime import RuntimeMode, detect_runtime
from core.attachments import AttachmentService
from core.lifecycle import RuntimeLoop
from core.api_runtime import LocalAPIServer
from core.conversation import ConversationService
from core.response_processing import ResponseProcessor
from core.change_requests import ChangeRequestService
from core.briefing import BriefingService
from core.proactive_service import ProactiveService
from core.message_service import MessageService
from core.skill_evolution import SkillEvolutionService
from core.status_service import StatusService
from core.bootstrap import seed_foundational_knowledge
from voice.language import LanguageDetector
from voice.speak import TrinityVoice
from voice.session import VoiceSessionController
from voice.capture import FfmpegMicrophoneCapture
from voice.runtime import LocalVoiceRuntime


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
        self.runtime_mode = detect_runtime()

        self.telegram_token = os.environ.get('TELEGRAM_BOT_TOKEN')
        self.chat_id = os.environ.get('TELEGRAM_CHAT_ID')
        self.gh_token = os.environ.get('GH_TOKEN')

        print("Loading memory...")
        self.memory = TrinityMemory()

        # Durable local Memory Vault (SQLite operational memory + Markdown).
        self.memory_store = MemoryStore()
        self.memory_pipeline = ConversationMemoryPipeline(self.memory_store)
        try:
            self.memory_store.import_legacy_brain(self.memory.brain)
        except Exception as exc:
            print(f"Memory Vault migration warning: {exc}")

        # ── Consciousness ──
        print("Loading consciousness...")
        self.consciousness = Consciousness("trinity_brain.json")
        self.persistence = StatePersistence(self.consciousness, self.memory_store)
        self.daemon = None  # set in run() if hardware mode
        self.events = EventBus()
        self.presence = PresenceEngine(self.events)
        self.awareness = AwarenessEngine(self.events)
        self.presence_server = PresenceServer(
            self.presence,
            awareness=self.awareness,
            host="127.0.0.1",
            port=int(os.environ.get("TRINITY_PRESENCE_PORT", "8765")),
        )
        self.audit = ActionAuditTrail(event_bus=self.events)
        self.permissions = PermissionEngine()

        telegram_enabled = os.environ.get("TRINITY_TELEGRAM_ENABLED", "true").lower() in {"1", "true", "yes"}
        telegram_notifications = os.environ.get("TRINITY_TELEGRAM_NOTIFICATIONS", "false").lower() in {"1", "true", "yes"}
        self.telegram = TelegramChannel(
            self.telegram_token,
            self.chat_id,
            error_handler=self._record_telegram_error,
            enabled=telegram_enabled,
            remote_notifications=telegram_notifications,
        )

        print("Setting up language detection...")
        self.language = LanguageDetector()

        print("Setting up voice...")
        self.voice = TrinityVoice(
            telegram_token=self.telegram_token,
            chat_id=self.chat_id
        )
        self.voice_session = VoiceSessionController(
            self.voice.local_voice,
            responder=lambda text, language: self.ask_trinity(text, language),
            on_state_change=lambda state: self.events.publish(
                "voice.state", state=state.value
            ),
            wake_words=(os.environ.get("TRINITY_WAKE_WORD", "trinity"),),
            require_wake_word=os.environ.get(
                "TRINITY_VOICE_REQUIRE_WAKE_WORD", "true"
            ).lower() in {"1", "true", "yes"},
        )
        self.voice_runtime = LocalVoiceRuntime(
            self.voice_session,
            FfmpegMicrophoneCapture(),
            chunk_seconds=float(os.environ.get("TRINITY_MIC_CHUNK_SECONDS", "5")),
            event_bus=self.events,
        )
        self.notifications = NotificationService(
            self.events, telegram=self.telegram, voice=self.voice
        )
        self.computer = ComputerController(
            permissions=self.permissions, audit_trail=self.audit
        )

        print("Loading all skills...")
        self.skills = SkillManager(
            gh_token=self.gh_token,
            brain_file="memory/trinity_brain.json",
            permission_engine=self.permissions,
            audit_trail=self.audit,
            computer_controller=self.computer,
        )

        print("Setting up AI brain...")
        self.llm = self.setup_llm()
        self.vision = LocalVisionService.from_environment()
        self.attachments = AttachmentService(self, self.telegram.download_file, self.vision)
        self.agents = build_default_agent_registry(
            memory=self.memory, llm=self.llm, gh_token=self.gh_token,
            permissions=self.permissions, audit_trail=self.audit,
        )

        print("Caching GitHub context...")
        self.github_context_cache = \
            self.skills.get_github_context()

        self.memory.update_last_wakeup()

        # ── Boot consciousness ──
        self.consciousness.boot()
        self._failed_skill_calls = {}  # track skill call failures for loop prevention
        self.response_processor = ResponseProcessor(self._failed_skill_calls)
        self._conversation_history = []  # rolling window so Trinity remembers what she just said
        self.conversation = ConversationService(self)
        self.change_requests = ChangeRequestService(self)
        self.briefings = BriefingService(self)
        self.proactive_service = ProactiveService(self)
        self.orchestrator = MessageOrchestrator()
        self.messages = MessageService(self)
        self.skill_evolution = SkillEvolutionService(self)
        self.status_service = StatusService(self)
        self.proactive = ProactiveEngine()
        self.commands = CommandHandler(self)
        self.perception = PerceptionService(
            self.computer,
            self.vision,
            event_bus=self.events,
            audit_trail=self.audit,
            context_sink=self.awareness.update_visual_context,
        )
        self.api_server = LocalAPIServer(self)
        self.lifecycle = RuntimeLoop(self)

        # Seed knowledge on first ever boot
        if self.consciousness.brain["meta"]["total_boots"] == 1:
            self._seed_knowledge()

        # Log this boot
        self.consciousness.add_working(
            f"Trinity fully initialized. LLM: {getattr(self, '_local_model_name', 'local')}",
            priority="high"
        )
        self.consciousness.save()

        print("Trinity is awake and ready!")

    # ==========================================
    # SEED KNOWLEDGE (first boot only)
    # ==========================================

    def _seed_knowledge(self):
        """Compatibility wrapper for first-boot foundational knowledge."""
        return seed_foundational_knowledge(self)

    # ==========================================
    # DETECT OPERATION MODE
    # ==========================================

    def _is_hardware_mode(self):
        """Return True when Trinity should run as the always-on local daemon."""
        mode = getattr(self, "runtime_mode", detect_runtime())
        return mode == RuntimeMode.LOCAL_DAEMON

    # ==========================================
    # SETUP
    # ==========================================

    def setup_llm(self):
        """Initialize Trinity's provider-neutral local AI stack."""
        stack = build_local_ai_from_environment()
        self.model_router = stack.router
        self.ai = stack.service
        self._local_model_name = stack.general_model_name
        self._using_ollama = stack.ollama_available
        provider_name = getattr(stack, "provider_name", "ollama")
        provider_available = getattr(stack, "provider_available", stack.ollama_available)
        if provider_available:
            print(f"Local AI ready: {provider_name} at {stack.base_url}")
        else:
            print(f"Local AI configured but {provider_name} is unavailable at {stack.base_url}")
        return stack.default_model

    def get_llm_for_task(self, question):
        """Return the local model selected for this task."""
        ai = getattr(self, 'ai', None)
        if ai is not None:
            return ai.model_for(question)
        router = getattr(self, 'model_router', None)
        if router is not None:
            # Compatibility for partial initialization and unit tests.
            task = LocalAIService(router).classify_task(question)
            return router.model(task)
        return getattr(self, 'llm', None)

    # ==========================================
    # LLM INVOCATION WITH AUTOMATIC FAILOVER
    # ==========================================

    def _llm_label(self, llm):
        """Return a human-readable name for the active local model facade."""
        return LocalAIService.label(llm)

    def _invoke_with_failover(self, messages, preferred_llm=None):
        """Compatibility wrapper for local-only model invocation."""
        llm = preferred_llm or getattr(self, 'llm', None)
        if llm is None:
            raise RuntimeError("Local AI unavailable — start Ollama and install the configured model")
        ai = getattr(self, 'ai', None)
        if ai is not None:
            return ai.invoke(messages, model=llm)
        try:
            return llm.invoke(messages)
        except Exception as exc:
            raise RuntimeError(f"Local AI invocation failed: {exc}") from exc

    def _record_telegram_error(self, exc):
        """Record transport failures without coupling the channel to consciousness."""
        print(f"Telegram error: {exc}")
        try:
            self.consciousness.remember(
                f"Telegram send/poll failed: {str(exc)[:200]}",
                "episodic",
                tags=["error", "telegram"],
                outcome="failure",
                importance=0.6,
            )
        except Exception:
            pass

    def send_telegram(self, message):
        """Direct reply over the optional Telegram remote-chat channel."""
        return self.telegram.send(message)

    def notify(self, message, *, category="general", urgent=False, speak=False):
        """Publish a local notification with optional opt-in remote delivery."""
        return self.notifications.notify(
            message, category=category, urgent=urgent, speak=speak
        )

    def get_updates(self, offset=None):
        """Compatibility wrapper for Telegram long polling."""
        return self.telegram.get_updates(offset)

    def get_latest_offset(self):
        """Compatibility wrapper used by the runtime loop."""
        return self.telegram.latest_offset()

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
        events = getattr(self, 'events', None)
        if events is not None:
            events.publish("tool.started", tool=tool, args=args)

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
            if events is not None:
                events.publish("tool.completed", tool=tool, duration_ms=duration)
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
            if events is not None:
                events.publish(
                    "tool.failed", tool=tool, error=str(e), duration_ms=duration
                )
            raise

    # ==========================================
    # SKILL CALL FIXING AND LOOP PREVENTION
    # ==========================================

    def fix_skill_call_format(self, content):
        """Compatibility wrapper for response/tool-call normalization."""
        return self.response_processor.fix_skill_call_format(content)

    def check_skill_call_loop(self, content):
        """Compatibility wrapper for repeated skill failure detection."""
        return self.response_processor.check_skill_call_loop(content)

    def record_skill_failure(self, content, error_msg):
        """Track a failed skill call for loop prevention."""
        self.response_processor.record_skill_failure(content)

    def reset_skill_failures(self):
        """Reset failure tracking at a conversation boundary."""
        self.response_processor.reset_skill_failures()
        self._failed_skill_calls = self.response_processor.failure_counts

    def clean_response_for_david(self, content):
        """Compatibility wrapper for plain-text response cleanup."""
        return self.response_processor.clean_response(content)

    # ==========================================
    # MORNING BRIEFING
    # ==========================================

    def deliver_morning_briefing(self):
        """Compatibility wrapper for the scheduled briefing service."""
        service = getattr(self, "briefings", None) or BriefingService(self)
        return service.deliver_morning()

    # ==========================================
    # HANDLE MESSAGES FROM DAVID
    # ==========================================

    def handle_message(self, text, chat_id):
        """Compatibility wrapper for incoming message orchestration."""
        service = getattr(self, "messages", None) or MessageService(self)
        return service.handle(text, chat_id)

    # ==========================================
    # BRAIN STATUS (new command)
    # ==========================================

    def _send_brain_status(self):
        """Compatibility wrapper for brain/memory status presentation."""
        service = getattr(self, "status_service", None) or StatusService(self)
        return service.send_brain_status()

    # ==========================================
    # ASK TRINITY AI
    # ==========================================

    def _save_to_history(self, user_msg, assistant_msg):
        """Persist a conversation exchange through the conversation service."""
        service = getattr(self, "conversation", None) or ConversationService(self)
        return service._save_to_history(user_msg, assistant_msg)

    def ask_trinity(self, question, language='english'):
        """Delegate reasoning while publishing channel-neutral conversation lifecycle events."""
        service = getattr(self, "conversation", None) or ConversationService(self)
        events = getattr(self, "events", None)
        if events is not None:
            events.publish("conversation.started", language=language)
        try:
            response = service.ask_trinity(question, language)
            if events is not None:
                events.publish("conversation.completed", response_chars=len(str(response)))
            return response
        except Exception as exc:
            if events is not None:
                events.publish("conversation.failed", error=str(exc))
            raise

    # ==========================================
    # PROCESS GITHUB CHANGE REQUEST
    # ==========================================

    def process_change_request(self, response, language):
        """Compatibility wrapper for permission-aware GitHub change staging."""
        service = getattr(self, "change_requests", None) or ChangeRequestService(self)
        return service.process(response, language)

    # ==========================================
    # FORMATTED RESPONSES
    # ==========================================

    def send_help(self, language='english'):
        """Compatibility wrapper for help presentation."""
        service = getattr(self, "status_service", None) or StatusService(self)
        return service.send_help(language)

    def send_status(self):
        """Compatibility wrapper for runtime status presentation."""
        service = getattr(self, "status_service", None) or StatusService(self)
        return service.send_status()

    # ==========================================
    # ATTACHMENTS (compatibility wrappers)
    # ==========================================

    def handle_photo_message(self, photos, caption, chat_id):
        """Delegate Telegram image handling to the attachment service."""
        self.attachments.handle_photo(photos, caption)

    def handle_document_message(self, doc, caption, chat_id):
        """Delegate Telegram document handling to the attachment service."""
        self.attachments.handle_document(doc, caption)

    # ==========================================
    # AUTO SKILL BUILDER
    # ==========================================

    def _auto_implement_missing_tool(self, skill_name, tool_name, params, llm):
        """Compatibility wrapper for controlled skill evolution."""
        service = getattr(self, "skill_evolution", None) or SkillEvolutionService(self)
        return service.implement_missing_tool(skill_name, tool_name, params, llm)

    # ==========================================
    # AUTO-BUILD BRAND-NEW SKILLS
    # ==========================================

    def _auto_build_new_skill(self, skill_name, description, context=""):
        """Compatibility wrapper for controlled new-skill creation."""
        service = getattr(self, "skill_evolution", None) or SkillEvolutionService(self)
        return service.build_new_skill(skill_name, description, context)

    # ==========================================
    # PROACTIVE INITIATIVE
    # ==========================================

    def _proactive_initiative_check(self):
        """Compatibility wrapper for proactive context evaluation."""
        service = getattr(self, "proactive_service", None) or ProactiveService(self)
        return service.check()

    # ==========================================
    # LOCAL STATE PERSISTENCE
    # ==========================================

    def _commit_brain(self):
        """Compatibility name: persist Trinity state locally.

        Historical versions pushed trinity_brain.json to Git. Local memory is now
        authoritative, so this method intentionally performs no Git operation.
        """
        persistence = getattr(self, "persistence", None)
        if persistence is None:
            self.consciousness.save()
            return True
        report = persistence.save()
        if report.success:
            print(f"[TRINITY] State persisted locally: {report.brain_path or 'memory vault'}")
            return True
        print(f"[TRINITY] Local persistence failed: {report.error}")
        return False

    # ==========================================
    # RUNTIME LIFECYCLE (compatibility wrappers)
    # ==========================================

    def run(self):
        """Run Trinity through the dedicated lifecycle service."""
        lifecycle = getattr(self, "lifecycle", None) or RuntimeLoop(self)
        return lifecycle.run()

    def _shutdown(self):
        """Gracefully shut down through the lifecycle service."""
        lifecycle = getattr(self, "lifecycle", None) or RuntimeLoop(self)
        return lifecycle.shutdown()

    def _handle_health_warning(self, warnings):
        """Forward daemon health warnings through the lifecycle service."""
        lifecycle = getattr(self, "lifecycle", None) or RuntimeLoop(self)
        return lifecycle.health_warning(warnings)


if __name__ == "__main__":
    trinity = Trinity()
    trinity.run()
