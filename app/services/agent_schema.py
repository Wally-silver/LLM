from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class ToolCall:
    tool: str | None = None
    args: dict = field(default_factory=dict)


@dataclass
class PlanStep:
    id: int
    action: str
    tool_call: ToolCall = field(default_factory=ToolCall)


@dataclass
class Plan:
    steps: list[PlanStep] = field(default_factory=list)

    @classmethod
    def from_dict(cls, obj: dict) -> "Plan":
        steps = []
        for s in obj.get("steps", []):
            tc = s.get("tool_call", {}) if isinstance(s, dict) else {}
            steps.append(
                PlanStep(
                    id=int(s.get("id", len(steps) + 1)),
                    action=s.get("action", "analyze"),
                    tool_call=ToolCall(tool=tc.get("tool"), args=tc.get("args", {})),
                )
            )
        return cls(steps=steps)

    def to_dict(self) -> dict:
        return {
            "steps": [
                {"id": s.id, "action": s.action, "tool_call": {"tool": s.tool_call.tool, "args": s.tool_call.args}}
                for s in self.steps
            ]
        }


@dataclass
class AgentIO:
    input: dict = field(default_factory=dict)
    output: dict = field(default_factory=dict)

    @classmethod
    def from_dict(cls, obj: dict) -> "AgentIO":
        return cls(input=obj.get("input", {}), output=obj.get("output", {}))

    def to_dict(self) -> dict:
        return {"input": self.input, "output": self.output}


@dataclass
class CriticResult:
    score: float = 0.0
    confidence: float = 0.0
    feedback: str = ""
    needs_revision: bool = False

    def to_dict(self) -> dict:
        return {
            "score": self.score,
            "confidence": self.confidence,
            "feedback": self.feedback,
            "needs_revision": self.needs_revision,
        }
