from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass
class EvalDataset:
    name: str
    category: str
    source_url: str
    sample_file: str


EVAL_DATASETS = [
    EvalDataset("HotpotQA", "multi_hop_qa", "https://hotpotqa.github.io/", "data/eval/hotpotqa.jsonl"),
    EvalDataset("2WikiMultiHopQA", "multi_hop_qa", "https://github.com/Alab-NII/2wikimultihop", "data/eval/2wiki.jsonl"),
    EvalDataset("MuSiQue", "multi_hop_qa", "https://huggingface.co/datasets/dwhiii/musique", "data/eval/musique.jsonl"),
    EvalDataset("MultiWOZ", "multi_turn_dialogue", "https://github.com/budzianowski/multiwoz", "data/eval/multiwoz.jsonl"),
    EvalDataset("ReDial", "personalized_recommendation", "https://redialdata.github.io/website/download", "data/eval/redial.jsonl"),
    EvalDataset("ScienceQA", "multimodal_reasoning", "https://github.com/lupantech/ScienceQA", "data/eval/scienceqa.jsonl"),
    EvalDataset("DocVQA", "multimodal_reasoning", "https://www.docvqa.org/datasets", "data/eval/docvqa.jsonl"),
]


def dataset_summaries() -> list[dict]:
    return [d.__dict__ for d in EVAL_DATASETS]


def resolve_sample_path(sample_file: str) -> Path:
    root = Path(__file__).resolve().parents[2]
    return root / sample_file
