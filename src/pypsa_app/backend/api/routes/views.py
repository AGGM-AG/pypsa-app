"""Routes of the view extensions (package-provided charts)"""

import logging

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from sqlalchemy.orm import Session

from pypsa_app.backend.api.deps import get_db, get_networks, require_permission
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
    networks = get_networks(db, body.network_ids, user)
    file_paths = [net.file_path for net in networks]

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
    networks = get_networks(db, body.network_ids, user)
    file_paths = [net.file_path for net in networks]

    return queue_task(
        get_view_selections_task,
        file_paths=file_paths,
        extension=body.extension,
    )
