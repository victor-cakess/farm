CREATE TABLE IF NOT EXISTS stations (
    code      text PRIMARY KEY,
    name      text NOT NULL,
    uf        text NOT NULL,
    latitude  double precision,
    longitude double precision
);

CREATE TABLE IF NOT EXISTS weather_daily (
    station_code text NOT NULL REFERENCES stations (code),
    date         date NOT NULL,
    rain_mm      double precision,
    temp_mean    double precision,
    temp_max     double precision,
    temp_min     double precision,
    wind_mean    double precision,
    frost_flag   boolean,
    -- Hours with a temperature reading, out of 24. Roughly 10 percent of station-days
    -- report only part of the day, which biases temp_min warm and rain_mm low, so the
    -- screens use this to qualify frost counts rather than hiding the gap.
    hours_observed smallint,
    PRIMARY KEY (station_code, date)
);

-- Screen 3 joins weather to price on date across all stations.
CREATE INDEX IF NOT EXISTS weather_daily_date_idx ON weather_daily (date);

CREATE TABLE IF NOT EXISTS price_daily (
    date      date PRIMARY KEY,
    price_brl numeric,
    price_usd numeric
);
