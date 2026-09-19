import os
import sys
import time

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.memory import MemoryService
from core.skill_manager import SkillManager
from core.consciousness import Consciousness
from core.memory_pipeline import ConversationMemoryPipeline
from core.ai_service import LocalAIService, build_local_ai_from_environment
from core.orchestrator import MessageOrchestrator
from core.events import EventBus
from core.audit import ActionAuditTrail
from core.notifications import NotificationService
from core.output import ResponseRouter
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
from core.process_manager import ProcessManager
from core.mcp import MCPServerManager
from core.runtime import detect_runtime
from core.attachments import AttachmentService
from core.lifecycle import RuntimeLoop
from core.api_runtime import LocalAPIServer
from core.conversation import ConversationService
from core.response_processing import ResponseProcessor
from core.change_requests import ChangeRequestService
from core.briefing import BriefingService
from core.proactive_service import ProactiveService
from core.proactive_events import ProactiveEventService
from core.message_service import MessageService
from core.skill_evolution import SkillEvolutionService
from core.capabilities import CapabilityRegistry
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
    Uses CapabilityRegistry for discovery and dedicated owners for execution
    Evolves and learns every single day

    Runtime/experience state:
    - Loads from the local runtime-state boundary
    - Persists locally after meaningful actions
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

        self.gh_token = os.environ.get('GH_TOKEN')

        print("Loading memory...")
        self.memory = MemoryService()
        self.memory_store = self.memory.store
        self.memory_pipeline = ConversationMemoryPipeline(self.memory_store)

        # ── Consciousness ──
        print("Loading consciousness...")
        self.consciousness = Consciousness()
        self.persistence = StatePersistence(self.consciousness, self.memory)
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
        self.processes = ProcessManager(
            event_bus=self.events, audit_trail=self.audit
        )
        self.mcp = MCPServerManager.from_environment(event_bus=self.events)

        self.output = ResponseRouter(self.events, default_responder=print)

        print("Setting up language detection...")
        self.language = LanguageDetector()

        print("Setting up voice...")
        self.voice = TrinityVoice()
        self.voice_session = VoiceSessionController(
            self.voice.local_voice,
            responder=lambda text, language: self.process_text(text, source="voice"),
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
        self.notifications = NotificationService(self.events, voice=self.voice)
        self.computer = ComputerController(
            permissions=self.permissions, audit_trail=self.audit
        )

        print("Loading all skills...")
        self.skills = SkillManager(
            gh_token=self.gh_token,
            memory=self.memory,
            permission_engine=self.permissions,
            audit_trail=self.audit,
            computer_controller=self.computer,
        )

        print("Setting up AI brain...")
        self.llm = self.setup_llm()
        self.vision = LocalVisionService.from_environment()
        self.attachments = AttachmentService(self, None, self.vision)
        self.agents = build_default_agent_registry(
            memory=self.memory, llm=self.llm, gh_token=self.gh_token,
            permissions=self.permissions, audit_trail=self.audit,
        )
        self.capabilities = CapabilityRegistry(
            self.permissions, skills=self.skills, agents=self.agents
        )
        self.capabilities.bind_runtime(self)
        self.skills.bind_capability_registry(self.capabilities)
        self.briefings = BriefingService(self)
        self.status_service = StatusService(self)

        print("Caching GitHub context...")
        self.github_context_cache = self.briefings.github_context()

        self.memory.update_last_wakeup()

        # ── Boot consciousness ──
        self.consciousness.boot()
        self._failed_skill_calls = {}  # track skill call failures for loop prevention
        self.response_processor = ResponseProcessor(self._failed_skill_calls)
        self._conversation_history = []  # rolling window so Trinity remembers what she just said
        self.conversation = ConversationService(self)
        self.change_requests = ChangeRequestService(self)
        self.proactive_service = ProactiveService(self)
        self.proactive_events = ProactiveEventService(self)
        self.proactive_events.start()
        self.orchestrator = MessageOrchestrator()
        self.messages = MessageService(self)
        self.skill_evolution = SkillEvolutionService(self)
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
            seed_foundational_knowledge(self)

        # Log this boot
        self.consciousness.add_working(
            f"Trinity fully initialized. LLM: {getattr(self, '_local_model_name', 'local')}",
            priority="high"
        )
        self.consciousness.save()

        print("Trinity is awake and ready!")

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

    def respond(self, message, *, kind="message"):
        """Emit a user-facing response through the currently bound interface."""
        return self.output.emit(str(message), kind=kind)

    def notify(self, message, *, category="general", urgent=False, speak=False):
        """Publish a local notification with optional local speech."""
        return self.notifications.notify(
            message, category=category, urgent=urgent, speak=speak
        )

    def process_text(self, text, *, source="local") -> str:
        """Run text from any interface through the single message pipeline."""
        emitted = []
        result = self.messages.handle(
            text, responder=emitted.append, source=source
        )
        if result is not None:
            return str(result)
        return str(emitted[-1]) if emitted else ""

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

    def run(self):
        """Run Trinity through the dedicated lifecycle service."""
        return self.lifecycle.run()

if __name__ == "__main__":
    trinity = Trinity()
    trinity.run()
