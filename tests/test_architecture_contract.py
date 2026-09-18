from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent


def _read(relative: str) -> str:
    return (ROOT / relative).read_text(encoding="utf-8")


def test_core_runtime_has_no_cloud_llm_dependencies():
    active_roots = ["core", "voice", "agents", "skills"]
    text = "\n".join(
        path.read_text(encoding="utf-8", errors="ignore")
        for root in active_roots
        for path in (ROOT / root).rglob("*.py")
    ).lower()
    forbidden = (
        "langchain-anthropic",
        "langchain_google_genai",
        "anthropic_api_key",
        "google-cloud-speech",
        "google-cloud-texttospeech",
        "gtts",
    )
    assert not [term for term in forbidden if term in text]


def test_daemon_cannot_persist_memory_to_git():
    daemon = _read("core/daemon.py").lower()
    assert "git push" not in daemon
    assert "git add" not in daemon
    assert "git commit every" not in daemon
    assert "def _git_commit" not in daemon


def test_github_actions_is_ci_not_a_trinity_runtime():
    workflow = _read(".github/workflows/trinity.yml").lower()
    assert "python -m pytest" in workflow
    assert "permissions:\n  contents: read" in workflow
    assert "python core/trinity.py" not in workflow
    assert "git push" not in workflow
    assert "anthropic_api_key" not in workflow


def test_obsolete_cloud_deployment_files_are_absent():
    for name in ("Procfile", "render.yaml", "railway.json"):
        assert not (ROOT / name).exists()


def test_legacy_consciousness_wrapper_is_retired():
    assert not (ROOT / "core" / "consciousness_integration.py").exists()


def test_api_cannot_start_a_second_lightweight_brain():
    assert not (ROOT / "core" / "api_brain.py").exists()
    api = _read("core/api.py")
    assert "TrinityAPIBrain" not in api
    assert "python -m core.run --mode daemon" in api


def test_requirements_match_local_architecture():
    requirements = _read("requirements.txt").lower()
    forbidden = (
        "anthropic",
        "langchain-google-genai",
        "google-cloud-speech",
        "google-cloud-texttospeech",
        "gtts",
        "gunicorn",
        "pygithub",
        "apscheduler",
        "langdetect",
    )
    assert not [term for term in forbidden if term in requirements]
    assert "pyyaml" in requirements


def test_active_runtime_does_not_depend_on_langchain_message_wrappers():
    active_roots = ["core", "voice", "agents", "skills"]
    text = "\n".join(
        path.read_text(encoding="utf-8", errors="ignore")
        for root in active_roots
        for path in (ROOT / root).rglob("*.py")
    ).lower()
    assert "langchain_core" not in text


def test_removed_remote_chat_transport_is_absent_from_active_runtime():
    active_roots = ("core", "voice", "agents", "skills")
    text = "\n".join(
        path.read_text(encoding="utf-8", errors="ignore")
        for root in active_roots
        for path in (ROOT / root).rglob("*.py")
    ).lower()
    forbidden = (
        "api.telegram.org",
        "telegram_bot_token",
        "trinity_telegram",
        "send_telegram",
        "core.channels.telegram",
    )
    assert not [term for term in forbidden if term in text]
