"""
matcher.py — TF-IDF cosine similarity + keyword scoring for the Resume Matcher.
"""

import os
import sys
from typing import Dict, List, Set, Tuple

from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

# Ensure the local parser.py is imported (not the stdlib parser module)
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from parser import extract_keywords, get_all_keywords  # noqa: E402


# ─── Scoring weights ──────────────────────────────────────────────────────────

WEIGHT_TFIDF    = 0.40   # semantic / contextual similarity
WEIGHT_KW_FLAT  = 0.30   # overall flat keyword match
WEIGHT_KW_CAT   = 0.30   # category-weighted keyword match

# Relative weights within the category component (must sum to 1.0)
CATEGORY_WEIGHTS = {
    "languages":  0.40,
    "frameworks": 0.35,
    "tools":      0.20,
    "soft_skills": 0.05,
}


# ─── Low-level helpers ────────────────────────────────────────────────────────

def _tfidf_similarity(text_a: str, text_b: str) -> float:
    """Return cosine similarity (0–1) between two texts via TF-IDF."""
    if not text_a.strip() or not text_b.strip():
        return 0.0
    try:
        vec = TfidfVectorizer(
            stop_words="english",
            ngram_range=(1, 2),
            max_features=10_000,
            sublinear_tf=True,
        )
        mat = vec.fit_transform([text_a, text_b])
        return float(cosine_similarity(mat[0:1], mat[1:2])[0][0])
    except Exception:
        return 0.0


def _kw_match_rate(jd_kws: Set[str], resume_kws: Set[str]) -> float:
    """Fraction of JD keywords present in resume.  Returns 1.0 if JD has none."""
    if not jd_kws:
        return 1.0
    return len(jd_kws & resume_kws) / len(jd_kws)


# ─── Main scorer ──────────────────────────────────────────────────────────────

def score_resume(
    jd_text: str,
    resume_text: str,
    jd_kw: Dict[str, Set[str]],
    res_kw: Dict[str, Set[str]],
) -> Dict:
    """
    Compute a comprehensive match score for one resume against a job description.

    Returns a dict:
        final_score       – overall match % (0–100)
        tfidf_similarity  – TF-IDF cosine similarity %
        keyword_match     – flat keyword match %
        category_scores   – {category: %}
        missing_keywords  – keywords in JD not found in resume (flat set)
        cat_missing       – {category: set of missing keywords}
        overlap_keywords  – keywords found in both JD and resume
        jd_keywords       – all JD keywords (flat)
        resume_keywords   – all resume keywords (flat)
        jd_kw_by_cat      – categorised JD keywords
    """
    jd_all  = get_all_keywords(jd_kw)
    res_all = get_all_keywords(res_kw)

    # 1. TF-IDF semantic similarity
    tfidf = _tfidf_similarity(jd_text, resume_text)

    # 2. Flat keyword match
    flat_kw = _kw_match_rate(jd_all, res_all)

    # 3. Category-level keyword match (weighted)
    cat_scores: Dict[str, float] = {}
    weighted_cat = 0.0
    for cat, w in CATEGORY_WEIGHTS.items():
        rate = _kw_match_rate(jd_kw.get(cat, set()), res_kw.get(cat, set()))
        cat_scores[cat] = rate
        weighted_cat += rate * w

    # 4. Combine into a single score
    final = (
        WEIGHT_TFIDF   * tfidf
        + WEIGHT_KW_FLAT * flat_kw
        + WEIGHT_KW_CAT  * weighted_cat
    )

    # 5. Derived information
    missing = jd_all - res_all
    overlap = jd_all & res_all
    cat_missing = {
        cat: (jd_kw.get(cat, set()) - res_kw.get(cat, set()))
        for cat in CATEGORY_WEIGHTS
    }

    return {
        "final_score":      round(final * 100, 1),
        "tfidf_similarity": round(tfidf * 100, 1),
        "keyword_match":    round(flat_kw * 100, 1),
        "category_scores":  {k: round(v * 100, 1) for k, v in cat_scores.items()},
        "missing_keywords": missing,
        "cat_missing":      cat_missing,
        "overlap_keywords": overlap,
        "jd_keywords":      jd_all,
        "resume_keywords":  res_all,
        "jd_kw_by_cat":     jd_kw,
    }


def rank_resumes(scores: Dict[str, Dict]) -> List[Tuple[str, Dict]]:
    """Return (name, score_dict) pairs sorted by final_score descending."""
    return sorted(scores.items(), key=lambda x: x[1]["final_score"], reverse=True)
