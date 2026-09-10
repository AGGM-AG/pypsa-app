"""Result folders registered in place: one scenario with its planning years."""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING

from sqlalchemy import select

from pypsa_app.backend.models import (
    Network,
    NetworkFolder,
    Permission,
    User,
    Visibility,
)
from pypsa_app.backend.permissions import has_permission
from pypsa_app.backend.services.network import (
    NetworkService,
    _calculate_file_hash,
)
from pypsa_app.backend.settings import settings

if TYPE_CHECKING:
    import uuid

    from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)

NETWORKS_SUBDIR = "networks"


def resolve_folder(raw_path: str) -> Path:
    """Validate a folder for in-place registration.

    The path must be absolute, exist, and lie below one of the configured
    ``NETWORK_ROOTS``.

    Raises:
        PermissionError: when no roots are configured or the path is outside them.
        ValueError: for a relative or missing path.

    """
    roots = settings.resolved_network_roots
    if not roots:
        msg = "In-place registration is disabled (NETWORK_ROOTS not set)"
        raise PermissionError(msg)
    candidate = Path(raw_path.strip())
    if not candidate.is_absolute():
        msg = "Path must be absolute"
        raise ValueError(msg)
    folder = candidate.resolve()
    if not folder.is_dir():
        msg = f"Not a directory: {candidate}"
        raise ValueError(msg)
    for root in roots:
        try:
            folder.relative_to(root)
        except ValueError:
            continue
        return folder
    msg = "Path is outside the registration roots"
    raise PermissionError(msg)


def network_files(folder: Path) -> list[Path]:
    """The ``.nc`` files of a result folder.

    A PyPSA-Eur run keeps them in ``<run>/networks/``; a plain folder holds
    them directly.
    """
    candidates = [folder / NETWORKS_SUBDIR, folder]
    for location in candidates:
        files = sorted(p for p in location.glob("*.nc") if p.is_file())
        if files:
            return files
    return []


def network_label(meta: dict | None, folder_name: str, file_path: Path) -> str:
    """``<scenario> <year>`` from the network metadata, else the file stem."""
    wildcards = (meta or {}).get("wildcards") or {}
    year = wildcards.get("planning_horizons")
    scenario = wildcards.get("run") or folder_name
    if year:
        return f"{scenario} {year}"
    return file_path.stem


def register_network_in_place(
    file_path: Path, folder: NetworkFolder, user_id: uuid.UUID, db: Session
) -> Network:
    """Create (or return) the record of a file that stays at its path."""
    existing = db.scalars(
        select(Network).where(Network.file_path == str(file_path))
    ).first()
    if existing:
        if existing.folder_id is None:
            existing.folder_id = folder.id
        return existing

    service = NetworkService(file_path, use_cache=False)
    info = service.extract_database_info()
    network = Network(
        user_id=user_id,
        folder_id=folder.id,
        visibility=folder.visibility,
        filename=network_label(info["meta"], folder.name, file_path),
        file_path=str(file_path),
        source_path=str(file_path),
        is_external=True,
        file_hash=_calculate_file_hash(file_path),
        file_size=service.get_file_size(),
        name=info["name"],
        dimensions=info["dimensions"],
        components_count=info["components_count"],
        meta=info["meta"],
        facets=info["facets"],
        update_history=[datetime.now(UTC).replace(tzinfo=None).isoformat()],
    )
    db.add(network)
    db.flush()
    return network


def register_folder(
    raw_path: str,
    user_id: uuid.UUID,
    db: Session,
    visibility: Visibility = Visibility.PRIVATE,
) -> NetworkFolder:
    """Register a result folder and its ``.nc`` files without copying them.

    Calling twice with the same folder returns the existing record and adds
    files that appeared since.
    """
    user = db.get(User, user_id)
    if not user or not has_permission(user, Permission.NETWORKS_MODIFY):
        msg = "User does not have permission to register networks"
        raise PermissionError(msg)

    folder_path = resolve_folder(raw_path)
    files = network_files(folder_path)
    if not files:
        msg = f"No .nc files in {folder_path} or {folder_path / NETWORKS_SUBDIR}"
        raise ValueError(msg)

    folder = db.scalars(
        select(NetworkFolder).where(NetworkFolder.path == str(folder_path))
    ).first()
    if folder is None:
        folder = NetworkFolder(
            user_id=user_id,
            visibility=visibility,
            name=folder_path.name,
            path=str(folder_path),
        )
        db.add(folder)
        db.flush()

    for file_path in files:
        register_network_in_place(file_path, folder, user_id, db)
    db.flush()
    db.refresh(folder)
    logger.info(
        "Registered result folder",
        extra={"folder": str(folder_path), "networks": len(folder.networks)},
    )
    return folder
