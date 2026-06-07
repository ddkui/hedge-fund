# gateway/alerts.py
"""
Email alert system for critical events.
Sends alerts for: circuit breaker trips, broker failures, hedge activations, monthly reports.
"""
import smtplib
import logging
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime, timezone
from typing import List, Optional

logger = logging.getLogger(__name__)


class AlertService:
    """Sends email alerts for trading events."""

    def __init__(self, smtp_host: str, smtp_port: int, sender_email: str, sender_password: str):
        self.smtp_host = smtp_host
        self.smtp_port = smtp_port
        self.sender_email = sender_email
        self.sender_password = sender_password

    def send_alert(
        self,
        to_email: str,
        subject: str,
        body: str,
        alert_type: str = "info",
    ) -> bool:
        """
        Send email alert.

        Args:
            to_email: Recipient email
            subject: Email subject
            body: Email body (HTML or text)
            alert_type: "info", "warning", "critical"

        Returns:
            True if sent successfully
        """
        try:
            msg = MIMEMultipart("alternative")
            msg["Subject"] = subject
            msg["From"] = self.sender_email
            msg["To"] = to_email

            # Add color coding based on severity
            color_map = {
                "info": "#0066cc",      # Blue
                "warning": "#ff9900",   # Orange
                "critical": "#cc0000",  # Red
            }
            color = color_map.get(alert_type, "#0066cc")

            # HTML email with styling
            html = f"""
            <html>
              <body style="font-family: Arial, sans-serif;">
                <div style="border-left: 4px solid {color}; padding-left: 20px;">
                  <h2 style="color: {color};">{subject}</h2>
                  <div style="color: #333;">
                    {body}
                  </div>
                  <hr style="margin-top: 20px; border: none; border-top: 1px solid #eee;">
                  <p style="color: #999; font-size: 12px;">
                    Alert Type: {alert_type.upper()} | {datetime.now(timezone.utc).isoformat()}
                  </p>
                </div>
              </body>
            </html>
            """

            part = MIMEText(html, "html")
            msg.attach(part)

            # Send email
            with smtplib.SMTP(self.smtp_host, self.smtp_port) as server:
                server.starttls()
                server.login(self.sender_email, self.sender_password)
                server.send_message(msg)

            logger.info(f"✅ Alert sent to {to_email}: {subject}")
            return True

        except Exception as e:
            logger.error(f"❌ Failed to send alert: {e}")
            return False

    def circuit_breaker_trip(
        self,
        to_email: str,
        portfolio_value: float,
        peak_value: float,
        loss_pct: float,
    ) -> bool:
        """Alert when circuit breaker trips."""
        subject = "🚨 Circuit Breaker Tripped - Trading Halted"
        body = f"""
        <p>Your hedge fund's circuit breaker has been triggered.</p>

        <table style="border-collapse: collapse; margin: 20px 0;">
          <tr style="background-color: #f5f5f5;">
            <td style="padding: 10px; border: 1px solid #ddd;"><strong>Portfolio Value</strong></td>
            <td style="padding: 10px; border: 1px solid #ddd;">${portfolio_value:,.2f}</td>
          </tr>
          <tr>
            <td style="padding: 10px; border: 1px solid #ddd;"><strong>Peak Value</strong></td>
            <td style="padding: 10px; border: 1px solid #ddd;">${peak_value:,.2f}</td>
          </tr>
          <tr style="background-color: #ffcccc;">
            <td style="padding: 10px; border: 1px solid #ddd;"><strong>Loss</strong></td>
            <td style="padding: 10px; border: 1px solid #ddd;"><strong>{loss_pct:.2f}%</strong></td>
          </tr>
        </table>

        <p><strong>Action:</strong> All trading has been halted. Manual review required before resuming.</p>
        <p><strong>Reset:</strong> Circuit breaker will automatically reset at end of trading day (23:59).</p>
        """
        return self.send_alert(to_email, subject, body, "critical")

    def broker_failure(
        self,
        to_email: str,
        broker_name: str,
        failed_trades: int,
        error_msg: str,
    ) -> bool:
        """Alert when broker connection fails."""
        subject = f"⚠️ Broker Failure: {broker_name.upper()}"
        body = f"""
        <p>Your hedge fund failed to connect to <strong>{broker_name}</strong>.</p>

        <table style="border-collapse: collapse; margin: 20px 0;">
          <tr style="background-color: #f5f5f5;">
            <td style="padding: 10px; border: 1px solid #ddd;"><strong>Broker</strong></td>
            <td style="padding: 10px; border: 1px solid #ddd;">{broker_name}</td>
          </tr>
          <tr>
            <td style="padding: 10px; border: 1px solid #ddd;"><strong>Failed Trades</strong></td>
            <td style="padding: 10px; border: 1px solid #ddd;">{failed_trades}</td>
          </tr>
          <tr>
            <td style="padding: 10px; border: 1px solid #ddd;"><strong>Error</strong></td>
            <td style="padding: 10px; border: 1px solid #ddd;"><code>{error_msg}</code></td>
          </tr>
        </table>

        <p><strong>Status:</strong> System is attempting failover to backup brokers.</p>
        """
        return self.send_alert(to_email, subject, body, "warning")

    def hedge_activation(
        self,
        to_email: str,
        portfolio_correlation: float,
        spy_price: float,
        hedge_qty: float,
    ) -> bool:
        """Alert when correlation hedge is activated."""
        subject = "🛡️ Correlation Hedge Activated"
        body = f"""
        <p>Portfolio correlation to SPY has exceeded 0.8. Hedge activated for risk reduction.</p>

        <table style="border-collapse: collapse; margin: 20px 0;">
          <tr style="background-color: #f5f5f5;">
            <td style="padding: 10px; border: 1px solid #ddd;"><strong>Portfolio Correlation</strong></td>
            <td style="padding: 10px; border: 1px solid #ddd;">{portfolio_correlation:.3f}</td>
          </tr>
          <tr>
            <td style="padding: 10px; border: 1px solid #ddd;"><strong>SPY Price</strong></td>
            <td style="padding: 10px; border: 1px solid #ddd;">${spy_price:,.2f}</td>
          </tr>
          <tr style="background-color: #ccffcc;">
            <td style="padding: 10px; border: 1px solid #ddd;"><strong>SPY Short Qty</strong></td>
            <td style="padding: 10px; border: 1px solid #ddd;">{hedge_qty:.0f} shares</td>
          </tr>
        </table>

        <p><strong>Effect:</strong> This hedge reduces portfolio correlation to broader market movements.</p>
        """
        return self.send_alert(to_email, subject, body, "info")

    def monthly_report_ready(
        self,
        to_email: str,
        investor_name: str,
        month: str,
        monthly_return_pct: float,
        sharpe_ratio: float,
        pdf_url: Optional[str] = None,
    ) -> bool:
        """Alert that monthly report is ready."""
        subject = f"📊 Monthly Report Ready: {month}"

        download_link = ""
        if pdf_url:
            download_link = f'<p><a href="{pdf_url}" style="background-color: #0066cc; color: white; padding: 10px 20px; text-decoration: none; border-radius: 4px;">📥 Download PDF Report</a></p>'

        body = f"""
        <p>Your monthly hedge fund report for <strong>{month}</strong> is ready.</p>

        <table style="border-collapse: collapse; margin: 20px 0;">
          <tr style="background-color: #f5f5f5;">
            <td style="padding: 10px; border: 1px solid #ddd;"><strong>Investor</strong></td>
            <td style="padding: 10px; border: 1px solid #ddd;">{investor_name}</td>
          </tr>
          <tr>
            <td style="padding: 10px; border: 1px solid #ddd;"><strong>Month</strong></td>
            <td style="padding: 10px; border: 1px solid #ddd;">{month}</td>
          </tr>
          <tr style="background-color: {'#ccffcc' if monthly_return_pct > 0 else '#ffcccc'};">
            <td style="padding: 10px; border: 1px solid #ddd;"><strong>Monthly Return</strong></td>
            <td style="padding: 10px; border: 1px solid #ddd;"><strong>{monthly_return_pct:+.2f}%</strong></td>
          </tr>
          <tr>
            <td style="padding: 10px; border: 1px solid #ddd;"><strong>Sharpe Ratio</strong></td>
            <td style="padding: 10px; border: 1px solid #ddd;">{sharpe_ratio:.2f}</td>
          </tr>
        </table>

        {download_link}

        <p>Login to your dashboard to view detailed analytics.</p>
        """
        return self.send_alert(to_email, subject, body, "info")

    def alpha_tier_change(
        self,
        to_email: str,
        old_tier: str,
        new_tier: str,
        alpha_pct: float,
        action: str,
    ) -> bool:
        """Alert when alpha tier changes."""
        tier_colors = {
            "learning": "#ff9900",
            "alpha_achieved": "#0066cc",
            "exceptional": "#00cc00",
        }

        subject = f"📈 Alpha Tier Changed: {old_tier} → {new_tier}"
        body = f"""
        <p>Your hedge fund's alpha tier has changed.</p>

        <table style="border-collapse: collapse; margin: 20px 0;">
          <tr style="background-color: #f5f5f5;">
            <td style="padding: 10px; border: 1px solid #ddd;"><strong>Previous Tier</strong></td>
            <td style="padding: 10px; border: 1px solid #ddd;"><span style="color: {tier_colors.get(old_tier, '#000')};">{old_tier}</span></td>
          </tr>
          <tr>
            <td style="padding: 10px; border: 1px solid #ddd;"><strong>New Tier</strong></td>
            <td style="padding: 10px; border: 1px solid #ddd;"><span style="color: {tier_colors.get(new_tier, '#000')}; font-weight: bold;">{new_tier}</span></td>
          </tr>
          <tr style="background-color: #f5f5f5;">
            <td style="padding: 10px; border: 1px solid #ddd;"><strong>Jensen's Alpha</strong></td>
            <td style="padding: 10px; border: 1px solid #ddd;">{alpha_pct:.2f}%</td>
          </tr>
        </table>

        <p><strong>Action Taken:</strong> {action}</p>

        <ul>
          <li><strong>learning</strong> (alpha &lt; 2%): Full parameter optimization allowed</li>
          <li><strong>alpha_achieved</strong> (alpha ≥ 2%): Micro-tuning only</li>
          <li><strong>exceptional</strong> (alpha ≥ 5%): Parameters locked for stability</li>
        </ul>
        """
        return self.send_alert(to_email, subject, body, "info")


# Singleton instance
_alert_service = None


def get_alert_service(
    smtp_host: str = "smtp.gmail.com",
    smtp_port: int = 587,
    sender_email: str = None,
    sender_password: str = None,
) -> AlertService:
    """Get or create alert service."""
    global _alert_service
    if _alert_service is None:
        import os
        sender_email = sender_email or os.getenv("GMAIL_SENDER")
        sender_password = sender_password or os.getenv("GMAIL_APP_PASSWORD")
        _alert_service = AlertService(smtp_host, smtp_port, sender_email, sender_password)
    return _alert_service
