"""面向项目落地的高级任务（多跳 / 多轮个性化 / 多模态）数据与文档包。"""

ADVANCED_REASONING_SOURCES = [
    # Multi-hop reasoning
    {
        "doc_id": "hotpotqa-homepage",
        "source_type": "url",
        "source_value": "https://hotpotqa.github.io/",
        "task_tags": ["multi_hop_qa"],
    },
    {
        "doc_id": "2wikimultihop-github",
        "source_type": "url",
        "source_value": "https://github.com/Alab-NII/2wikimultihop",
        "task_tags": ["multi_hop_qa"],
    },
    {
        "doc_id": "musique-hf",
        "source_type": "url",
        "source_value": "https://huggingface.co/datasets/dwhiii/musique",
        "task_tags": ["multi_hop_qa"],
    },
    # Multi-turn / personalization
    {
        "doc_id": "multiwoz-github",
        "source_type": "url",
        "source_value": "https://github.com/budzianowski/multiwoz",
        "task_tags": ["multi_turn_dialogue", "personalization"],
    },
    {
        "doc_id": "redial-download",
        "source_type": "url",
        "source_value": "https://redialdata.github.io/website/download",
        "task_tags": ["recommendation", "multi_turn_dialogue"],
    },
    # Multimodal reasoning
    {
        "doc_id": "scienceqa-github",
        "source_type": "url",
        "source_value": "https://github.com/lupantech/ScienceQA",
        "task_tags": ["multimodal_reasoning"],
    },
    {
        "doc_id": "docvqa-dataset",
        "source_type": "url",
        "source_value": "https://www.docvqa.org/datasets",
        "task_tags": ["document_vqa", "multimodal_reasoning"],
    },
]

ADVANCED_REASONING_TASKS = [
    "任务1（多跳推理）：基于 HotpotQA/2Wiki/MuSiQue 的证据链问答，输出每一步 supporting facts。",
    "任务2（多轮问答）：基于 MultiWOZ 构建可上下文记忆的任务型对话（酒店/餐厅/交通联动）。",
    "任务3（个性化推荐）：基于 ReDial 做多轮电影推荐，结合用户偏好历史做可解释推荐。",
    "任务4（多模态知识推理）：基于 ScienceQA + DocVQA 做图文/文档问答推理与引用。",
]

ADVANCED_REASONING_DATASET_CATALOG = [
    {
        "name": "HotpotQA",
        "category": "multi_hop_qa",
        "url": "https://hotpotqa.github.io/",
        "note": "多跳问答基准，含 supporting facts。",
    },
    {
        "name": "2WikiMultiHopQA",
        "category": "multi_hop_qa",
        "url": "https://github.com/Alab-NII/2wikimultihop",
        "note": "结构化+非结构化多跳推理数据。",
    },
    {
        "name": "MuSiQue",
        "category": "multi_hop_qa",
        "url": "https://huggingface.co/datasets/dwhiii/musique",
        "note": "组合式多跳问题，适合复杂链路推理评测。",
    },
    {
        "name": "MultiWOZ",
        "category": "multi_turn_dialogue",
        "url": "https://github.com/budzianowski/multiwoz",
        "note": "经典多领域多轮任务型对话。",
    },
    {
        "name": "ReDial",
        "category": "personalized_recommendation",
        "url": "https://redialdata.github.io/website/download",
        "note": "会话推荐数据集（电影推荐）。",
    },
    {
        "name": "ScienceQA",
        "category": "multimodal_reasoning",
        "url": "https://github.com/lupantech/ScienceQA",
        "note": "图文多模态科学问答。",
    },
    {
        "name": "DocVQA",
        "category": "multimodal_reasoning",
        "url": "https://www.docvqa.org/datasets",
        "note": "文档图像问答，适合 OCR+推理链路。",
    },
]
