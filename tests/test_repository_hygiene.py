from scripts.check_repository_hygiene import find_forbidden_paths, forbidden_reason


def test_repository_hygiene_rejects_runtime_state_and_generated_artifacts():
    paths = [
        "memory/trinity_brain.json",
        "trinity_brain.json",
        "memory/trinity_memory.db",
        "memory/trinity_memory.db-wal",
        "memory/vault/identity/profile.md",
        "memory/daily_logs/2026-09-18.json",
        "memory/runtime/action_audit.jsonl",
        "backups/trinity-memory.tar.gz",
        "core/__pycache__/runtime.cpython-313.pyc",
        ".pytest_cache/v/cache/nodeids",
        ".env.local",
        "models/qwen.gguf",
    ]

    violations = {path for path, _ in find_forbidden_paths(paths)}

    assert violations == set(paths)


def test_repository_hygiene_allows_source_docs_tests_and_config_templates():
    paths = [
        "core/memory_store.py",
        "scripts/check_repository_hygiene.py",
        "tests/test_memory.py",
        "docs/RUNTIME_DATA.md",
        "config/local_ai.yaml",
        "memory/README.md",
    ]

    assert find_forbidden_paths(paths) == []


def test_repository_hygiene_normalizes_windows_and_relative_paths():
    assert forbidden_reason(r".\\memory\\vault\\identity\\profile.md") == "runtime-generated directory"
