from __future__ import annotations

import json
import re
from pathlib import Path

from app.eval.registry import EVAL_DATASETS, resolve_sample_path


class AutoEvaluator:
    """Automatic evaluator over 7 datasets (sampled JSONL subsets)."""

    @staticmethod
    def _normalize(text: str) -> str:
        text = text.lower().strip()
        text = re.sub(r"\s+", " ", text)
        return text

    @classmethod
    def exact_match(cls, pred: str, gold: str) -> float:
        return float(cls._normalize(pred) == cls._normalize(gold))

    @classmethod
    def token_f1(cls, pred: str, gold: str) -> float:
        p = cls._normalize(pred).split()
        g = cls._normalize(gold).split()
        if not p or not g:
            return 0.0
        common = set(p) & set(g)
        if not common:
            return 0.0
        precision = len(common) / len(set(p))
        recall = len(common) / len(set(g))
        return 2 * precision * recall / (precision + recall)

    def _load_samples(self, path: Path, limit: int) -> list[dict]:
        if not path.exists():
            return []
        samples = []
        for line in path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line:
                continue
            samples.append(json.loads(line))
            if len(samples) >= limit:
                break
        return samples

    async def evaluate(self, answer_func, limit_per_dataset: int = 20) -> dict:
        results = []
        total = {"count": 0, "em": 0.0, "f1": 0.0}

        for ds in EVAL_DATASETS:
            samples = self._load_samples(resolve_sample_path(ds.sample_file), limit_per_dataset)
            if not samples:
                results.append({"dataset": ds.name, "count": 0, "em": 0.0, "f1": 0.0})
                continue

            em_sum = 0.0
            f1_sum = 0.0
            for s in samples:
                pred = await answer_func(s["question"], s.get("context", ""))
                em_sum += self.exact_match(pred, s["answer"])
                f1_sum += self.token_f1(pred, s["answer"])

            cnt = len(samples)
            ds_result = {
                "dataset": ds.name,
                "category": ds.category,
                "source_url": ds.source_url,
                "count": cnt,
                "em": round(em_sum / cnt, 4),
                "f1": round(f1_sum / cnt, 4),
            }
            results.append(ds_result)
            total["count"] += cnt
            total["em"] += em_sum
            total["f1"] += f1_sum

        total_metrics = {
            "count": total["count"],
            "em": round(total["em"] / total["count"], 4) if total["count"] else 0.0,
            "f1": round(total["f1"] / total["count"], 4) if total["count"] else 0.0,
        }
        return {"datasets": results, "overall": total_metrics}


class AgentQualityEvaluator:
    """Rule-based evaluator for planning/reflection/autonomous-agent quality."""

    def evaluate_plan_quality(self, plan: dict) -> dict:
        steps = plan.get("steps", []) if isinstance(plan, dict) else []
        dep_steps = [s for s in steps if s.get("depends_on")]
        tool_steps = [s for s in steps if s.get("tool_call", {}).get("tool")]
        return {
            "plan_step_count": len(steps),
            "dependency_coverage": round(len(dep_steps) / len(steps), 4) if steps else 0.0,
            "structured_tool_usage": round(len(tool_steps) / len(steps), 4) if steps else 0.0,
        }

    def evaluate_reflection_trace(self, state: dict) -> dict:
        history = state.get("history", []) if isinstance(state, dict) else []
        transitions = [h.get("transition_decision") for h in history]
        reflection_triggered = any(t == "retry" for t in transitions)
        replan_triggered = any(t == "replan" for t in transitions)
        successful_recovery = state.get("status") == "done" and (reflection_triggered or replan_triggered)
        return {
            "reflection_triggered": reflection_triggered,
            "replan_triggered": replan_triggered,
            "successful_recovery": successful_recovery,
            "final_status": state.get("status", "unknown"),
        }

    def evaluate_agent_run(self, run_output: dict) -> dict:
        metadata = run_output.get("metadata", {})
        plan = metadata.get("plan", {})
        state = metadata.get("final_state", {})
        plan_q = self.evaluate_plan_quality(plan)
        trace_q = self.evaluate_reflection_trace(state)
        answer_present = bool(run_output.get("answer"))
        return {
            **plan_q,
            **trace_q,
            "answer_present": answer_present,
        }
