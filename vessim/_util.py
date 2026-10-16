from typing import Any


def flatten_dict(d: dict, parent_key: str = "") -> dict:
    items: list[tuple[str, Any]] = []
    for k, v in d.items():
        # Escape path separators and the escape character to preserve distinct keys.
        key = k.replace("%", "%25").replace(".", "%2E")
        new_key = parent_key + "." + key if parent_key else key
        if isinstance(v, dict):
            items.extend(flatten_dict(v, str(new_key)).items())
        else:
            items.append((new_key, v))
    return dict(items)
