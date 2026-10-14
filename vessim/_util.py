from typing import Any


def flatten_dict(d: dict, parent_key: str = "") -> dict:
    items: list[tuple[str, Any]] = []
    for k, v in d.items():
        new_key = parent_key + "." + k if parent_key else k
        if isinstance(v, dict):
            items.extend(flatten_dict(v, str(new_key)).items())
        else:
            items.append((new_key, v))
    return dict(items)
