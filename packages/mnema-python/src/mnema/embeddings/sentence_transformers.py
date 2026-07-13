"""Local offline embedding provider backed by ``sentence-transformers``.

Loads a small model (default ``all-MiniLM-L6-v2``, 384-d) once and reuses it
for every embed call. The model is downloaded on first use and cached under
``~/.cache/huggingface`` (or ``HF_HOME``).

Install with::

    curl -fsSL https://raw.githubusercontent.com/mienetic/mnema/main/scripts/install.sh \\
      | MNEMA_EXTRAS='chroma,local' bash
"""

from __future__ import annotations

from collections.abc import Sequence

import anyio

from mnema.config import MnemaConfig
from mnema.embeddings.base import EmbeddingProvider
from mnema.errors import BackendInitError

# Known dims for popular models so we can avoid loading the model just to
# discover the dimensionality (useful for backend schema setup).
_KNOWN_DIMS: dict[str, int] = {
    "all-MiniLM-L6-v2": 384,
    "all-MiniLM-L12-v2": 384,
    "bge-small-en-v1.5": 384,
    "bge-base-en-v1.5": 768,
    "bge-small-zh-v1.5": 512,
    "paraphrase-multilingual-MiniLM-L12-v2": 384,
}


class SentenceTransformersProvider(EmbeddingProvider):
    """Offline embedding provider."""

    name = "local"

    def __init__(self, config: MnemaConfig) -> None:
        try:
            from sentence_transformers import SentenceTransformer
        except ImportError as exc:  # pragma: no cover - guarded by factory
            raise BackendInitError(
                "sentence-transformers is not installed. Reinstall Mnema with "
                "the 'local' extra:\n"
                "    curl -fsSL https://raw.githubusercontent.com/mienetic/mnema/main/scripts/install.sh "
                "| MNEMA_EXTRAS='chroma,local' bash"
            ) from exc

        self._model_name = config.embedding_model or "all-MiniLM-L6-v2"
        try:
            self._model = SentenceTransformer(self._model_name)
        except Exception as exc:
            raise BackendInitError(
                f"Failed to load sentence-transformers model "
                f"{self._model_name!r}: {exc}"
            ) from exc
        # get_sentence_embedding_dimension() was renamed in newer versions;
        # fall back gracefully to support both old and new releases.
        get_dim = getattr(
            self._model, "get_embedding_dimension", None
        ) or self._model.get_sentence_embedding_dimension
        self.dim = int(config.embedding_dim or get_dim())
        self._name = f"local:{self._model_name}"

    @property
    def display_name(self) -> str:
        return self._name

    async def embed(self, texts: Sequence[str]) -> list[list[float]]:
        texts = list(texts)

        def _do() -> list[list[float]]:
            vecs = self._model.encode(texts, normalize_embeddings=True)
            return [list(map(float, v)) for v in vecs]

        return await anyio.to_thread.run_sync(_do)


__all__ = ["SentenceTransformersProvider", "_KNOWN_DIMS"]
