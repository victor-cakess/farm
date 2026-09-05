"""Agronomic measures derived from daily weather. Pure functions, no I/O.

The water balance uses no crop coefficient and no soil survey, so it describes the weather
at the station rather than the water available in any particular field. Every screen that
shows it says so.
"""

import numpy as np
import pandas as pd

from src import config

SOLAR_CONSTANT = 0.0820  # MJ per square metre per minute
MJ_TO_MM = 0.408


def extraterrestrial_radiation(day_of_year, latitude_deg):
    """FAO-56 Ra, converted to millimetres of evaporation equivalent."""
    phi = np.radians(latitude_deg)
    j = 2 * np.pi * day_of_year / 365
    distance = 1 + 0.033 * np.cos(j)
    declination = 0.409 * np.sin(j - 1.39)
    # Brazil never reaches the polar cases, but clip so the arccos is always defined.
    sunset = np.arccos(np.clip(-np.tan(phi) * np.tan(declination), -1, 1))
    radiation = (
        (24 * 60 / np.pi)
        * SOLAR_CONSTANT
        * distance
        * (
            sunset * np.sin(phi) * np.sin(declination)
            + np.cos(phi) * np.cos(declination) * np.sin(sunset)
        )
    )
    return radiation * MJ_TO_MM


def hargreaves_et0(frame, latitude):
    """FAO-56 Hargreaves. Needs only the temperatures already stored."""
    spread = (frame["temp_max"] - frame["temp_min"]).clip(lower=0)
    radiation = extraterrestrial_radiation(frame["date"].dt.dayofyear, latitude)
    et0 = 0.0023 * (frame["temp_mean"] + 17.8) * np.sqrt(spread) * radiation
    return et0.where(frame[["temp_max", "temp_min", "temp_mean"]].notna().all(axis=1)).clip(
        lower=0
    )


def soil_water(frame):
    """Walk a single bucket through the record in date order.

    A day with no rain or no ET0 leaves the store untouched and records no value, so a gap
    in the record never reads as a drying soil.
    """
    store = config.SOIL_START_MM
    values = []
    for rain, et0 in zip(frame["rain_mm"], frame["et0_mm"], strict=True):
        if pd.isna(rain) or pd.isna(et0):
            values.append(None)
            continue
        store = min(max(store + rain - et0, 0.0), config.SOIL_CAPACITY_MM)
        values.append(store)
    return values


def growing_degree_days(frame):
    """Soy thermal time, base 10 C with an upper cap of 30 C. Complete days only."""
    # Both ends are clipped to [base, cap]: a tropical night above the cap contributes no
    # more growth than the cap itself, and leaving it uncapped pushes a day past the
    # theoretical daily maximum of cap - base.
    capped_max = frame["temp_max"].clip(config.GDD_BASE_C, config.GDD_CAP_C)
    floored_min = frame["temp_min"].clip(config.GDD_BASE_C, config.GDD_CAP_C)
    gdd = ((capped_max + floored_min) / 2 - config.GDD_BASE_C).clip(lower=0)
    return gdd.where(frame["hours_observed"] >= config.FULL_COVERAGE_HOURS)
