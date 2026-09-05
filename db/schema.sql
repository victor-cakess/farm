-- Full schema. Postgres runs this once, on an empty volume.
--
-- There is no migration path: the database is rebuilt from source with `make reset`
-- followed by `make ingest`, and every loader upserts, so the data is reproducible.
-- Table order below follows the foreign keys.

-- IBGE municipalities, for the states in TARGET_UFS.
CREATE TABLE municipalities (
    ibge_code integer PRIMARY KEY,
    name      text NOT NULL,
    uf        text NOT NULL
);

-- INMET automatic weather stations. ibge_code is the municipality the station sits in,
-- which is how weather is joined to municipal yield.
CREATE TABLE stations (
    code      text PRIMARY KEY,
    name      text NOT NULL,
    uf        text NOT NULL,
    latitude  double precision,
    longitude double precision,
    ibge_code integer REFERENCES municipalities (ibge_code)
);

-- One row per station per day, aggregated from hourly INMET records.
-- rain_mm is null, never zero, on a day with no rain reading: a gap in the record must
-- never be presented as a dry day.
CREATE TABLE weather_daily (
    station_code text NOT NULL REFERENCES stations (code),
    date         date NOT NULL,
    rain_mm      double precision,
    temp_mean    double precision,
    temp_max     double precision,
    temp_min     double precision,
    wind_mean    double precision,
    frost_flag   boolean,
    -- Hours with a temperature reading, out of 24. Only about half of station-days report
    -- all 24, and a partial day biases temp_min warm, so frost and heat counts are taken
    -- only over days with at least FULL_COVERAGE_HOURS.
    hours_observed smallint,
    -- Filled by `make derive`, null wherever the inputs are missing.
    et0_mm         double precision,
    soil_water_mm  double precision,
    gdd            double precision,
    PRIMARY KEY (station_code, date)
);

-- Screen 3 joins weather to price on date across all stations.
CREATE INDEX weather_daily_date_idx ON weather_daily (date);

-- One row per station per harvest year: 1 Oct of year-1 through 30 Apr of year.
CREATE TABLE season_features (
    station_code           text NOT NULL REFERENCES stations (code),
    harvest_year           smallint NOT NULL,
    total_days             smallint NOT NULL,
    rain_days_observed     smallint NOT NULL,
    complete_days          smallint NOT NULL,
    rain_total_mm          double precision,
    longest_dry_spell_days smallint,
    dry_spell_jan_mar_days smallint,
    frost_days             smallint,
    heat_days              smallint,
    gdd_total              double precision,
    water_deficit_days     smallint,
    -- False when the station reported too little of the season to describe it. Insufficient
    -- seasons are excluded from every comparison rather than quietly weakening it.
    sufficient             boolean NOT NULL,
    PRIMARY KEY (station_code, harvest_year)
);

-- Municipal average soy yield. Source IBGE PAM, table 1612, soy in grain (c81 2713).
-- This is the municipality average and is never presented as one farm's yield.
CREATE TABLE yield_municipal (
    ibge_code    integer NOT NULL REFERENCES municipalities (ibge_code),
    year         smallint NOT NULL,
    yield_kg_ha  numeric,
    area_ha      numeric,
    production_t numeric,
    PRIMARY KEY (ibge_code, year)
);

-- One row per municipality per forecast day per period, overwritten on every refresh.
-- INMET publishes five days and no rain amount, only the text summary.
CREATE TABLE forecast (
    ibge_code     integer NOT NULL REFERENCES municipalities (ibge_code),
    forecast_date date NOT NULL,
    period        text NOT NULL,
    issued_at     timestamptz NOT NULL,
    resumo        text,
    temp_min      smallint,
    temp_max      smallint,
    umidade_min   smallint,
    umidade_max   smallint,
    dir_vento     text,
    int_vento     text,
    cod_icone     text,
    PRIMARY KEY (ibge_code, forecast_date, period)
);

-- CEPEA/ESALQ Soja Paranagua indicator. Business days only, so gaps are expected.
CREATE TABLE price_daily (
    date      date PRIMARY KEY,
    price_brl numeric,
    price_usd numeric
);

-- Average price received by Parana producers, monthly. Source DERAL/SEAB.
CREATE TABLE price_monthly_pr (
    year         smallint NOT NULL,
    month        smallint NOT NULL,
    price_brl_sc numeric NOT NULL,
    PRIMARY KEY (year, month)
);

-- Same, by DERAL regional, for the most recent published week.
CREATE TABLE price_weekly_pr (
    week_date    date NOT NULL,
    regional     text NOT NULL,
    price_brl_sc numeric,
    PRIMARY KEY (week_date, regional)
);

-- One row per field per season, entered by the farmer. Single user, no auth: local POC.
CREATE TABLE farm_records (
    season_year  smallint NOT NULL,
    field_name   text NOT NULL,
    area_ha      numeric,
    yield_sc_ha  numeric NOT NULL CHECK (yield_sc_ha > 0),
    cost_brl_ha  numeric CHECK (cost_brl_ha > 0),
    notes        text,
    created_at   timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (season_year, field_name)
);

-- Reference cost of production per state and season. Source CONAB, loaded manually.
-- A farmer's own cost always takes precedence over this.
CREATE TABLE cost_reference (
    uf          text NOT NULL,
    season_year smallint NOT NULL,
    cost_brl_ha numeric NOT NULL,
    yield_sc_ha numeric,
    source      text NOT NULL,
    PRIMARY KEY (uf, season_year)
);
