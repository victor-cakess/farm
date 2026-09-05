"""The agronomic maths. Pure functions, so no database and no network."""

import numpy as np
import pandas as pd
import pytest

from src import config
from src.domain import agronomy


def daily(dates, temp_max, temp_min, temp_mean=None, rain=None, hours=24):
    """A minimal weather frame of the shape the derivation expects."""
    frame = pd.DataFrame(
        {
            "date": pd.to_datetime(dates),
            "temp_max": temp_max,
            "temp_min": temp_min,
        }
    )
    frame["temp_mean"] = (
        temp_mean if temp_mean is not None else (frame["temp_max"] + frame["temp_min"]) / 2
    )
    frame["rain_mm"] = rain if rain is not None else 0.0
    frame["hours_observed"] = hours
    return frame


class TestExtraterrestrialRadiation:
    def test_within_physical_range_across_the_year(self):
        days = np.arange(1, 366)
        values = agronomy.extraterrestrial_radiation(pd.Series(days), -15.0)
        # Ra in evaporation-equivalent mm/day never leaves this band in the tropics.
        assert values.min() > 8
        assert values.max() < 19

    def test_southern_summer_exceeds_southern_winter(self):
        january = agronomy.extraterrestrial_radiation(pd.Series([15]), -25.0).iloc[0]
        july = agronomy.extraterrestrial_radiation(pd.Series([196]), -25.0).iloc[0]
        assert january > july

    def test_defined_at_extreme_latitudes(self):
        # The arccos is clipped, so a polar latitude must not produce NaN.
        value = agronomy.extraterrestrial_radiation(pd.Series([180]), -89.0).iloc[0]
        assert np.isfinite(value)


class TestHargreavesEt0:
    def test_plausible_magnitude(self):
        frame = daily(["2024-01-15"], [32.0], [20.0])
        et0 = agronomy.hargreaves_et0(frame, -15.0).iloc[0]
        assert 3 < et0 < 9

    def test_null_when_a_temperature_is_missing(self):
        frame = daily(["2024-01-15", "2024-01-16"], [32.0, np.nan], [20.0, 20.0])
        et0 = agronomy.hargreaves_et0(frame, -15.0)
        assert pd.notna(et0.iloc[0])
        assert pd.isna(et0.iloc[1])

    def test_never_negative(self):
        # temp_max below temp_min is nonsense, but must not produce a negative demand.
        frame = daily(["2024-06-01"], [10.0], [18.0], temp_mean=-30.0)
        assert agronomy.hargreaves_et0(frame, -25.0).iloc[0] >= 0


class TestSoilWater:
    def _frame(self, rain, et0):
        return pd.DataFrame({"rain_mm": rain, "et0_mm": et0})

    def test_never_leaves_the_bucket(self):
        # Alternating drenching and drought must stay inside [0, capacity].
        rain = [200.0, 0.0, 0.0, 0.0, 300.0, 0.0]
        et0 = [1.0, 40.0, 40.0, 40.0, 1.0, 50.0]
        values = agronomy.soil_water(self._frame(rain, et0))
        assert all(0.0 <= v <= config.SOIL_CAPACITY_MM for v in values)

    def test_fills_to_capacity_and_no_further(self):
        values = agronomy.soil_water(self._frame([500.0], [0.0]))
        assert values[0] == config.SOIL_CAPACITY_MM

    def test_gap_records_nothing_and_carries_the_store(self):
        # The day with no rain reading must not drain the soil, and must store no value:
        # a gap in the record is unknown, not dry.
        rain = [0.0, np.nan, 0.0]
        et0 = [0.0, 5.0, 0.0]
        values = agronomy.soil_water(self._frame(rain, et0))
        assert values[1] is None
        assert values[2] == values[0] == config.SOIL_START_MM

    def test_missing_et0_also_skips_the_day(self):
        values = agronomy.soil_water(self._frame([5.0, 5.0], [np.nan, 0.0]))
        assert values[0] is None
        assert values[1] == config.SOIL_START_MM + 5.0


class TestGrowingDegreeDays:
    def test_caps_at_exactly_cap_minus_base(self):
        # A 35 C tropical night with a 41 C day is real in Mato Grosso. Clipping only the
        # maximum let such a day score 22.5, past the theoretical daily maximum of 20.
        frame = daily(["2024-11-11"], [41.0], [35.0])
        gdd = agronomy.growing_degree_days(frame).iloc[0]
        assert gdd == pytest.approx(config.GDD_CAP_C - config.GDD_BASE_C)

    def test_zero_below_the_base(self):
        frame = daily(["2024-07-01"], [8.0], [2.0])
        assert agronomy.growing_degree_days(frame).iloc[0] == 0

    def test_ordinary_day(self):
        frame = daily(["2024-01-15"], [30.0], [20.0])
        assert agronomy.growing_degree_days(frame).iloc[0] == pytest.approx(15.0)

    def test_null_on_an_incomplete_day(self):
        frame = daily(["2024-01-15"], [30.0], [20.0], hours=config.FULL_COVERAGE_HOURS - 1)
        assert pd.isna(agronomy.growing_degree_days(frame).iloc[0])
