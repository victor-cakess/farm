"""Screen 1: CEPEA soy price over time and its monthly seasonality."""

import altair as alt
import streamlit as st

from src.app import queries, theme

MONTHS = [
    "Jan", "Fev", "Mar", "Abr", "Mai", "Jun",
    "Jul", "Ago", "Set", "Out", "Nov", "Dez",
]


def render():
    st.title("Preco da soja")
    st.caption(
        "Indicador Soja CEPEA/ESALQ - Paranagua, diario, apenas dias uteis. "
        "Lacunas em fins de semana e feriados sao esperadas."
    )

    price = queries.get_price()
    if price.empty:
        st.warning("Sem dados de preco. Rode `make ingest-price`.")
        return

    currency = st.radio("Moeda", ["R$ por saca", "US$ por saca"], horizontal=True)
    column = "price_brl" if currency.startswith("R$") else "price_usd"
    label = "R$/saca" if column == "price_brl" else "US$/saca"

    latest = price.iloc[-1]
    st.metric(
        f"Ultimo indicador ({latest['date']:%d/%m/%Y})",
        f"{latest[column]:,.2f}".replace(",", "."),
    )

    line = (
        alt.Chart(price)
        .mark_line(color=theme.SERIES_1, strokeWidth=2)
        .encode(
            x=alt.X("date:T", title=None),
            y=alt.Y(f"{column}:Q", title=label, scale=alt.Scale(zero=False)),
            tooltip=[
                alt.Tooltip("date:T", title="Data", format="%d/%m/%Y"),
                alt.Tooltip(f"{column}:Q", title=label, format=".2f"),
            ],
        )
    )
    st.altair_chart(theme.base(line), width="stretch")

    st.subheader("Padrao por mes do ano")

    # Comparing raw monthly averages across a decade mostly measures inflation and the
    # price trend, which buries the seasonal shape. Each day is compared to the average
    # of its own year first, so what is left is how the month sits within its year.
    seasonal = price[["date", column]].dropna().copy()
    seasonal["ano"] = seasonal["date"].dt.year
    seasonal["mes"] = seasonal["date"].dt.month
    year_mean = seasonal.groupby("ano")[column].transform("mean")
    seasonal["desvio"] = (seasonal[column] / year_mean - 1) * 100

    monthly = seasonal.groupby("mes", as_index=False)["desvio"].mean()
    monthly["nome"] = monthly["mes"].map(lambda m: MONTHS[m - 1])
    monthly["sinal"] = monthly["desvio"] >= 0

    span = monthly["desvio"].max() - monthly["desvio"].min()
    st.caption(
        f"Cada dia comparado a media do seu proprio ano, entre {seasonal['ano'].min()} e "
        f"{seasonal['ano'].max()}. Do mes mais baixo ao mais alto a diferenca e de "
        f"{span:.1f} pontos percentuais. Isto descreve o passado do indicador, nao uma "
        "previsao para o proximo ano."
    )

    bars = (
        alt.Chart(monthly)
        .mark_bar(cornerRadiusEnd=4, size=22)
        .encode(
            x=alt.X("nome:N", sort=MONTHS, title=None),
            y=alt.Y("desvio:Q", title="% em relacao a media do ano"),
            color=alt.Color(
                "sinal:N",
                scale=alt.Scale(domain=[True, False], range=[theme.SERIES_1, theme.CRITICAL]),
                legend=None,
            ),
            tooltip=[
                alt.Tooltip("nome:N", title="Mes"),
                alt.Tooltip("desvio:Q", title="Desvio (%)", format="+.1f"),
            ],
        )
    )
    st.altair_chart(theme.base(bars), width="stretch")
