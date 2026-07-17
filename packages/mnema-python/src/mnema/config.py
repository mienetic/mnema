"""Environment-driven configuration for Mnema.

All knobs are configurable through environment variables (or a ``.env`` file)
so the MCP server can be tuned without code changes. The same
:class:`MnemaConfig` instance is used by the server, the SDK, and the CLI.
"""

from __future__ import annotations

from typing import Literal

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from mnema.errors import ConfigError

BackendName = Literal["chroma", "qdrant", "sqlite_vec"]
EmbeddingName = Literal["local", "openai", "ollama"]
TransportName = Literal["stdio", "http"]


class MnemaConfig(BaseSettings):
    """Resolved configuration for a Mnema instance.

    Every field has a sensible default so a fresh checkout runs with zero
    configuration::

        config = MnemaConfig()          # read from env / .env
        service = MemoryService(config)
    """

    model_config = SettingsConfigDict(
        env_prefix="MNEMA_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    # --- Backend -----------------------------------------------------------
    backend: BackendName = Field(
        default="chroma",
        description="Vector backend: 'chroma' (default, embedded), 'qdrant', 'sqlite_vec'",
    )
    backend_path: str = Field(
        default=".mnema/data",
        description="Local persistent path, or a remote URL for server backends",
    )
    backend_collection: str = Field(
        default="memories",
        description="Collection / table name inside the backend",
    )

    # --- Embedding ---------------------------------------------------------
    embedding: EmbeddingName = Field(
        default="local",
        description="Embedding provider: 'local' (sentence-transformers, offline) or 'openai'",
    )
    embedding_model: str = Field(
        default="all-MiniLM-L6-v2",
        description="Model name for the chosen provider (local model or OpenAI model id)",
    )
    embedding_dim: int | None = Field(
        default=None,
        description=(
            "Vector dimensionality override. Auto-detected when None. "
            "Set explicitly if you pin a specific OpenAI dimensions param."
        ),
    )
    openai_api_key: str | None = Field(
        default=None,
        description="OpenAI API key (only required when embedding='openai')",
    )
    openai_base_url: str | None = Field(
        default=None,
        description="Optional OpenAI-compatible base URL (Azure, local proxies, etc.)",
    )
    ollama_url: str = Field(
        default="http://localhost:11434",
        description="Ollama server URL (only used when embedding='ollama')",
    )
    # --- Behavior ----------------------------------------------------------
    default_scope: str = Field(
        default="global",
        description="Scope used when a tool omits the scope argument",
    )
    decay_half_life_days: float = Field(
        default=30.0,
        description="Half-life (in days) for the recency decay component",
        gt=0,
    )
    decay_floor: float = Field(
        default=0.05,
        description="Minimum decay score (so old memories are never fully zeroed)",
        ge=0,
        le=1,
    )
    vector_weight: float = Field(
        default=0.7,
        description="Weight of vector similarity in the hybrid score",
        ge=0,
        le=1,
    )
    keyword_weight: float = Field(
        default=0.2,
        description="Weight of tag/keyword overlap in the hybrid score",
        ge=0,
        le=1,
    )
    decay_weight: float = Field(
        default=0.1,
        description="Weight of the decay component in the hybrid score",
        ge=0,
        le=1,
    )

    # --- Transport ---------------------------------------------------------
    transport: TransportName = Field(
        default="stdio",
        description="MCP transport: 'stdio' (default) or 'http'",
    )
    http_host: str = Field(default="127.0.0.1", description="Bind host for HTTP transport")
    http_port: int = Field(default=8000, description="Bind port for HTTP transport")

    # --- Logging / diagnostics -------------------------------------------
    log_level: str = Field(
        default="WARNING",
        description=(
            "Logging level: DEBUG, INFO, WARNING (default), ERROR. "
            "Set to DEBUG to see backend queries, embed latency, search "
            "scores, etc. (useful when reporting bugs)."
        ),
    )

    # --- Auto Dream (background memory consolidation) --------------------
    dream_enabled: bool = Field(
        default=False,
        description=(
            "Enable the Auto Dream background scheduler. When True, Mnema "
            "periodically summarizes and forgets low-value memories while "
            "the server is running — like a brain consolidating memories "
            "during sleep."
        ),
    )
    dream_interval_seconds: float = Field(
        default=3600.0,
        description="Seconds between Auto Dream cycles (default: 1 hour).",
        gt=0,
    )
    dream_decay_threshold: float = Field(
        default=0.05,
        description="Decay score at or below which a memory is forgotten during dreaming.",
        ge=0,
        le=1,
    )
    dream_summarize_scopes: list[str] = Field(
        default_factory=list,
        description=(
            "Scopes to summarize during dreaming. Empty = all scopes. "
            "Summarization only plans — the calling agent must execute."
        ),
    )

    @field_validator("vector_weight", "keyword_weight", "decay_weight")
    @classmethod
    def _check_weights(cls, v: float) -> float:
        # Individual range is checked by Field(ge=0, le=1); the sum is checked
        # lazily in validate() so all three can be set together.
        return v

    def validate_runtime(self) -> None:
        """Validate cross-field constraints that pydantic can't express.

        Raises:
            ConfigError: if the score weights don't sum to ~1.0.
        """
        total = self.vector_weight + self.keyword_weight + self.decay_weight
        if abs(total - 1.0) > 0.001:
            raise ConfigError(
                f"vector_weight + keyword_weight + decay_weight must sum to 1.0 "
                f"(got {total:.3f}: {self.vector_weight=} "
                f"{self.keyword_weight=} {self.decay_weight=})."
            )
        if self.embedding == "openai" and not self.openai_api_key:
            raise ConfigError(
                "embedding='openai' requires MNEMA_OPENAI_API_KEY "
                "(or OPENAI_API_KEY) to be set."
            )


def load_config(**overrides: object) -> MnemaConfig:
    """Load configuration from env / .env, applying explicit overrides.

    Validates the result and returns a ready-to-use config.
    """
    cfg = MnemaConfig(**overrides)  # type: ignore[arg-type]
    cfg.validate_runtime()
    return cfg


__all__ = ["BackendName", "EmbeddingName", "MnemaConfig", "TransportName", "load_config"]
