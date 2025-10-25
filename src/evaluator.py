# src/evaluator.py
from __future__ import annotations
from typing import Dict, Any, List
from openai import OpenAI
import json
import re

RUBRIC = """
You are a fair, detail-oriented academic grader.

Return a STRICT JSON object (no prose) with this exact schema:
{
  "total": <int 0..100>,
  "breakdown": {
    "content": <int 0..40>,
    "structure": <int 0..20>,
    "language": <int 0..20>,
    "originality": <int 0..20>
  },
  "strengths": [<string>, ...],
  "weaknesses": [<string>, ...],
  "suggestions": [<string>, ...],
  "feedback": <string>
}

SCORING:
- Always give scores even if the text is noisy/short/multi-language; do not return zeros across the board.
- Content (0..40): factual correctness, relevance, completeness, evidence/examples.
- Structure (0..20): organization, intro/body/conclusion, transitions.
- Language (0..20): grammar, clarity, appropriate register.
- Originality (0..20): insight, analysis, creativity.

LANGUAGE:
- Detect the student’s dominant language automatically and write all text fields
  ("strengths", "weaknesses", "suggestions", "feedback") in that language.
- If the text is multilingual or messy, choose the dominant or most readable one, but still grade it.

CONSTRAINTS:
- Values MUST be integers in the specified ranges.
- "total" MUST equal content+structure+language+originality (cap to 100 if needed).
- Keep feedback 4–8 sentences.
- No markdown, no code blocks, only the JSON object.
"""

def _clamp(v: int, lo: int, hi: int) -> int:
    try:
        v = int(round(float(v)))
    except Exception:
        v = 0
    if v < lo: v = lo
    if v > hi: v = hi
    return v

def _coerce_payload(d: Dict[str, Any]) -> Dict[str, Any]:
    # ensure keys
    d = dict(d or {})
    bd = dict(d.get("breakdown") or {})
    # clamp
    bd["content"] = _clamp(bd.get("content", 0), 0, 40)
    bd["structure"] = _clamp(bd.get("structure", 0), 0, 20)
    bd["language"] = _clamp(bd.get("language", 0), 0, 20)
    bd["originality"] = _clamp(bd.get("originality", 0), 0, 20)
    total = bd["content"] + bd["structure"] + bd["language"] + bd["originality"]
    d["breakdown"] = bd
    d["total"] = _clamp(d.get("total", total), 0, 100)
    # Eğer toplam farklıysa, toplamı breakdown’dan hesapla (100’ü aşarsa 100’e kırp)
    if d["total"] != total:
        d["total"] = min(total, 100)

    # list alanları garanti et
    for k in ("strengths", "weaknesses", "suggestions"):
        v = d.get(k)
        if not isinstance(v, list):
            if isinstance(v, str) and v.strip():
                v = [v.strip()]
            else:
                v = []
        # boşsa en az bir öğe bırak
        if not v:
            v = ["Kısa ve gürültülü bir metin olduğu için notlar sınırlı doğrulukla verilmiştir."]
        d[k] = v

    # feedback garanti et
    fb = d.get("feedback")
    if not isinstance(fb, str) or not fb.strip():
        fb = "Metin zayıf veya okunması güç olsa da, temel ölçütlere göre değerlendirme yapılmıştır."
    d["feedback"] = fb.strip()
    return d

def _parse_json_loose(text: str) -> Dict[str, Any]:
    # Kod bloğu içindeki JSON
    m = re.search(r"```json\s*(\{[\s\S]*?\})\s*```", text, re.I)
    if m:
        try:
            return json.loads(m.group(1))
        except Exception:
            pass
    # Düz metindeki ilk JSON
    m = re.search(r"\{[\s\S]*\}", text.strip())
    if m:
        try:
            return json.loads(m.group(0))
        except Exception:
            pass
    # Olmadıysa minimal payload
    return {
        "total": 0,
        "breakdown": {"content": 0, "structure": 0, "language": 0, "originality": 0},
        "strengths": [],
        "weaknesses": [],
        "suggestions": [],
        "feedback": text.strip()[:1500] if text else "",
    }

def _chat(client: OpenAI, model: str, system_msg: str, user_msg: str, force_json: bool = True) -> Dict[str, Any]:
    kwargs = dict(
        model=model,
        messages=[
            {"role": "system", "content": system_msg},
            {"role": "user",   "content": user_msg},
        ],
        temperature=0.1,
        max_tokens=900,
    )
    if force_json:
        kwargs["response_format"] = {"type": "json_object"}
    resp = client.chat.completions.create(**kwargs)
    out = resp.choices[0].message.content or ""
    try:
        data = json.loads(out)
    except Exception:
        data = _parse_json_loose(out)
    return _coerce_payload(data)

def evaluate_text(api_key: str, student_text: str, filename: str) -> Dict[str, Any]:
    client = OpenAI(api_key=api_key)

    # Gürültülü OCR metinlerini biraz kısaltıp normalize et
    text = (student_text or "").replace("\x0c", " ").strip()
    text = re.sub(r"\s+", " ", text)
    # Çok uzun metinleri kes (token güvenliği)
    if len(text) > 12000:
        text = text[:12000]

    system_msg = RUBRIC
    user_msg = f"FILENAME: {filename}\nSTUDENT_TEXT:\n{text}"

    try:
        data = _chat(client, "gpt-4o-mini", system_msg, user_msg, force_json=True)
    except Exception:
        # bir kez toleranslı dene (JSON zorunlu değil)
        data = _chat(client, "gpt-4o-mini", system_msg, user_msg, force_json=False)

    return data
