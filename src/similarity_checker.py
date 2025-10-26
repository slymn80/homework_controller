# src/similarity_checker.py
from __future__ import annotations
from typing import List, Dict, Any, Tuple
import re
from itertools import combinations

try:
    from rapidfuzz import fuzz
except Exception:
    fuzz = None  # requirements'a rapidfuzz ekleyeceğiz

def _clean(t: str) -> str:
    t = t or ""
    t = t.lower()
    t = re.sub(r"\s+", " ", t)
    return t.strip()

def _shingles(text: str, k: int = 3) -> set:
    text = re.sub(r"[^a-zA-Z0-9çğıöşüüğİÇĞÖŞÜА-Яа-яЁёӘәІіҚқҢңҰұҮүҺһ\s]", " ", text, flags=re.UNICODE)
    tokens = [tok for tok in text.split() if tok]
    if len(tokens) < k:
        return set(tokens)
    return set(tuple(tokens[i:i+k]) for i in range(len(tokens)-k+1))

def pair_score(a_text: str, b_text: str) -> Dict[str, Any]:
    a = _clean(a_text)
    b = _clean(b_text)
    # RapidFuzz oranları
    rf = {}
    if fuzz:
        rf["token_set_ratio"] = float(fuzz.token_set_ratio(a, b))
        rf["partial_ratio"]   = float(fuzz.partial_ratio(a, b))
        rf["ratio"]           = float(fuzz.ratio(a, b))
    else:
        rf["token_set_ratio"] = rf["partial_ratio"] = rf["ratio"] = 0.0

    # 3-gram jaccard
    A = _shingles(a, 3); B = _shingles(b, 3)
    inter = len(A & B); uni = len(A | B) if (A or B) else 1
    jaccard = inter / uni

    # normalize 0..100 arası bir “combined” skor
    combined = 0.5 * (rf["token_set_ratio"]/100.0) + 0.5 * jaccard
    return {
        "rf_ratio": rf["ratio"],
        "rf_token_set": rf["token_set_ratio"],
        "rf_partial": rf["partial_ratio"],
        "jaccard_3gram": round(jaccard*100, 2),
        "combined": round(combined*100, 2),
    }

def find_similar(assignments: List[Dict[str, Any]], threshold: float = 80.0) -> List[Dict[str, Any]]:
    """
    assignments: [{ "file_name": str, "text": str, "file_id": str, "student": str, ...}, ...]
    threshold: combined skorda alt sınır (0..100)
    """
    results: List[Dict[str, Any]] = []
    for a, b in combinations(assignments, 2):
        sc = pair_score(a.get("text",""), b.get("text",""))
        if sc["combined"] >= threshold:
            results.append({
                "file_a": a.get("file_name"),
                "file_b": b.get("file_name"),
                "student_a": a.get("student"),
                "student_b": b.get("student"),
                "file_id_a": a.get("file_id"),
                "file_id_b": b.get("file_id"),
                **sc
            })
    # skora göre sırala
    results.sort(key=lambda x: x["combined"], reverse=True)
    return results
