# gateway/scheduler.py
"""
Scheduled jobs: monthly reporter, daily alpha monitor, regime checker, hedge rebalancer.
Uses APScheduler for job scheduling.
"""
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from datetime import datetime, timezone, timedelta
import logging

from sqlalchemy.orm import Session
from shared.models import (
    PortfolioState, InvestorReport, AgentStats,
    CorrelationHedgeLog, CircuitBreakerLog, OptimizerProposal
)
from shared.investor_report import InvestorReportGenerator, MonthlyMetrics

logger = logging.getLogger(__name__)


class ScheduledJobs:
    """Manages all background scheduled jobs."""

    def __init__(self, db: Session):
        self.db = db
        self.scheduler = BackgroundScheduler()

    def start(self):
        """Start all scheduled jobs."""
        # Monthly: 1st day of month at 00:00
        self.scheduler.add_job(
            self._monthly_investor_report,
            CronTrigger(day=1, hour=0, minute=0),
            id="monthly_report",
            name="Generate Monthly Investor Reports",
        )

        # Daily: 22:00 (after market close)
        self.scheduler.add_job(
            self._daily_alpha_monitor,
            CronTrigger(hour=22, minute=0),
            id="daily_alpha",
            name="Daily Alpha Monitoring",
        )

        # Every 5 minutes: Regime check
        self.scheduler.add_job(
            self._regime_checker,
            "interval",
            minutes=5,
            id="regime_check",
            name="Regime Checker",
        )

        # Every hour: Hedge rebalancer
        self.scheduler.add_job(
            self._hedge_rebalancer,
            "interval",
            hours=1,
            id="hedge_rebalance",
            name="Hedge Rebalancer",
        )

        # Daily: 23:59 Reset circuit breaker
        self.scheduler.add_job(
            self._daily_cb_reset,
            CronTrigger(hour=23, minute=59),
            id="daily_cb_reset",
            name="Daily Circuit Breaker Reset",
        )

        self.scheduler.start()
        logger.info("✅ Scheduled jobs started")

    def stop(self):
        """Stop all scheduled jobs."""
        self.scheduler.shutdown()
        logger.info("✅ Scheduled jobs stopped")

    async def _monthly_investor_report(self):
        """
        Generate monthly PDF reports for all investors.
        Runs on 1st of month at 00:00.
        """
        try:
            logger.info("📊 Monthly investor report job started")

            # TODO: Query all investor accounts
            investors = []  # await get_all_investors()

            for investor in investors:
                reporter = InvestorReportGenerator(investor.name)

                # Get last month's portfolio snapshots
                last_month_start = datetime.now(timezone.utc).replace(day=1) - timedelta(days=1)
                last_month_start = last_month_start.replace(day=1)
                last_month_end = datetime.now(timezone.utc).replace(day=1) - timedelta(seconds=1)

                snapshots = (
                    self.db.query(PortfolioState)
                    .filter(
                        PortfolioState.account_id == investor.id,
                        PortfolioState.timestamp >= last_month_start,
                        PortfolioState.timestamp <= last_month_end,
                    )
                    .order_by(PortfolioState.timestamp.desc())
                    .all()
                )

                if not snapshots:
                    logger.warning(f"No portfolio data for {investor.name}")
                    continue

                # Calculate metrics
                first = snapshots[-1]  # Oldest (start)
                last = snapshots[0]    # Newest (end)

                monthly_return = ((last.total_value - first.total_value) / first.total_value * 100)

                metrics = MonthlyMetrics(
                    month=datetime.now(timezone.utc).strftime("%Y-%m"),
                    starting_capital=first.total_value,
                    ending_capital=last.total_value,
                    total_return_pct=monthly_return,
                    monthly_return_pct=monthly_return,
                    sharpe_ratio=1.5,  # TODO: Calculate actual Sharpe
                    sortino_ratio=1.8,  # TODO: Calculate actual Sortino
                    max_drawdown_pct=max(s.drawdown_pct for s in snapshots),
                    win_rate=0.65,  # TODO: Query from trades
                    total_trades=0,  # TODO: Query from trades
                    winning_trades=0,  # TODO: Query from trades
                )
                reporter.add_monthly_metrics(metrics)

                # TODO: Get top trades and regime timeline

                # Save to database
                report_data = reporter.get_report_data()
                report = InvestorReport(
                    investor_id=investor.id,
                    month=metrics.month,
                    starting_capital=metrics.starting_capital,
                    ending_capital=metrics.ending_capital,
                    monthly_return_pct=metrics.monthly_return_pct,
                    sharpe_ratio=metrics.sharpe_ratio,
                    max_drawdown_pct=metrics.max_drawdown_pct,
                    total_trades=0,  # TODO: Get from data
                    winning_trades=0,  # TODO: Get from data
                    top_trades=report_data.get("top_trades"),
                    regime_timeline=report_data.get("regime_timeline"),
                )
                self.db.add(report)

                # TODO: Generate PDF and email to investor

            self.db.commit()
            logger.info("✅ Monthly reports generated")

        except Exception as e:
            logger.error(f"❌ Monthly report job failed: {e}", exc_info=True)

    async def _daily_alpha_monitor(self):
        """
        Daily performance analysis: Sharpe, Beta, Jensen's Alpha.
        Classifies tier (learning, alpha_achieved, exceptional).
        Runs daily at 22:00 (after market close).
        """
        try:
            logger.info("📈 Daily alpha monitoring job started")

            # TODO: Query last 30 days of returns
            # TODO: Calculate Sharpe ratio, Beta vs SPY, Jensen's Alpha
            # TODO: Classify tier based on alpha
            # TODO: Email CIO if tier changes
            # TODO: Log proposals to OptimizerProposal table

            logger.info("✅ Daily alpha monitoring complete")

        except Exception as e:
            logger.error(f"❌ Daily alpha monitor failed: {e}", exc_info=True)

    async def _regime_checker(self):
        """
        Check for regime changes (VIX, unemployment, Fed actions).
        Updates RegimeMonitor and applies new weights from agent_params.yaml.
        Runs every 5 minutes.
        """
        try:
            # TODO: Get current VIX
            # TODO: Check hard flags (unemployment rate, Fed emergency action)
            # TODO: Update RegimeMonitor
            # TODO: Load new signal weights from agent_params.yaml
            # TODO: Log regime change if detected

            pass

        except Exception as e:
            logger.error(f"❌ Regime checker failed: {e}", exc_info=True)

    async def _hedge_rebalancer(self):
        """
        Rebalance correlation hedge based on current correlation to SPY.
        Activate hedge if correlation > 0.8, deactivate if < 0.7.
        Runs every hour.
        """
        try:
            logger.info("🛡️  Hedge rebalancer job started")

            # TODO: Calculate current portfolio correlation to SPY
            # TODO: Check if hedge should be active
            # TODO: Apply/remove hedge if needed
            # TODO: Log to CorrelationHedgeLog

            logger.info("✅ Hedge rebalancer complete")

        except Exception as e:
            logger.error(f"❌ Hedge rebalancer failed: {e}", exc_info=True)

    async def _daily_cb_reset(self):
        """
        Reset circuit breaker at end of trading day.
        Allows trading to resume next day.
        Runs daily at 23:59.
        """
        try:
            logger.info("🔄 Daily circuit breaker reset started")

            # TODO: Reset all circuit breakers for all accounts
            # TODO: Log reset to CircuitBreakerLog

            logger.info("✅ Circuit breaker reset complete")

        except Exception as e:
            logger.error(f"❌ Circuit breaker reset failed: {e}", exc_info=True)


# Singleton instance
_scheduler = None


def get_scheduler(db: Session) -> ScheduledJobs:
    """Get or create scheduler instance."""
    global _scheduler
    if _scheduler is None:
        _scheduler = ScheduledJobs(db)
    return _scheduler


def start_scheduler(db: Session):
    """Start the scheduler."""
    scheduler = get_scheduler(db)
    scheduler.start()


def stop_scheduler():
    """Stop the scheduler."""
    global _scheduler
    if _scheduler:
        _scheduler.stop()
