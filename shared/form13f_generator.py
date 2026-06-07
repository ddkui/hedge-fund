# shared/form13f_generator.py
"""SEC Form 13F filing generation."""
from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, List, Optional


@dataclass
class Form13FPosition:
    """A single position in a 13F filing."""
    symbol: str
    quantity: int
    market_value: float
    price_per_share: float
    cusip: str
    value_code: str = "000"  # Dollar value code (000 = > $1M)


class Form13FGenerator:
    """Generate SEC Form 13F quarterly filings."""

    QUARTER_END_DATES = {
        "Q1": "03-31",
        "Q2": "06-30",
        "Q3": "09-30",
        "Q4": "12-31",
    }

    def __init__(
        self,
        cik: str,
        fund_name: str,
        fiscal_quarter: str,
        fiscal_year: int,
    ):
        self.cik = cik
        self.fund_name = fund_name
        self.fiscal_quarter = fiscal_quarter
        self.fiscal_year = fiscal_year
        self.positions: Dict[str, Form13FPosition] = {}

    def add_position(
        self,
        symbol: str,
        quantity: int,
        market_value: float,
        price_per_share: float,
        cusip: str,
    ) -> None:
        """Add or update a position."""
        if symbol in self.positions:
            # Aggregate with existing
            existing = self.positions[symbol]
            existing.quantity += quantity
            existing.market_value += market_value
        else:
            self.positions[symbol] = Form13FPosition(
                symbol=symbol,
                quantity=quantity,
                market_value=market_value,
                price_per_share=price_per_share,
                cusip=cusip,
            )

    def get_positions(self) -> List[Form13FPosition]:
        """Get all positions sorted by market value descending."""
        return sorted(
            self.positions.values(),
            key=lambda x: x.market_value,
            reverse=True,
        )

    def get_period_ended(self) -> str:
        """Get period ended date (YYYY-MM-DD)."""
        date_str = self.QUARTER_END_DATES.get(self.fiscal_quarter, "12-31")
        return f"{self.fiscal_year}-{date_str}"

    def generate_filing(self) -> Dict:
        """Generate 13F filing as dictionary."""
        positions = self.get_positions()
        total_value = sum(pos.market_value for pos in positions)

        return {
            "cik": self.cik,
            "fund_name": self.fund_name,
            "period_ended": self.get_period_ended(),
            "fiscal_quarter": self.fiscal_quarter,
            "fiscal_year": self.fiscal_year,
            "positions": positions,
            "total_value": total_value,
            "position_count": len(positions),
        }

    def export_csv(self) -> str:
        """Export filing as CSV (for Schedule 13F-1)."""
        lines = [
            "CUSIP,SYMBOL,QUANTITY,PRICE_PER_SHARE,MARKET_VALUE",
        ]

        for pos in self.get_positions():
            lines.append(
                f"{pos.cusip},{pos.symbol},{pos.quantity},{pos.price_per_share},{pos.market_value}"
            )

        return "\n".join(lines)
