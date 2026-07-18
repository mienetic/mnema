# Mnema — Long-term Memory for AI

> 🧠 Give your AI agents persistent, searchable memory. Solve the context-window problem with **MCP × Vector DB**.

This is the Python package directory. The full project README lives at the
repo root: **[../../README.md](../../README.md)**.

## Install

```bash
curl -fsSL https://raw.githubusercontent.com/mienetic/mnema/main/scripts/install.sh | bash
```

See the [full README](../../README.md) for setup, configuration, and
[GETTING_STARTED.md](../../GETTING_STARTED.md) for a Thai step-by-step guide.

## Quick SDK example

```python
import asyncio
from mnema.sdk import MemoryClient

async def main():
    async with MemoryClient() as client:
        await client.remember("Alice likes Earl Grey tea", tags=["preferences"])
        hits = await client.search("what does Alice drink?")
        print(hits.results[0].memory.text)

asyncio.run(main())
```

License: MIT.

<!--
mcp-name: io.github.mienetic/mnema
This marker is the MCP Registry's PyPI ownership-verification token (see
https://github.com/modelcontextprotocol/registry/blob/main/docs/modelcontextprotocol-io/package-types.mdx#pypi-packages).
It has no effect until this package is published to PyPI under the identifier
`mnema-mcp` — see ../../README.md#-mcp-registry for the full submission plan.
-->

