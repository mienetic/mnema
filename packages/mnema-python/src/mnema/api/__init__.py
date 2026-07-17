"""Mnema REST API package.

A thin FastAPI layer over :class:`~mnema.service.MemoryService`. Importing this
package pulls in FastAPI, so it is only imported on demand (by ``mnema serve``)
— ``import mnema`` stays free of the optional ``api`` extra.

Install the dependency with the ``api`` extra::

    uv pip install 'mnema-mcp[api]'

Then serve::

    mnema serve --port 8000
"""

from __future__ import annotations

from mnema.api.app import create_app

__all__ = ["create_app"]
