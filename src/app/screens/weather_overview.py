"""Screen 2: daily weather for the selected station."""

import altair as alt
import streamlit as st

from src.app import queries, theme

# A day with at least this many hourly temperature readings is treated as fully
# observed. Below it, the daily minimum is the minimum of the hours that reported,
# not of the day, so it is not counted as a frost verdict either way.
FULL_COVERAGE_HOURS = 20


def render(station):
    st.title("Clima local")
    st.caption(f"Estacao automatica INMET {station['code']} - {station['name']} ({station['uf']})")

    weather = queries.get_weather(station["code"])
    if weather.empty:
        st.warning("Sem dados de clima para esta estacao.")
        return

    years = sorted(weather["date"].dt.year.unique(), reverse=True)
    year = st.selectbox("Ano", years)
    data = weather[weather["date"].dt.year == year].copy()

    complete = data[data["hours_observed"] >= FULL_COVERAGE_HOURS]
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
        f"{FULL_COVERAGE_HOURS} horas registradas, para nao inventar nem perder geadas em "
        f"dias incompletos. O total de chuva soma os {rain_days} dias com leitura de "
        "chuva, entao e um minimo medido, nao a chuva total do ano."
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
    st.altair_chart(
        theme.base(alt.layer(band, maxima, minima, frost)), width="stretch"
    )
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

    with st.expander("Ver tabela"):
        st.dataframe(data, width="stretch", hide_index=True)
