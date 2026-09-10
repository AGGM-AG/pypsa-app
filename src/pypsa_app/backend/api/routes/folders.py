"""Result folders registered in place (one scenario, its planning years)"""

import logging
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Path
from sqlalchemy import or_, select
from sqlalchemy.orm import Session, joinedload

from pypsa_app.backend.api.deps import get_db, require_permission
from pypsa_app.backend.models import NetworkFolder, Permission, User, Visibility
from pypsa_app.backend.permissions import can_access, can_modify, has_permission
from pypsa_app.backend.schemas.common import MessageResponse
from pypsa_app.backend.schemas.folder import (
    FolderListResponse,
    FolderRegisterRequest,
    FolderResponse,
)
from pypsa_app.backend.services.folders import register_folder

router = APIRouter()
logger = logging.getLogger(__name__)


def _folder_query():  # noqa: ANN202
    return select(NetworkFolder).options(
        joinedload(NetworkFolder.owner), joinedload(NetworkFolder.networks)
    )


def get_folder(db: Session, folder_id: UUID, user: User) -> NetworkFolder:
    """Fetch a folder the user may read. Raises 404 otherwise."""
    folder = (
        db.scalars(_folder_query().where(NetworkFolder.id == folder_id))
        .unique()
        .first()
    )
    if folder is None or not can_access(user, folder):
        raise HTTPException(404, "Folder not found")
    return folder


@router.post("/register", response_model=FolderResponse, status_code=201)
def register(
    body: FolderRegisterRequest,
    db: Session = Depends(get_db),
    user: User = Depends(require_permission(Permission.NETWORKS_MODIFY)),
) -> NetworkFolder:
    """Register a result folder at its path; the files stay in place.

    Allowed below the configured NETWORK_ROOTS only. The folder name is the
    scenario name; every .nc file (in the folder or its networks/ subfolder)
    becomes a network named "<scenario> <year>".
    """
    try:
        folder = register_folder(body.absolute_path, user.id, db, body.visibility)
    except PermissionError as exc:
        raise HTTPException(403, str(exc)) from exc
    except (ValueError, FileNotFoundError) as exc:
        raise HTTPException(400, str(exc)) from exc
    except OSError as exc:
        raise HTTPException(400, f"Cannot access path: {exc}") from exc
    db.commit()
    return get_folder(db, folder.id, user)


@router.get("/", response_model=FolderListResponse)
def list_folders(
    db: Session = Depends(get_db),
    user: User = Depends(require_permission(Permission.NETWORKS_VIEW)),
) -> dict:
    """Registered folders the user may see"""
    query = _folder_query().order_by(NetworkFolder.created_at.desc())
    if not has_permission(user, Permission.NETWORKS_MANAGE_ALL):
        query = query.where(
            or_(
                NetworkFolder.user_id == user.id,
                NetworkFolder.visibility == Visibility.PUBLIC,
            )
        )
    return {"data": db.scalars(query).unique().all()}


@router.get("/{folder_id}", response_model=FolderResponse)
def read_folder(
    folder_id: UUID = Path(..., description="Folder UUID"),
    db: Session = Depends(get_db),
    user: User = Depends(require_permission(Permission.NETWORKS_VIEW)),
) -> NetworkFolder:
    """A folder with its networks"""
    return get_folder(db, folder_id, user)


@router.delete("/{folder_id}", response_model=MessageResponse)
def delete_folder(
    folder_id: UUID = Path(..., description="Folder UUID"),
    db: Session = Depends(get_db),
    user: User = Depends(require_permission(Permission.NETWORKS_MODIFY)),
) -> dict:
    """Forget a folder and its network records; files are never touched"""
    folder = get_folder(db, folder_id, user)
    if not can_modify(user, folder):
        raise HTTPException(404, "Folder not found")
    name = folder.name
    for network in list(folder.networks):
        db.delete(network)
    db.delete(folder)
    db.commit()
    return {"message": f"Folder {name} removed (files kept in place)"}
