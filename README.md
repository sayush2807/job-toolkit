# Job Toolkit — Resume Matcher & Job Search Analytics

A pair of Streamlit apps to help you match resumes against job descriptions and track patterns across your job search.

---

## Apps

### 🎯 Resume Matcher (`app.py`)
Upload one or more resume PDFs, paste a job description, and instantly see which resume fits best — with missing keywords, ATS simulation, and optional AI coaching.

### 📊 Analytics Dashboard (`analytics.py`)
Connect your tracked applications and explore trends — skill demand, salary ranges, application funnel, and resume version performance.

---

## Features

**Resume Matcher**
- Multi-resume comparison ranked by overall match score
- Scoring: 40% TF-IDF cosine similarity + 30% keyword match + 30% category coverage
- Keyword gap analysis broken down by languages, frameworks, tools, and soft skills
- Radar chart per resume showing category-level coverage
- **ATS Score Simulation** — exact keyword matching only (no synonyms), with a side-by-side comparison against the semantic score
  - Synonym detection: flags when resume uses `K8s` but JD says `Kubernetes`, `ML` vs `machine learning`, etc.
  - Per-keyword table: Found / Synonym / Missing with actionable suggestions
  - Score improvement projection: shows projected ATS score if all gaps are fixed
  - ATS formatting tips panel
- Optional AI coaching via Gemini 2.0 Flash (bring your own API key)

**Analytics Dashboard**
- Search Overview: KPI metrics, weekly application timeline, status funnel, source breakdown
- Skill Demand: top-25 skills bar chart, skill × role heatmap, skill share by source
- Salary Insights: distribution histogram, box plot by role, by remote type, by company size
- Market Map: industry breakdown, work-type donut, top companies, education requirements, experience distribution
- Resume Performance: match score distribution, score by outcome, response rate by resume version, cover letter impact
- Sidebar filters (status, source, work type, date range) applied across all views

---

## Screenshots

*Coming soon.*

---

## Tech Stack

| Layer | Library |
|---|---|
| UI | [Streamlit](https://streamlit.io) |
| PDF parsing | [pdfplumber](https://github.com/jsvine/pdfplumber) |
| Keyword matching | [scikit-learn](https://scikit-learn.org) TF-IDF |
| Charts | [Plotly](https://plotly.com/python/) |
| AI coaching | [Google Gemini 2.0 Flash](https://aistudio.google.com/) (optional) |
| Data | [pandas](https://pandas.pydata.org/) + SQLite |

---

## Setup

```bash
# 1. Clone the repo
git clone https://github.com/sayush2807/job-toolkit.git
cd job-toolkit

# 2. Install dependencies
pip install -r requirements.txt

# 3. Run the Resume Matcher
streamlit run app.py

# 4. Run the Analytics Dashboard (requires a jobs.db from tracked applications)
streamlit run analytics.py
```

The dark theme is pre-configured in `.streamlit/config.toml` and applies automatically.

---

## Optional: AI Coaching (Gemini)

The Resume Matcher includes an optional AI analysis powered by Gemini 2.0 Flash. To use it:

1. Get a free API key from [Google AI Studio](https://aistudio.google.com/)
2. Toggle **Enable AI Analysis** in the sidebar
3. Paste your key — it stays in the browser session only, never stored

---

## Project Structure

```
job-toolkit/
├── app.py              # Resume Matcher & ATS Simulator
├── analytics.py        # Job Search Analytics Dashboard
├── matcher.py          # TF-IDF + keyword scoring logic
├── parser.py           # PDF text extraction + keyword parsing
├── requirements.txt
└── .streamlit/
    └── config.toml     # Dark theme
```

---

## License

MIT — see [LICENSE](LICENSE) for details.

---

Built by [Ayush Srivastava](https://github.com/sayush2807)
