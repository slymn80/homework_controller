from __future__ import annotations
from typing import Dict, Any
from openai import OpenAI
import json, re

RUBRIC = """Y📘 GENERAL ACADEMIC RUBRIC (For All Subjects)
... (sende mevcut uzun rubric içeriği burada aynen kalsın) ...
"""

def _coerce_numbers(d: Dict[str, Any]) -> Dict[str, Any]:
    bd = d.get("breakdown") or {}
    def to_int(x, default=0):
        try:
            return int(round(float(x)))
        except Exception:
            return default
    d["total"] = to_int(d.get("total"))
    bd["content"] = to_int(bd.get("content"))
    bd["structure"] = to_int(bd.get("structure"))
    bd["language"] = to_int(bd.get("language"))
    bd["originality"] = to_int(bd.get("originality"))
    d["breakdown"] = bd
    return d

def _parse_json_loose(text: str) -> Dict[str, Any]:
    mm = re.search(r"```json\s*(\{[\s\S]*?\})\s*```", text, flags=re.IGNORECASE)
    if mm:
        try:
            return json.loads(mm.group(1))
        except Exception:
            pass
    m = re.search(r"\{[\s\S]*\}", text.strip())
    if m:
        try:
            return json.loads(m.group(0))
        except Exception:
            pass
    return {"total": 0, "breakdown": {}, "feedback": text.strip()[:1500]}

def _call(client: OpenAI, model: str, system_msg: str, user_msg: str, force_json: bool = True) -> Dict[str, Any]:
    kwargs = {
        "model": model,
        "messages": [
            {"role": "system", "content": system_msg},
            {"role": "user", "content": user_msg},
        ],
        "temperature": 0.1,
        "max_tokens": 800,
    }
    if force_json:
        kwargs["response_format"] = {"type": "json_object"}
    resp = client.chat.completions.create(**kwargs)
    out_text = resp.choices[0].message.content or ""
    try:
        data = json.loads(out_text)
    except Exception:
        data = _parse_json_loose(out_text)
    return _coerce_numbers(data)

def evaluate_text(api_key: str, student_text: str, filename: str) -> Dict[str, Any]:
    client = OpenAI(api_key=api_key)

    system_msg = (
        "You are a multilingual, subject-aware academic grader. "
        "Detect both the language and the subject automatically. "
        "Always return STRICT JSON as specified. "
        + RUBRIC
    )
    user_msg = f"FILENAME: {filename}\nTEXT:\n{student_text[:12000]}"

    try:
        data = _call(client, "gpt-4o-mini", system_msg, user_msg, force_json=True)
    except Exception:
        # tek retry: json zorlamadan
        data = _call(client, "gpt-4o-mini", system_msg, user_msg, force_json=False)

    return data
