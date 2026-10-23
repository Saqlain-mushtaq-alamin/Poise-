import re


def strip_thinking_tokens(text: str) -> str:
    """Strips <think>...</think>, <thought>...</thought>, <reasoning>...</reasoning>,

    and [THINK]...[/THINK] blocks from reasoning models (e.g. Qwen, DeepSeek-R1).
    Also handles unclosed thinking blocks if output was truncated.
    """
    if not text:
        return ""
    # Strip closed thinking tags
    t = re.sub(r"<think>[\s\S]*?</think>", "", text, flags=re.IGNORECASE)
    t = re.sub(r"<thought>[\s\S]*?</thought>", "", t, flags=re.IGNORECASE)
    t = re.sub(r"<reasoning>[\s\S]*?</reasoning>", "", t, flags=re.IGNORECASE)
    t = re.sub(r"\[think\][\s\S]*?\[/think\]", "", t, flags=re.IGNORECASE)

    # If <think> was unclosed (e.g. max_tokens cutoff inside thinking), strip everything after opening tag
    t = re.sub(r"<think>[\s\S]*$", "", t, flags=re.IGNORECASE)
    t = re.sub(r"<thought>[\s\S]*$", "", t, flags=re.IGNORECASE)
    t = re.sub(r"<reasoning>[\s\S]*$", "", t, flags=re.IGNORECASE)
    return t.strip()


def repair_json_string(text: str) -> str:
    """Removes common LLM syntax errors such as trailing commas before closing braces/brackets."""
    t = text.strip()
    # Remove trailing commas: , } -> } and , ] -> ]
    t = re.sub(r",\s*\}", "}", t)
    t = re.sub(r",\s*\]", "]", t)
    return t


def extract_json_from_llm(text: str) -> str:
    """Extracts JSON from an LLM response that might contain markdown fences,

    preamble text, or <think> reasoning tags.
    """
    if not text:
        return ""

    # 1. Strip reasoning / thinking tokens first so braces inside <think> don't confuse parser
    t = strip_thinking_tokens(text)

    # 2. Attempt to extract from code fences
    start_fence = t.find("```")
    if start_fence != -1:
        end_fence = t.rfind("```")
        if end_fence != -1 and end_fence > start_fence:
            candidate = t[start_fence + 3 : end_fence].strip()
            if candidate.lower().startswith("json"):
                candidate = candidate[4:].strip()
            return repair_json_string(candidate)

    # 3. Fallback: attempt to find outermost brackets
    first_brace = t.find("{")
    last_brace = t.rfind("}")

    first_bracket = t.find("[")
    last_bracket = t.rfind("]")

    is_object = first_brace != -1 and last_brace != -1
    is_array = first_bracket != -1 and last_bracket != -1

    if is_object and is_array:
        if first_brace < first_bracket:
            is_array = False
        else:
            is_object = False

    if is_object:
        return repair_json_string(t[first_brace : last_brace + 1])
    elif is_array:
        return repair_json_string(t[first_bracket : last_bracket + 1])

    return repair_json_string(t)

