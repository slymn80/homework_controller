# src/evaluator.py
from __future__ import annotations
from typing import Dict, Any
from openai import OpenAI

RUBRIC = """Y📘 GENERAL ACADEMIC RUBRIC (For All Subjects)

You are a fair, detail-oriented academic grader. 
Your task is to evaluate the student's assignment based on the following universal criteria and, if possible, 
adapt the interpretation of each criterion to the detected subject (history, literature, science, computer science, etc.).

-------------------------------------------------------
🎯 1. CONTENT UNDERSTANDING (0–40)
- Accuracy of information and factual correctness.
- Relevance to the question or topic.
- Completeness of ideas, explanations, or arguments.
- Use of evidence, data, or examples supporting claims.

    🧭 Subject Hints:
    • History → Chronology, cause–effect reasoning, source use, factual accuracy.
    • Literature → Theme development, symbolism, narrative clarity, interpretation.
    • Science (Physics/Chemistry/Biology) → Correct use of terminology, logic, formulas, experimental reasoning.
    • Informatics / Programming → Understanding of algorithms, clarity of logic, correctness of explanations.
    • Social Sciences → Balanced argumentation, multiple perspectives, conceptual precision.

-------------------------------------------------------
📐 2. STRUCTURE & COHERENCE (0–20)
- Logical organization and flow of ideas.
- Clear paragraphing and transitions.
- Presence of introduction, body, and conclusion.
- Consistency of tone and academic style.

-------------------------------------------------------
✍️ 3. LANGUAGE USE (0–20)
- Grammar, spelling, and punctuation.
- Vocabulary richness and appropriateness.
- Clarity and conciseness of expression.
- Academic or technical tone suited to the subject.

-------------------------------------------------------
💡 4. ORIGINALITY & INSIGHT (0–20)
- Creativity, depth of thought, and analytical perspective.
- Personal or critical reflections.
- Ability to connect ideas or concepts beyond the obvious.
- Absence of plagiarism or direct copying.

-------------------------------------------------------
🧾 OUTPUT FORMAT (JSON)
You must always return a valid JSON object with the following structure:

{
  "total": <integer between 0–100>,
  "breakdown": {
      "content": <0–40>,
      "structure": <0–20>,
      "language": <0–20>,
      "originality": <0–20>
  },
  "strengths": ["...", "...", "..."],
  "weaknesses": ["...", "...", "..."],
  "suggestions": ["...", "...", "..."],
  "feedback": "A concise paragraph (5–8 sentences) summarizing the overall evaluation."
}

-------------------------------------------------------
🗣️ LANGUAGE BEHAVIOR
- Detect the language of the student's text automatically.
- Provide all feedback, strengths, weaknesses, and suggestions in the same language as the student's text.
- If multiple languages appear, respond in the dominant one.

-------------------------------------------------------
💬 STYLE
- Be constructive and professional.
- Highlight what the student did well.
- Offer actionable suggestions to improve future work.
- Keep total score consistent with the rubric scale.
"""

def evaluate_text(api_key: str, student_text: str, filename: str) -> Dict[str, Any]:
    """
    Yeni OpenAI SDK (v1.x) ile değerlendirme yapar ve
    RUBRIC'teki JSON şemasını döndürür.
    """
    client = OpenAI(api_key=api_key)

    system_msg = (
        "You are a multilingual, subject-aware academic grader. "
        "Detect both the language and the subject of the student's text automatically. "
        "Evaluate according to the rubric and provide feedback in the same language.\n"
        f"{RUBRIC}"
    )
    # Tek çağrıda çok uzun promptlardan kaçınmak için güvenli kısaltma
    text_snippet = (student_text or "")[:12000]
    user_msg = f"FILENAME: {filename}\nTEXT:\n{text_snippet}"

    resp = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": system_msg},
            {"role": "user", "content": user_msg},
        ],
        temperature=0.2,
        max_tokens=800,
    )

    out_text = (resp.choices[0].message.content or "").strip()

    # --- JSON'a toleranslı parse ---
    import json, re

    def _coerce_result(obj: Dict[str, Any]) -> Dict[str, Any]:
        # Şemayı eksiksiz hale getir (eski yapıyı BOZMADAN)
        bd = obj.get("breakdown") or {}
        result = {
            "total": obj.get("total"),
            "breakdown": {
                "content": bd.get("content"),
                "structure": bd.get("structure"),
                "language": bd.get("language"),
                "originality": bd.get("originality"),
            },
            "strengths": obj.get("strengths") or [],
            "weaknesses": obj.get("weaknesses") or [],
            "suggestions": obj.get("suggestions") or [],
            "feedback": obj.get("feedback") or "",
        }
        # Tip/limit düzeltmeleri (yumuşak)
        def _as_int(x):
            try:
                return int(round(float(x)))
            except Exception:
                return x
        # toplam ve alt skorları mümkünse int'e çek
        if isinstance(result["total"], (int, float, str)):
            result["total"] = _as_int(result["total"])
        for k in ("content", "structure", "language", "originality"):
            v = result["breakdown"].get(k)
            if isinstance(v, (int, float, str)):
                result["breakdown"][k] = _as_int(v)
        return result

    parsed: Dict[str, Any] | None = None

    # ```json ... ``` bloğu
    m1 = re.search(r"```json\s*(\{[\s\S]*?\})\s*```", out_text, flags=re.IGNORECASE)
    if m1:
        try:
            parsed = json.loads(m1.group(1))
        except Exception:
            parsed = None

    # Son çare: metin içindeki ilk { ... } bloğu
    if parsed is None:
        m2 = re.search(r"\{[\s\S]*\}", out_text)
        if m2:
            try:
                parsed = json.loads(m2.group(0))
            except Exception:
                parsed = None

    if parsed is None:
        # JSON veremediyse, feedback'e ham metni koy
        return {
            "total": None,
            "breakdown": {
                "content": None,
                "structure": None,
                "language": None,
                "originality": None,
            },
            "strengths": [],
            "weaknesses": [],
            "suggestions": [],
            "feedback": out_text[:1500],
        }

    return _coerce_result(parsed)
