"""Season windows and the counts taken inside them."""

import numpy as np
import pandas as pd

from src import config
from src.domain import seasons


class TestSeasonBounds:
    def test_runs_october_to_april(self):
        start, end = seasons.season_bounds(2025)
        assert (start.year, start.month, start.day) == (2024, 10, 1)
        assert (end.year, end.month, end.day) == (2025, 4, 30)

    def test_slice_excludes_days_outside_the_window(self):
        weather = pd.DataFrame(
            {
                "date": pd.to_datetime(
                    ["2024-09-30", "2024-10-01", "2025-04-30", "2025-05-01"]
                )
            }
        )
        inside = seasons.season_slice(weather, 2025)
        assert list(inside["date"].dt.strftime("%Y-%m-%d")) == ["2024-10-01", "2025-04-30"]


class TestLatestHarvestYear:
    def test_after_april_the_season_of_that_year_has_ended(self):
        assert seasons.latest_harvest_year(pd.Timestamp("2025-12-31")) == 2025

    def test_during_the_season_the_previous_one_is_the_latest_finished(self):
        assert seasons.latest_harvest_year(pd.Timestamp("2025-03-15")) == 2024

    def test_boundary_at_the_end_of_april(self):
        assert seasons.latest_harvest_year(pd.Timestamp("2025-04-30")) == 2024
        assert seasons.latest_harvest_year(pd.Timestamp("2025-05-01")) == 2025


class TestLongestDrySpell:
    def test_counts_consecutive_zero_rain_days(self):
        assert seasons.longest_dry_spell(pd.Series([0.0, 0.0, 0.0, 5.0, 0.0])) == 3

    def test_a_gap_breaks_the_run_rather_than_extending_it(self):
        # The central day was never reported. Treating it as dry would report a 5-day
        # drought that never happened, which is the failure this rule exists to prevent.
        rain = pd.Series([0.0, 0.0, np.nan, 0.0, 0.0])
        assert seasons.longest_dry_spell(rain) == 2

    def test_all_missing_is_not_a_drought(self):
        assert seasons.longest_dry_spell(pd.Series([np.nan, np.nan, np.nan])) == 0

    def test_no_dry_days(self):
        assert seasons.longest_dry_spell(pd.Series([1.0, 2.0])) == 0


def _season_frame(
    station="A001",
    rain=0.0,
    hours=24,
    temp_max=25.0,
    gdd=10.0,
    soil=50.0,
    frost=False,
    start="2024-10-01",
    days=212,
):
    dates = pd.date_range(start, periods=days, freq="D")
    return pd.DataFrame(
        {
            "station_code": station,
            "date": dates,
            "rain_mm": rain,
            "hours_observed": hours,
            "temp_max": temp_max,
            "frost_flag": frost,
            "gdd": gdd,
            "soil_water_mm": soil,
        }
    )


class TestSeasonRows:
    def test_emits_columns_in_the_declared_order(self):
        rows = seasons.season_rows(_season_frame())
        assert len(rows[0]) == len(seasons.SEASON_COLUMNS)

    def test_full_season_is_sufficient(self):
        rows = seasons.season_rows(_season_frame())
        row = dict(zip(seasons.SEASON_COLUMNS, rows[0], strict=True))
        assert row["harvest_year"] == 2025
        assert row["total_days"] == 212
        assert row["sufficient"] is True

    def test_denominator_is_the_calendar_season_not_the_rows_present(self):
        # A station reporting only the first month must be measured against the whole
        # season, so it comes out insufficient rather than looking complete.
        rows = seasons.season_rows(_season_frame(days=30))
        row = dict(zip(seasons.SEASON_COLUMNS, rows[0], strict=True))
        assert row["total_days"] == 212
        assert row["rain_days_observed"] == 30
        assert row["sufficient"] is False

    def test_incomplete_days_are_excluded_from_frost_and_heat(self):
        frame = _season_frame(
            hours=config.FULL_COVERAGE_HOURS - 1, frost=True, temp_max=40.0
        )
        row = dict(zip(seasons.SEASON_COLUMNS, seasons.season_rows(frame)[0], strict=True))
        assert row["complete_days"] == 0
        assert row["frost_days"] is None
        assert row["heat_days"] is None
        assert row["sufficient"] is False

    def test_water_deficit_counts_days_below_the_threshold(self):
        frame = _season_frame(soil=config.SOIL_DEFICIT_MM - 1)
        row = dict(zip(seasons.SEASON_COLUMNS, seasons.season_rows(frame)[0], strict=True))
        assert row["water_deficit_days"] == 212

    def test_rain_total_is_null_when_nothing_was_measured(self):
        frame = _season_frame(rain=np.nan)
        row = dict(zip(seasons.SEASON_COLUMNS, seasons.season_rows(frame)[0], strict=True))
        assert row["rain_total_mm"] is None
        assert row["rain_days_observed"] == 0
