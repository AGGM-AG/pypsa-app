"""View extensions: custom, package-provided charts on top of pypsa.statistics.

An extension is an importable module that exposes

- ``list_views() -> list[dict]``: the catalogue, one record per view with
  ``name``, ``title``, ``description``, ``chart``, ``per_year`` and
  ``params_schema`` (JSON schema of the parameters);
- ``load_collection(file_paths) -> object``: the networks the views run on;
- ``render(view, collection, parameters) -> dict``: one Plotly figure as a
  JSON-compatible dict;
- optionally ``selections(collection) -> dict``: what the collection can be
  rendered for (e.g. locations and years).

Extensions are discovered through the ``pypsa_app.views`` entry point group
or listed explicitly in ``settings.extensions``.
"""

from __future__ import annotations

import importlib
import logging
from dataclasses import dataclass, field
from functools import cache
from importlib.metadata import entry_points
from typing import TYPE_CHECKING, Any

from pypsa_app.backend.settings import settings

if TYPE_CHECKING:
    from types import ModuleType

logger = logging.getLogger(__name__)

ENTRY_POINT_GROUP = "pypsa_app.views"


@dataclass(frozen=True)
class ViewSpec:
    """A view offered by an extension."""

    name: str
    extension: str
    title: str
    description: str = ""
    chart: str = ""
    per_year: bool = False
    params_schema: dict[str, Any] = field(default_factory=dict)


def _import_extensions() -> dict[str, ModuleType]:
    """Import the configured or discovered extension modules by name."""
    modules: dict[str, ModuleType] = {}
    names = settings.resolved_extensions
    if names:
        for name in names:
            modules[name] = importlib.import_module(name)
    else:
        for ep in entry_points(group=ENTRY_POINT_GROUP):
            modules[ep.name] = ep.load()
    return modules


@cache
def get_extensions() -> dict[str, ModuleType]:
    """Loaded extension modules keyed by extension name (cached per process)."""
    modules = _import_extensions()
    for name, module in modules.items():
        for attr in ("list_views", "load_collection", "render"):
            if not callable(getattr(module, attr, None)):
                msg = f"View extension {name!r} lacks a callable {attr}()"
                raise TypeError(msg)
    logger.info("View extensions loaded", extra={"extensions": sorted(modules)})
    return modules


@cache
def get_view_specs() -> dict[str, ViewSpec]:
    """All views of all extensions keyed by view name."""
    specs: dict[str, ViewSpec] = {}
    for ext_name, module in get_extensions().items():
        for record in module.list_views():
            spec = ViewSpec(
                name=record["name"],
                extension=record.get("extension", ext_name),
                title=record.get("title", record["name"]),
                description=record.get("description", ""),
                chart=record.get("chart", ""),
                per_year=bool(record.get("per_year", False)),
                params_schema=record.get("params_schema", {}),
            )
            if spec.name in specs:
                msg = (
                    f"View {spec.name!r} is offered by both "
                    f"{specs[spec.name].extension!r} and {ext_name!r}"
                )
                raise ValueError(msg)
            specs[spec.name] = spec
    return specs


def reset_extensions() -> None:
    """Forget loaded extensions (tests, settings changes)."""
    get_extensions.cache_clear()
    get_view_specs.cache_clear()


def _extension_for(view: str) -> tuple[ViewSpec, ModuleType]:
    spec = get_view_specs().get(view)
    if spec is None:
        msg = f"Unknown view {view!r}"
        raise KeyError(msg)
    module = get_extensions()[spec.extension]
    return spec, module


def get_view(file_paths: list[str], view: str, parameters: dict) -> dict:
    """Render one view chart for the networks in ``file_paths``.

    The extension loads the files into its own collection (year and scenario
    come from the network metadata), runs the view and returns Plotly JSON.
    """
    spec, module = _extension_for(view)
    collection = module.load_collection(file_paths)
    figure = module.render(view, collection, parameters or {})
    logger.debug(
        "Rendered view",
        extra={
            "view": view,
            "extension": spec.extension,
            "num_networks": len(file_paths),
            "parameters": parameters,
        },
    )
    return figure


def get_view_selections(file_paths: list[str], extension: str) -> dict:
    """What the networks can be rendered for, as the extension reports it."""
    module = get_extensions()[extension]
    collection = module.load_collection(file_paths)
    selections = getattr(module, "selections", None)
    return selections(collection) if callable(selections) else {}
