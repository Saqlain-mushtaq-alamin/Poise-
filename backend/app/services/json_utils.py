def extract_json_from_llm(text: str) -> str:
    """Extracts JSON from an LLM response that might contain markdown fences or preamble text."""
    t = text.strip()
    
    # Attempt to extract from code fences first
    start_fence = t.find("```")
    if start_fence != -1:
        end_fence = t.rfind("```")
        if end_fence != -1 and end_fence > start_fence:
            t = t[start_fence + 3 : end_fence].strip()
            if t.lower().startswith("json"):
                t = t[4:].strip()
            return t
            
    # Fallback: attempt to find outermost brackets
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
        return t[first_brace : last_brace + 1]
    elif is_array:
        return t[first_bracket : last_bracket + 1]
        
    return t
