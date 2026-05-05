-- ============================================================
-- OilPulse — Supabase schema
-- Run ONCE in: Supabase dashboard → SQL Editor → New query
-- Safe to re-run (CREATE TABLE IF NOT EXISTS + ALTER IF NOT EXISTS)
-- ============================================================

CREATE TABLE IF NOT EXISTS regions (
    region      TEXT PRIMARY KEY,
    state_codes TEXT,
    basin_type  TEXT,
    lat         DOUBLE PRECISION,
    lon         DOUBLE PRECISION
);

CREATE TABLE IF NOT EXISTS production (
    region       TEXT        NOT NULL,
    commodity    TEXT        NOT NULL,
    period       DATE        NOT NULL,
    value        DOUBLE PRECISION,
    source       TEXT,
    unit         TEXT,
    process_name TEXT,
    product_name TEXT,
    updated_at   TIMESTAMPTZ DEFAULT NOW(),
    PRIMARY KEY (region, commodity, period)
);

CREATE TABLE IF NOT EXISTS state_production (
    state        TEXT        NOT NULL,
    commodity    TEXT        NOT NULL,
    period       DATE        NOT NULL,
    value        DOUBLE PRECISION,
    unit         TEXT,
    source       TEXT,
    process_name TEXT,
    product_name TEXT,
    process_code TEXT,
    product_code TEXT,
    updated_at   TIMESTAMPTZ DEFAULT NOW(),
    PRIMARY KEY (state, commodity, period)
);

CREATE TABLE IF NOT EXISTS rig_counts (
    region  TEXT NOT NULL,
    period  DATE NOT NULL,
    rigs    INTEGER,
    PRIMARY KEY (region, period)
);

CREATE TABLE IF NOT EXISTS forecasts (
    region      TEXT    NOT NULL,
    commodity   TEXT    NOT NULL,
    period      DATE    NOT NULL,
    forecast    DOUBLE PRECISION,
    lower_ci    DOUBLE PRECISION,
    upper_ci    DOUBLE PRECISION,
    run_date    DATE    NOT NULL,
    PRIMARY KEY (region, commodity, period, run_date)
);

CREATE TABLE IF NOT EXISTS scores (
    region             TEXT PRIMARY KEY,
    score              DOUBLE PRECISION,
    rank               INTEGER,
    projected_prod     DOUBLE PRECISION,
    yoy_growth         DOUBLE PRECISION,
    decline_rate       DOUBLE PRECISION,
    revenue_potential  DOUBLE PRECISION,
    consistency_score  DOUBLE PRECISION,
    volatility         DOUBLE PRECISION,
    rel_performance    DOUBLE PRECISION,
    momentum           DOUBLE PRECISION,
    wti_price_used     DOUBLE PRECISION,
    henry_price_used   DOUBLE PRECISION,
    computed_at        TIMESTAMPTZ DEFAULT NOW()
);

-- ── quarterly_kpis — Tier 1 Required KPI at quarterly granularity ─────────────
-- One row per (region, commodity, year, quarter).
-- Covers all historical quarters (data_type = actual) and
-- forecast quarters (data_type = forecast) up to 3 years ahead.
-- This is the table the dashboard KPI cards read directly.
--
-- value      — total production for the quarter (Mbbl/quarter or MMcf/quarter)
-- lower_ci   — 80% CI lower bound (NULL for actuals)
-- upper_ci   — 80% CI upper bound (NULL for actuals)
-- is_forecast — TRUE when SARIMA was used, FALSE for real data
-- data_type  — 'actual' | 'forecast'
-- confidence — 'high' (actual) | 'medium' (1-3yr forecast) | 'low' (3yr+)
-- qoq_growth — quarter-over-quarter % change
-- yoy_growth — same quarter vs same quarter prior year % change
CREATE TABLE IF NOT EXISTS quarterly_kpis (
    region      TEXT             NOT NULL,
    commodity   TEXT             NOT NULL,
    year        INTEGER          NOT NULL,
    quarter     TEXT             NOT NULL,   -- 'Q1' | 'Q2' | 'Q3' | 'Q4'
    value       DOUBLE PRECISION,
    lower_ci    DOUBLE PRECISION,
    upper_ci    DOUBLE PRECISION,
    is_forecast BOOLEAN          DEFAULT FALSE,
    data_type   TEXT,                        -- 'actual' | 'forecast'
    confidence  TEXT,                        -- 'high' | 'medium' | 'low'
    qoq_growth  DOUBLE PRECISION,
    yoy_growth  DOUBLE PRECISION,
    computed_at TIMESTAMPTZ      DEFAULT NOW(),
    PRIMARY KEY (region, commodity, year, quarter)
);

-- ── ALTER statements — run if tables already exist ────────────────────────────
ALTER TABLE scores ADD COLUMN IF NOT EXISTS decline_rate      DOUBLE PRECISION;
ALTER TABLE scores ADD COLUMN IF NOT EXISTS revenue_potential DOUBLE PRECISION;
ALTER TABLE scores ADD COLUMN IF NOT EXISTS consistency_score DOUBLE PRECISION;
ALTER TABLE scores ADD COLUMN IF NOT EXISTS rel_performance   DOUBLE PRECISION;
ALTER TABLE scores ADD COLUMN IF NOT EXISTS wti_price_used    DOUBLE PRECISION;
ALTER TABLE scores ADD COLUMN IF NOT EXISTS henry_price_used  DOUBLE PRECISION;

ALTER TABLE production
    ADD COLUMN IF NOT EXISTS process_name TEXT,
    ADD COLUMN IF NOT EXISTS product_name TEXT;

ALTER TABLE state_production
    ADD COLUMN IF NOT EXISTS process_name TEXT,
    ADD COLUMN IF NOT EXISTS product_name TEXT,
    ADD COLUMN IF NOT EXISTS process_code TEXT,
    ADD COLUMN IF NOT EXISTS product_code TEXT;
