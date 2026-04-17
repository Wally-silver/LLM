from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class ToolCall:
    tool: str | None = None
    args: dict = field(default_factory=dict)
    purpose: str = ""
    required: bool = False

    @classmethod
    def from_dict(cls, obj: dict | None) -> "ToolCall":
        obj = obj or {}
        return cls(
            tool=obj.get("tool"),
            args=obj.get("args", {}) if isinstance(obj.get("args", {}), dict) else {},
            purpose=obj.get("purpose", ""),
            required=bool(obj.get("required", False)),
        )

    def to_dict(self) -> dict:
        return {
            "tool": self.tool,
            "args": self.args,
            "purpose": self.purpose,
            "required": self.required,
        }


@dataclass
class PlanStep:
    id: int
    action: str
    description: str = ""
    depends_on: list[int] = field(default_factory=list)
    tool_call: ToolCall = field(default_factory=ToolCall)
    expected_output: str = ""
    fallback_action: str | None = None
    status: str = "pending"

    @classmethod
    def from_dict(cls, obj: dict) -> "PlanStep":
        return cls(
            id=int(obj.get("id", 0) or 0),
            action=obj.get("action", "analyze"),
            description=obj.get("description", ""),
            depends_on=[int(x) for x in obj.get("depends_on", []) if str(x).isdigit() or isinstance(x, int)],
            tool_call=ToolCall.from_dict(obj.get("tool_call", {})),
            expected_output=obj.get("expected_output", ""),
            fallback_action=obj.get("fallback_action"),
            status=obj.get("status", "pending"),
        )

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "action": self.action,
            "description": self.description,
            "depends_on": self.depends_on,
            "tool_call": self.tool_call.to_dict(),
            "expected_output": self.expected_output,
            "fallback_action": self.fallback_action,
            "status": self.status,
        }


@dataclass
class Plan:
    steps: list[PlanStep] = field(default_factory=list)
    goal: str = ""
    strategy: str = ""

    @classmethod
    def from_dict(cls, obj: dict) -> "Plan":
        steps = []
        for s in obj.get("steps", []):
            if isinstance(s, dict):
                step = PlanStep.from_dict(s)
                if step.id <= 0:
                    step.id = len(steps) + 1
                steps.append(step)
        return cls(steps=steps, goal=obj.get("goal", ""), strategy=obj.get("strategy", ""))

    def to_dict(self) -> dict:
        return {"goal": self.goal, "strategy": self.strategy, "steps": [s.to_dict() for s in self.steps]}


@dataclass
class AgentIO:
    input: dict = field(default_factory=dict)
    output: dict = field(default_factory=dict)

    @classmethod
    def from_dict(cls, obj: dict) -> "AgentIO":
        out = obj.get("output", {}) if isinstance(obj.get("output", {}), dict) else {}
        normalized = {
            "result": out.get("result"),
            "confidence": out.get("confidence", 0.0),
            "reasoning": out.get("reasoning", ""),
            "evidence": out.get("evidence", []),
            "citations": out.get("citations", []),
            "error": out.get("error", ""),
        }
        return cls(input=obj.get("input", {}), output=normalized)

    def to_dict(self) -> dict:
        output = {
            "result": self.output.get("result"),
            "confidence": self.output.get("confidence", 0.0),
            "reasoning": self.output.get("reasoning", ""),
            "evidence": self.output.get("evidence", []),
            "citations": self.output.get("citations", []),
            "error": self.output.get("error", ""),
        }
        return {"input": self.input, "output": output}


@dataclass
class CriticResult:
    score: float = 0.0
    confidence: float = 0.0
    feedback: str = ""
    needs_revision: bool = False
    error_type: str = "none"
    suggestion: str = ""
    should_replan: bool = False
    should_retry: bool = False
    should_skip: bool = False

    @classmethod
    def from_dict(cls, obj: dict | None) -> "CriticResult":
        obj = obj or {}
        return cls(
            score=float(obj.get("score", 0.0)),
            confidence=float(obj.get("confidence", 0.0)),
            feedback=obj.get("feedback", ""),
            needs_revision=bool(obj.get("needs_revision", False)),
            error_type=obj.get("error_type", "none"),
            suggestion=obj.get("suggestion", ""),
            should_replan=bool(obj.get("should_replan", False)),
            should_retry=bool(obj.get("should_retry", False)),
            should_skip=bool(obj.get("should_skip", False)),
        )

    def to_dict(self) -> dict:
        return {
            "score": self.score,
            "confidence": self.confidence,
            "feedback": self.feedback,
            "needs_revision": self.needs_revision,
            "error_type": self.error_type,
            "suggestion": self.suggestion,
            "should_replan": self.should_replan,
            "should_retry": self.should_retry,
            "should_skip": self.should_skip,
        }
