from dataclasses import dataclass
from datetime import datetime


@dataclass
class CodePatch:
    agent_name: str
    file_path: str
    description: str
    original_content: str
    patched_content: str
    regime: str = ""
    win_rate: float = 0.0
    reason: str = ""


@dataclass
class WeightProposal:
    agent_name: str
    regime: str
    current_weight: float
    proposed_weight: float
    win_rate: float
    total_signals: int
    auto_apply: bool

    @property
    def change_pct(self) -> float:
        if self.current_weight == 0:
            return 0.0
        return abs((self.proposed_weight - self.current_weight) / self.current_weight) * 100


@dataclass
class HermesReport:
    cycle_time: datetime
    outcomes_analyzed: int
    proposals_generated: int
    auto_applied: int
    queued_for_approval: int
    summary: str
