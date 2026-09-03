"""Streamlit entry point. Reads from Postgres only."""

import streamlit as st

from src.app import queries
from src.app.screens import (
    price_overview,
    production_impact,
    weather_overview,
    weather_vs_price,
)

st.set_page_config(page_title="Soja: preco e clima", layout="wide")


def selected_station():
    """Station selector shared by every screen that needs one."""
    stations = queries.get_stations()
    if stations.empty:
        return None

    labels = stations["name"] + " (" + stations["uf"] + ")"
    index = st.sidebar.selectbox(
        "Estacao",
        range(len(stations)),
        index=int(stations["observed_days"].argmax()),
        format_func=lambda i: labels.iloc[i],
    )
    return stations.iloc[index]


st.sidebar.title("Soja: preco e clima")
station = selected_station()

if station is None:
    st.warning(
        "Nenhuma estacao com dados de clima. Rode `make ingest` antes de abrir o app."
    )
    st.stop()

st.sidebar.caption(
    "Dados: indicador CEPEA/ESALQ Soja Paranagua e estacoes automaticas do INMET."
)

page = st.navigation(
    [
        st.Page(price_overview.render, title="Preco", icon=":material/payments:"),
        st.Page(
            lambda: weather_overview.render(station),
            title="Clima local",
            icon=":material/rainy:",
            url_path="clima",
        ),
        st.Page(
            lambda: weather_vs_price.render(station),
            title="Clima e preco",
            icon=":material/timeline:",
            url_path="clima-e-preco",
        ),
        st.Page(
            lambda: production_impact.render(station),
            title="Clima e producao",
            icon=":material/agriculture:",
            url_path="producao",
        ),
    ]
)
page.run()
