"""Audit log export to CSV and PDF."""
from dataclasses import dataclass, field
from typing import List, Optional
from datetime import datetime
from io import BytesIO

# Install reportlab if needed: pip install reportlab
from reportlab.lib.pagesizes import letter, landscape
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, PageBreak
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.lib import colors


@dataclass
class TradeAuditRecord:
    """Complete audit trail for a single trade."""
    trade_id: str
    symbol: str
    action: str  # BUY or SELL
    quantity: int
    price: float
    executed_at: datetime
    agent_signals: List[str]  # ["agent:signal:confidence", ...]
    consensus_score: float
    risk_check_passed: bool
    cio_approval_required: bool
    execution_notes: str = ""


class AuditExporter:
    """Export audit trail to CSV and PDF."""

    def __init__(self):
        self.records: List[TradeAuditRecord] = []

    def add_record(self, record: TradeAuditRecord) -> None:
        """Add a trade record to audit trail."""
        self.records.append(record)

    def export_csv(self) -> str:
        """Export audit trail as CSV."""
        lines = [
            "trade_id,symbol,action,quantity,price,executed_at,agent_signals,"
            "consensus_score,risk_check_passed,cio_approval_required,execution_notes"
        ]

        for record in self.records:
            signals_str = "|".join(record.agent_signals)
            lines.append(
                f"{record.trade_id},{record.symbol},{record.action},{record.quantity},"
                f"{record.price},{record.executed_at.isoformat()},"
                f'"{signals_str}",{record.consensus_score},'
                f"{record.risk_check_passed},{record.cio_approval_required},"
                f'"{record.execution_notes}"'
            )

        return "\n".join(lines)

    def export_pdf(self) -> bytes:
        """Export audit trail as PDF with full decision details."""
        buffer = BytesIO()
        doc = SimpleDocTemplate(buffer, pagesize=landscape(letter))
        story = []
        styles = getSampleStyleSheet()

        # Title
        title = Paragraph("Trade Audit Trail Report", styles['Title'])
        story.append(title)
        story.append(Spacer(1, 0.2*inch))

        # Generate timestamp
        report_date = Paragraph(
            f"<b>Report Generated:</b> {datetime.now().isoformat()[:10]}",
            styles['Normal']
        )
        story.append(report_date)
        story.append(Spacer(1, 0.3*inch))

        # Table data
        table_data = [
            ["Trade ID", "Symbol", "Action", "Qty", "Price", "Time", "Consensus", "Risk OK", "Signals"]
        ]

        for record in self.records:
            signals_summary = ", ".join(record.agent_signals[:2])
            if len(record.agent_signals) > 2:
                signals_summary += f" +{len(record.agent_signals) - 2} more"

            table_data.append([
                record.trade_id,
                record.symbol,
                record.action,
                str(record.quantity),
                f"${record.price:.2f}",
                record.executed_at.strftime("%H:%M"),
                f"{record.consensus_score:.2%}",
                "✓" if record.risk_check_passed else "✗",
                signals_summary,
            ])

        # Create table
        table = Table(table_data, colWidths=[1*inch, 0.7*inch, 0.6*inch, 0.5*inch, 0.7*inch, 0.7*inch, 0.8*inch, 0.6*inch, 1.5*inch])
        table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 10),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
            ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
            ('GRID', (0, 0), (-1, -1), 1, colors.black),
            ('FONTSIZE', (0, 1), (-1, -1), 8),
        ]))

        story.append(table)
        story.append(PageBreak())

        # Detailed records
        story.append(Paragraph("Detailed Trade Decision Trail", styles['Heading2']))
        story.append(Spacer(1, 0.2*inch))

        for record in self.records:
            detail_text = f"""
            <b>Trade ID:</b> {record.trade_id}<br/>
            <b>Symbol:</b> {record.symbol} ({record.action} {record.quantity} @ ${record.price:.2f})<br/>
            <b>Executed:</b> {record.executed_at.isoformat()}<br/>
            <b>Consensus Score:</b> {record.consensus_score:.1%}<br/>
            <b>Risk Check:</b> {'PASSED' if record.risk_check_passed else 'FAILED'}<br/>
            <b>Agent Signals:</b> {', '.join(record.agent_signals)}<br/>
            <b>Notes:</b> {record.execution_notes}<br/>
            """
            story.append(Paragraph(detail_text, styles['Normal']))
            story.append(Spacer(1, 0.3*inch))

        # Build PDF
        doc.build(story)
        return buffer.getvalue()
