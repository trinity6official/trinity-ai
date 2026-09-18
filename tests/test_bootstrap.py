from types import SimpleNamespace
from unittest.mock import MagicMock

from core.bootstrap import FOUNDATIONAL_KNOWLEDGE, seed_foundational_knowledge


def test_seed_foundational_knowledge_is_local_runtime_first():
    consciousness = MagicMock()
    host = SimpleNamespace(consciousness=consciousness)
    seed_foundational_knowledge(host)
    facts = [call.args[0] for call in consciousness.learn.call_args_list]
    assert len(facts) == len(FOUNDATIONAL_KNOWLEDGE)
    assert any("primary runtime is the local Mac Mini" in fact for fact in facts)
    assert any("local-only model router" in fact for fact in facts)
    consciousness.save.assert_called_once()
