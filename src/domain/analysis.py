"""Relating municipal yield to the weather of the same season.

Municipal yield rises over time with genetics, fertiliser and management. Comparing raw
yields across seventeen years would mostly measure that trend, so yields are detrended
against a straight line through the available years, and every comparison is made on the
deviation from that line.

Which weather measure to compare against was decided by measurement, not assumption. Over
1,612 season-observations across 122 stations, correlation with the yield deviation was:

    water_deficit_days      pooled -0.216, per-station median -0.264, 77% negative
    heat_days               pooled -0.189, per-station median -0.393, 83% negative
    longest_dry_spell_days  pooled -0.024, per-station median -0.089, 66% negative
    dry_spell_jan_mar_days  pooled -0.043, per-station median -0.103, 59% negative

A run of days with no rain is therefore a poor description of drought: a season can go
without rain for a fortnight and still carry enough water in the soil. The bucket balance
and the heat counts are what track yield, so they are what the screen compares.

One station against one municipality's average is still a weak, noisy signal. The screens
present it alongside how consistently the same direction appears across every station in
the region, and never as a causal estimate.
"""

import numpy as np
import pandas as pd

from src import config

# Season measures worth comparing against yield, in the order the screen offers them.
FEATURES = {
    "water_deficit_days": "Dias com solo seco",
    "heat_days": f"Dias acima de {config.HEAT_STRESS_C:.0f} C",
    "rain_total_mm": "Chuva total da safra (mm)",
    "longest_dry_spell_days": "Maior sequencia sem chuva (dias)",
}


def detrend(frame, value="yield_sc_ha", year="year"):
    """Add trend and deviation columns. Deviation is percent away from the trend line."""
    frame = frame.dropna(subset=[value]).sort_values(year).copy()
    if len(frame) < 3:
        frame["trend"] = np.nan
        frame["deviation_pct"] = np.nan
        return frame

    slope, intercept = np.polyfit(frame[year], frame[value], 1)
    frame["trend"] = slope * frame[year] + intercept
    frame["deviation_pct"] = (frame[value] / frame["trend"] - 1) * 100
    return frame


def yield_with_seasons(municipal, seasons):
    """Join municipal yield to the station's season features, sufficient seasons only.

    The municipal harvest year and the season's harvest year carry the same label, which
    is why the season window is defined to end inside that year.
    """
    if municipal.empty or seasons.empty:
        return pd.DataFrame()

    yields = municipal.copy()
    yields["yield_sc_ha"] = yields["yield_kg_ha"].astype(float) / config.SACA_KG
    usable = seasons[seasons["sufficient"]]
    joined = yields.merge(usable, left_on="year", right_on="harvest_year", how="inner")
    return detrend(joined)


def feature_correlation(joined, feature):
    """Correlation between a season measure and the yield deviation, or None if too thin."""
    if len(joined) < config.MIN_SEASONS_FOR_COMPARISON:
        return None
    subset = joined.dropna(subset=[feature, "deviation_pct"])
    # A measure that barely varies across the seasons cannot be correlated with anything.
    if len(subset) < config.MIN_SEASONS_FOR_COMPARISON or subset[feature].nunique() < 3:
        return None

    return {
        "r": float(subset[feature].corr(subset["deviation_pct"])),
        "n": len(subset),
        "first_year": int(subset["year"].min()),
        "last_year": int(subset["year"].max()),
    }


def prepare_pooled(pooled):
    """Detrend every station's series separately, so deviations are comparable."""
    if pooled.empty:
        return pooled
    frame = pooled.copy()
    frame["yield_sc_ha"] = frame["yield_kg_ha"].astype(float) / config.SACA_KG
    parts = [
        detrend(group)
        for _, group in frame.groupby("station_code", sort=False)
        if len(group) >= 3
    ]
    return pd.concat(parts, ignore_index=True) if parts else pooled.iloc[0:0]


def regional_consistency(pooled, feature):
    """How often the same direction shows up across every station in the region.

    A single station has too few seasons to be convincing on its own. This says whether
    the region agrees, which is the honest way to read one noisy local number.
    """
    correlations = []
    for _, group in pooled.groupby("station_code"):
        subset = group.dropna(subset=[feature, "deviation_pct"])
        if len(subset) < config.MIN_SEASONS_FOR_COMPARISON or subset[feature].nunique() < 3:
            continue
        value = subset[feature].corr(subset["deviation_pct"])
        if pd.notna(value):
            correlations.append(value)

    if not correlations:
        return None
    negative = sum(1 for value in correlations if value < 0)
    return {
        "stations": len(correlations),
        "negative": negative,
        "negative_share": negative / len(correlations),
        "median_r": float(np.median(correlations)),
    }
