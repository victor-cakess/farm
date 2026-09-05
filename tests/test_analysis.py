"""Detrending and the yield-versus-weather comparison.

These functions carry the product's central claim, and the guards below are what stop a
single observation being presented as a finding.
"""

import numpy as np
import pandas as pd
import pytest

from src import config
from src.domain import analysis


def yield_frame(years, kg_ha):
    return pd.DataFrame({"year": years, "yield_kg_ha": kg_ha})


def season_frame(years, water_deficit_days, sufficient=True):
    return pd.DataFrame(
        {
            "harvest_year": years,
            "water_deficit_days": water_deficit_days,
            "heat_days": 10,
            "rain_total_mm": 900.0,
            "longest_dry_spell_days": 8,
            "sufficient": sufficient,
        }
    )


class TestDetrend:
    def test_deviations_average_out_around_zero(self):
        frame = pd.DataFrame({"year": range(2010, 2020), "yield_sc_ha": np.arange(40, 50)})
        result = analysis.detrend(frame)
        assert result["deviation_pct"].mean() == pytest.approx(0, abs=0.5)

    def test_a_pure_trend_leaves_no_deviation(self):
        frame = pd.DataFrame(
            {"year": range(2010, 2020), "yield_sc_ha": np.arange(40, 50.0)}
        )
        result = analysis.detrend(frame)
        assert result["deviation_pct"].abs().max() == pytest.approx(0, abs=1e-9)

    def test_a_bad_year_shows_as_negative(self):
        values = list(np.arange(40, 50.0))
        values[5] = 20.0
        frame = pd.DataFrame({"year": range(2010, 2020), "yield_sc_ha": values})
        result = analysis.detrend(frame)
        assert result.loc[result["year"] == 2015, "deviation_pct"].iloc[0] < -30

    def test_too_few_points_to_fit_a_line(self):
        frame = pd.DataFrame({"year": [2020, 2021], "yield_sc_ha": [40.0, 42.0]})
        result = analysis.detrend(frame)
        assert result["deviation_pct"].isna().all()


class TestYieldWithSeasons:
    def test_converts_kilos_to_sacas(self):
        joined = analysis.yield_with_seasons(
            yield_frame([2020, 2021, 2022], [3000.0, 3060.0, 3120.0]),
            season_frame([2020, 2021, 2022], [10, 20, 30]),
        )
        assert joined["yield_sc_ha"].iloc[0] == pytest.approx(3000.0 / config.SACA_KG)

    def test_insufficient_seasons_are_excluded(self):
        joined = analysis.yield_with_seasons(
            yield_frame([2020, 2021, 2022], [3000.0, 3060.0, 3120.0]),
            season_frame([2020, 2021, 2022], [10, 20, 30], sufficient=[True, False, True]),
        )
        assert sorted(joined["year"]) == [2020, 2022]

    def test_empty_inputs(self):
        assert analysis.yield_with_seasons(pd.DataFrame(), pd.DataFrame()).empty


def _joined(n=12, deficit=None):
    years = list(range(2010, 2010 + n))
    deficit = deficit if deficit is not None else [10 + i for i in range(n)]
    return analysis.yield_with_seasons(
        yield_frame(years, [3000.0 + 30 * i for i in range(n)]),
        season_frame(years, deficit),
    )


class TestFeatureCorrelation:
    def test_reports_r_and_the_sample(self):
        result = analysis.feature_correlation(_joined(), "water_deficit_days")
        assert result is not None
        assert -1 <= result["r"] <= 1
        assert result["n"] == 12

    def test_withheld_below_the_minimum_seasons(self):
        thin = _joined(n=config.MIN_SEASONS_FOR_COMPARISON - 1)
        assert analysis.feature_correlation(thin, "water_deficit_days") is None

    def test_withheld_when_the_measure_barely_varies(self):
        # A measure with two distinct values across a decade correlates with anything.
        flat = _joined(deficit=[10] * 6 + [11] * 6)
        assert analysis.feature_correlation(flat, "water_deficit_days") is None


class TestRegionalConsistency:
    # Deliberately not monotonic in the year: a deficit that rises with time would be
    # absorbed by the trend line, leaving no residual to correlate against.
    DEFICIT = [10, 90, 20, 80, 30, 70, 40, 60, 50, 100]

    def _pooled(self, stations, deficit=None):
        deficit = deficit if deficit is not None else self.DEFICIT
        parts = []
        for code, sign in stations.items():
            n = len(deficit)
            parts.append(
                pd.DataFrame(
                    {
                        "station_code": code,
                        "year": range(2010, 2010 + n),
                        # A rising trend plus a term that moves with the deficit in the
                        # direction `sign`.
                        "yield_kg_ha": [
                            3000.0 + 30 * i + sign * 20 * deficit[i] for i in range(n)
                        ],
                        "water_deficit_days": deficit,
                    }
                )
            )
        return pd.concat(parts, ignore_index=True)

    def test_counts_stations_pointing_the_same_way(self):
        # Two stations where more deficit tracks lower yield, one where it does not.
        pooled = self._pooled({"A": -1, "B": -1, "C": +1})
        prepared = analysis.prepare_pooled(pooled)
        result = analysis.regional_consistency(prepared, "water_deficit_days")
        assert result["stations"] == 3
        assert result["negative"] == 2
        assert result["negative_share"] == pytest.approx(2 / 3)
        assert result["median_r"] < 0

    def test_none_when_nothing_qualifies(self):
        # Three seasons is below MIN_SEASONS_FOR_COMPARISON.
        pooled = self._pooled({"A": -1}, deficit=[10, 50, 30])
        prepared = analysis.prepare_pooled(pooled)
        assert analysis.regional_consistency(prepared, "water_deficit_days") is None

    def test_prepare_pooled_detrends_each_station_separately(self):
        pooled = self._pooled({"A": -1, "B": +1})
        prepared = analysis.prepare_pooled(pooled)
        assert "deviation_pct" in prepared.columns
        assert set(prepared["station_code"]) == {"A", "B"}
        # Each station is centred on its own trend, not on a pooled one.
        for _, group in prepared.groupby("station_code"):
            assert group["deviation_pct"].mean() == pytest.approx(0, abs=1.0)
