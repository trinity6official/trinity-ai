# `agents/` — Domain Agents

Agents provide domain-specific capabilities on top of Trinity's shared runtime.

Current agents include business, content, GitHub, and security-oriented capabilities. They are registered through `core/agent_runtime.py` / `core/agent_bootstrap.py` rather than called as unrestricted standalone automation.

Each agent should declare a capability contract covering inputs, network access, memory access, and side effects. Invocation is normalized into an immutable `AgentExecutionRequest`, and execution must pass through the central permission and audit layers before the handler receives an immutable `AgentContext`.

Adding a new agent:

1. Keep domain logic inside `agents/`.
2. Register it through the central AgentRegistry.
3. Declare the actions/capability contract clearly.
4. Route side effects through `PermissionEngine`.
5. Add audit coverage and tests.
6. Do not embed cloud LLM-specific message classes or provider secrets.
