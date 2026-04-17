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

        if total["count"]:
            total_metrics = {
                "count": total["count"],
                "em": round(total["em"] / total["count"], 4),
                "f1": round(total["f1"] / total["count"], 4),
            }
        else:
            total_metrics = {"count": 0, "em": 0.0, "f1": 0.0}

        return {"datasets": results, "overall": total_metrics}
