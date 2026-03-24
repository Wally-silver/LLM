from app.services.prompting import extract_json


def test_extract_json_plain():
    text = '{"answer":"ok","citations":[],"used_tools":[],"metadata":{}}'
    obj = extract_json(text)
    assert obj["answer"] == "ok"


def test_extract_json_recover():
    text = "prefix {\"answer\": \"ok\", \"citations\": []} suffix"
    obj = extract_json(text)
    assert obj["answer"] == "ok"
    assert obj["metadata"]["json_recovered"] is True
