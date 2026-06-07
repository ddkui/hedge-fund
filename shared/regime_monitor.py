# shared/regime_monitor.py
"""
Intraday regime switching based on volatility and macro signals.
Adjusts parameters when VIX > 30 or other hard flags triggered.
"""
from enum import Enum
from datetime import datetime, timezone


class Regime(str, Enum):
    EXPANSION = "expansion"
    CRISIS = "crisis"
    PANDEMIC = "pandemic"


class RegimeMonitor:
    def __init__(self):
        self.current_regime = Regime.EXPANSION
        self.vix_threshold_crisis = 30.0
        self.vix_threshold_panic = 50.0
        self.hard_flags = {
            "vix_above_threshold": False,
            "unemployment_spike": False,
            "fed_emergency_action": False,
        }

    def update_vix(self, vix_value: float) -> Regime:
        """
        Update regime based on VIX level.

        Returns:
            New regime (may be same as current)
        """
        if vix_value > self.vix_threshold_panic:
            self.current_regime = Regime.PANDEMIC
            self.hard_flags["vix_above_threshold"] = True
        elif vix_value > self.vix_threshold_crisis:
            self.current_regime = Regime.CRISIS
            self.hard_flags["vix_above_threshold"] = True
        else:
            self.current_regime = Regime.EXPANSION
            self.hard_flags["vix_above_threshold"] = False

        return self.current_regime

    def check_hard_flags(self, flags: dict) -> Regime:
        """
        Check hard flags (unemployment spike, Fed action, etc).

        Args:
            flags: Dict of flag_name -> bool

        Returns:
            Updated regime
        """
        self.hard_flags.update(flags)

        if any([
            self.hard_flags.get("unemployment_spike", False),
            self.hard_flags.get("fed_emergency_action", False),
        ]):
            self.current_regime = Regime.CRISIS
        elif self.hard_flags.get("vix_above_threshold", False):
            self.current_regime = Regime.CRISIS

        return self.current_regime

    def get_regime(self) -> Regime:
        """Get current regime."""
        return self.current_regime

    def reset_daily(self) -> None:
        """Reset intraday flags at market open."""
        self.hard_flags = {k: False for k in self.hard_flags}
