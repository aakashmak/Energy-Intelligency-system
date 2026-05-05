-- Colorado DJ Basin Case Study — 4 new tables
-- Run this in Supabase SQL Editor before running aggregator.py

-- ── Monthly basin totals ──────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS colorado_monthly (
    period              date PRIMARY KEY,
    year                integer NOT NULL,
    month               integer NOT NULL,
    oil_bbl             numeric,
    gas_mcf             numeric,
    water_bbl           numeric,
    active_wells        integer,
    active_operators    integer,
    computed_at         timestamptz DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_colorado_monthly_year ON colorado_monthly(year);

-- ── Formation-level annual totals ─────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS colorado_formations (
    year                integer NOT NULL,
    formation           text NOT NULL,
    oil_bbl             numeric,
    gas_mcf             numeric,
    wells               integer,
    computed_at         timestamptz DEFAULT now(),
    PRIMARY KEY (year, formation)
);

CREATE INDEX IF NOT EXISTS idx_colorado_formations_year ON colorado_formations(year);

-- ── Top operators (lifetime) ──────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS colorado_operators (
    operator            text PRIMARY KEY,
    oil_bbl             numeric,
    gas_mcf             numeric,
    wells               integer,
    years_active        integer,
    computed_at         timestamptz DEFAULT now()
);

-- ── Normalized decline curve ──────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS colorado_decline_curve (
    month_index             integer PRIMARY KEY,
    avg_oil_bbl             numeric,
    avg_gas_mcf             numeric,
    well_count              integer,
    oil_pct_of_month1       numeric,
    gas_pct_of_month1       numeric,
    computed_at             timestamptz DEFAULT now()
);
