# Execution provider adapters (development)

Projectwright supports two execution provider modes in development.

**Default:** Omitting `provider` selects `{"type":"hermes"}`, preserving
the previously configured Hermes CLI model/provider behavior. The worker
invokes Hermes with its established one-shot chat arguments; the planner uses
the established structured JSON prompt invocation.

**Experimental stdin command adapter:** Provide an explicit adapter in the
project configuration:

```json
{
  "provider": {
    "type": "command",
    "planner_argv": ["/absolute/path/to/planner-adapter"],
    "worker_argv": ["/absolute/path/to/worker-adapter"]
  }
}
```

Each process receives a plain-text prompt on stdin. The planner must emit a
single valid proposal JSON object on stdout; its shape is validated by the
existing planner logic. The worker must write its completion result to the
exact file path specified in the prompt; the existing worker checks task ID,
status, scope, journal, queue and Git evidence before accepting completion.

No shell is used. The first argv element must be an absolute path and the
command list must contain nonempty strings. Projectwright does **not** infer
an executable from the network or choose a model. Provider selection does not
override authorization or approval rules.

This adapter contract allows a non-Hermes executable, including a wrapper
around another LLM/agent service. CI uses only a local disposable Python
process as its alternate provider—no additional model credentials, network
requests or production projects are involved.

**Not ready for general deployment:** cancellation, per-provider status,
credential management, structured protocol versioning, stderr diagnostics,
working-directory isolation, and live provider tests remain release gates.
The command adapter's explicit executable is trusted as a locally configured
program and can perform actions within the invoking user's OS permissions;
it must be run under an appropriately constrained account.
