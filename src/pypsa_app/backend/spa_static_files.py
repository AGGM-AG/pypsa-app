"""Static files handler for the single-page frontend.

Serves the built frontend from ``static/app`` and falls back to ``index.html``
for client-side routes.
"""

from http import HTTPStatus

from fastapi.staticfiles import StaticFiles
from starlette.exceptions import HTTPException
from starlette.responses import Response
from starlette.types import Scope


class SPAStaticFiles(StaticFiles):
    """Static files for a single-page application."""

    async def get_response(self, path: str, scope: Scope) -> Response:
        try:
            return await super().get_response(path, scope)
        except HTTPException as ex:
            if ex.status_code == HTTPStatus.NOT_FOUND:
                # Return index.html for all non-file routes so the client-side
                # router handles them
                return await super().get_response("index.html", scope)
            raise
