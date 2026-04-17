from app.domain.advanced_reasoning import (
    ADVANCED_REASONING_DATASET_CATALOG,
    ADVANCED_REASONING_SOURCES,
    ADVANCED_REASONING_TASKS,
)


def test_advanced_reasoning_domain_pack():
    assert len(ADVANCED_REASONING_SOURCES) >= 7
    assert len(ADVANCED_REASONING_TASKS) >= 4
    assert len(ADVANCED_REASONING_DATASET_CATALOG) >= 7
    assert any(d["name"] == "HotpotQA" for d in ADVANCED_REASONING_DATASET_CATALOG)
