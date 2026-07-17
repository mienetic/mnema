"""Auto Dream — background memory consolidation.

Just like the brain consolidates memories during sleep, Mnema's "dream cycle"
periodically tidies the memory store in the background:

1. **Forget** memories whose decay score has fallen below a threshold.
2. **Plan summarization** for cluttered scopes (the plan is logged; the
   calling agent is expected to execute it via ``mnema_summarize``).

The dreamer is opt-in (``MNEMA_DREAM_ENABLED=true``) and only runs while the
MCP server is alive. It sleeps between cycles so it costs nothing when idle.

Usage::

    from mnema.dream import Dreamer
    dreamer = Dreamer(service, config)
    await dreamer.start()    # spawns a background task
    ...
    await dreamer.stop()     # cancels the task

Or run a single cycle synchronously (used by ``mnema dream``)::

    from mnema.dream import dream_once
    report = await dream_once(service, config)
"""

from __future__ import annotations

import asyncio
import logging
import time
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from mnema.config import MnemaConfig
    from mnema.service import MemoryService

logger = logging.getLogger("mnema.dream")


@dataclass
class DreamReport:
    """Result of one dream cycle."""

    cycled_at: float = field(default_factory=time.time)
    scopes_summarized: list[str] = field(default_factory=list)
    memories_forgotten: int = 0
    memory_count_before: int = 0
    memory_count_after: int = 0
    elapsed_seconds: float = 0.0
    plans: list[str] = field(default_factory=list)  # one summary prompt per scope

    def summary(self) -> str:
        return (
            f"dream @ {time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(self.cycled_at))}: "
            f"forgot {self.memories_forgotten} low-value memories "
            f"({self.memory_count_before}→{self.memory_count_after}), "
            f"summarized {len(self.scopes_summarized)} scope(s) "
            f"in {self.elapsed_seconds:.2f}s"
        )


async def dream_once(
    service: MemoryService,
    config: MnemaConfig,
) -> DreamReport:
    """Run a single dream cycle: decay-forget + summarize-plan.

    This is the building block used by both the background scheduler and the
    ``mnema dream`` CLI command.

    Args:
        service: A MemoryService instance.
        config: The resolved MnemaConfig (dream_* fields are read).
    """
    from mnema.summarize import build_summary_prompt

    report = DreamReport()
    start = time.time()
    report.memory_count_before = await service.backend.count()

    # 1. Decay sweep — forget low-value memories.
    threshold = config.dream_decay_threshold
    candidates = await service.apply_decay(threshold=threshold, dry_run=False)
    report.memories_forgotten = len(candidates)
    if candidates:
        logger.info("dream: forgot %d memories (threshold=%.3f)", len(candidates), threshold)

    # 2. Summarization planning — for each requested scope (or all).
    if config.dream_summarize_scopes:
        target_scopes = list(config.dream_summarize_scopes)
    else:
        target_scopes = list((await service.list_scopes()).keys())
    for scope in target_scopes:
        try:
            plan = await service.summarize(scope=scope)
            # Only record plans that would actually condense (>1 cluster).
            if len(plan.clusters) > 1 or plan.total_memories > 5:
                prompt = build_summary_prompt(plan)
                report.plans.append(prompt)
                report.scopes_summarized.append(scope)
                logger.info(
                    "dream: scope %s has %d memories in %d clusters — summarization planned",
                    scope,
                    plan.total_memories,
                    len(plan.clusters),
                )
        except Exception:
            # A bad scope shouldn't abort the whole dream cycle.
            logger.exception("dream: failed to plan summarization for scope %s", scope)

    report.memory_count_after = await service.backend.count()
    report.elapsed_seconds = time.time() - start
    return report


class Dreamer:
    """Background scheduler that runs :func:`dream_once` on an interval.

    The dreamer is deliberately conservative:

    * It only runs while the server is alive (not a system cron).
    * It sleeps for ``config.dream_interval_seconds`` between cycles.
    * Exceptions in a cycle are logged and swallowed — the next cycle runs
      on schedule regardless.
    """

    def __init__(self, service: MemoryService, config: MnemaConfig) -> None:
        self._service = service
        self._config = config
        self._task: asyncio.Task | None = None
        self._stop = asyncio.Event()
        self.last_report: DreamReport | None = None

    async def start(self) -> None:
        """Spawn the background dream loop. Safe to call once."""
        if self._task is not None:
            return
        self._stop.clear()
        self._task = asyncio.create_task(self._loop(), name="mnema-dreamer")
        logger.info(
            "Auto Dream started — interval=%ss, decay_threshold=%.3f",
            self._config.dream_interval_seconds,
            self._config.dream_decay_threshold,
        )

    async def stop(self) -> None:
        """Cancel the background loop and wait for it to finish."""
        if self._task is None:
            return
        self._stop.set()
        self._task.cancel()
        with __import__("contextlib").suppress(asyncio.CancelledError):
            await self._task
        self._task = None
        logger.info("Auto Dream stopped.")

    async def _loop(self) -> None:
        """Run dream cycles forever until :meth:`stop` is called."""
        # Run the first cycle soon after start (not immediately, to let the
        # server finish warming up), then on the configured interval.
        while not self._stop.is_set():
            try:
                await asyncio.wait_for(self._stop.wait(), timeout=self._config.dream_interval_seconds)
                return  # stop was set during the sleep
            except TimeoutError:
                pass  # interval elapsed — time to dream

            try:
                report = await dream_once(self._service, self._config)
                # Only record non-trivial cycles so an empty store doesn't
                # clobber a meaningful last_report.
                if report.memory_count_before > 0 or report.memories_forgotten > 0:
                    self.last_report = report
                logger.info(report.summary())
            except Exception:
                logger.exception("dream cycle failed — will retry next interval")


__all__ = ["DreamReport", "Dreamer", "dream_once"]
