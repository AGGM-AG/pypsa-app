"""Routes of the view extensions (package-provided charts)"""

import logging
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from sqlalchemy.orm import Session

from pypsa_app.backend.api.deps import get_db, get_networks, require_permission
from pypsa_app.backend.api.routes.folders import get_folder
from pypsa_app.backend.api.utils.task_utils import queue_task
from pypsa_app.backend.models import Permission, User
from pypsa_app.backend.ratelimit import limiter
from pypsa_app.backend.schemas.task import TaskQueuedResponse
from pypsa_app.backend.schemas.view import (
    ViewGenerateRequest,
    ViewListResponse,
    ViewSelectionsRequest,
)
from pypsa_app.backend.services.views import get_extensions, get_view_specs
from pypsa_app.backend.settings import settings
from pypsa_app.backend.tasks import get_view_selections_task, get_view_task

router = APIRouter()
logger = logging.getLogger(__name__)


def _file_paths(
    db: Session, user: User, network_ids: list[str], folder_id: str | None
) -> list[str]:
    """Resolve the request's networks: a registered folder or explicit ids."""
    if folder_id:
        try:
            folder = get_folder(db, UUID(folder_id), user)
        except ValueError as exc:
            raise HTTPException(404, "Folder not found") from exc
        return [net.file_path for net in folder.networks]
    if not network_ids:
        raise HTTPException(422, "Pass network_ids or folder_id")
    return [net.file_path for net in get_networks(db, network_ids, user)]


@router.get("/", response_model=ViewListResponse)
def list_views(
    user: User = Depends(require_permission(Permission.NETWORKS_VIEW)),
) -> dict:
    """Catalogue of the views the installed extensions offer"""
    return {
        "data": list(get_view_specs().values()),
        "extensions": sorted(get_extensions()),
    }


@router.post("/generate", response_model=TaskQueuedResponse)
@limiter.limit(settings.ratelimit_expensive)
def generate_view(
    request: Request,
    response: Response,
    body: ViewGenerateRequest,
    db: Session = Depends(get_db),
    user: User = Depends(require_permission(Permission.NETWORKS_VIEW)),
) -> dict:
    """Render one view chart for a set of networks (one scenario, its years)"""
    if body.view not in get_view_specs():
        raise HTTPException(400, f"Unknown view '{body.view}'")
    file_paths = _file_paths(db, user, body.network_ids, body.folder_id)

    return queue_task(
        get_view_task,
        file_paths=file_paths,
        view=body.view,
        parameters=body.parameters,
    )


@router.post("/selections", response_model=TaskQueuedResponse)
@limiter.limit(settings.ratelimit_expensive)
def view_selections(
    request: Request,
    response: Response,
    body: ViewSelectionsRequest,
    db: Session = Depends(get_db),
    user: User = Depends(require_permission(Permission.NETWORKS_VIEW)),
) -> dict:
    """What a set of networks can be rendered for (locations, years, ...)"""
    if body.extension not in get_extensions():
        raise HTTPException(400, f"Unknown extension '{body.extension}'")
    file_paths = _file_paths(db, user, body.network_ids, body.folder_id)

    return queue_task(
        get_view_selections_task,
        file_paths=file_paths,
        extension=body.extension,
    )
