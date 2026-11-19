"""Minimal agent-workflow runtime (sanitized showcase).

SIMULATED: this is a small, dependency-free illustration of the workflow
pattern used in my OpenClaw environment. It is not the private OpenClaw
implementation. There are no network calls, no credentials, no model calls,
and no real messaging. "Delivery" appends to an in-memory outbox.

Ideas demonstrated:
  * A task representation produced from a natural-language request
  * Tool registration and a simple router
  * Structured workflow state with an auditable list of transitions
  * Validation before completion - plausible model text is not proof of success
  * External actions (delivery) only after validation passes
  * A per-workflow lock so overlapping runs fail safely
  * A safe failure result instead of a partial "success"
"""

from __future__ import annotations

import json
import threading
from dataclasses import dataclass, field
from typing import Any, Callable

Context = dict[str, Any]
ToolFn = Callable[[Context], Any]
Validator = Callable[[Context], "str | None"]  # returns an error message or None


# --------------------------------------------------------------------------- #
# Core types
# --------------------------------------------------------------------------- #

@dataclass(frozen=True)
class Task:
    request: str
    workflow: str
    params: dict[str, Any] = field(default_factory=dict)


ALLOWED_TRANSITIONS: dict[str, set[str]] = {
    "pending": {"running", "failed"},
    "running": {"validating", "failed"},
    "validating": {"delivering", "failed"},
    "delivering": {"completed", "failed"},
    "completed": set(),
    "failed": set(),
}


@dataclass
class WorkflowState:
    task: Task
    status: str = "pending"
    outputs: Context = field(default_factory=dict)
    transitions: list[dict[str, Any]] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)

    def transition(self, new_status: str, note: str = "") -> None:
        if new_status not in ALLOWED_TRANSITIONS[self.status]:
            raise RuntimeError(f"illegal transition {self.status} -> {new_status}")
        self.transitions.append(
            {"seq": len(self.transitions) + 1, "from": self.status, "to": new_status, "note": note}
        )
        self.status = new_status

    def fail(self, reason: str) -> None:
        self.errors.append(reason)
        if self.status not in ("completed", "failed"):
            self.transition("failed", reason)


@dataclass
class WorkflowResult:
    ok: bool
    status: str
    outputs: Context
    errors: list[str]
    transitions: list[dict[str, Any]]
    completion_record: dict[str, Any] | None


class ToolRegistry:
    def __init__(self) -> None:
        self._tools: dict[str, tuple[ToolFn, str]] = {}

    def register(self, name: str, description: str) -> Callable[[ToolFn], ToolFn]:
        def decorator(fn: ToolFn) -> ToolFn:
            if name in self._tools:
                raise ValueError(f"tool already registered: {name}")
            self._tools[name] = (fn, description)
            return fn
        return decorator

    def call(self, name: str, context: Context) -> Any:
        if name not in self._tools:
            raise KeyError(f"unknown tool: {name}")
        return self._tools[name][0](context)

    def describe(self) -> dict[str, str]:
        return {name: desc for name, (_, desc) in self._tools.items()}


@dataclass
class Workflow:
    name: str
    steps: list[tuple[str, str]]            # (tool name, output key)
    validators: list[Validator]
    deliver: str                            # tool that performs the external action


# --------------------------------------------------------------------------- #
# Router and runtime
# --------------------------------------------------------------------------- #

class KeywordRouter:
    """Stand-in for model-based routing: maps a request to a workflow name."""

    def __init__(self, routes: dict[str, list[str]]) -> None:
        self.routes = routes

    def route(self, request: str) -> Task | None:
        text = request.casefold()
        for workflow, keywords in self.routes.items():
            if any(k in text for k in keywords):
                return Task(request=request, workflow=workflow)
        return None


class AgentRuntime:
    def __init__(self, registry: ToolRegistry, workflows: dict[str, Workflow],
                 router: KeywordRouter) -> None:
        self.registry = registry
        self.workflows = workflows
        self.router = router
        self._locks = {name: threading.Lock() for name in workflows}

    def handle(self, request: str) -> WorkflowResult:
        task = self.router.route(request)
        if task is None or task.workflow not in self.workflows:
            state = WorkflowState(Task(request=request, workflow="unrouted"))
            state.fail("no workflow matched the request")
            return self._result(state, completion=None)
        return self.run(task)

    def run(self, task: Task) -> WorkflowResult:
        workflow = self.workflows[task.workflow]
        state = WorkflowState(task)
        lock = self._locks[workflow.name]

        if not lock.acquire(blocking=False):
            state.fail("workflow already running; refusing overlapping run")
            return self._result(state, completion=None)

        try:
            state.transition("running", f"workflow={workflow.name}")
            context: Context = {"params": task.params, **state.outputs}
            for tool_name, output_key in workflow.steps:
                context[output_key] = self.registry.call(tool_name, context)
                state.outputs[output_key] = context[output_key]

            state.transition("validating")
            problems = [msg for v in workflow.validators if (msg := v(context))]
            if problems:
                for p in problems:
                    state.fail(f"validation: {p}")
                return self._result(state, completion=None)

            # External action happens only after validation succeeded.
            state.transition("delivering")
            state.outputs["delivery"] = self.registry.call(workflow.deliver, context)
            state.transition("completed")
            completion = {
                "workflow": workflow.name,
                "status": "completed",
                "validated_outputs": sorted(k for k in state.outputs if k != "delivery"),
            }
            return self._result(state, completion=completion)

        except Exception as exc:  # safe failure: never report partial success
            state.fail(f"{type(exc).__name__}: {exc}")
            return self._result(state, completion=None)
        finally:
            lock.release()

    @staticmethod
    def _result(state: WorkflowState, completion: dict[str, Any] | None) -> WorkflowResult:
        return WorkflowResult(
            ok=state.status == "completed",
            status=state.status,
            outputs=state.outputs,
            errors=state.errors,
            transitions=state.transitions,
            completion_record=completion,
        )


# --------------------------------------------------------------------------- #
# SIMULATED demo: a tiny watchlist summary workflow with fictional data
# --------------------------------------------------------------------------- #

OUTBOX: list[str] = []  # in-memory stand-in for a messaging channel
registry = ToolRegistry()


@registry.register("load_sample_quotes", "Return fictional daily quotes (no network).")
def load_sample_quotes(ctx: Context) -> dict[str, Any]:
    if ctx["params"].get("simulate_stale_data"):
        return {"session_date": "2030-01-14", "expected_date": "2030-01-15", "quotes": []}
    return {
        "session_date": "2030-01-15",
        "expected_date": "2030-01-15",
        "benchmark_pct": 0.4,
        "quotes": [
            {"symbol": "FICT-A", "pct": 3.1, "rel_volume": 2.4},
            {"symbol": "FICT-B", "pct": -1.8, "rel_volume": 1.1},
        ],
    }


@registry.register("build_report", "Build a structured report from quotes.")
def build_report(ctx: Context) -> dict[str, Any]:
    data = ctx["quotes"]
    rows = [
        {**q, "vs_benchmark": round(q["pct"] - data.get("benchmark_pct", 0.0), 2)}
        for q in data["quotes"]
    ]
    return {"session_date": data["session_date"], "rows": rows, "label": "SIMULATED"}


@registry.register("draft_summary", "Simulated model text; NOT treated as proof of success.")
def draft_summary(ctx: Context) -> str:
    return "Report complete! Everything looks great."  # plausible, unverified text


@registry.register("deliver_to_outbox", "Append the validated report to an in-memory outbox.")
def deliver_to_outbox(ctx: Context) -> dict[str, Any]:
    OUTBOX.append(json.dumps(ctx["report"], sort_keys=True))
    return {"delivered": True, "outbox_size": len(OUTBOX)}


def data_is_fresh(ctx: Context) -> str | None:
    q = ctx["quotes"]
    if q["session_date"] != q["expected_date"]:
        return "stale or non-trading-day data; skipping report"
    return None


def report_has_rows(ctx: Context) -> str | None:
    rows = ctx["report"].get("rows")
    if not rows:
        return "report has no rows"
    if any("vs_benchmark" not in r for r in rows):
        return "report row missing benchmark comparison"
    return None


WORKFLOWS = {
    "watchlist_summary": Workflow(
        name="watchlist_summary",
        steps=[("load_sample_quotes", "quotes"), ("build_report", "report"),
               ("draft_summary", "summary")],
        validators=[data_is_fresh, report_has_rows],
        deliver="deliver_to_outbox",
    )
}

ROUTER = KeywordRouter({"watchlist_summary": ["watchlist", "stocks", "market summary"]})


def main() -> None:
    runtime = AgentRuntime(registry, WORKFLOWS, ROUTER)

    print("SIMULATED RUN 1 - fresh fictional data")
    ok = runtime.handle("Give me today's watchlist summary")
    print(json.dumps({"ok": ok.ok, "status": ok.status, "completion": ok.completion_record,
                      "transitions": ok.transitions}, indent=2))

    print("\nSIMULATED RUN 2 - stale data; the summary text still claims success")
    stale = runtime.run(Task("watchlist summary", "watchlist_summary",
                             {"simulate_stale_data": True}))
    print(json.dumps({"ok": stale.ok, "status": stale.status, "errors": stale.errors,
                      "model_text": stale.outputs.get("summary"),
                      "outbox_size": len(OUTBOX)}, indent=2))

    print("\nSIMULATED RUN 3 - unroutable request")
    none = runtime.handle("Book me a flight")
    print(json.dumps({"ok": none.ok, "status": none.status, "errors": none.errors}, indent=2))


if __name__ == "__main__":
    main()
