"""Unit tests for app.services.json_utils.extract_json_from_llm."""

import json

from app.services.json_utils import extract_json_from_llm


def test_extract_pure_json_object():
    raw = '{"greeting": "hello", "count": 10}'
    extracted = extract_json_from_llm(raw)
    assert json.loads(extracted) == {"greeting": "hello", "count": 10}


def test_extract_pure_json_array():
    raw = '[{"id": 1}, {"id": 2}]'
    extracted = extract_json_from_llm(raw)
    assert json.loads(extracted) == [{"id": 1}, {"id": 2}]


def test_extract_markdown_json_fenced_block():
    raw = """Here is the JSON you requested:
```json
{
  "sections": ["behavioral", "technical"],
  "total_minutes": 45
}
```
Let me know if you need any adjustments!"""
    extracted = extract_json_from_llm(raw)
    data = json.loads(extracted)
    assert data["sections"] == ["behavioral", "technical"]
    assert data["total_minutes"] == 45


def test_extract_markdown_generic_fence():
    raw = """```
{"status": "ok", "ready": true}
```"""
    extracted = extract_json_from_llm(raw)
    assert json.loads(extracted) == {"status": "ok", "ready": True}


def test_extract_json_surrounded_by_explanatory_text():
    raw = 'Sure! Here is the output: {"success": true, "code": 200}. End of transmission.'
    extracted = extract_json_from_llm(raw)
    assert json.loads(extracted) == {"success": True, "code": 200}


def test_extract_array_surrounded_by_explanatory_text():
    raw = 'Here are the questions: ["What is your background?", "Explain dependency injection."] That is all.'
    extracted = extract_json_from_llm(raw)
    assert json.loads(extracted) == ["What is your background?", "Explain dependency injection."]


def test_extract_nested_structures():
    nested = {
        "candidate": {"name": "Alice", "skills": ["Python", "Rust"]},
        "scores": {"behavioral": 8.5, "coding": 9.0},
    }
    raw = f"Output: ```json\n{json.dumps(nested, indent=2)}\n```"
    extracted = extract_json_from_llm(raw)
    assert json.loads(extracted) == nested


def test_extract_empty_or_whitespace():
    assert extract_json_from_llm("") == ""
    assert extract_json_from_llm("   ") == ""
    assert extract_json_from_llm("\n\t\n") == ""


def test_extract_raw_non_json_string():
    raw = "No JSON or fences here at all."
    assert extract_json_from_llm(raw) == "No JSON or fences here at all."


def test_extract_object_preferred_over_array_when_object_comes_first():
    raw = 'Result: {"list": [1, 2, 3]}'
    extracted = extract_json_from_llm(raw)
    assert json.loads(extracted) == {"list": [1, 2, 3]}


def test_extract_array_preferred_over_object_when_array_comes_first():
    raw = 'Items: [{"key": "val"}]'
    extracted = extract_json_from_llm(raw)
    assert json.loads(extracted) == [{"key": "val"}]


def test_strip_think_tags_with_internal_json_braces():
    raw = """<think>
Let's see what JSON format we should use:
{ "debug_plan": true }
Now let me output the real answer in markdown code block.
</think>
```json
{
  "status": "ready",
  "questions": ["Tell me about yourself"]
}
```"""
    extracted = extract_json_from_llm(raw)
    data = json.loads(extracted)
    assert data == {"status": "ready", "questions": ["Tell me about yourself"]}


def test_strip_think_tags_without_code_fences():
    raw = """<think>
Reasoning about the candidate's background { "dummy": 123 }
</think>
{
  "score": 0.85,
  "feedback": "Strong communication"
}"""
    extracted = extract_json_from_llm(raw)
    data = json.loads(extracted)
    assert data == {"score": 0.85, "feedback": "Strong communication"}


def test_repair_trailing_commas():
    raw = """{
  "name": "Jane",
  "skills": ["Python", "Rust",],
  "active": true,
}"""
    extracted = extract_json_from_llm(raw)
    data = json.loads(extracted)
    assert data == {"name": "Jane", "skills": ["Python", "Rust"], "active": True}


def test_unclosed_think_tag_truncated():
    raw = """<think>
Thinking about this question..."""
    extracted = extract_json_from_llm(raw)
    assert extracted == ""

