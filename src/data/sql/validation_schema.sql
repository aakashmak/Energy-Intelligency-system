-- ── model_validation — SARIMA accuracy metrics ───────────────────────────────
-- One row per (region, commodity) per validation run.
-- Computed via walk-forward cross-validation (80% train / 20% test).
CREATE TABLE IF NOT EXISTS model_validation (
    region        TEXT             NOT NULL,
    commodity     TEXT             NOT NULL,
    model         TEXT,                        -- e.g. 'SARIMA(1,1,1)(1,1,0)[12]'
    mae           DOUBLE PRECISION,            -- Mean Absolute Error
    rmse          DOUBLE PRECISION,            -- Root Mean Squared Error
    mape          DOUBLE PRECISION,            -- Mean Absolute Percentage Error (%)
    aic           DOUBLE PRECISION,            -- Akaike Information Criterion
    bic           DOUBLE PRECISION,            -- Bayesian Information Criterion
    skill_score   DOUBLE PRECISION,            -- % improvement vs naive baseline
    grade         TEXT,                        -- A / B / C / D
    train_months  INTEGER,
    test_months   INTEGER,
    train_end     TEXT,
    test_start    TEXT,
    test_end      TEXT,
    unit          TEXT,
    validated_at  TIMESTAMPTZ DEFAULT NOW(),
    PRIMARY KEY (region, commodity)
);
