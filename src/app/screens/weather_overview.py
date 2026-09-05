"""Screen 2: daily weather for the selected station."""

import altair as alt
import pandas as pd
import streamlit as st

from src import config
from src.app import queries, theme

PERIOD_LABELS = {"manha": "Manha", "tarde": "Tarde", "noite": "Noite", "dia": "Dia todo"}
# Sorting by the column would put "noite" before "tarde"; the day runs in config's order,
# with the whole-day block used by days 3 to 5 last.
PERIOD_ORDER = {name: i for i, name in enumerate(config.FORECAST_PERIODS)}
PERIOD_ORDER[config.FORECAST_WHOLE_DAY] = len(config.FORECAST_PERIODS)


def render(station):
    st.title("Clima local")
    st.caption(
        f"Estacao automatica INMET {station['code']} - {station['name']} ({station['uf']})"
    )

    _forecast(station)
    st.divider()

    weather = queries.get_weather(station["code"])
    if weather.empty:
        st.warning("Sem dados de clima para esta estacao.")
        return

    years = sorted(weather["date"].dt.year.unique(), reverse=True)
    year = st.selectbox("Ano", years)
    data = weather[weather["date"].dt.year == year].copy()

    complete = data[data["hours_observed"] >= config.FULL_COVERAGE_HOURS]
    frost_days = int(complete["frost_flag"].sum())

    left, middle, right = st.columns(3)
    rain_days = int(data["rain_mm"].notna().sum())
    left.metric("Chuva medida (mm)", f"{data['rain_mm'].sum():,.0f}".replace(",", "."))
    middle.metric("Dias de geada", frost_days)
    right.metric(
        "Dias com registro completo",
        f"{len(complete)} de {len(data)}",
    )
    st.caption(
        f"A estacao nem sempre reporta as 24 horas do dia. Os {frost_days} dias de geada "
        f"sao contados apenas entre os {len(complete)} dias com pelo menos "
        f"{config.FULL_COVERAGE_HOURS} horas registradas, para nao inventar nem perder "
        f"geadas em dias incompletos. O total de chuva soma os {rain_days} dias com "
        "leitura de chuva, entao e um minimo medido, nao a chuva total do ano."
    )

    # All three charts share the full selected year, so a stretch the station did not
    # report reads as a gap in the record instead of each chart silently zooming in on
    # whichever weeks it happens to have.
    year_axis = alt.X(
        "date:T",
        title=None,
        scale=alt.Scale(
            domain=[
                alt.DateTime(year=year, month=1, date=1),
                alt.DateTime(year=year, month=12, date=31),
            ]
        ),
    )

    st.subheader("Chuva diaria")
    rain = (
        alt.Chart(data)
        .mark_bar(color=theme.SERIES_1, cornerRadiusEnd=2)
        .encode(
            x=year_axis,
            y=alt.Y("rain_mm:Q", title="mm"),
            tooltip=[
                alt.Tooltip("date:T", title="Data", format="%d/%m/%Y"),
                alt.Tooltip("rain_mm:Q", title="Chuva (mm)", format=".1f"),
            ],
        )
    )
    st.altair_chart(theme.base(rain), width="stretch")

    st.subheader("Temperatura maxima e minima")
    band = (
        alt.Chart(data)
        .mark_area(color=theme.SERIES_2, opacity=0.18)
        .encode(
            x=year_axis,
            y=alt.Y("temp_min:Q", title="graus C", scale=alt.Scale(zero=False)),
            y2="temp_max:Q",
        )
    )
    maxima = (
        alt.Chart(data)
        .mark_line(color=theme.SERIES_2, strokeWidth=1.5)
        .encode(x="date:T", y="temp_max:Q")
    )
    minima = (
        alt.Chart(data)
        .mark_line(color=theme.SERIES_1, strokeWidth=1.5)
        .encode(
            x="date:T",
            y="temp_min:Q",
            tooltip=[
                alt.Tooltip("date:T", title="Data", format="%d/%m/%Y"),
                alt.Tooltip("temp_min:Q", title="Minima", format=".1f"),
                alt.Tooltip("temp_max:Q", title="Maxima", format=".1f"),
            ],
        )
    )
    frost = (
        alt.Chart(complete[complete["frost_flag"] == True])  # noqa: E712
        .mark_point(color=theme.CRITICAL, size=45, filled=True, shape="triangle-down")
        .encode(
            x="date:T",
            y="temp_min:Q",
            tooltip=[
                alt.Tooltip("date:T", title="Geada em", format="%d/%m/%Y"),
                alt.Tooltip("temp_min:Q", title="Minima", format=".1f"),
            ],
        )
    )
    st.altair_chart(theme.base(alt.layer(band, maxima, minima, frost)), width="stretch")
    st.caption(
        "Laranja: maxima diaria. Azul: minima diaria. "
        "Triangulo vermelho: dia marcado como geada."
    )

    st.subheader("Vento medio diario")
    wind = (
        alt.Chart(data)
        .mark_line(color=theme.SERIES_1, strokeWidth=1.5)
        .encode(
            x=year_axis,
            y=alt.Y("wind_mean:Q", title="m/s", scale=alt.Scale(zero=False)),
            tooltip=[
                alt.Tooltip("date:T", title="Data", format="%d/%m/%Y"),
                alt.Tooltip("wind_mean:Q", title="Vento (m/s)", format=".1f"),
            ],
        )
    )
    st.altair_chart(theme.base(wind), width="stretch")

    st.subheader("Agua no solo (balanco de referencia)")
    water = (
        alt.Chart(data.dropna(subset=["soil_water_mm"]))
        .mark_area(color=theme.SERIES_1, opacity=0.35, line={"color": theme.SERIES_1})
        .encode(
            x=year_axis,
            y=alt.Y(
                "soil_water_mm:Q",
                title="mm",
                scale=alt.Scale(domain=[0, config.SOIL_CAPACITY_MM]),
            ),
            tooltip=[
                alt.Tooltip("date:T", title="Data", format="%d/%m/%Y"),
                alt.Tooltip("soil_water_mm:Q", title="Reserva (mm)", format=".0f"),
                alt.Tooltip("et0_mm:Q", title="Evapotranspiracao (mm)", format=".1f"),
            ],
        )
    )
    threshold = (
        alt.Chart(pd.DataFrame({"y": [config.SOIL_DEFICIT_MM]}))
        .mark_rule(color=theme.CRITICAL, strokeDash=[4, 4])
        .encode(y="y:Q")
    )
    st.altair_chart(theme.base(alt.layer(water, threshold)), width="stretch")
    st.caption(
        f"Reserva estimada por um balanco simples: chuva menos evapotranspiracao, num solo "
        f"de {config.SOIL_CAPACITY_MM:.0f} mm. A linha vermelha marca "
        f"{config.SOIL_DEFICIT_MM:.0f} mm, abaixo dos quais o dia conta como solo seco. "
        "Nao usa coeficiente de cultura nem analise do seu solo, entao descreve o clima da "
        "estacao, nao a agua disponivel na sua lavoura."
    )

    with st.expander("Ver tabela"):
        st.dataframe(data, width="stretch", hide_index=True)


def _forecast(station):
    """INMET's five-day forecast, read from Postgres and refreshed on demand."""
    ibge_code = station.get("ibge_code")
    if not ibge_code or pd.isna(ibge_code):
        return

    forecast = queries.get_forecast(ibge_code)
    header, button = st.columns([4, 1])
    header.subheader(f"Previsao para {station.get('municipio') or station['name']}")

    if button.button("Atualizar previsao"):
        with st.spinner("Consultando o INMET..."):
            try:
                rows = queries.refresh_forecast(ibge_code)
            except Exception as error:  # INMET being down must not break the screen
                st.error(
                    f"Nao foi possivel falar com o INMET agora ({type(error).__name__})."
                )
                rows = 0
        if rows:
            queries.get_forecast.clear()
            st.rerun()

    if forecast.empty:
        st.info(
            "Nenhuma previsao guardada para este municipio. Use 'Atualizar previsao' para "
            "buscar no INMET."
        )
        return

    issued = forecast["issued_at"].max()
    forecast = forecast.assign(
        _order=forecast["period"].map(PERIOD_ORDER).fillna(9)
    ).sort_values(["forecast_date", "_order"])
    for date, group in forecast.groupby("forecast_date"):
        st.markdown(f"**{date:%d/%m}**")
        columns = st.columns(len(group))
        for column, (_, row) in zip(columns, group.iterrows(), strict=True):
            column.caption(PERIOD_LABELS.get(row["period"], row["period"]))
            column.write(f"{row['temp_min']} - {row['temp_max']} C")
            column.caption(row["resumo"] or "")
    st.caption(
        f"Previsao do INMET para o municipio, emitida em {issued:%d/%m/%Y %H:%M} UTC. "
        "O INMET publica cinco dias e nao informa quantidade de chuva, apenas a descricao "
        "do tempo. Esta ferramenta nao faz previsao propria nem estende esse prazo."
    )
