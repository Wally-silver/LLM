import hashlib
import json
import re

SYSTEM_PROMPT = """你是企业级AI Assistant。
输出必须是JSON，包含字段：answer, citations, used_tools, metadata。"""


def build_user_prompt(query: str, context: str, history: str, tool_result: dict | None = None) -> str:
    return (
        "[历史对话]\n"
        f"{history}\n\n"
        "[工具结果]\n"
        f"{json.dumps(tool_result or {}, ensure_ascii=False)}\n\n"
        "[检索上下文]\n"
        f"{context}\n\n"
        "[用户问题]\n"
        f"{query}\n\n"
        "请严格返回JSON对象。"
    )


def build_rag_prompt(query: str, context: str, history: str, tool_result: dict | None = None) -> str:
    return (
        "[历史对话]\n"
        f"{history}\n\n"
        "[工具结果]\n"
        f"{json.dumps(tool_result or {}, ensure_ascii=False)}\n\n"
        "[知识库检索上下文]\n"
        f"{context}\n\n"
        "[用户问题]\n"
        f"{query}\n\n"
        "请严格依据知识库检索上下文回答。若上下文不足，请明确说明知识库中没有足够信息。请严格返回JSON对象。"
    )


def build_no_rag_prompt(query: str, history: str, tool_result: dict | None = None) -> str:
    return (
        "[历史对话]\n"
        f"{history}\n\n"
        "[工具结果]\n"
        f"{json.dumps(tool_result or {}, ensure_ascii=False)}\n\n"
        "[用户问题]\n"
        f"{query}\n\n"
        "请基于你的通用知识回答，不要假设存在外部检索上下文。当前为普通问答模式，请不要引用或假设存在检索上下文；如历史回答中出现知识库内容，仅作为对话历史参考，不作为当前检索依据。请严格返回JSON对象。"
    )


def build_planner_prompt(query: str, history: str) -> str:
    return (
        "你是 Planner，请输出结构化计划 JSON。"
        "包括 goal, strategy, steps[].{id,action,description,depends_on,tool_call,expected_output,fallback_action}.\n"
        f"query={query}\n"
        f"history={history[-2000:]}"
    )


def build_replanner_prompt(query: str, state: dict, failed_step: dict, critic: dict) -> str:
    return (
        "你是 Replanner，请基于失败步骤和critic反馈重规划。\n"
        "尽量保留已完成步骤，修复失败路径。输出完整 plan JSON。\n"
        f"query={query}\nstate={json.dumps(state, ensure_ascii=False)[:3000]}\n"
        f"failed_step={json.dumps(failed_step, ensure_ascii=False)}\n"
        f"critic={json.dumps(critic, ensure_ascii=False)}"
    )


def build_executor_prompt(action: str, query: str, context: str, history: str, tool_result: dict | None = None) -> str:
    return f"[action]={action}\n" + build_user_prompt(query, context, history, tool_result)


def history_fingerprint(history_text: str) -> str:
    return hashlib.sha256(history_text.encode("utf-8")).hexdigest()[:16]


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
