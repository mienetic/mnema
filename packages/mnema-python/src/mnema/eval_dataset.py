"""Seed dataset + Q&A pairs for the Mnema recall evaluation.

This module provides a curated set of memories and natural-language queries
designed to exercise Mnema's semantic + hybrid search across realistic
agent-memory scenarios (preferences, decisions, configs, relationships).

Used by ``scripts/eval_recall.py`` and the ``mnema eval`` CLI.
"""

from __future__ import annotations

# Each seed memory: (text, scope, tags, importance)
SEED_MEMORIES: list[tuple[str, str, list[str], int]] = [
    # --- preferences ---
    ("Alice prefers Earl Grey tea and avoids coffee after 2pm.", "user:alice", ["preference", "food"], 7),
    ("Alice's code editor is Neovim with a gruvbox theme.", "user:alice", ["preference", "editor"], 5),
    ("Bob uses a Dvorak keyboard layout.", "user:bob", ["preference", "hardware"], 6),
    ("The team prefers tabs over spaces for indentation.", "team:eng", ["preference", "style"], 4),
    ("Charlie likes dark mode everywhere, including terminals.", "user:charlie", ["preference", "ui"], 5),

    # --- decisions ---
    ("We decided to use Postgres instead of MySQL for the main database.", "project:api", ["decision", "database"], 9),
    ("The team chose Fly.io over Railway for deployment because of region coverage.", "project:web", ["decision", "deploy"], 8),
    ("We standardized on Python 3.11 for all new services.", "team:eng", ["decision", "python"], 7),
    ("Authentication will use OAuth 2.1 with PKCE, not API keys.", "project:auth", ["decision", "security"], 9),
    ("Logs go to Loki, not Elasticsearch — cost was the deciding factor.", "team:eng", ["decision", "observability"], 6),

    # --- configs / infra ---
    ("The production database URL is in AWS Secrets Manager under prod/db/main.", "project:api", ["config", "secret", "aws"], 10),
    ("The staging environment runs on Fly.io in the sin region.", "project:web", ["config", "deploy", "staging"], 8),
    ("Redis is used for caching and the connection string is in redis.conf.", "project:api", ["config", "cache"], 7),
    ("The CI pipeline runs on GitHub Actions with Python 3.10–3.13 matrix.", "team:eng", ["config", "ci"], 6),
    ("Feature flags are managed by Unleash, hosted at flags.internal:4242.", "project:web", ["config", "flags"], 7),

    # --- people / relationships ---
    ("Bob is the tech lead for the infra team and owns the Kubernetes cluster.", "team:org", ["person", "role"], 8),
    ("Alice reports to Diana, who is the engineering manager.", "team:org", ["person", "role"], 6),
    ("Charlie handles all frontend bug reports and triages them on Mondays.", "team:org", ["person", "role"], 5),
    ("Diana's timezone is Europe/Lisbon (WET, UTC+0).", "user:diana", ["person", "timezone"], 6),
    ("Bob's working hours are 09:00–17:00 Asia/Bangkok (ICT).", "user:bob", ["person", "timezone", "schedule"], 7),

    # --- project facts ---
    ("The auth service exposes /v1/login and /v1/refresh endpoints.", "project:auth", ["api", "endpoint"], 7),
    ("The rate limit is 100 requests per minute per API key.", "project:api", ["config", "limit"], 8),
    ("Database migrations are handled by Alembic and run before each deploy.", "project:api", ["tool", "migration"], 6),
    ("The frontend bundle is built with Vite and outputs to dist/.", "project:web", ["tool", "build"], 5),
    ("Error tracking is done with Sentry, DSN is in the SENTRY_DSN env var.", "project:web", ["config", "observability"], 8),

    # --- misc / edge cases ---
    ("The API key for the payment provider is stored in Stripe under pk_live_x22.", "project:billing", ["config", "secret", "stripe"], 10),
    ("We had an incident on 2026-06-14 where Redis OOM caused 5xx errors for 12 minutes.", "team:eng", ["incident", "redis"], 7),
    ("The legal review for the privacy policy is due on 2026-08-01.", "project:legal", ["deadline", "legal"], 8),
    ("Customer feedback shows the most-requested feature is CSV export.", "project:product", ["feedback", "feature"], 5),
    ("The on-call rotation is Bob, Alice, Charlie, repeating weekly.", "team:eng", ["schedule", "oncall"], 6),
]

# Each Q&A pair: (query, expected_substring, tags_to_boost)
# "expected_substring" must appear (case-insensitive) in the top-k result's text.
EVAL_QUESTIONS: list[tuple[str, str, list[str]]] = [
    # --- preferences ---
    ("What kind of tea does Alice drink?", "earl grey", []),
    ("Does Alice drink coffee in the evening?", "coffee", []),
    ("What editor does Alice use?", "neovim", []),
    ("What keyboard layout does Bob use?", "dvorak", []),
    ("Does the team use tabs or spaces?", "tabs", []),

    # --- decisions ---
    ("Which database did we pick?", "postgres", ["decision"]),
    ("Where do we deploy and why?", "fly.io", ["decision"]),
    ("What Python version is standard?", "3.11", ["decision"]),
    ("How does authentication work?", "oauth", ["decision", "security"]),
    ("Where do logs go?", "loki", ["decision"]),

    # --- configs ---
    ("Where is the production database URL stored?", "secrets manager", ["config"]),
    ("What region is staging in?", "sin", ["config"]),
    ("What is the rate limit?", "100", ["config"]),
    ("How are migrations run?", "alembic", []),
    ("Where is the Sentry DSN?", "sentry_dsn", ["config"]),

    # --- people ---
    ("Who owns the Kubernetes cluster?", "bob", ["person"]),
    ("Who does Alice report to?", "diana", ["person"]),
    ("What is Diana's timezone?", "lisbon", ["timezone"]),
    ("When does Bob work?", "bangkok", ["timezone"]),

    # --- misc ---
    ("Where is the Stripe key?", "stripe", ["secret"]),
    ("What happened on June 14th?", "redis", ["incident"]),
    ("When is the legal review due?", "2026-08-01", ["deadline"]),
    ("What feature do customers want most?", "csv export", ["feedback"]),
    ("Who is on the on-call rotation?", "bob", ["schedule"]),
]

__all__ = ["EVAL_QUESTIONS", "SEED_MEMORIES"]
