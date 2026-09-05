"""Source-file parsing rules that have already bitten us once each."""

import pandas as pd
import pytest

from src.ingestion import deral, price, weather


class TestWeatherDates:
    def test_accepts_every_format_inmet_has_used(self):
        # ISO in the older archives, slashes in the recent ones.
        for value, expected in (
            ("2010-01-01", "2010-01-01"),
            ("2025/01/01", "2025-01-01"),
            ("01/02/2015", "2015-02-01"),
        ):
            parsed = weather.parse_dates(pd.Series([value]), "member.CSV")
            assert parsed.iloc[0].strftime("%Y-%m-%d") == expected

    def test_raises_on_an_unknown_format(self):
        # Coercing to NaT instead would load the year as zero rows, silently.
        with pytest.raises(ValueError, match="member.CSV"):
            weather.parse_dates(pd.Series(["Jan 1 2010"]), "member.CSV")


class TestWeatherColumns:
    def test_matches_one_column_by_keyword(self):
        columns = [
            "PRECIPITAÇÃO TOTAL, HORÁRIO (mm)",
            "TEMPERATURA DO AR - BULBO SECO, HORARIA (°C)",
            "TEMPERATURA MÁXIMA NA HORA ANT. (AUT) (°C)",
            "VENTO, RAJADA MAXIMA (m/s)",
            "VENTO, VELOCIDADE HORARIA (m/s)",
        ]
        assert weather.find_column(columns, "PRECIPITA", "m") == columns[0]
        # Must pick the hourly air temperature, not the max-in-previous-hour column.
        assert weather.find_column(columns, "TEMPERATURA DO AR", "m") == columns[1]
        # Must pick the hourly speed, not the gust.
        assert weather.find_column(columns, "VELOCIDADE HORARIA", "m") == columns[4]

    def test_raises_when_a_keyword_is_missing_or_ambiguous(self):
        with pytest.raises(ValueError, match="member.CSV"):
            weather.find_column(["A", "B"], "PRECIPITA", "member.CSV")
        with pytest.raises(ValueError, match="member.CSV"):
            weather.find_column(["PRECIPITA 1", "PRECIPITA 2"], "PRECIPITA", "member.CSV")


class TestWeatherNumbers:
    def test_sentinel_becomes_missing(self):
        # Older archives write -9999 where recent ones leave the cell empty.
        values = weather.to_numeric(pd.Series(["-9999", "12,5", ""]))
        assert pd.isna(values.iloc[0])
        assert values.iloc[1] == 12.5 or pd.isna(values.iloc[1])
        assert pd.isna(values.iloc[2])


class TestDeral:
    def test_reads_the_week_from_the_header_cell(self):
        class Sheet:
            def cell_value(self, row, column):
                assert (row, column) == deral.WEEKLY_PERIOD_CELL
                return "PERÍODO: 31/08/2026 a 04/09/2026"

        # The end of the period, not the start.
        assert deral.parse_week_end(Sheet()) == "2026-09-04"

    def test_raises_when_the_period_is_not_where_it_should_be(self):
        class Sheet:
            def cell_value(self, row, column):
                return "algo diferente"

        with pytest.raises(ValueError):
            deral.parse_week_end(Sheet())

    def test_aggregate_columns_are_skipped_despite_accents(self):
        # The sheet writes MEDIA with an accent, so upper() alone never matched it and the
        # state average was loaded as if it were a regional.
        assert deral.strip_accents("MÉDIA").upper() in deral.WEEKLY_SKIP
        assert deral.strip_accents("Cornélio Procópio").upper() not in deral.WEEKLY_SKIP


class TestPriceNumbers:
    def test_brazilian_decimals(self):
        assert price.to_number("1.234,56") == 1234.56
        assert price.to_number("119,18") == 119.18

    def test_passes_through_numbers(self):
        assert price.to_number(160.14) == 160.14

    def test_missing_and_unparseable_become_none(self):
        assert price.to_number(None) is None
        assert price.to_number(float("nan")) is None
        assert price.to_number("nao ha") is None
