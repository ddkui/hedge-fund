#!/usr/bin/env python3
"""Run once to create the TimescaleDB schema. Requires Docker services running."""
import asyncio
import asyncpg
import sys
sys.path.insert(0, ".")
from shared.config import settings

SCHEMA = """
CREATE EXTENSION IF NOT EXISTS timescaledb;

CREATE TABLE IF NOT EXISTS prices (
    time        TIMESTAMPTZ NOT NULL,
    symbol      TEXT NOT NULL,
    asset_class TEXT NOT NULL,
    open        DOUBLE PRECISION,
    high        DOUBLE PRECISION,
    low         DOUBLE PRECISION,
    close       DOUBLE PRECISION NOT NULL,
    volume      DOUBLE PRECISION
);
SELECT create_hypertable('prices', 'time', if_not_exists => TRUE);
CREATE INDEX IF NOT EXISTS prices_symbol_time ON prices (symbol, time DESC);

CREATE TABLE IF NOT EXISTS signals (
    time        TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    agent       TEXT NOT NULL,
    symbol      TEXT,
    signal_type TEXT NOT NULL,
    confidence  DOUBLE PRECISION,
    reasoning   TEXT,
    metadata    JSONB
);
SELECT create_hypertable('signals', 'time', if_not_exists => TRUE);

CREATE TABLE IF NOT EXISTS positions (
    id              SERIAL PRIMARY KEY,
    symbol          TEXT NOT NULL,
    asset_class     TEXT NOT NULL,
    direction       TEXT NOT NULL,
    quantity        DOUBLE PRECISION NOT NULL,
    entry_price     DOUBLE PRECISION NOT NULL,
    entry_time      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    entry_thesis    TEXT,
    status          TEXT NOT NULL DEFAULT 'open',
    exit_price      DOUBLE PRECISION,
    exit_time       TIMESTAMPTZ
);

CREATE TABLE IF NOT EXISTS trades (
    id          SERIAL PRIMARY KEY,
    time        TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    position_id INTEGER REFERENCES positions(id),
    action      TEXT NOT NULL,
    symbol      TEXT NOT NULL,
    quantity    DOUBLE PRECISION NOT NULL,
    price       DOUBLE PRECISION NOT NULL,
    paper       BOOLEAN NOT NULL DEFAULT TRUE,
    status      TEXT NOT NULL DEFAULT 'pending',
    pm_reasoning TEXT,
    confidence  DOUBLE PRECISION
);

CREATE TABLE IF NOT EXISTS quant_algos (
    id              SERIAL PRIMARY KEY,
    name            TEXT NOT NULL,
    quant_agent     TEXT NOT NULL,
    strategy_type   TEXT NOT NULL,
    status          TEXT NOT NULL DEFAULT 'testing',
    sharpe_ratio    DOUBLE PRECISION,
    max_drawdown    DOUBLE PRECISION,
    win_rate        DOUBLE PRECISION,
    trade_count     INTEGER,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    retired_at      TIMESTAMPTZ,
    retirement_reason TEXT,
    config          JSONB
);

CREATE TABLE IF NOT EXISTS agent_health (
    time        TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    agent       TEXT NOT NULL,
    status      TEXT NOT NULL,
    message     TEXT,
    metadata    JSONB
);
SELECT create_hypertable('agent_health', 'time', if_not_exists => TRUE);

-- Unique constraint on prices for idempotent inserts
DO $$ BEGIN
    ALTER TABLE prices ADD CONSTRAINT prices_time_symbol_unique UNIQUE (time, symbol);
EXCEPTION WHEN duplicate_object THEN NULL;
END $$;

CREATE TABLE IF NOT EXISTS macro_data (
    time        TIMESTAMPTZ NOT NULL,
    series_id   TEXT NOT NULL,
    value       DOUBLE PRECISION NOT NULL,
    source      TEXT NOT NULL DEFAULT 'FRED',
    UNIQUE (time, series_id)
);

CREATE TABLE IF NOT EXISTS news_items (
    id              SERIAL PRIMARY KEY,
    time            TIMESTAMPTZ NOT NULL,
    source          TEXT NOT NULL,
    headline        TEXT NOT NULL,
    url             TEXT NOT NULL DEFAULT '',
    sentiment_score DOUBLE PRECISION,
    UNIQUE (time, source, headline)
);

CREATE TABLE IF NOT EXISTS sec_filings (
    id          SERIAL PRIMARY KEY,
    time        TIMESTAMPTZ NOT NULL,
    ticker      TEXT NOT NULL,
    form_type   TEXT NOT NULL,
    period      TEXT NOT NULL,
    filing_url  TEXT NOT NULL,
    summary     TEXT,
    UNIQUE (ticker, form_type, period)
);

CREATE TABLE IF NOT EXISTS portfolio_state (
    id             SERIAL PRIMARY KEY,
    time           TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    cash           DOUBLE PRECISION NOT NULL,
    total_value    DOUBLE PRECISION NOT NULL,
    peak_value     DOUBLE PRECISION NOT NULL,
    open_positions INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS risk_events (
    id           SERIAL PRIMARY KEY,
    time         TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    agent        TEXT NOT NULL,
    symbol       TEXT,
    limit_type   TEXT NOT NULL,
    details      TEXT NOT NULL,
    action_taken TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_portfolio_state_time ON portfolio_state(time DESC);
CREATE INDEX IF NOT EXISTS idx_risk_events_time ON risk_events(time DESC);
CREATE INDEX IF NOT EXISTS idx_risk_events_agent_time ON risk_events(agent, time DESC);

CREATE TABLE IF NOT EXISTS kronos_forecasts (
    id                  BIGSERIAL,
    time                TIMESTAMPTZ NOT NULL,
    symbol              TEXT NOT NULL,
    model               TEXT NOT NULL DEFAULT 'NeoQuasar/Kronos-mini',
    lookback_candles    INTEGER,
    pred_horizon_candles INTEGER,
    pred_close          DOUBLE PRECISION,
    pred_change_pct     DOUBLE PRECISION,
    signal_type         TEXT,
    confidence          DOUBLE PRECISION,
    pred_high           DOUBLE PRECISION,
    pred_low            DOUBLE PRECISION,
    reasoning           TEXT
);
SELECT create_hypertable('kronos_forecasts', 'time', if_not_exists => TRUE);
CREATE INDEX IF NOT EXISTS kronos_forecasts_symbol_time ON kronos_forecasts (symbol, time DESC);

CREATE TABLE IF NOT EXISTS broker_fills (
    id              BIGSERIAL,
    time            TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    trade_id        INTEGER REFERENCES trades(id),
    broker_name     TEXT NOT NULL,
    status          TEXT NOT NULL,
    fill_price      DOUBLE PRECISION,
    fill_qty        DOUBLE PRECISION,
    error_msg       TEXT
);
CREATE INDEX IF NOT EXISTS broker_fills_trade_id ON broker_fills(trade_id);
CREATE INDEX IF NOT EXISTS broker_fills_broker_time ON broker_fills(broker_name, time DESC);

CREATE TABLE IF NOT EXISTS signal_outcomes (
    id              BIGSERIAL PRIMARY KEY,
    time            TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    agent           TEXT NOT NULL,
    symbol          TEXT,
    signal_type     TEXT NOT NULL,
    confidence      DOUBLE PRECISION,
    regime          TEXT NOT NULL DEFAULT 'unknown',
    entry_price     DOUBLE PRECISION,
    exit_price      DOUBLE PRECISION,
    pnl             DOUBLE PRECISION,
    was_correct     BOOLEAN,
    horizon_candles INTEGER
);
CREATE INDEX IF NOT EXISTS signal_outcomes_agent_regime ON signal_outcomes(agent, regime, time DESC);

CREATE TABLE IF NOT EXISTS optimizer_proposals (
    id              BIGSERIAL PRIMARY KEY,
    time            TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    agent           TEXT NOT NULL,
    regime          TEXT NOT NULL,
    param_name      TEXT NOT NULL,
    current_value   DOUBLE PRECISION,
    proposed_value  DOUBLE PRECISION,
    change_pct      DOUBLE PRECISION,
    reason          TEXT,
    status          TEXT NOT NULL DEFAULT 'pending',
    reviewed_at     TIMESTAMPTZ,
    reviewed_by     TEXT
);

CREATE TABLE IF NOT EXISTS optimizer_history (
    id              BIGSERIAL PRIMARY KEY,
    time            TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    agent           TEXT,
    regime          TEXT,
    param_name      TEXT,
    old_value       DOUBLE PRECISION,
    new_value       DOUBLE PRECISION,
    reason          TEXT,
    auto_applied    BOOLEAN DEFAULT TRUE
);

CREATE OR REPLACE FUNCTION now_or_backtest()
RETURNS timestamptz AS $$
  SELECT COALESCE(
    NULLIF(current_setting('backtest.now', true), '')::timestamptz,
    NOW()
  )
$$ LANGUAGE SQL STABLE;
"""

async def main():
    print("Connecting to TimescaleDB...")
    conn = await asyncpg.connect(settings.db_dsn)
    print("Creating schema...")
    await conn.execute(SCHEMA)
    await conn.close()
    print("Schema created successfully.")

if __name__ == "__main__":
    asyncio.run(main())
