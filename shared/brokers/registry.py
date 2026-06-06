# shared/brokers/registry.py
import os
import re
import yaml
from shared.brokers.base import BrokerAdapter


def _resolve_env(value: str) -> str:
    if not isinstance(value, str):
        return value
    return re.sub(r"\$\{(\w+)\}", lambda m: os.environ.get(m.group(1), ""), value)


def _resolve_dict(d: dict) -> dict:
    return {k: _resolve_env(v) if isinstance(v, str) else v for k, v in d.items()}


class BrokerRegistry:
    def __init__(self, config_path: str = "brokers.yaml"):
        self._config_path = config_path
        self._adapters: list[BrokerAdapter] = []

    def load(self) -> "BrokerRegistry":
        try:
            with open(self._config_path) as f:
                config = yaml.safe_load(f)
        except FileNotFoundError:
            return self
        for entry in config.get("brokers", []):
            if not entry.get("enabled", True):
                continue
            resolved = _resolve_dict(entry)
            broker_type = resolved.get("type")
            name = resolved.get("name", broker_type)
            try:
                adapter = self._make_adapter(broker_type, name, resolved)
                if adapter:
                    self._adapters.append(adapter)
            except Exception as exc:
                import warnings
                warnings.warn(f"BrokerRegistry: failed to init {name} ({broker_type}): {exc}")
        return self

    def _make_adapter(self, broker_type: str, name: str, config: dict) -> BrokerAdapter | None:
        if broker_type == "alpaca":
            from shared.brokers.alpaca import AlpacaAdapter
            return AlpacaAdapter(name, config)
        if broker_type == "ib":
            from shared.brokers.ib import IBAdapter
            return IBAdapter(name, config)
        if broker_type == "capital_com":
            from shared.brokers.capital_com import CapitalComAdapter
            return CapitalComAdapter(name, config)
        return None

    def get_all(self) -> list[BrokerAdapter]:
        return self._adapters
