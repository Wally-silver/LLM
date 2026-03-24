import json
import re

SYSTEM_PROMPT = """你是企业级AI Agent。请基于可验证信息回答，减少幻觉。
输出必须是JSON，包含字段：answer, citations, used_tools, metadata。"""


def build_user_prompt(query: str, context: str, history: str) -> str:
    return (
        "[历史对话]\n"
        f"{history}\n\n"
        "[检索上下文]\n"
        f"{context}\n\n"
        "[用户问题]\n"
        f"{query}\n\n"
        "请严格返回JSON对象。"
    )


def extract_json(text: str) -> dict:
    """Best-effort JSON recovery for robust output parsing."""
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", text, flags=re.DOTALL)
        if not match:
            return {"answer": text.strip(), "citations": [], "used_tools": [], "metadata": {"json_recovered": False}}
        try:
            obj = json.loads(match.group(0))
            obj.setdefault("metadata", {})
            obj["metadata"]["json_recovered"] = True
            return obj
        except json.JSONDecodeError:
            return {"answer": text.strip(), "citations": [], "used_tools": [], "metadata": {"json_recovered": False}}
