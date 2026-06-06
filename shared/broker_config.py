# shared/broker_config.py
"""
Read/write helper for brokers.yaml — backs the dashboard Brokers management UI.

Secrets are stored in brokers.yaml. When listing for the UI, secret fields are
masked (only last 4 chars shown) so keys are never sent back to the browser in full.
"""
import os
import yaml

SECRET_FIELDS = {"api_key", "secret_key", "password"}
DEFAULT_PATH = "brokers.yaml"

# Required fields per broker type (besides name + type + enabled)
TYPE_FIELDS = {
    "alpaca": ["api_key", "secret_key", "paper"],
    "ib": ["host", "port", "client_id"],
    "capital_com": ["api_key", "identifier", "password", "base_url"],
}


def _mask(value) -> str:
    s = str(value or "")
    if len(s) <= 4:
        return "****"
    return "****" + s[-4:]


def _load_raw(path: str = DEFAULT_PATH) -> dict:
    if not os.path.exists(path):
        return {"brokers": []}
    with open(path) as f:
        return yaml.safe_load(f) or {"brokers": []}


def _save_raw(data: dict, path: str = DEFAULT_PATH) -> None:
    with open(path, "w") as f:
        yaml.dump(data, f, default_flow_style=False, sort_keys=False)


def list_brokers(path: str = DEFAULT_PATH) -> list[dict]:
    """Return all brokers with secret fields masked, safe to send to the browser."""
    data = _load_raw(path)
    result = []
    for b in data.get("brokers", []):
        safe = {}
        for k, v in b.items():
            safe[k] = _mask(v) if k in SECRET_FIELDS else v
        result.append(safe)
    return result


def add_broker(broker: dict, path: str = DEFAULT_PATH) -> dict:
    """Add a broker account. Raises ValueError on validation failure."""
    name = broker.get("name", "").strip()
    btype = broker.get("type", "").strip()
    if not name:
        raise ValueError("name is required")
    if btype not in TYPE_FIELDS:
        raise ValueError(f"unsupported broker type: {btype}")

    data = _load_raw(path)
    if any(b["name"] == name for b in data.get("brokers", [])):
        raise ValueError(f"broker '{name}' already exists")

    entry = {"name": name, "type": btype, "enabled": broker.get("enabled", True)}
    for field in TYPE_FIELDS[btype]:
        if field in broker:
            entry[field] = broker[field]
    data.setdefault("brokers", []).append(entry)
    _save_raw(data, path)
    return {"name": name, "type": btype}


def remove_broker(name: str, path: str = DEFAULT_PATH) -> bool:
    data = _load_raw(path)
    before = len(data.get("brokers", []))
    data["brokers"] = [b for b in data.get("brokers", []) if b["name"] != name]
    if len(data["brokers"]) == before:
        return False
    _save_raw(data, path)
    return True


def toggle_broker(name: str, enabled: bool, path: str = DEFAULT_PATH) -> bool:
    data = _load_raw(path)
    found = False
    for b in data.get("brokers", []):
        if b["name"] == name:
            b["enabled"] = enabled
            found = True
    if found:
        _save_raw(data, path)
    return found
