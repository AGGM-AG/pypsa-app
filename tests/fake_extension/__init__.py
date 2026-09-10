"""A minimal view extension used by the tests."""

from pathlib import Path


def list_views() -> list[dict]:
    return [
        {
            "name": "view_bus_count",
            "title": "Bus count",
            "description": "Number of buses per network",
            "chart": "bar",
            "per_year": False,
            "params_schema": {
                "type": "object",
                "properties": {"location": {"type": "string", "default": "AT"}},
            },
        }
    ]


def load_collection(file_paths: list[str]) -> list[Path]:
    return [Path(p) for p in file_paths]


def selections(collection: list[Path]) -> dict:
    return {"locations": ["AT"], "years": [p.stem for p in collection]}


def render(view: str, collection: list[Path], parameters: dict) -> dict:
    import pypsa

    counts = [len(pypsa.Network(p).buses) for p in collection]
    return {
        "data": [{"type": "bar", "x": [p.stem for p in collection], "y": counts}],
        "layout": {"title": {"text": f"{view} {parameters.get('location', '')}"}},
    }
