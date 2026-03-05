"""
app.py — Resume Matcher & Selector · Phase 1 of the Job Application Toolkit.

Run with:
    streamlit run app.py
"""

import os
import re
import sys
from typing import Dict, List, Set, Tuple

import plotly.graph_objects as go
import streamlit as st

# Ensure local modules (parser.py, matcher.py) are always found first
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from parser import extract_keywords, extract_text_from_pdf, get_all_keywords
from matcher import rank_resumes, score_resume


# ─── Page configuration ───────────────────────────────────────────────────────

st.set_page_config(
    page_title="Resume Matcher | Job Application Toolkit",
    page_icon="🎯",
    layout="wide",
)


# ─── Custom CSS ───────────────────────────────────────────────────────────────

st.markdown(
    """
<style>
/* ── Layout & base ── */
.stApp { background-color: #0d1117; }

/* ── Best-match banner ── */
.banner {
    background: linear-gradient(135deg, #0d2818 0%, #0d3b22 100%);
    border: 1px solid #2ea043;
    border-radius: 14px;
    padding: 22px 30px;
    margin: 16px 0 24px 0;
}
.banner-label { font-size: 12px; color: #8b949e; text-transform: uppercase;
                letter-spacing: .08em; margin-bottom: 4px; }
.banner-name  { font-size: 20px; font-weight: 700; color: #e6edf3;
                margin-bottom: 10px; }
.banner-score { font-size: 52px; font-weight: 800; color: #3fb950;
                line-height: 1; }
.banner-sub   { font-size: 13px; color: #3fb950; margin-top: 2px; }

/* ── Section dividers ── */
.sec-header {
    font-size: 17px; font-weight: 700; color: #e6edf3;
    padding-bottom: 8px; border-bottom: 1px solid #30363d;
    margin: 24px 0 14px 0;
}

/* ── Score display ── */
.score-big   { font-size: 44px; font-weight: 800; line-height: 1; }
.score-green  { color: #3fb950; }
.score-yellow { color: #d29922; }
.score-orange { color: #e3a547; }
.score-red    { color: #f85149; }

/* ── Rank badges ── */
.rank-badge {
    display: inline-block;
    padding: 3px 11px; border-radius: 20px;
    font-size: 11px; font-weight: 700;
    margin-right: 8px; vertical-align: middle;
}
.rank-1 { background:#3b2700; color:#d29922; border:1px solid #d29922; }
.rank-2 { background:#1c2127; color:#8b949e; border:1px solid #8b949e; }
.rank-3 { background:#1a1000; color:#c77b17; border:1px solid #c77b17; }
.rank-n { background:#0d2650; color:#388bfd; border:1px solid #1f6feb; }

/* ── Keyword tags ── */
.kw-tag {
    display: inline-block;
    padding: 3px 11px; margin: 2px 3px;
    border-radius: 20px; font-size: 12px; font-weight: 500;
}
.kw-missing { background:#2d0e0e; color:#f85149; border:1px solid #6e1111; }
.kw-matched { background:#0d2818; color:#3fb950; border:1px solid #196c2e; }
.kw-neutral { background:#21262d; color:#8b949e; border:1px solid #30363d; }

/* ── Category pill ── */
.cat-pill {
    display: inline-block;
    padding: 2px 9px; border-radius: 12px;
    font-size: 11px; font-weight: 600; margin-right: 4px;
    background: #21262d; color: #8b949e; border: 1px solid #30363d;
}

/* ── Metric row ── */
.metric-row { display: flex; gap: 12px; flex-wrap: wrap; margin: 10px 0; }
.metric-box {
    background: #161b22; border: 1px solid #30363d;
    border-radius: 8px; padding: 12px 18px;
    min-width: 130px; text-align: center;
}
.metric-box .label { font-size: 11px; color: #8b949e; margin-bottom: 4px; }
.metric-box .value { font-size: 22px; font-weight: 700; }

/* ── ATS Simulator ── */
.ats-cmp-box {
    background: #161b22; border: 1px solid #30363d;
    border-radius: 10px; padding: 20px 24px;
    text-align: center;
}
.ats-cmp-label { font-size: 11px; color: #8b949e; text-transform: uppercase;
                  letter-spacing: .08em; margin-bottom: 4px; }
.ats-cmp-value { font-size: 40px; font-weight: 800; line-height: 1; }
.ats-cmp-sub   { font-size: 12px; color: #8b949e; margin-top: 6px; }
.ats-kw-table  { width: 100%; border-collapse: collapse; font-size: 13px; }
.ats-kw-table th {
    color: #8b949e; font-weight: 600; font-size: 11px;
    text-transform: uppercase; letter-spacing: .06em;
    border-bottom: 1px solid #30363d; padding: 6px 10px; text-align: left;
}
.ats-kw-table td { padding: 7px 10px; border-bottom: 1px solid #21262d; vertical-align: top; }
.ats-kw-table tr:last-child td { border-bottom: none; }
.ats-tip  { background:#0d2218; border:1px solid #196c2e; border-radius:8px;
             padding:14px 18px; margin:8px 0; font-size:13px; color:#c9d1d9; }
.ats-warn { background:#2d1a00; border:1px solid #6e3c00; border-radius:8px;
             padding:14px 18px; margin:8px 0; font-size:13px; color:#c9d1d9; }

/* ── Misc ── */
#MainMenu { visibility: hidden; }
footer    { visibility: hidden; }
</style>
""",
    unsafe_allow_html=True,
)


# ─── Helper: colour class for scores ─────────────────────────────────────────

def _score_css(score: float) -> str:
    if score >= 70:  return "score-green"
    if score >= 50:  return "score-yellow"
    if score >= 30:  return "score-orange"
    return "score-red"


def _rank_badge(rank: int) -> str:
    cls   = {1: "rank-1", 2: "rank-2", 3: "rank-3"}.get(rank, "rank-n")
    label = {1: "🥇 Best Match", 2: "🥈 #2", 3: "🥉 #3"}.get(rank, f"#{rank}")
    return f'<span class="rank-badge {cls}">{label}</span>'


def _kw_tags(kws: Set[str], css_class: str, cap: int = 40) -> str:
    tags = "".join(
        f'<span class="kw-tag {css_class}">{kw}</span>'
        for kw in sorted(kws)[:cap]
    )
    if len(kws) > cap:
        extra = len(kws) - cap
        tags += f'<span class="kw-tag kw-neutral">+{extra} more</span>'
    return tags or "<em style='color:#8b949e'>None found</em>"


# ─── Plotly chart builders ────────────────────────────────────────────────────

_CHART_BG  = "#0d1117"
_CARD_BG   = "#161b22"
_GRID_CLR  = "#30363d"
_TEXT_CLR  = "#c9d1d9"

# ─── ATS synonym map (full form → [abbreviations]) ────────────────────────────
# Bidirectional: if JD says full form but resume has abbrev (or vice versa)
_ATS_SYNONYMS: Dict[str, List[str]] = {
    "kubernetes":                       ["k8s"],
    "machine learning":                 ["ml"],
    "javascript":                       ["js"],
    "typescript":                       ["ts"],
    "deep learning":                    ["dl"],
    "natural language processing":      ["nlp"],
    "computer vision":                  ["cv"],
    "amazon web services":              ["aws"],
    "google cloud platform":            ["gcp"],
    "database":                         ["db"],
    "application programming interface": ["api"],
    "continuous integration":           ["ci/cd", "ci cd", "cicd"],
    "object oriented programming":      ["oop", "object-oriented"],
    "data science":                     ["ds"],
    "artificial intelligence":          ["ai"],
    "neural network":                   ["nn"],
    "random forest":                    ["rf"],
    "support vector machine":           ["svm"],
    "logistic regression":              ["lr"],
    "postgresql":                       ["postgres"],
    "mongodb":                          ["mongo"],
    "scikit-learn":                     ["sklearn"],
    "tensorflow":                       ["tf"],
    "pytorch":                          ["pt"],
}
# Reverse map: abbreviation → full form
_ATS_SYN_REV: Dict[str, str] = {}
for _full, _abbrevs in _ATS_SYNONYMS.items():
    for _abbrev in _abbrevs:
        _ATS_SYN_REV[_abbrev] = _full


def _score_bar_chart(ranked: List[Tuple[str, Dict]]) -> go.Figure:
    """Horizontal bar chart ranking all resumes by overall score."""
    names  = [r[0] for r in ranked]
    scores = [r[1]["final_score"] for r in ranked]

    short  = [n[:35] + "…" if len(n) > 36 else n for n in names]
    colors = [
        "#3fb950" if s >= 70 else "#d29922" if s >= 50 else "#e3a547" if s >= 30 else "#f85149"
        for s in scores
    ]

    fig = go.Figure(go.Bar(
        x=scores, y=short, orientation="h",
        marker_color=colors,
        text=[f"  {s}%" for s in scores],
        textposition="outside",
        textfont=dict(size=13, color=_TEXT_CLR),
        hovertemplate="<b>%{y}</b><br>Match Score: %{x}%<extra></extra>",
    ))
    fig.update_layout(
        title=dict(text="Overall Resume Rankings", font=dict(size=15, color=_TEXT_CLR)),
        xaxis=dict(
            title="Match Score (%)", range=[0, 115],
            showgrid=True, gridcolor=_GRID_CLR,
            tickfont=dict(color=_TEXT_CLR),
        ),
        yaxis=dict(autorange="reversed", tickfont=dict(color=_TEXT_CLR)),
        plot_bgcolor=_CARD_BG, paper_bgcolor=_CHART_BG,
        font=dict(color=_TEXT_CLR),
        height=max(220, 70 * len(ranked) + 80),
        margin=dict(l=20, r=80, t=50, b=20),
    )
    return fig


def _keyword_overlap_chart(ranked: List[Tuple[str, Dict]]) -> go.Figure:
    """Grouped bar chart: matched vs missing keywords per resume per category."""
    categories = ["languages", "frameworks", "tools", "soft_skills"]
    cat_labels  = ["Languages", "Frameworks", "Tools", "Soft Skills"]

    names   = [r[0][:25] + "…" if len(r[0]) > 26 else r[0] for r in ranked]
    matched = {cat: [] for cat in categories}
    missing = {cat: [] for cat in categories}

    for _, data in ranked:
        jd_cats  = data.get("jd_kw_by_cat", {})
        cat_miss = data.get("cat_missing", {})
        for cat in categories:
            jd_cat  = jd_cats.get(cat, set())
            miss    = cat_miss.get(cat, set())
            hit     = jd_cat - miss
            matched[cat].append(len(hit))
            missing[cat].append(len(miss))

    colors_match = ["#3fb950", "#388bfd", "#d29922", "#a371f7"]
    colors_miss  = ["#2d0e0e", "#0d2650", "#3b2700", "#21130d"]

    fig = go.Figure()
    for i, cat in enumerate(categories):
        fig.add_trace(go.Bar(
            name=f"{cat_labels[i]} – Matched",
            x=names, y=matched[cat],
            marker_color=colors_match[i],
            legendgroup=cat, offsetgroup=i,
            hovertemplate=f"<b>%{{x}}</b><br>{cat_labels[i]} matched: %{{y}}<extra></extra>",
        ))
        fig.add_trace(go.Bar(
            name=f"{cat_labels[i]} – Missing",
            x=names, y=missing[cat],
            marker_color=colors_miss[i],
            marker_line=dict(color=colors_match[i], width=1),
            legendgroup=cat, offsetgroup=i,
            base=matched[cat],
            hovertemplate=f"<b>%{{x}}</b><br>{cat_labels[i]} missing: %{{y}}<extra></extra>",
        ))

    fig.update_layout(
        barmode="stack",
        title=dict(text="Keyword Coverage by Category", font=dict(size=15, color=_TEXT_CLR)),
        xaxis=dict(tickfont=dict(color=_TEXT_CLR)),
        yaxis=dict(
            title="# Keywords",
            showgrid=True, gridcolor=_GRID_CLR,
            tickfont=dict(color=_TEXT_CLR),
        ),
        plot_bgcolor=_CARD_BG, paper_bgcolor=_CHART_BG,
        font=dict(color=_TEXT_CLR),
        legend=dict(
            bgcolor=_CARD_BG, bordercolor=_GRID_CLR, borderwidth=1,
            font=dict(size=10),
        ),
        height=360,
        margin=dict(l=20, r=20, t=50, b=20),
    )
    return fig


def _radar_chart(score_data: Dict) -> go.Figure:
    """Radar / spider chart for per-category scores of one resume."""
    cats   = ["languages", "frameworks", "tools", "soft_skills"]
    labels = ["Languages", "Frameworks", "Tools", "Soft Skills"]
    vals   = [score_data["category_scores"].get(c, 0) for c in cats]

    # Close the polygon
    vals_c   = vals + [vals[0]]
    labels_c = labels + [labels[0]]

    fig = go.Figure(go.Scatterpolar(
        r=vals_c, theta=labels_c,
        fill="toself",
        fillcolor="rgba(31,111,235,0.18)",
        line=dict(color="#1f6feb", width=2),
        marker=dict(size=7, color="#1f6feb"),
        hovertemplate="%{theta}: %{r:.0f}%<extra></extra>",
    ))
    fig.update_layout(
        polar=dict(
            bgcolor=_CARD_BG,
            radialaxis=dict(
                visible=True, range=[0, 100],
                tickfont=dict(size=9, color="#8b949e"),
                gridcolor=_GRID_CLR, linecolor=_GRID_CLR,
            ),
            angularaxis=dict(
                tickfont=dict(size=12, color=_TEXT_CLR),
                linecolor=_GRID_CLR, gridcolor=_GRID_CLR,
            ),
        ),
        paper_bgcolor=_CHART_BG,
        font=dict(color=_TEXT_CLR),
        height=270,
        margin=dict(l=30, r=30, t=30, b=30),
    )
    return fig


# ─── Gemini AI analysis ───────────────────────────────────────────────────────

def _gemini_analysis(jd_text: str, resume_text: str, api_key: str) -> str:
    """Call Gemini 2.0 Flash for a structured resume review."""
    try:
        import google.generativeai as genai

        genai.configure(api_key=api_key)
        model = genai.GenerativeModel("gemini-2.0-flash")

        prompt = f"""You are an expert resume reviewer and career coach.
Analyse how well this resume matches the job description. Be specific and actionable.

Respond in exactly this markdown format — no extra sections:

## Overall Fit
[2–3 sentences on match quality and readiness for the role]

## Key Strengths ✅
- [Strength relative to this JD]
- [Another strength]
- [Another strength]

## Critical Gaps ❌
- [Missing or insufficient skill/experience]
- [Another gap]
- [Another gap]

## Recommendations 💡
- [Specific, actionable improvement]
- [Another recommendation]
- [Another recommendation]

## Keywords to Add
[Comma-separated list of 6–10 high-value keywords from the JD to incorporate]

---
**JOB DESCRIPTION:**
{jd_text[:2500]}

**RESUME:**
{resume_text[:2500]}
"""
        response = model.generate_content(prompt)
        return response.text
    except Exception as exc:
        return f"⚠️ AI Analysis failed: {exc}"


# ─── ATS scoring helpers ──────────────────────────────────────────────────────

def _ats_exact(word: str, text_lower: str) -> bool:
    """Whole-word / whole-phrase case-insensitive match (no synonym expansion)."""
    return bool(re.search(
        r"(?<![a-z0-9])" + re.escape(word.lower()) + r"(?![a-z0-9])",
        text_lower,
    ))


def _ats_compute(jd_keywords: Set[str], resume_text: str) -> Dict:
    """
    Simulate exact-match ATS scoring against a flat set of JD keywords.

    Returns:
        score         — 0-100 (exact matches only)
        total         — total keyword count
        matched       — set of keywords found verbatim
        missing       — set not found at all (no synonym either)
        synonym_hits  — dict {jd_keyword: synonym_found_in_resume}
    """
    text_lower = resume_text.lower()
    matched: Set[str]       = set()
    missing: Set[str]       = set()
    synonym_hits: Dict[str, str] = {}

    for kw in jd_keywords:
        kw_lower = kw.lower()
        if _ats_exact(kw_lower, text_lower):
            matched.add(kw)
            continue

        # Check: JD has full form, resume might use abbreviation
        syn_found = None
        if kw_lower in _ATS_SYNONYMS:
            for abbrev in _ATS_SYNONYMS[kw_lower]:
                if _ats_exact(abbrev, text_lower):
                    syn_found = abbrev
                    break

        # Check: JD has abbreviation, resume might use full form
        if syn_found is None and kw_lower in _ATS_SYN_REV:
            full_form = _ATS_SYN_REV[kw_lower]
            if _ats_exact(full_form, text_lower):
                syn_found = full_form

        if syn_found:
            synonym_hits[kw] = syn_found
        else:
            missing.add(kw)

    total = len(jd_keywords)
    score = round(len(matched) / total * 100) if total else 0
    return {
        "score":        score,
        "total":        total,
        "matched":      matched,
        "missing":      missing,
        "synonym_hits": synonym_hits,
    }


# ─── Sidebar ─────────────────────────────────────────────────────────────────

with st.sidebar:
    st.markdown("### ⚙️ Settings")
    st.divider()

    ai_enabled = st.toggle("Enable AI Analysis", value=False,
                            help="Use Gemini to get deeper insights beyond keyword matching.")

    gemini_key = ""
    if ai_enabled:
        st.info(
            "AI Analysis sends your JD + resume to the **Gemini 2.0 Flash** model. "
            "Get your free API key from [Google AI Studio](https://aistudio.google.com/).",
            icon="ℹ️",
        )
        gemini_key = st.text_input(
            "Gemini API Key",
            type="password",
            placeholder="AIza…",
            help="Your key is never stored — it lives only in this browser session.",
        )
        if gemini_key:
            st.success("Key received ✓", icon="🔑")

    st.divider()
    st.caption("**Job Application Toolkit** · Phase 1")
    st.caption("Powered by scikit-learn TF-IDF + Gemini 2.0 Flash")


# ─── Header ──────────────────────────────────────────────────────────────────

st.markdown("# 🎯 Resume Matcher")
st.markdown(
    "Paste a job description, upload your resume PDFs, and instantly see which resume "
    "fits best — with missing keywords and optional AI coaching."
)
st.divider()


# ─── Input section ────────────────────────────────────────────────────────────

col_jd, col_up = st.columns([3, 2], gap="large")

with col_jd:
    st.markdown("#### 📋 Job Description")
    jd_input = st.text_area(
        label="jd",
        label_visibility="collapsed",
        height=360,
        placeholder=(
            "Paste the full job description here…\n\n"
            "Include the responsibilities, required skills, "
            "qualifications, and any preferred experience."
        ),
    )

with col_up:
    st.markdown("#### 📄 Resume PDFs")
    uploaded_files = st.file_uploader(
        label="upload",
        label_visibility="collapsed",
        type=["pdf"],
        accept_multiple_files=True,
        help="Upload one or more PDF resumes to compare.",
    )
    if uploaded_files:
        for f in uploaded_files:
            st.markdown(f"✅ `{f.name}`")
    else:
        st.markdown(
            "<span style='color:#8b949e;font-size:13px'>"
            "Upload at least one PDF to get started.</span>",
            unsafe_allow_html=True,
        )

st.divider()

# ─── Analyse button ───────────────────────────────────────────────────────────

_, btn_col, _ = st.columns([1, 2, 1])
with btn_col:
    analyse = st.button("🔍  Analyse Resumes", use_container_width=True, type="primary")


# ─── Run analysis ─────────────────────────────────────────────────────────────

if analyse:
    if not jd_input.strip():
        st.error("Please paste a job description before analysing.")
    elif not uploaded_files:
        st.error("Please upload at least one resume PDF.")
    else:
        with st.spinner("Extracting keywords and scoring resumes…"):

            jd_kw  = extract_keywords(jd_input)
            jd_all = get_all_keywords(jd_kw)

            results      : Dict[str, Dict]  = {}
            resume_texts : Dict[str, str]   = {}
            parse_warnings: List[str]        = []

            seen_names: Dict[str, int] = {}
            for pdf in uploaded_files:
                raw_name = pdf.name
                # Deduplicate filenames
                if raw_name in seen_names:
                    seen_names[raw_name] += 1
                    name = f"{raw_name} ({seen_names[raw_name]})"
                else:
                    seen_names[raw_name] = 0
                    name = raw_name

                text = extract_text_from_pdf(pdf)
                if text.startswith("[PDF_EXTRACTION_ERROR"):
                    parse_warnings.append(f"**{name}**: {text}")
                    text = ""

                resume_texts[name] = text
                res_kw = extract_keywords(text)
                results[name] = score_resume(jd_input, text, jd_kw, res_kw)

            if parse_warnings:
                for w in parse_warnings:
                    st.warning(w)

            ranked = rank_resumes(results)

        # Persist to session state so results survive reruns
        st.session_state.update(
            ranked=ranked,
            jd_input=jd_input,
            jd_kw=jd_kw,
            jd_all=jd_all,
            resume_texts=resume_texts,
            ai_enabled=ai_enabled,
            gemini_key=gemini_key,
        )


# ─── Results section ──────────────────────────────────────────────────────────

if "ranked" not in st.session_state:
    st.stop()

ranked       = st.session_state["ranked"]
jd_input_ss  = st.session_state["jd_input"]
jd_kw_ss     = st.session_state["jd_kw"]
jd_all_ss    = st.session_state["jd_all"]
resume_texts = st.session_state["resume_texts"]
ai_on        = st.session_state.get("ai_enabled", False)
g_key        = st.session_state.get("gemini_key", "")

st.divider()
st.markdown("## 📊 Results")

# ── Best-match banner ─────────────────────────────────────────────────────────

best_name, best_data = ranked[0]
bcss = _score_css(best_data["final_score"])
st.markdown(
    f"""
<div class="banner">
  <div class="banner-label">🏆 Best Match</div>
  <div class="banner-name">{best_name}</div>
  <div class="banner-score {bcss}">{best_data['final_score']}%</div>
  <div class="banner-sub">Overall match score</div>
</div>
""",
    unsafe_allow_html=True,
)

# ── JD keyword summary ────────────────────────────────────────────────────────

with st.expander("📌 Detected JD Keywords", expanded=False):
    c1, c2, c3, c4 = st.columns(4)
    with c1:
        st.markdown("**Languages**")
        st.markdown(
            _kw_tags(jd_kw_ss.get("languages", set()), "kw-neutral")
            or "<em style='color:#8b949e'>none detected</em>",
            unsafe_allow_html=True,
        )
    with c2:
        st.markdown("**Frameworks**")
        st.markdown(
            _kw_tags(jd_kw_ss.get("frameworks", set()), "kw-neutral"),
            unsafe_allow_html=True,
        )
    with c3:
        st.markdown("**Tools & Platforms**")
        st.markdown(
            _kw_tags(jd_kw_ss.get("tools", set()), "kw-neutral"),
            unsafe_allow_html=True,
        )
    with c4:
        st.markdown("**Soft Skills**")
        st.markdown(
            _kw_tags(jd_kw_ss.get("soft_skills", set()), "kw-neutral"),
            unsafe_allow_html=True,
        )
    if jd_kw_ss.get("experience"):
        st.markdown("**Experience mentions:** " +
                    ", ".join(sorted(jd_kw_ss["experience"])))

# ── Charts ────────────────────────────────────────────────────────────────────

st.markdown('<div class="sec-header">📈 Visualisations</div>', unsafe_allow_html=True)

chart_tab1, chart_tab2 = st.tabs(["Overall Rankings", "Keyword Coverage"])

with chart_tab1:
    st.plotly_chart(_score_bar_chart(ranked), use_container_width=True, key="chart_rankings")

with chart_tab2:
    if jd_all_ss:
        st.plotly_chart(_keyword_overlap_chart(ranked), use_container_width=True, key="chart_kw_overlap")
    else:
        st.info("No technical keywords were detected in the job description.")

# ── Per-resume detailed breakdown ─────────────────────────────────────────────

st.markdown('<div class="sec-header">🔍 Detailed Breakdown</div>',
            unsafe_allow_html=True)

for rank_pos, (name, data) in enumerate(ranked, start=1):
    score      = data["final_score"]
    score_css  = _score_css(score)
    badge_html = _rank_badge(rank_pos)

    rank_icon = {1: "🥇", 2: "🥈", 3: "🥉"}.get(rank_pos, f"#{rank_pos}")
    with st.expander(
        f"{rank_icon}  {name}  —  {score}% match",
        expanded=(rank_pos == 1),
    ):
        # ── Header row
        st.markdown(
            f"{badge_html} "
            f"<span style='font-size:17px;font-weight:600;color:#e6edf3'>{name}</span>",
            unsafe_allow_html=True,
        )

        top_left, top_right = st.columns([1, 1], gap="large")

        with top_left:
            # Big score + sub-metrics
            st.markdown(
                f"<div style='margin:12px 0'>"
                f"  <div class='score-big {score_css}'>{score}%</div>"
                f"  <div style='color:#8b949e;font-size:13px;margin-top:4px'>Overall Match</div>"
                f"</div>",
                unsafe_allow_html=True,
            )
            st.markdown(
                f"""
<div class="metric-row">
  <div class="metric-box">
    <div class="label">TF-IDF Similarity</div>
    <div class="value {_score_css(data['tfidf_similarity'])}">{data['tfidf_similarity']}%</div>
  </div>
  <div class="metric-box">
    <div class="label">Keyword Match</div>
    <div class="value {_score_css(data['keyword_match'])}">{data['keyword_match']}%</div>
  </div>
</div>
""",
                unsafe_allow_html=True,
            )

            # Category scores as small progress bars
            st.markdown("**Category Scores**")
            cat_labels = {
                "languages": "Languages", "frameworks": "Frameworks",
                "tools": "Tools & Platforms", "soft_skills": "Soft Skills",
            }
            for cat, label in cat_labels.items():
                val = data["category_scores"].get(cat, 0)
                st.markdown(
                    f"<div style='font-size:12px;color:#8b949e;margin:4px 0 1px'>{label}</div>",
                    unsafe_allow_html=True,
                )
                st.progress(int(val) / 100, text=f"{val}%")

        with top_right:
            # Radar chart
            st.plotly_chart(_radar_chart(data), use_container_width=True, key=f"chart_radar_{rank_pos}")

        st.divider()

        # ── Missing keywords ──────────────────────────────────────────────────
        st.markdown("**❌ Missing Keywords from JD**")

        tab_miss_flat, tab_miss_cat = st.tabs(["All Missing", "By Category"])

        with tab_miss_flat:
            if data["missing_keywords"]:
                st.markdown(
                    _kw_tags(data["missing_keywords"], "kw-missing"),
                    unsafe_allow_html=True,
                )
                st.caption(
                    f"Your resume is missing **{len(data['missing_keywords'])}** "
                    f"keyword(s) that appear in the JD."
                )
            else:
                st.success("All detected JD keywords are present in this resume! 🎉")

        with tab_miss_cat:
            for cat, label in cat_labels.items():
                miss_set = data["cat_missing"].get(cat, set())
                if miss_set:
                    st.markdown(
                        f'<span class="cat-pill">{label}</span>'
                        + _kw_tags(miss_set, "kw-missing"),
                        unsafe_allow_html=True,
                    )
            if not any(data["cat_missing"].get(c) for c in cat_labels):
                st.success("No category-specific gaps detected! 🎉")

        st.divider()

        # ── Matched keywords ──────────────────────────────────────────────────
        if data["overlap_keywords"]:
            st.markdown("**✅ Matched Keywords**")
            st.markdown(
                _kw_tags(data["overlap_keywords"], "kw-matched"),
                unsafe_allow_html=True,
            )

        # ── AI Analysis ───────────────────────────────────────────────────────
        if ai_on:
            st.divider()
            st.markdown("**🤖 AI Analysis (Gemini 2.0 Flash)**")
            if not g_key:
                st.warning(
                    "AI Analysis is enabled but no API key was provided. "
                    "Enter your Gemini API key in the sidebar.",
                    icon="⚠️",
                )
            else:
                ai_btn_key = f"ai_btn_{rank_pos}"
                ai_res_key = f"ai_result_{name}"

                if st.button(f"✨ Generate AI Analysis for {name}", key=ai_btn_key):
                    with st.spinner("Calling Gemini 2.0 Flash…"):
                        result = _gemini_analysis(
                            jd_input_ss,
                            resume_texts.get(name, ""),
                            g_key,
                        )
                        st.session_state[ai_res_key] = result

                if ai_res_key in st.session_state:
                    st.markdown(st.session_state[ai_res_key])


# ─── ATS Score Simulation ─────────────────────────────────────────────────────

st.divider()
st.markdown('<div class="sec-header">🎯 ATS Score Simulation</div>', unsafe_allow_html=True)
st.caption(
    "ATS (Applicant Tracking Systems) are dumb — they do exact keyword matching only, "
    "with no semantic understanding. This simulation shows how an automated screener "
    "would score your resume before a human ever reads it."
)

# Resume selector
ats_names = list(resume_texts.keys())
if len(ats_names) > 1:
    ats_sel = st.selectbox("Select resume to simulate", ats_names, key="ats_resume_sel")
else:
    ats_sel = ats_names[0]

ats_resume_text = resume_texts.get(ats_sel, "")

if not jd_all_ss:
    st.info("No keywords were detected in the JD — ATS simulation requires at least one keyword.")
else:
    ats = _ats_compute(jd_all_ss, ats_resume_text)
    our_score = next((d["final_score"] for n, d in ranked if n == ats_sel), None)

    ats_score = ats["score"]
    ats_hex   = "#3fb950" if ats_score >= 80 else "#d29922" if ats_score >= 60 else "#f85149"
    ats_label = "Strong Pass" if ats_score >= 80 else "Borderline" if ats_score >= 60 else "Likely Filtered"

    # ── Score comparison cards ────────────────────────────────────────────────
    cmp_l, cmp_m, cmp_r = st.columns([5, 1, 5])

    with cmp_l:
        our_hex = "#3fb950" if (our_score or 0) >= 70 else "#d29922" if (our_score or 0) >= 50 else "#f85149"
        st.markdown(
            f"""<div class="ats-cmp-box">
  <div class="ats-cmp-label">Our Match Score</div>
  <div class="ats-cmp-value" style="color:{our_hex}">{our_score}%</div>
  <div class="ats-cmp-sub">Semantic + keyword matching</div>
</div>""",
            unsafe_allow_html=True,
        )

    with cmp_m:
        st.markdown(
            "<div style='display:flex;align-items:center;justify-content:center;"
            "height:100%;font-size:26px;color:#30363d'>⟷</div>",
            unsafe_allow_html=True,
        )

    with cmp_r:
        st.markdown(
            f"""<div class="ats-cmp-box">
  <div class="ats-cmp-label">ATS Score</div>
  <div class="ats-cmp-value" style="color:{ats_hex}">{ats_score}%</div>
  <div class="ats-cmp-sub">{ats_label} · exact keyword only</div>
</div>""",
            unsafe_allow_html=True,
        )

    # ── Gap message ───────────────────────────────────────────────────────────
    if our_score is not None:
        gap = our_score - ats_score
        if gap > 10:
            st.info(
                f"**Gap detected:** Your resume is smarter than an ATS thinks. "
                f"Our semantic score ({our_score}%) is {gap}% higher than the ATS score "
                f"({ats_score}%). Adding exact keyword spellings would close this gap.",
                icon="💡",
            )
        elif ats_score >= 80:
            st.success(
                f"Strong ATS profile! Your exact keyword coverage ({ats_score}%) would "
                f"pass most automated screeners.",
                icon="✅",
            )

    # ── Score improvement callout ─────────────────────────────────────────────
    n_actionable = len(ats["missing"]) + len(ats["synonym_hits"])
    if n_actionable > 0 and ats["total"] > 0:
        improved = round((len(ats["matched"]) + n_actionable) / ats["total"] * 100)
        st.markdown(
            f'<div class="ats-tip" style="margin-top:14px">💡 <strong>Score Improvement:</strong> '
            f"Fixing or adding these <strong>{n_actionable}</strong> keyword(s) would raise "
            f"your ATS score from <strong>{ats_score}%</strong> to "
            f"<strong>{improved}%</strong>.</div>",
            unsafe_allow_html=True,
        )

    # ── Keyword comparison table ──────────────────────────────────────────────
    st.markdown("<br>", unsafe_allow_html=True)
    with st.expander("📋 Keyword Comparison Table", expanded=True):
        # Sort: missing → synonym → matched
        def _ats_sort_key(k: str) -> int:
            if k in ats["missing"]:      return 0
            if k in ats["synonym_hits"]: return 1
            return 2

        sorted_kws = sorted(jd_all_ss, key=_ats_sort_key)

        rows_html = ""
        for kw in sorted_kws:
            if kw in ats["matched"]:
                status = '<span style="color:#3fb950;font-weight:600">✓ Found</span>'
                suggestion = "—"
            elif kw in ats["synonym_hits"]:
                syn = ats["synonym_hits"][kw]
                status = '<span style="color:#d29922;font-weight:600">~ Synonym</span>'
                suggestion = (
                    f"Found as <code>{syn}</code> — "
                    f"change to <code>{kw}</code> for ATS"
                )
            else:
                status = '<span style="color:#f85149;font-weight:600">✗ Missing</span>'
                suggestion = f"Add <code>{kw}</code> to your skills section"

            rows_html += (
                f"<tr>"
                f"<td><code>{kw}</code></td>"
                f"<td>{status}</td>"
                f"<td style='color:#c9d1d9'>{suggestion}</td>"
                f"</tr>\n"
            )

        st.markdown(
            f"""<table class="ats-kw-table">
<thead>
  <tr>
    <th style="width:30%">JD Keyword</th>
    <th style="width:20%">Found in Resume?</th>
    <th>Suggestion</th>
  </tr>
</thead>
<tbody>
{rows_html}</tbody>
</table>""",
            unsafe_allow_html=True,
        )

        n_m = len(ats["matched"])
        n_s = len(ats["synonym_hits"])
        n_x = len(ats["missing"])
        st.markdown("<br>", unsafe_allow_html=True)
        st.markdown(
            f"**Summary:** "
            f"<span style='color:#3fb950'>{n_m} exact matches</span> &nbsp;·&nbsp; "
            f"<span style='color:#d29922'>{n_s} synonym-only (not ATS-safe)</span> &nbsp;·&nbsp; "
            f"<span style='color:#f85149'>{n_x} missing</span>",
            unsafe_allow_html=True,
        )

    # ── ATS formatting tips ───────────────────────────────────────────────────
    st.markdown("<br>", unsafe_allow_html=True)
    st.markdown("**📐 ATS Formatting Tips**")
    st.markdown(
        """<div class="ats-warn">
⚠️ <strong>Common ATS formatting mistakes to avoid:</strong>
<ul style="margin:8px 0 0 0;padding-left:20px;line-height:2">
  <li>Avoid tables and multi-column layouts — ATS parsers often skip content inside them</li>
  <li>Use standard section headers: <code>Experience</code>, <code>Education</code>, <code>Skills</code>, <code>Summary</code></li>
  <li>Save as <code>.docx</code> or a plain, unformatted PDF — no text boxes or graphics</li>
  <li>Don't put contact info only in the header/footer — some ATS systems skip those regions</li>
  <li>Spell out abbreviations at least once: e.g. <em>Machine Learning (ML)</em> — then ATS finds both</li>
</ul>
</div>""",
        unsafe_allow_html=True,
    )


# ─── Footer ───────────────────────────────────────────────────────────────────

st.divider()
st.markdown(
    "<div style='text-align:center;color:#8b949e;font-size:12px'>"
    "Job Application Toolkit · Phase 1 · Resume Matcher<br>"
    "Scoring = 40% TF-IDF + 30% Keyword Match + 30% Category Keywords"
    "</div>",
    unsafe_allow_html=True,
)
