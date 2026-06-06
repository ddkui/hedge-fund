# gateway/routers/kronos.py
import io
from datetime import datetime, timezone

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse

from shared.db import Database
from gateway.deps import get_db

router = APIRouter()


# ------------------------------------------------------------------ #
#  JSON endpoint — latest forecast per symbol                          #
# ------------------------------------------------------------------ #

@router.get("/forecasts")
async def get_forecasts(db: Database = Depends(get_db)):
    rows = await db.fetch(
        """
        SELECT DISTINCT ON (symbol)
            symbol, model, pred_close, pred_change_pct, signal_type,
            confidence, pred_high, pred_low, reasoning, time,
            lookback_candles, pred_horizon_candles
        FROM kronos_forecasts
        ORDER BY symbol, time DESC
        """
    )
    return [dict(r) for r in rows]


@router.get("/history/{symbol}")
async def get_symbol_history(symbol: str, limit: int = 20, db: Database = Depends(get_db)):
    rows = await db.fetch(
        """
        SELECT time, pred_change_pct, signal_type, confidence, pred_close
        FROM kronos_forecasts
        WHERE symbol = $1
        ORDER BY time DESC
        LIMIT $2
        """,
        symbol.upper(), limit,
    )
    return [dict(r) for r in rows]


# ------------------------------------------------------------------ #
#  PDF report endpoint                                                  #
# ------------------------------------------------------------------ #

@router.get("/report.pdf")
async def get_kronos_pdf(db: Database = Depends(get_db)):
    rows = await db.fetch(
        """
        SELECT DISTINCT ON (symbol)
            symbol, model, pred_close, pred_change_pct, signal_type,
            confidence, pred_high, pred_low, time, pred_horizon_candles
        FROM kronos_forecasts
        ORDER BY symbol, time DESC
        """
    )
    forecasts = [dict(r) for r in rows]

    # Also fetch macro regime for context
    macro = await db.fetch(
        "SELECT signal_type FROM signals WHERE agent = 'macro' ORDER BY time DESC LIMIT 1"
    )
    regime = macro[0]["signal_type"] if macro else "unknown"

    pdf_bytes = _build_pdf(forecasts, regime)

    return StreamingResponse(
        io.BytesIO(pdf_bytes),
        media_type="application/pdf",
        headers={
            "Content-Disposition": f'inline; filename="kronos-report-{datetime.now(timezone.utc).strftime("%Y%m%d-%H%M")}.pdf"'
        },
    )


# ------------------------------------------------------------------ #
#  PDF generation                                                       #
# ------------------------------------------------------------------ #

def _build_pdf(forecasts: list[dict], regime: str) -> bytes:
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.units import cm
    from reportlab.lib import colors
    from reportlab.platypus import (
        SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle,
        HRFlowable,
    )

    buf = io.BytesIO()
    doc = SimpleDocTemplate(
        buf,
        pagesize=A4,
        leftMargin=1.8 * cm,
        rightMargin=1.8 * cm,
        topMargin=1.8 * cm,
        bottomMargin=1.8 * cm,
    )

    W, _ = A4
    usable = W - 3.6 * cm

    styles = getSampleStyleSheet()
    now = datetime.now(timezone.utc)

    # ---- custom styles ----
    title_style = ParagraphStyle(
        "HFTitle",
        parent=styles["Title"],
        fontSize=20,
        textColor=colors.HexColor("#00d4aa"),
        spaceAfter=4,
    )
    sub_style = ParagraphStyle(
        "HFSub",
        parent=styles["Normal"],
        fontSize=9,
        textColor=colors.HexColor("#6b7280"),
        spaceAfter=2,
    )
    section_style = ParagraphStyle(
        "HFSection",
        parent=styles["Heading2"],
        fontSize=12,
        textColor=colors.HexColor("#e2e8f0"),
        spaceBefore=14,
        spaceAfter=6,
    )
    footer_style = ParagraphStyle(
        "HFFooter",
        parent=styles["Normal"],
        fontSize=8,
        textColor=colors.HexColor("#4b5563"),
        alignment=1,
    )

    story = []

    # ---- header ----
    story.append(Paragraph("AI Hedge Fund", title_style))
    story.append(Paragraph("Kronos Foundation Model — Price Forecast Report", sub_style))
    story.append(Paragraph(
        f"Generated: {now.strftime('%Y-%m-%d %H:%M UTC')}  |  "
        f"Model: NeoQuasar/Kronos-mini  |  "
        f"Macro Regime: {regime.upper().replace('_', ' ')}",
        sub_style,
    ))
    story.append(HRFlowable(width="100%", thickness=1, color=colors.HexColor("#1e1e2e"), spaceAfter=10))

    if not forecasts:
        story.append(Paragraph(
            "No Kronos forecasts available yet. Run the Kronos agent first.",
            styles["Normal"],
        ))
        doc.build(story)
        return buf.getvalue()

    # ---- summary stats ----
    bullish = [f for f in forecasts if "bullish" in f["signal_type"]]
    bearish = [f for f in forecasts if "bearish" in f["signal_type"]]
    neutral = [f for f in forecasts if "neutral" in f["signal_type"]]

    horizon = forecasts[0].get("pred_horizon_candles", 24) if forecasts else 24

    summary_data = [
        ["Symbols", "Horizon", "Bullish", "Bearish", "Neutral"],
        [
            str(len(forecasts)),
            f"{horizon} candles",
            str(len(bullish)),
            str(len(bearish)),
            str(len(neutral)),
        ],
    ]
    summary_table = Table(summary_data, colWidths=[usable / 5] * 5)
    summary_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#13131a")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.HexColor("#9ca3af")),
        ("FONTSIZE", (0, 0), (-1, 0), 8),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("BACKGROUND", (0, 1), (-1, 1), colors.HexColor("#0a0a0f")),
        ("TEXTCOLOR", (0, 1), (-1, 1), colors.white),
        ("FONTSIZE", (0, 1), (-1, 1), 14),
        ("FONTNAME", (0, 1), (-1, 1), "Helvetica-Bold"),
        ("ALIGN", (0, 0), (-1, -1), "CENTER"),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("ROWBACKGROUNDS", (2, 1), (-1, 1), [colors.HexColor("#00d4aa"), colors.HexColor("#ff4757"), colors.HexColor("#6b7280")]),
        ("TEXTCOLOR", (2, 1), (2, 1), colors.HexColor("#00d4aa")),
        ("TEXTCOLOR", (3, 1), (3, 1), colors.HexColor("#ff4757")),
        ("BOX", (0, 0), (-1, -1), 0.5, colors.HexColor("#1e1e2e")),
        ("INNERGRID", (0, 0), (-1, -1), 0.25, colors.HexColor("#1e1e2e")),
        ("TOPPADDING", (0, 0), (-1, -1), 8),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
    ]))
    story.append(summary_table)
    story.append(Spacer(1, 14))

    # ---- forecast table ----
    story.append(Paragraph("Forecast Detail", section_style))

    COL_WIDTHS = [
        usable * 0.12,  # Symbol
        usable * 0.12,  # Signal
        usable * 0.10,  # Change %
        usable * 0.13,  # Current
        usable * 0.13,  # Predicted
        usable * 0.13,  # Low
        usable * 0.13,  # High
        usable * 0.10,  # Conf
        usable * 0.04,  # (last col padding)
    ]
    # Adjust to fit
    COL_WIDTHS = [usable * w for w in [0.12, 0.11, 0.10, 0.135, 0.135, 0.12, 0.12, 0.10]]

    header_row = ["Symbol", "Signal", "Change", "Current", "Predicted", "Low", "High", "Conf"]
    table_data = [header_row]

    for fc in sorted(forecasts, key=lambda x: x["pred_change_pct"], reverse=True):
        sig = fc["signal_type"].replace("_signal", "").upper()
        arrow = "UP" if "bullish" in fc["signal_type"] else ("DN" if "bearish" in fc["signal_type"] else "--")
        table_data.append([
            fc["symbol"],
            f"{arrow} {sig}",
            f"{fc['pred_change_pct']:+.2f}%",
            f"{fc.get('pred_close', 0) / (1 + fc['pred_change_pct'] / 100):.4f}" if fc['pred_change_pct'] != 0 else "—",
            f"{fc['pred_close']:.4f}",
            f"{fc['pred_low']:.4f}",
            f"{fc['pred_high']:.4f}",
            f"{fc['confidence']:.0f}%",
        ])

    forecast_table = Table(table_data, colWidths=COL_WIDTHS, repeatRows=1)

    # Build row-specific styles
    ts = [
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#13131a")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.HexColor("#9ca3af")),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 8),
        ("ALIGN", (0, 0), (-1, -1), "RIGHT"),
        ("ALIGN", (0, 0), (1, -1), "LEFT"),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
        ("BOX", (0, 0), (-1, -1), 0.5, colors.HexColor("#1e1e2e")),
        ("INNERGRID", (0, 0), (-1, -1), 0.25, colors.HexColor("#1e1e2e")),
    ]
    for i, fc in enumerate(sorted(forecasts, key=lambda x: x["pred_change_pct"], reverse=True), start=1):
        if "bullish" in fc["signal_type"]:
            bg = colors.HexColor("#0a1f1a")
            fg = colors.HexColor("#00d4aa")
        elif "bearish" in fc["signal_type"]:
            bg = colors.HexColor("#1f0a0a")
            fg = colors.HexColor("#ff4757")
        else:
            bg = colors.HexColor("#0d0d14")
            fg = colors.HexColor("#9ca3af")
        ts += [
            ("BACKGROUND", (0, i), (-1, i), bg),
            ("TEXTCOLOR", (0, i), (1, i), fg),
            ("FONTNAME", (0, i), (0, i), "Helvetica-Bold"),
        ]

    forecast_table.setStyle(TableStyle(ts))
    story.append(forecast_table)

    # ---- latest run timestamp ----
    if forecasts and forecasts[0].get("time"):
        ts_str = str(forecasts[0]["time"])[:19] + " UTC"
        story.append(Spacer(1, 8))
        story.append(Paragraph(f"Data as of: {ts_str}", sub_style))

    # ---- disclaimer ----
    story.append(Spacer(1, 20))
    story.append(HRFlowable(width="100%", thickness=0.5, color=colors.HexColor("#1e1e2e")))
    story.append(Spacer(1, 6))
    story.append(Paragraph(
        "This report is generated by the Kronos foundation model (AAAI 2026) for research purposes only. "
        "Forecasts are probabilistic and not financial advice. Past model performance does not guarantee future results.",
        footer_style,
    ))
    story.append(Paragraph(
        f"AI Hedge Fund System  |  {now.strftime('%Y-%m-%d %H:%M UTC')}",
        footer_style,
    ))

    doc.build(story)
    return buf.getvalue()
