"""
analytics.py — Phase 11: Job Search Analytics Dashboard.

Run with:
    streamlit run analytics.py

Five views:
    1. Search Overview   — KPIs, application timeline, status funnel, source breakdown
    2. Skill Demand      — top skills, skills by role, skill source distribution
    3. Salary Insights   — salary distribution, by role, by remote type, by company size
    4. Market Map        — industry, remote type, education, experience, top companies
    5. Resume Performance— match score distribution, score vs outcome, resume versions
"""

import os
import re
import sqlite3
from collections import Counter
from datetime import datetime, timedelta

import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
import streamlit as st

# ─── Constants ────────────────────────────────────────────────────────────────

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "jobs.db")

_BG   = "#0d1117"
_CARD = "#161b22"
_GRID = "#30363d"
_TEXT = "#c9d1d9"
_DIM  = "#8b949e"
_ACCENT = "#388bfd"

STATUS_COLOR = {
    "saved":        "#388bfd",
    "applied":      "#d29922",
    "interviewing": "#a371f7",
    "rejected":     "#f85149",
    "offer":        "#3fb950",
    "ghosted":      "#8b949e",
}

_PLOTLY_LAYOUT = dict(
    paper_bgcolor=_BG,
    plot_bgcolor=_CARD,
    font=dict(color=_TEXT, family="monospace"),
    xaxis=dict(gridcolor=_GRID, zerolinecolor=_GRID, color=_TEXT),
    yaxis=dict(gridcolor=_GRID, zerolinecolor=_GRID, color=_TEXT),
    margin=dict(l=40, r=20, t=40, b=40),
    legend=dict(bgcolor=_CARD, bordercolor=_GRID, borderwidth=1),
)


# ─── Page config ──────────────────────────────────────────────────────────────

st.set_page_config(
    page_title="Job Search Analytics",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="collapsed",
)

st.markdown(f"""
<style>
  html, body, [data-testid="stAppViewContainer"] {{
      background-color: {_BG};
      color: {_TEXT};
  }}
  [data-testid="stSidebar"] {{
      background-color: {_CARD};
  }}
  .block-container {{ padding-top: 1.2rem; padding-bottom: 0; }}
  h1, h2, h3 {{ color: {_TEXT}; font-family: monospace; }}
  [data-testid="metric-container"] {{
      background: {_CARD};
      border: 1px solid {_GRID};
      border-radius: 8px;
      padding: 12px 16px;
  }}
  [data-testid="metric-container"] label {{ color: {_DIM} !important; font-size: 0.78rem; }}
  [data-testid="metric-container"] [data-testid="stMetricValue"] {{
      color: {_TEXT} !important; font-size: 1.6rem;
  }}
  [data-testid="metric-container"] [data-testid="stMetricDelta"] {{
      font-size: 0.80rem;
  }}
  div[data-testid="stTabs"] button {{
      color: {_DIM};
      background: transparent;
      border-bottom: 2px solid transparent;
  }}
  div[data-testid="stTabs"] button[aria-selected="true"] {{
      color: {_TEXT};
      border-bottom: 2px solid {_ACCENT};
  }}
  footer {{ visibility: hidden; }}
  .analytics-footer {{
      text-align: center;
      color: {_DIM};
      font-size: 0.75rem;
      font-family: monospace;
      padding: 24px 0 8px 0;
      border-top: 1px solid {_GRID};
      margin-top: 32px;
  }}
  .section-header {{
      font-size: 0.72rem;
      font-family: monospace;
      color: {_DIM};
      text-transform: uppercase;
      letter-spacing: 0.12em;
      border-bottom: 1px solid {_GRID};
      padding-bottom: 4px;
      margin-bottom: 12px;
  }}
  .empty-state {{
      background: {_CARD};
      border: 1px dashed {_GRID};
      border-radius: 8px;
      padding: 32px;
      text-align: center;
      color: {_DIM};
      font-family: monospace;
  }}
</style>
""", unsafe_allow_html=True)


# ─── Data loading ─────────────────────────────────────────────────────────────

@st.cache_data(ttl=60)
def load_data() -> pd.DataFrame:
    if not os.path.exists(DB_PATH):
        return pd.DataFrame()
    try:
        with sqlite3.connect(DB_PATH) as conn:
            df = pd.read_sql("SELECT * FROM jobs ORDER BY last_updated DESC", conn)
    except Exception:
        return pd.DataFrame()

    # Normalize dates
    for col in ["date_applied", "posting_date", "last_updated"]:
        if col in df.columns:
            df[col] = pd.to_datetime(df[col], errors="coerce")

    # Numeric coercion
    for col in ["pay_min", "pay_max", "match_score", "experience_years"]:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")

    return df


def _parse_list_col(series: pd.Series) -> list[str]:
    """Flatten a column of comma/newline-separated strings into a single list."""
    items = []
    for val in series.dropna():
        for part in re.split(r"[,\n]+", str(val)):
            part = part.strip()
            if len(part) > 1:
                items.append(part.lower())
    return items


def _role_group(title: str) -> str:
    t = title.lower()
    if any(x in t for x in ["data scientist", "ds "]):
        return "Data Scientist"
    if any(x in t for x in ["machine learning", "ml engineer", "mle"]):
        return "ML Engineer"
    if any(x in t for x in ["data engineer", " de "]):
        return "Data Engineer"
    if any(x in t for x in ["software engineer", "swe", "backend", "frontend", "fullstack"]):
        return "Software Engineer"
    if any(x in t for x in ["ai engineer", "ai "]):
        return "AI Engineer"
    if "analyst" in t:
        return "Analyst"
    return "Other"


def _fig(fig: go.Figure) -> go.Figure:
    fig.update_layout(**_PLOTLY_LAYOUT)
    return fig


def _empty_chart(msg: str = "No data yet") -> go.Figure:
    fig = go.Figure()
    fig.add_annotation(text=msg, x=0.5, y=0.5, xref="paper", yref="paper",
                        showarrow=False, font=dict(color=_DIM, size=14))
    return _fig(fig)


# ─── View helpers ─────────────────────────────────────────────────────────────

def _metric_row(cols_data: list[tuple]) -> None:
    """Render a row of st.metric cards. cols_data = [(label, value, delta?), ...]"""
    cols = st.columns(len(cols_data))
    for col, item in zip(cols, cols_data):
        label, value = item[0], item[1]
        delta = item[2] if len(item) > 2 else None
        col.metric(label, value, delta)


# ─── View 1: Search Overview ──────────────────────────────────────────────────

def view_overview(df: pd.DataFrame) -> None:
    st.markdown('<div class="section-header">Key Metrics</div>', unsafe_allow_html=True)

    total    = len(df)
    applied  = len(df[df["status"].isin(["applied", "interviewing", "offer", "rejected", "ghosted"])])
    inter    = len(df[df["status"] == "interviewing"])
    offers   = len(df[df["status"] == "offer"])
    rejected = len(df[df["status"] == "rejected"])
    ghosted  = len(df[df["status"] == "ghosted"])
    resp_rate = f"{(inter + offers) / applied * 100:.1f}%" if applied else "—"
    rej_rate  = f"{rejected / applied * 100:.1f}%" if applied else "—"

    _metric_row([
        ("Total Tracked", total),
        ("Applied", applied),
        ("Interviewing", inter),
        ("Offers", offers),
        ("Response Rate", resp_rate),
        ("Rejection Rate", rej_rate),
    ])

    st.markdown("<br>", unsafe_allow_html=True)
    left, right = st.columns([3, 2])

    # ── Timeline ──
    with left:
        st.markdown('<div class="section-header">Applications Over Time</div>', unsafe_allow_html=True)
        applied_df = df[df["date_applied"].notna()].copy()
        if applied_df.empty:
            st.markdown('<div class="empty-state">No application dates recorded yet.</div>', unsafe_allow_html=True)
        else:
            applied_df["week"] = applied_df["date_applied"].dt.to_period("W").dt.start_time
            weekly = (
                applied_df.groupby(["week", "status"])
                .size()
                .reset_index(name="count")
            )
            fig = go.Figure()
            for status, color in STATUS_COLOR.items():
                sub = weekly[weekly["status"] == status]
                if sub.empty:
                    continue
                fig.add_trace(go.Bar(
                    x=sub["week"], y=sub["count"],
                    name=status.capitalize(), marker_color=color,
                ))
            fig.update_layout(
                **_PLOTLY_LAYOUT,
                barmode="stack",
                title=dict(text="Weekly Applications by Status", font=dict(color=_TEXT, size=13)),
                xaxis_title="Week",
                yaxis_title="Applications",
                showlegend=True,
            )
            st.plotly_chart(fig, use_container_width=True)

    # ── Status funnel ──
    with right:
        st.markdown('<div class="section-header">Application Funnel</div>', unsafe_allow_html=True)
        funnel_stages = ["saved", "applied", "interviewing", "offer"]
        funnel_counts = [len(df[df["status"] == s]) for s in funnel_stages]
        if sum(funnel_counts) == 0:
            st.markdown('<div class="empty-state">No funnel data yet.</div>', unsafe_allow_html=True)
        else:
            fig = go.Figure(go.Funnel(
                y=[s.capitalize() for s in funnel_stages],
                x=funnel_counts,
                marker=dict(color=[STATUS_COLOR[s] for s in funnel_stages]),
                textinfo="value+percent initial",
                textfont=dict(color=_TEXT),
                connector=dict(line=dict(color=_GRID, width=1)),
            ))
            fig.update_layout(
                **_PLOTLY_LAYOUT,
                title=dict(text="Hiring Funnel", font=dict(color=_TEXT, size=13)),
            )
            st.plotly_chart(fig, use_container_width=True)

    # ── Source breakdown + status donut ──
    c1, c2 = st.columns(2)

    with c1:
        st.markdown('<div class="section-header">Applications by Source</div>', unsafe_allow_html=True)
        if "source" in df.columns and df["source"].notna().any():
            src = df["source"].value_counts().reset_index()
            src.columns = ["source", "count"]
            fig = go.Figure(go.Bar(
                x=src["source"].str.capitalize(),
                y=src["count"],
                marker_color=_ACCENT,
                text=src["count"],
                textposition="outside",
                textfont=dict(color=_TEXT),
            ))
            fig.update_layout(
                **_PLOTLY_LAYOUT,
                title=dict(text="Source Breakdown", font=dict(color=_TEXT, size=13)),
                xaxis_title="Source",
                yaxis_title="Count",
                showlegend=False,
            )
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.markdown('<div class="empty-state">No source data.</div>', unsafe_allow_html=True)

    with c2:
        st.markdown('<div class="section-header">Current Status Distribution</div>', unsafe_allow_html=True)
        status_counts = df["status"].value_counts()
        if status_counts.empty:
            st.markdown('<div class="empty-state">No status data.</div>', unsafe_allow_html=True)
        else:
            fig = go.Figure(go.Pie(
                labels=[s.capitalize() for s in status_counts.index],
                values=status_counts.values,
                marker=dict(colors=[STATUS_COLOR.get(s, _DIM) for s in status_counts.index]),
                hole=0.45,
                textinfo="label+percent",
                textfont=dict(color=_TEXT),
                hovertemplate="%{label}: %{value}<extra></extra>",
            ))
            fig.update_layout(
                **_PLOTLY_LAYOUT,
                title=dict(text="Status Donut", font=dict(color=_TEXT, size=13)),
                showlegend=False,
            )
            st.plotly_chart(fig, use_container_width=True)


# ─── View 2: Skill Demand ─────────────────────────────────────────────────────

def view_skills(df: pd.DataFrame) -> None:
    st.markdown('<div class="section-header">Top Skills</div>', unsafe_allow_html=True)

    all_skills = _parse_list_col(df.get("tech_stack", pd.Series(dtype=str)))
    all_skills += _parse_list_col(df.get("skills_required", pd.Series(dtype=str)))

    if not all_skills:
        st.markdown('<div class="empty-state">No skill data found. Add tech_stack or skills_required to your tracked jobs.</div>', unsafe_allow_html=True)
        return

    skill_counts = Counter(all_skills)
    top_n = 25
    top_skills = pd.DataFrame(skill_counts.most_common(top_n), columns=["skill", "count"])

    # ── Top 25 skills bar ──
    palette = [_ACCENT] * len(top_skills)
    palette[0] = "#3fb950"
    palette[1] = "#a371f7"
    palette[2] = "#d29922"

    fig = go.Figure(go.Bar(
        x=top_skills["count"],
        y=top_skills["skill"].str.title(),
        orientation="h",
        marker_color=palette,
        text=top_skills["count"],
        textposition="outside",
        textfont=dict(color=_TEXT, size=10),
    ))
    fig.update_layout(
        **_PLOTLY_LAYOUT,
        title=dict(text=f"Top {top_n} Most Required Skills", font=dict(color=_TEXT, size=13)),
        xaxis_title="Mentions",
        yaxis=dict(autorange="reversed", gridcolor=_GRID, color=_TEXT),
        height=600,
        showlegend=False,
    )
    st.plotly_chart(fig, use_container_width=True)

    # ── Skills by role group ──
    st.markdown('<div class="section-header">Skill Demand by Role Group</div>', unsafe_allow_html=True)

    if "title" not in df.columns:
        st.markdown('<div class="empty-state">No title data for role grouping.</div>', unsafe_allow_html=True)
        return

    df2 = df.copy()
    df2["role_group"] = df2["title"].fillna("").apply(_role_group)
    role_groups = [g for g in df2["role_group"].unique() if g != "Other"]

    if not role_groups:
        st.markdown('<div class="empty-state">Not enough role variety for skill breakdown.</div>', unsafe_allow_html=True)
        return

    # Build heatmap: top 15 skills × role groups
    top15 = [s for s, _ in skill_counts.most_common(15)]
    heat_data = []
    for role in role_groups:
        sub = df2[df2["role_group"] == role]
        role_skills = _parse_list_col(sub.get("tech_stack", pd.Series(dtype=str)))
        role_skills += _parse_list_col(sub.get("skills_required", pd.Series(dtype=str)))
        rc = Counter(role_skills)
        total = max(len(sub), 1)
        heat_data.append([rc.get(s, 0) / total for s in top15])

    fig = go.Figure(go.Heatmap(
        z=heat_data,
        x=[s.title() for s in top15],
        y=role_groups,
        colorscale=[[0, _CARD], [0.5, "#1d3557"], [1, _ACCENT]],
        text=[[f"{v:.0%}" for v in row] for row in heat_data],
        texttemplate="%{text}",
        textfont=dict(size=9, color=_TEXT),
        hovertemplate="Role: %{y}<br>Skill: %{x}<br>Frequency: %{text}<extra></extra>",
        showscale=True,
        colorbar=dict(
            tickfont=dict(color=_TEXT),
            bgcolor=_CARD,
            bordercolor=_GRID,
        ),
    ))
    fig.update_layout(
        **_PLOTLY_LAYOUT,
        title=dict(text="Skill Frequency by Role Group (% of jobs in group)", font=dict(color=_TEXT, size=13)),
        height=350,
        xaxis=dict(tickangle=-35, color=_TEXT, gridcolor=_GRID),
    )
    st.plotly_chart(fig, use_container_width=True)

    # ── Skills by source ──
    if "source" in df.columns:
        st.markdown('<div class="section-header">Top Skills by Job Source</div>', unsafe_allow_html=True)
        sources = df["source"].dropna().unique()
        top8 = [s for s, _ in skill_counts.most_common(8)]

        traces_data = []
        for src in sources:
            sub = df[df["source"] == src]
            s_skills = _parse_list_col(sub.get("tech_stack", pd.Series(dtype=str)))
            s_skills += _parse_list_col(sub.get("skills_required", pd.Series(dtype=str)))
            sc = Counter(s_skills)
            total = max(len(sub), 1)
            traces_data.append((src, [sc.get(s, 0) / total for s in top8]))

        fig = go.Figure()
        colors = [_ACCENT, "#3fb950", "#a371f7", "#d29922"]
        for i, (src, vals) in enumerate(traces_data):
            fig.add_trace(go.Bar(
                name=src.capitalize(),
                x=[s.title() for s in top8],
                y=vals,
                marker_color=colors[i % len(colors)],
            ))
        fig.update_layout(
            **_PLOTLY_LAYOUT,
            barmode="group",
            title=dict(text="Skill Frequency by Source (% of postings)", font=dict(color=_TEXT, size=13)),
            yaxis_title="Share of postings",
            yaxis_tickformat=".0%",
        )
        st.plotly_chart(fig, use_container_width=True)


# ─── View 3: Salary Insights ──────────────────────────────────────────────────

def view_salary(df: pd.DataFrame) -> None:
    salary_df = df[df["pay_min"].notna() | df["pay_max"].notna()].copy()

    if salary_df.empty:
        st.markdown('<div class="empty-state">No salary data yet. Add jobs with salary information to see insights.</div>', unsafe_allow_html=True)
        return

    salary_df["pay_mid"] = salary_df[["pay_min", "pay_max"]].mean(axis=1)
    salary_df["role_group"] = salary_df["title"].fillna("").apply(_role_group)

    # ── Distribution histogram ──
    st.markdown('<div class="section-header">Salary Distribution</div>', unsafe_allow_html=True)
    c1, c2 = st.columns(2)

    with c1:
        fig = go.Figure()
        if salary_df["pay_min"].notna().any():
            fig.add_trace(go.Histogram(
                x=salary_df["pay_min"].dropna() / 1000,
                name="Min Salary",
                marker_color="#388bfd",
                opacity=0.75,
                nbinsx=20,
            ))
        if salary_df["pay_max"].notna().any():
            fig.add_trace(go.Histogram(
                x=salary_df["pay_max"].dropna() / 1000,
                name="Max Salary",
                marker_color="#3fb950",
                opacity=0.75,
                nbinsx=20,
            ))
        fig.update_layout(
            **_PLOTLY_LAYOUT,
            barmode="overlay",
            title=dict(text="Salary Range Distribution (K USD)", font=dict(color=_TEXT, size=13)),
            xaxis_title="Salary (K USD)",
            yaxis_title="Jobs",
        )
        st.plotly_chart(fig, use_container_width=True)

    with c2:
        # Midpoint salary by status
        s_status = (
            salary_df.groupby("status")["pay_mid"]
            .median()
            .reset_index()
            .sort_values("pay_mid", ascending=False)
        )
        fig = go.Figure(go.Bar(
            x=s_status["status"].str.capitalize(),
            y=s_status["pay_mid"] / 1000,
            marker_color=[STATUS_COLOR.get(s, _ACCENT) for s in s_status["status"]],
            text=(s_status["pay_mid"] / 1000).round(0).astype(int).astype(str) + "K",
            textposition="outside",
            textfont=dict(color=_TEXT),
        ))
        fig.update_layout(
            **_PLOTLY_LAYOUT,
            title=dict(text="Median Mid-Salary by Application Status", font=dict(color=_TEXT, size=13)),
            xaxis_title="Status",
            yaxis_title="Median Salary (K USD)",
            showlegend=False,
        )
        st.plotly_chart(fig, use_container_width=True)

    # ── Salary by role ──
    st.markdown('<div class="section-header">Salary by Role Group</div>', unsafe_allow_html=True)
    role_order = (
        salary_df.groupby("role_group")["pay_mid"].median()
        .sort_values(ascending=False).index.tolist()
    )
    fig = go.Figure()
    colors = [_ACCENT, "#3fb950", "#a371f7", "#d29922", "#f85149", "#8b949e"]
    for i, role in enumerate(role_order):
        sub = salary_df[salary_df["role_group"] == role]["pay_mid"].dropna()
        if sub.empty:
            continue
        fig.add_trace(go.Box(
            y=sub / 1000,
            name=role,
            marker_color=colors[i % len(colors)],
            line_color=colors[i % len(colors)],
            fillcolor=colors[i % len(colors)] + "33",
            boxmean=True,
        ))
    fig.update_layout(
        **_PLOTLY_LAYOUT,
        title=dict(text="Mid-Salary Box Plot by Role Group (K USD)", font=dict(color=_TEXT, size=13)),
        yaxis_title="Salary (K USD)",
        showlegend=False,
    )
    st.plotly_chart(fig, use_container_width=True)

    # ── Salary by remote type and company size ──
    c3, c4 = st.columns(2)

    with c3:
        st.markdown('<div class="section-header">Salary by Remote Type</div>', unsafe_allow_html=True)
        if "remote_type" in salary_df.columns:
            rt = (
                salary_df.groupby("remote_type")["pay_mid"]
                .median()
                .reset_index()
                .sort_values("pay_mid", ascending=False)
            )
            rt_colors = {"remote": "#3fb950", "hybrid": "#d29922", "onsite": "#388bfd"}
            fig = go.Figure(go.Bar(
                x=rt["remote_type"].str.capitalize(),
                y=rt["pay_mid"] / 1000,
                marker_color=[rt_colors.get(r, _DIM) for r in rt["remote_type"]],
                text=(rt["pay_mid"] / 1000).round(0).astype(int).astype(str) + "K",
                textposition="outside",
                textfont=dict(color=_TEXT),
            ))
            fig.update_layout(
                **_PLOTLY_LAYOUT,
                title=dict(text="Median Salary by Work Type", font=dict(color=_TEXT, size=13)),
                yaxis_title="Salary (K USD)",
                showlegend=False,
            )
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.markdown('<div class="empty-state">No remote_type data.</div>', unsafe_allow_html=True)

    with c4:
        st.markdown('<div class="section-header">Salary by Company Size</div>', unsafe_allow_html=True)
        if "company_size" in salary_df.columns and salary_df["company_size"].notna().any():
            cs = (
                salary_df.groupby("company_size")["pay_mid"]
                .median()
                .reset_index()
                .sort_values("pay_mid", ascending=False)
            )
            fig = go.Figure(go.Bar(
                x=cs["pay_mid"] / 1000,
                y=cs["company_size"],
                orientation="h",
                marker_color=_ACCENT,
                text=(cs["pay_mid"] / 1000).round(0).astype(int).astype(str) + "K",
                textposition="outside",
                textfont=dict(color=_TEXT),
            ))
            fig.update_layout(
                **_PLOTLY_LAYOUT,
                title=dict(text="Median Salary by Company Size", font=dict(color=_TEXT, size=13)),
                xaxis_title="Salary (K USD)",
                yaxis=dict(autorange="reversed", color=_TEXT, gridcolor=_GRID),
                showlegend=False,
            )
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.markdown('<div class="empty-state">No company size data.</div>', unsafe_allow_html=True)


# ─── View 4: Market Map ───────────────────────────────────────────────────────

def view_market(df: pd.DataFrame) -> None:
    c1, c2 = st.columns(2)

    # ── Industry pie ──
    with c1:
        st.markdown('<div class="section-header">Industry Breakdown</div>', unsafe_allow_html=True)
        if "industry" in df.columns and df["industry"].notna().any():
            ind = df["industry"].value_counts().reset_index()
            ind.columns = ["industry", "count"]
            fig = go.Figure(go.Pie(
                labels=ind["industry"].str.title(),
                values=ind["count"],
                hole=0.35,
                textinfo="label+percent",
                textfont=dict(color=_TEXT, size=10),
                marker=dict(colors=px.colors.qualitative.Set2),
                hovertemplate="%{label}: %{value}<extra></extra>",
            ))
            fig.update_layout(
                **_PLOTLY_LAYOUT,
                title=dict(text="Jobs by Industry", font=dict(color=_TEXT, size=13)),
                showlegend=False,
            )
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.markdown('<div class="empty-state">No industry data.</div>', unsafe_allow_html=True)

    # ── Remote type donut ──
    with c2:
        st.markdown('<div class="section-header">Work Type Distribution</div>', unsafe_allow_html=True)
        if "remote_type" in df.columns and df["remote_type"].notna().any():
            rt = df["remote_type"].value_counts().reset_index()
            rt.columns = ["remote_type", "count"]
            rt_colors = {"remote": "#3fb950", "hybrid": "#d29922", "onsite": "#388bfd"}
            fig = go.Figure(go.Pie(
                labels=rt["remote_type"].str.capitalize(),
                values=rt["count"],
                hole=0.45,
                textinfo="label+value",
                textfont=dict(color=_TEXT),
                marker=dict(colors=[rt_colors.get(r, _DIM) for r in rt["remote_type"]]),
                hovertemplate="%{label}: %{value}<extra></extra>",
            ))
            fig.update_layout(
                **_PLOTLY_LAYOUT,
                title=dict(text="Remote / Hybrid / Onsite", font=dict(color=_TEXT, size=13)),
                showlegend=True,
            )
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.markdown('<div class="empty-state">No remote type data.</div>', unsafe_allow_html=True)

    # ── Top companies + Education ──
    c3, c4 = st.columns(2)

    with c3:
        st.markdown('<div class="section-header">Top Companies Hiring</div>', unsafe_allow_html=True)
        if "company" in df.columns and df["company"].notna().any():
            co = df["company"].value_counts().head(15).reset_index()
            co.columns = ["company", "count"]
            fig = go.Figure(go.Bar(
                x=co["count"],
                y=co["company"],
                orientation="h",
                marker_color=_ACCENT,
                text=co["count"],
                textposition="outside",
                textfont=dict(color=_TEXT, size=10),
            ))
            fig.update_layout(
                **_PLOTLY_LAYOUT,
                title=dict(text="Top 15 Companies (by job count)", font=dict(color=_TEXT, size=13)),
                xaxis_title="Jobs",
                yaxis=dict(autorange="reversed", color=_TEXT, gridcolor=_GRID),
                height=400,
                showlegend=False,
            )
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.markdown('<div class="empty-state">No company data.</div>', unsafe_allow_html=True)

    with c4:
        st.markdown('<div class="section-header">Education Requirements</div>', unsafe_allow_html=True)
        if "education" in df.columns and df["education"].notna().any():
            edu = df["education"].value_counts().reset_index()
            edu.columns = ["education", "count"]
            fig = go.Figure(go.Bar(
                x=edu["count"],
                y=edu["education"].str.title(),
                orientation="h",
                marker_color="#a371f7",
                text=edu["count"],
                textposition="outside",
                textfont=dict(color=_TEXT, size=10),
            ))
            fig.update_layout(
                **_PLOTLY_LAYOUT,
                title=dict(text="Education Level Required", font=dict(color=_TEXT, size=13)),
                xaxis_title="Jobs",
                yaxis=dict(autorange="reversed", color=_TEXT, gridcolor=_GRID),
                height=400,
                showlegend=False,
            )
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.markdown('<div class="empty-state">No education requirement data.</div>', unsafe_allow_html=True)

    # ── Experience distribution ──
    st.markdown('<div class="section-header">Experience Requirements</div>', unsafe_allow_html=True)
    if "experience_years" in df.columns and df["experience_years"].notna().any():
        exp_df = df[df["experience_years"].notna()].copy()
        fig = go.Figure(go.Histogram(
            x=exp_df["experience_years"],
            nbinsx=15,
            marker_color=_ACCENT,
            opacity=0.85,
        ))
        # Add median line
        med = exp_df["experience_years"].median()
        fig.add_vline(x=med, line_dash="dash", line_color="#3fb950",
                      annotation_text=f"Median: {med:.1f} yrs",
                      annotation_font_color="#3fb950")
        fig.update_layout(
            **_PLOTLY_LAYOUT,
            title=dict(text="Years of Experience Required", font=dict(color=_TEXT, size=13)),
            xaxis_title="Years",
            yaxis_title="Jobs",
        )
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.markdown('<div class="empty-state">No experience data yet.</div>', unsafe_allow_html=True)


# ─── View 5: Resume Performance ───────────────────────────────────────────────

def view_resume(df: pd.DataFrame) -> None:
    st.markdown('<div class="section-header">Match Score Analysis</div>', unsafe_allow_html=True)

    score_df = df[df["match_score"].notna()].copy()
    if score_df.empty:
        st.markdown('<div class="empty-state">No match scores recorded. Run the JD parser on your tracked jobs to generate scores.</div>', unsafe_allow_html=True)
        return

    c1, c2 = st.columns(2)

    # ── Score distribution ──
    with c1:
        fig = go.Figure(go.Histogram(
            x=score_df["match_score"],
            nbinsx=20,
            marker_color=_ACCENT,
            opacity=0.85,
        ))
        median_score = score_df["match_score"].median()
        fig.add_vline(x=median_score, line_dash="dash", line_color="#3fb950",
                      annotation_text=f"Median: {median_score:.0f}%",
                      annotation_font_color="#3fb950")
        fig.update_layout(
            **_PLOTLY_LAYOUT,
            title=dict(text="Match Score Distribution", font=dict(color=_TEXT, size=13)),
            xaxis_title="Match Score (%)",
            yaxis_title="Jobs",
        )
        st.plotly_chart(fig, use_container_width=True)

    # ── Score by status box ──
    with c2:
        status_order = ["saved", "applied", "interviewing", "offer", "rejected", "ghosted"]
        fig = go.Figure()
        for status in status_order:
            sub = score_df[score_df["status"] == status]["match_score"]
            if sub.empty:
                continue
            fig.add_trace(go.Box(
                y=sub,
                name=status.capitalize(),
                marker_color=STATUS_COLOR.get(status, _DIM),
                line_color=STATUS_COLOR.get(status, _DIM),
                fillcolor=STATUS_COLOR.get(status, _DIM) + "33",
                boxmean=True,
            ))
        fig.update_layout(
            **_PLOTLY_LAYOUT,
            title=dict(text="Match Score by Outcome", font=dict(color=_TEXT, size=13)),
            yaxis_title="Match Score (%)",
            showlegend=False,
        )
        st.plotly_chart(fig, use_container_width=True)

    # ── Resume version performance ──
    st.markdown('<div class="section-header">Resume Version Performance</div>', unsafe_allow_html=True)
    if "resume_used" in df.columns and df["resume_used"].notna().any():
        positives = {"interviewing", "offer"}
        resume_df = df[df["resume_used"].notna() & df["status"].isin(
            ["applied", "interviewing", "offer", "rejected", "ghosted"]
        )].copy()

        if resume_df.empty:
            st.markdown('<div class="empty-state">Apply with a resume_used tag to compare versions.</div>', unsafe_allow_html=True)
        else:
            rv = (
                resume_df.groupby("resume_used")
                .agg(
                    apps=("id", "count"),
                    responses=("status", lambda x: x.isin(positives).sum()),
                    avg_score=("match_score", "mean"),
                )
                .reset_index()
            )
            rv["response_rate"] = rv["responses"] / rv["apps"]
            rv = rv.sort_values("response_rate", ascending=False)

            c3, c4 = st.columns(2)
            with c3:
                fig = go.Figure(go.Bar(
                    x=rv["resume_used"],
                    y=rv["response_rate"] * 100,
                    marker_color=_ACCENT,
                    text=(rv["response_rate"] * 100).round(1).astype(str) + "%",
                    textposition="outside",
                    textfont=dict(color=_TEXT),
                ))
                fig.update_layout(
                    **_PLOTLY_LAYOUT,
                    title=dict(text="Interview/Offer Rate by Resume Version", font=dict(color=_TEXT, size=13)),
                    yaxis_title="Response Rate (%)",
                    xaxis_title="Resume",
                    showlegend=False,
                )
                st.plotly_chart(fig, use_container_width=True)

            with c4:
                rv_score = rv[rv["avg_score"].notna()]
                if rv_score.empty:
                    st.markdown('<div class="empty-state">No match scores for resume versions.</div>', unsafe_allow_html=True)
                else:
                    fig = go.Figure(go.Bar(
                        x=rv_score["resume_used"],
                        y=rv_score["avg_score"],
                        marker_color="#a371f7",
                        text=rv_score["avg_score"].round(0).astype(int).astype(str) + "%",
                        textposition="outside",
                        textfont=dict(color=_TEXT),
                    ))
                    fig.update_layout(
                        **_PLOTLY_LAYOUT,
                        title=dict(text="Avg Match Score by Resume Version", font=dict(color=_TEXT, size=13)),
                        yaxis_title="Avg Match Score (%)",
                        xaxis_title="Resume",
                        showlegend=False,
                    )
                    st.plotly_chart(fig, use_container_width=True)
    else:
        st.markdown('<div class="empty-state">Tag applications with resume_used to compare resume versions.</div>', unsafe_allow_html=True)

    # ── Cover letter impact ──
    st.markdown('<div class="section-header">Cover Letter Impact</div>', unsafe_allow_html=True)
    if "cover_letter_used" in df.columns:
        cl_df = df[df["status"].isin(["applied", "interviewing", "offer", "rejected", "ghosted"])].copy()
        if cl_df.empty:
            st.markdown('<div class="empty-state">No applied jobs to measure cover letter impact.</div>', unsafe_allow_html=True)
        else:
            positives = {"interviewing", "offer"}
            cl_df["has_cl"] = cl_df["cover_letter_used"].fillna(0).astype(bool)
            cl_summary = (
                cl_df.groupby("has_cl")
                .agg(
                    apps=("id", "count"),
                    responses=("status", lambda x: x.isin(positives).sum()),
                )
                .reset_index()
            )
            cl_summary["response_rate"] = cl_summary["responses"] / cl_summary["apps"]
            cl_summary["label"] = cl_summary["has_cl"].map({True: "With Cover Letter", False: "Without Cover Letter"})

            fig = go.Figure(go.Bar(
                x=cl_summary["label"],
                y=cl_summary["response_rate"] * 100,
                marker_color=["#3fb950" if v else _DIM for v in cl_summary["has_cl"]],
                text=(cl_summary["response_rate"] * 100).round(1).astype(str) + "%",
                textposition="outside",
                textfont=dict(color=_TEXT),
            ))
            fig.update_layout(
                **_PLOTLY_LAYOUT,
                title=dict(text="Interview/Offer Rate: With vs Without Cover Letter", font=dict(color=_TEXT, size=13)),
                yaxis_title="Response Rate (%)",
                showlegend=False,
            )
            st.plotly_chart(fig, use_container_width=True)


# ─── Main ─────────────────────────────────────────────────────────────────────

def main() -> None:
    st.markdown(
        "<h1 style='font-family:monospace;font-size:1.6rem;margin-bottom:0'>📊 Job Search Analytics</h1>",
        unsafe_allow_html=True,
    )
    st.markdown(
        f"<p style='color:{_DIM};font-size:0.82rem;margin-top:2px;font-family:monospace'>"
        "Insights from your tracked applications — refreshes every 60 s</p>",
        unsafe_allow_html=True,
    )

    df = load_data()

    if df.empty:
        st.markdown(
            '<div class="empty-state" style="margin-top:40px">'
            "<b>No jobs found in jobs.db.</b><br><br>"
            "Start tracking applications in <code>dashboard.py</code> or run the job scraper "
            "(<code>python scraper/scheduler.py</code>) to populate your database."
            "</div>",
            unsafe_allow_html=True,
        )
        return

    # ── Sidebar filters ──
    with st.sidebar:
        st.markdown(f"<h3 style='color:{_TEXT};font-family:monospace'>Filters</h3>", unsafe_allow_html=True)

        status_opts = ["All"] + sorted(df["status"].dropna().unique().tolist())
        sel_status = st.multiselect("Status", status_opts[1:], default=[])

        source_opts = sorted(df["source"].dropna().unique().tolist()) if "source" in df.columns else []
        sel_source = st.multiselect("Source", source_opts, default=[])

        remote_opts = sorted(df["remote_type"].dropna().unique().tolist()) if "remote_type" in df.columns else []
        sel_remote = st.multiselect("Work Type", remote_opts, default=[])

        date_col = "date_applied" if "date_applied" in df.columns else "last_updated"
        valid_dates = df[date_col].dropna()
        if not valid_dates.empty:
            min_d = valid_dates.min().date()
            max_d = valid_dates.max().date()
            date_range = st.date_input("Date Range", value=(min_d, max_d), min_value=min_d, max_value=max_d)
        else:
            date_range = None

        st.markdown("---")
        st.markdown(f"<span style='color:{_DIM};font-size:0.75rem'>{len(df)} total jobs in DB</span>", unsafe_allow_html=True)
        if st.button("Refresh Data", use_container_width=True):
            st.cache_data.clear()
            st.rerun()

    # Apply filters
    filtered = df.copy()
    if sel_status:
        filtered = filtered[filtered["status"].isin(sel_status)]
    if sel_source:
        filtered = filtered[filtered["source"].isin(sel_source)]
    if sel_remote:
        filtered = filtered[filtered["remote_type"].isin(sel_remote)]
    if date_range and len(date_range) == 2 and date_col in filtered.columns:
        start_d = pd.Timestamp(date_range[0])
        end_d   = pd.Timestamp(date_range[1]) + timedelta(days=1)
        filtered = filtered[
            (filtered[date_col] >= start_d) & (filtered[date_col] < end_d)
        ]

    if filtered.empty:
        st.warning("No jobs match the current filters.")
        return

    if len(filtered) < len(df):
        st.markdown(
            f"<p style='color:{_DIM};font-size:0.78rem;font-family:monospace'>"
            f"Showing {len(filtered)} / {len(df)} jobs</p>",
            unsafe_allow_html=True,
        )

    # ── Tab navigation ──
    tab1, tab2, tab3, tab4, tab5 = st.tabs([
        "Search Overview",
        "Skill Demand",
        "Salary Insights",
        "Market Map",
        "Resume Performance",
    ])

    with tab1:
        view_overview(filtered)
    with tab2:
        view_skills(filtered)
    with tab3:
        view_salary(filtered)
    with tab4:
        view_market(filtered)
    with tab5:
        view_resume(filtered)

    # ── Footer ──
    st.markdown(
        "<div class='analytics-footer'>"
        "Built by Ayush Srivastava | "
        "<a href='https://github.com/sayush2807' style='color:#388bfd;text-decoration:none'>"
        "github.com/sayush2807</a>"
        "</div>",
        unsafe_allow_html=True,
    )


if __name__ == "__main__":
    main()
