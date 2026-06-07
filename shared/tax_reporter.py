"""Tax report generation with Schedule D export."""
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Dict, List
from shared.tax_calculator import TaxCalculator


@dataclass
class TaxGain:
    """A single capital gain/loss for tax reporting."""
    symbol: str
    quantity: int
    cost_basis: float
    proceeds: float
    gain: float
    holding_period: str  # "short_term" or "long_term"


class TaxReporter:
    """Generate tax reports including Schedule D exports."""

    def __init__(self, calculator: TaxCalculator):
        """Initialize with a TaxCalculator instance."""
        self.calculator = calculator

    def generate_schedule_d(self) -> Dict:
        """
        Generate Schedule D report with short-term and long-term gains.

        Returns:
            Dict with:
            - part_i_short_term: List[TaxGain] for short-term gains
            - part_ii_long_term: List[TaxGain] for long-term gains
            - part_i_total_gain: float - total short-term gains
            - part_ii_total_gain: float - total long-term gains
            - total_gain: float - total gains/losses across both parts
        """
        short_term_gains = []
        long_term_gains = []

        # Process each sale
        for sale in self.calculator.sales:
            symbol = sale["symbol"]
            quantity = sale["quantity"]
            sale_price = sale["sale_price"]
            sale_date = sale["sale_date"]
            gain = sale["gain"]
            purchase_date = sale.get("purchase_date")

            # Classify as short-term or long-term based on holding period
            if purchase_date:
                holding_days = (sale_date - purchase_date).days
                is_long_term = holding_days >= 365
            else:
                # Default to short-term if we can't determine
                is_long_term = False

            # Calculate cost basis and proceeds
            cost_basis = quantity * sale_price - gain
            proceeds = quantity * sale_price

            # Create TaxGain record
            tax_gain = TaxGain(
                symbol=symbol,
                quantity=quantity,
                cost_basis=cost_basis,
                proceeds=proceeds,
                gain=gain,
                holding_period="long_term" if is_long_term else "short_term"
            )

            if is_long_term:
                long_term_gains.append(tax_gain)
            else:
                short_term_gains.append(tax_gain)

        # Calculate totals
        part_i_total = sum(g.gain for g in short_term_gains)
        part_ii_total = sum(g.gain for g in long_term_gains)
        total_gain = part_i_total + part_ii_total

        return {
            "part_i_short_term": short_term_gains,
            "part_ii_long_term": long_term_gains,
            "part_i_total_gain": part_i_total,
            "part_ii_total_gain": part_ii_total,
            "total_gain": total_gain,
        }

    def export_schedule_d_csv(self) -> str:
        """
        Export Schedule D as CSV in IRS Schedule D format.

        Returns:
            CSV string with Part I and Part II sections
        """
        schedule_d = self.generate_schedule_d()
        lines = []

        # Header
        lines.append("SYMBOL,QUANTITY,COST_BASIS,PROCEEDS,GAIN")

        # Part I - Short-Term Capital Gains
        lines.append("")
        lines.append("Part I - Short-Term Capital Gains or Losses")
        lines.append("SYMBOL,QUANTITY,COST_BASIS,PROCEEDS,GAIN")

        for gain in schedule_d["part_i_short_term"]:
            lines.append(
                f"{gain.symbol},{gain.quantity},{gain.cost_basis},{gain.proceeds},{gain.gain}"
            )

        lines.append(f"Part I Total,,,, {schedule_d['part_i_total_gain']}")

        # Part II - Long-Term Capital Gains
        lines.append("")
        lines.append("Part II - Long-Term Capital Gains or Losses")
        lines.append("SYMBOL,QUANTITY,COST_BASIS,PROCEEDS,GAIN")

        for gain in schedule_d["part_ii_long_term"]:
            lines.append(
                f"{gain.symbol},{gain.quantity},{gain.cost_basis},{gain.proceeds},{gain.gain}"
            )

        lines.append(f"Part II Total,,,, {schedule_d['part_ii_total_gain']}")

        # Grand Total
        lines.append("")
        lines.append(f"Grand Total,,,, {schedule_d['total_gain']}")

        return "\n".join(lines)

