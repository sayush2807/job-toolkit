"""
parser.py — PDF text extraction and keyword extraction for the Resume Matcher.
"""

import re
import pdfplumber
from typing import Dict, Set


# ─── Keyword Dictionaries ─────────────────────────────────────────────────────

PROGRAMMING_LANGUAGES: Set[str] = {
    "python", "java", "javascript", "typescript", "c", "c++", "csharp", "c#",
    "go", "golang", "rust", "r", "sql", "scala", "kotlin", "swift", "php",
    "ruby", "perl", "matlab", "julia", "bash", "shell", "powershell", "dart",
    "lua", "haskell", "elixir", "clojure", "groovy", "assembly", "cobol",
    "fortran", "erlang", "zig", "nim", "crystal", "ocaml", "fsharp", "f#",
    "racket", "prolog", "vba", "apex", "solidity", "move", "abap",
}

FRAMEWORKS_LIBRARIES: Set[str] = {
    # Frontend
    "react", "angular", "vue", "svelte", "nextjs", "nuxtjs", "gatsby",
    "redux", "mobx", "graphql", "jquery", "bootstrap", "tailwind", "sass",
    "less", "webpack", "vite", "parcel", "rollup", "babel", "electron",
    # Backend
    "django", "flask", "fastapi", "spring", "springboot", "express", "nestjs",
    "rails", "laravel", "symfony", "gin", "fiber", "actix", "axum",
    "phoenix", "ktor", "quarkus", "micronaut", "dotnet", "asp.net", "blazor",
    # ML / AI
    "tensorflow", "pytorch", "keras", "sklearn", "scikit-learn", "pandas",
    "numpy", "scipy", "matplotlib", "seaborn", "plotly", "bokeh",
    "huggingface", "transformers", "langchain", "llamaindex", "openai",
    "ray", "dask", "polars", "xgboost", "lightgbm", "catboost", "mlflow",
    "kubeflow", "bentoml", "fastai", "jax", "flax", "spacy", "nltk",
    "gensim", "opencv", "albumentations", "timm", "pyspark",
    # Data pipelines
    "spark", "flink", "kafka", "airflow", "luigi", "prefect", "dagster",
    "dbt", "great expectations",
    # Testing
    "jest", "pytest", "junit", "selenium", "cypress", "playwright", "mocha",
    "chai", "enzyme", "testing-library",
    # Mobile
    "react native", "flutter", "ionic", "xamarin", "swiftui",
    # REST / API
    "rest", "grpc", "graphql", "websocket", "oauth", "openapi", "swagger",
}

TOOLS_PLATFORMS: Set[str] = {
    # Containers / Infra
    "docker", "kubernetes", "k8s", "helm", "terraform", "ansible", "puppet",
    "chef", "vagrant", "nomad", "consul", "vault",
    # CI/CD
    "jenkins", "circleci", "travisci", "github actions", "gitlab ci",
    "argocd", "spinnaker", "flux",
    # Cloud
    "aws", "azure", "gcp", "heroku", "vercel", "netlify", "digitalocean",
    "cloudflare", "linode", "oracle cloud", "ibm cloud", "lambda",
    "ec2", "s3", "rds", "eks", "ecs",
    # Databases
    "mysql", "postgresql", "postgres", "mongodb", "redis", "elasticsearch",
    "cassandra", "dynamodb", "firebase", "supabase", "neo4j", "influxdb",
    "clickhouse", "cockroachdb", "sqlite", "mariadb", "oracle", "mssql",
    "sql server", "hive", "hbase",
    # Data warehousing / BI
    "snowflake", "databricks", "bigquery", "redshift", "synapse", "looker",
    "tableau", "powerbi", "metabase", "superset", "mode", "qlik",
    # Message queues
    "rabbitmq", "nats", "pulsar", "sqs", "pubsub", "eventbridge",
    # Monitoring / Observability
    "prometheus", "grafana", "datadog", "newrelic", "splunk",
    "elk", "loki", "jaeger", "zipkin",
    # VCS / Collab
    "git", "github", "gitlab", "bitbucket", "jira", "confluence", "notion",
    "figma", "sketch", "storybook",
    # AI / ML tools
    "sagemaker", "vertex ai", "azure ml", "wandb", "neptune", "comet",
    "triton", "onnx", "mlflow",
    # Dev tools
    "linux", "unix", "ubuntu", "centos", "debian", "macos",
    "nginx", "apache", "caddy", "traefik", "istio", "envoy",
    "postman", "insomnia", "vscode", "intellij", "pycharm", "vim", "neovim",
}

SOFT_SKILLS: Set[str] = {
    "communication", "leadership", "teamwork", "collaboration",
    "problem solving", "problem-solving", "analytical", "creative",
    "adaptable", "organized", "detail oriented", "detail-oriented",
    "self-motivated", "proactive", "innovative", "strategic",
    "mentoring", "coaching", "presentation", "negotiation",
    "time management", "project management", "agile", "scrum", "kanban",
    "critical thinking", "decision making", "interpersonal",
    "cross-functional", "stakeholder management", "customer-facing",
    "entrepreneurial", "ownership", "initiative", "fast learner",
    "multitasking", "written communication", "verbal communication",
}


# ─── Normalisation helpers ────────────────────────────────────────────────────

def _normalise(text: str) -> str:
    """Lower-case and canonicalise common tech-name variations."""
    t = text.lower()
    t = re.sub(r"\bnode\.js\b",      "nodejs",       t)
    t = re.sub(r"\bnext\.js\b",      "nextjs",       t)
    t = re.sub(r"\bnuxt\.js\b",      "nuxtjs",       t)
    t = re.sub(r"\bspring\s+boot\b", "springboot",   t)
    t = re.sub(r"\bscikit[\s\-]learn\b", "scikit-learn", t)
    t = re.sub(r"\bc\+\+\b",         "c++",          t)
    t = re.sub(r"\bc#\b",            "csharp",       t)
    t = re.sub(r"\b\.net\b",         "dotnet",       t)
    t = re.sub(r"\basp\.net\b",      "asp.net",      t)
    t = re.sub(r"\bk8s\b",           "kubernetes",   t)
    t = re.sub(r"\bml\b",            " ",            t)  # too ambiguous alone
    return t


# ─── PDF extraction ───────────────────────────────────────────────────────────

def extract_text_from_pdf(pdf_file) -> str:
    """
    Extract plain text from a PDF file-like object using pdfplumber.
    Returns an empty string (with a warning prefix) if extraction fails.
    """
    pages = []
    try:
        with pdfplumber.open(pdf_file) as pdf:
            for page in pdf.pages:
                page_text = page.extract_text()
                if page_text:
                    pages.append(page_text)
    except Exception as exc:
        return f"[PDF_EXTRACTION_ERROR: {exc}]"
    return "\n".join(pages)


# ─── Keyword extraction ───────────────────────────────────────────────────────

def extract_keywords(text: str) -> Dict[str, Set[str]]:
    """
    Extract categorised keywords from text.

    Returns a dict with keys:
        languages, frameworks, tools, soft_skills, experience
    """
    normalised = _normalise(text)

    # Build unigram token set
    token_list = re.findall(r"\b[\w\+\#\-\.]+\b", normalised)
    tokens: Set[str] = set(token_list)

    # Build bigram token set for multi-word terms
    bigrams: Set[str] = {
        f"{token_list[i]} {token_list[i + 1]}"
        for i in range(len(token_list) - 1)
    }

    all_tokens = tokens | bigrams

    def _find(keyword_set: Set[str]) -> Set[str]:
        return {kw for kw in keyword_set if kw in all_tokens}

    languages  = _find(PROGRAMMING_LANGUAGES)
    frameworks = _find(FRAMEWORKS_LIBRARIES)
    tools      = _find(TOOLS_PLATFORMS)
    soft       = _find(SOFT_SKILLS)

    # Extract experience mentions: "3+ years", "5 years of experience", etc.
    exp_hits = re.findall(
        r"\d+\+?\s*(?:to\s*\d+\s*)?(?:years?|yrs?)(?:\s+of\s+(?:experience|exp))?",
        normalised,
    )

    return {
        "languages":  languages,
        "frameworks": frameworks,
        "tools":      tools,
        "soft_skills": soft,
        "experience": set(exp_hits),
    }


def get_all_keywords(categorised: Dict[str, Set[str]]) -> Set[str]:
    """Flatten all keyword categories except 'experience' into a single set."""
    result: Set[str] = set()
    for cat, kws in categorised.items():
        if cat != "experience":
            result.update(kws)
    return result
