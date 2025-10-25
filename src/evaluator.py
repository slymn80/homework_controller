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
    client = OpenAI(api_key=api_key)

    system_msg = f"""
        You are a multilingual, subject-aware academic grader.
        Detect both the language and the subject of the student's text automatically.
        Evaluate according to the rubric and provide feedback in the same language.
        {RUBRIC}
        """
    user_msg = f"FILENAME: {filename}\nTEXT:\n{student_text[:12000]}"

    resp = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": system_msg},
            {"role": "user", "content": user_msg}
        ],
        temperature=0.2,
        max_tokens=600
    )

    out_text = resp.choices[0].message.content or ""

    # JSON'a toleranslı parse
    import json, re
    json_block = None

    # Kod bloğu içindeki JSON'u yakalamaya çalış (```json ... ```)
    mm = re.search(r"```json\\s*(\\{[\\s\\S]*?\\})\\s*```", out_text, flags=re.IGNORECASE)
    if mm:
        try:
            json_block = json.loads(mm.group(1))
        except Exception:
            json_block = None

    # Aksi halde düz metnin sonundaki { ... } bloğunu yakala
    if not json_block:
        m = re.search(r"\\{[\\s\\S]*\\}", out_text.strip())
        if m:
            try:
                json_block = json.loads(m.group(0))
            except Exception:
                json_block = None

    if not json_block:
        # Son çare: düz metni feedback olarak koy
        json_block = {"total": None, "breakdown": {}, "feedback": out_text.strip()[:1500]}

    return json_block
