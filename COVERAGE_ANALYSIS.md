# Test Coverage Analysis — Trinity AI

## Executive Summary

**Current coverage: 0%**

The codebase contains 24 Python source files (~9,000 lines) and **zero test files**.
No test framework, no pytest configuration, and no coverage tooling exist.

This document identifies the highest-risk untested areas, proposes concrete tests,
and provides a prioritised roadmap for building meaningful coverage.

---

## Codebase Snapshot

| Category | Files | Approx. Lines |
|---|---|---|
| Core engine | 8 | ~5,100 |
| Skills | 7 | ~5,200 |
| Agents | 4 | ~4,300 |
| Voice / language | 2 | ~1,600 |
| Raspberry Pi | 1 | ~700 |
| **Total** | **24** | **~9,000** |

---

## Priority 1 — Critical Safety Logic (implement first)

### `core/decisions.py` — TrinityDecisions

**Why critical:** This is Trinity's safety boundary. The three allow-lists
(`can_act_alone`, `needs_approval`, `never_do`) determine whether Trinity
acts autonomously or waits for David's approval. A bug here could cause
Trinity to spend money, contact clients, or delete files without permission.

**Risk:** Pure Python list lookups — trivially testable, currently untested.

**Proposed tests** (see `tests/test_decisions.py`):

| Test | What it validates |
|---|---|
| All safe actions return `True` from `can_act_alone` | Baseline autonomy works |
| Risky actions return `False` from `can_act_alone` | Risky actions blocked from autonomous execution |
| All approval actions return `True` from `needs_approval` | Approval gate works |
| All forbidden actions return `True` from `never_do` | Hard safety boundary is intact |
| No overlap between `can_act_alone` and `never_do` lists | Logical consistency — no action is both safe and forbidden |
| `request_approval` stores entry with `status: pending` | Approval workflow persists |
| `check_approval_response` returns `not_found` for unknown IDs | Lookup is safe |
| `generate_daily_recommendation` with critical website | Correct urgency escalation |
| `generate_daily_recommendation` with failed workflows | Correct repo names surfaced |
| `generate_daily_recommendation` with zero revenue | Client outreach recommendation fires |

---

### `core/memory.py` — TrinityMemory

**Why critical:** All decisions, alerts, wellbeing scores, and conversation
history are persisted here. Data loss or corruption means Trinity loses
context between runs and cannot track David's wellbeing or company health.

**Risk:** Filesystem I/O — testable with `tmp_path` fixtures, currently untested.

**Proposed tests** (see `tests/test_memory.py`):

| Test | What it validates |
|---|---|
| Missing file → returns `{}` | Graceful cold-start |
| Corrupted JSON → returns `{}` | Resilience to file corruption |
| Save + reload roundtrip | Data actually persists to disk |
| `update_last_wakeup` increments `days_alive` correctly | Day counter accuracy |
| `add_alert` appears in both `history` and `monitoring` | Alert storage consistency |
| `clear_alert` removes only the target type | Alert cleanup precision |
| `clear_alert` on empty brain does not raise | Defensive safety |
| `record_decision` stores correct fields | Decision audit trail integrity |
| `learn('what_works', ...)` deduplicates | No redundant knowledge entries |
| `learn('pattern', ...)` allows duplicates | Timestamped observations preserved |
| `add_conversation` caps at 100 entries | Memory does not grow unbounded |
| Most recent messages kept after cap | Correct ring-buffer behaviour |
| `get_full_context` returns valid JSON | LLM context injection works |

---

## Priority 2 — Pure Logic, Zero Dependencies

### `voice/language.py` — LanguageDetector

**Why important:** Every response Trinity sends is formatted based on the
detected language. A false Tamil detection sends English text in Tamil;
a missed Tamil detection replies in English to David speaking Tamil.

**Risk:** Zero external dependencies — pure string logic. All tests run
instantly with no mocks.

**Proposed tests** (see `tests/test_language.py`):

| Test | What it validates |
|---|---|
| Empty string → `english` | Edge case |
| Plain English → `english` | Baseline |
| Tamil Unicode → `tamil` | Unicode detection works |
| Transliterated Tamil word → `tamil` | Tanglish detection works |
| Case-insensitive Tanglish → `tamil` | `.lower()` applied correctly |
| `has_tamil_script` boundary code points (U+0B80, U+0BFF) | Exact range boundary correctness |
| `translate_status('healthy', 'english')` → `'healthy'` | English passthrough |
| `translate_status('healthy', 'tamil')` → Tamil string | Tamil translation correct |
| Unknown status key → returns key itself | Safe fallback |
| Unknown language → falls back to English | Safe fallback |
| `get_response_prefix` has all required keys | Template contract not broken |
| `format_briefing` with no alerts → "No issues today" | Default state renders |
| `format_briefing` with alerts → all alerts listed | Alert rendering works |
| Tamil briefing contains Tamil header | Language-correct formatting |

---

## Priority 3 — Routing & Protocol Parsing

### `core/skill_manager.py` — SkillManager.process_skill_call

**Why important:** `process_skill_call` parses a custom text protocol embedded
in LLM output and dispatches tool calls to skills. Parsing bugs cause tool
calls to be silently dropped, passed the wrong parameters, or executed against
the wrong skill. This is an inherently fragile pattern — manual parsing of
free-text LLM output.

**Risk:** Complex text parsing with implicit type coercion. Highest bug
surface area in the routing layer.

**Proposed tests** (see `tests/test_skill_manager.py`):

| Test | What it validates |
|---|---|
| No `SKILL_CALL` marker → returns `(None, original_text)` | Pass-through unchanged |
| Valid block → skill `.execute` called once with correct tool | Happy path |
| `count: 10` → `params['count'] == 10` (int, not `'10'`) | Type coercion: integers |
| `amount: 9999.99` → `params['amount'] == 9999.99` (float) | Type coercion: floats |
| `repo: trinity-ai` → `params['repo'] == 'trinity-ai'` (str) | String passthrough |
| Result text injected as `[skill.tool result]` | Output includes result marker |
| Text outside blocks preserved in output | Context not discarded |
| Two `SKILL_CALL` blocks in one response → both executed | Multi-call handling |
| Unknown skill → error dict with `success: False` | Graceful unknown skill |
| Skill raises exception → error dict, no re-raise | Exception isolation |
| `get_pending_changes()` with no GitHub skill loaded → `{}` | Lazy-load safety |
| `commit_change()` with no GitHub skill → `(False, ...)` | Graceful degradation |

---

## Priority 4 — Business Logic

### `agents/business_agent.py` — BusinessAgent

**Why important:** Health score calculation and alert generation drive the
recommendations Trinity surfaces to David. Wrong scores mean wrong
priorities; missing alerts mean missed business risks.

**Proposed tests** (see `tests/test_business_agent.py`):

| Test | What it validates |
|---|---|
| No memory → returns `{}` | Guard clause works |
| 0 days, 0 revenue, 0 clients → score 90 | Baseline penalty only for no clients |
| 31 days, 0 revenue, 0 clients → score 70 | Both penalties applied |
| Revenue alert fires only after 30 days | Threshold correct |
| No-clients alert fires when `clients == []` | Alert threshold |
| No-clients alert absent when clients exist | No false alerts |
| `total_clients` reflects actual list length | Count correct |
| `health_score` never exceeds 100 | Score is bounded |

---

## Priority 5 — Integration & Regression Tests (future)

These require more setup (mock GitHub API and other external boundaries) but are worth
investing in once unit coverage is established:

### `core/trinity.py` — Main orchestration
- Morning briefing executes all expected sub-calls
- Interface message routing reaches the correct skill
- `handle_message` with approval keyword updates pending approval status

### `core/consciousness.py` — Consciousness / memory pruning
- `empty_brain()` returns all required top-level keys
- Memory pruning respects `MAX_EPISODIC`, `MAX_SEMANTIC`, etc.
- `_hash()` produces consistent 12-char hex string
- Episodic memory decays below `DECAY_THRESHOLD`

### `skills/github_skill.py` — GitHub operations
- All write operations (create/update/delete) add to `pending_changes` and do not commit immediately
- `commit_change` only executes after it appears in `pending_changes`
- `cancel_change` removes entry from `pending_changes`

### `agents/security_agent.py` — Security monitoring
- Known vulnerable port numbers flagged correctly
- SSL expiry within 30 days generates a warning alert
- Expired SSL generates a critical alert

---

## What to Add to `requirements.txt`

```
pytest>=8.0
pytest-mock>=3.14
```

---

## How to Run Tests

```bash
# Install test dependencies
pip install pytest pytest-mock

# Run all tests with verbose output
pytest

# Run a specific module
pytest tests/test_decisions.py -v

# Run with coverage (after installing pytest-cov)
pip install pytest-cov
pytest --cov=core --cov=agents --cov=voice --cov-report=term-missing
```

---

## Recommended Test Writing Order

1. `tests/test_language.py` — zero dependencies, fastest feedback loop
2. `tests/test_decisions.py` — critical safety layer, pure logic
3. `tests/test_memory.py` — persistence layer, uses `tmp_path` fixture
4. `tests/test_business_agent.py` — health score logic
5. `tests/test_skill_manager.py` — parser and routing
6. `tests/test_consciousness.py` — schema and pruning (future)
7. Integration tests with mocked GitHub and external APIs (future)

---

## Files That Are Hardest to Test (and Why)

| File | Difficulty | Reason |
|---|---|---|
| `core/trinity.py` | High | Composition root still coordinates many runtime dependencies simultaneously |
| `core/run.py` | Medium | Detects environment via `os.environ`; needs careful patching |
| `raspberry_pi/trinity_lite.py` | Medium | Depends on local Llama model installation |
| `voice/speak.py` | Medium | Depends on local speech-provider availability |
| `skills/github_skill.py` | Medium | All interesting behaviour hits live GitHub API |

For these, the recommended approach is to inject dependencies (tokens, API
clients) rather than reading them from `os.environ` directly inside methods,
which makes patching clean and reliable.
