"""Screen 1: the soy price, what a producer actually receives, and what moved it."""

import altair as alt
import numpy as np
import pandas as pd
import streamlit as st

from src.app import queries, theme

MONTHS = [
    "Jan",
    "Fev",
    "Mar",
    "Abr",
    "Mai",
    "Jun",
    "Jul",
    "Ago",
    "Set",
    "Out",
    "Nov",
    "Dez",
]
DECOMPOSITION_MONTHS = 24


def render(station):
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
    breakeven = _breakeven(station) if column == "price_brl" else None
    if breakeven:
        rule = (
            alt.Chart(pd.DataFrame({"y": [breakeven["value"]]}))
            .mark_rule(color=theme.CRITICAL, strokeWidth=2, strokeDash=[6, 4])
            .encode(y="y:Q")
        )
        line = alt.layer(line, rule)
    st.altair_chart(theme.base(line), width="stretch")

    if breakeven:
        difference = latest["price_brl"] - breakeven["value"]
        left, right = st.columns(2)
        left.metric("Seu custo por saca", f"R$ {breakeven['value']:,.2f}".replace(",", "."))
        right.metric("Indicador menos o custo", f"R$ {difference:+,.2f}".replace(",", "."))
        st.caption(
            f"{breakeven['source']} A linha vermelha marca esse custo. O indicador e "
            "Paranagua: o que chega na fazenda e menor, entao a diferenca real e menor do "
            "que a mostrada aqui."
        )

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
                scale=alt.Scale(
                    domain=[True, False], range=[theme.SERIES_1, theme.CRITICAL]
                ),
                legend=None,
            ),
            tooltip=[
                alt.Tooltip("nome:N", title="Mes"),
                alt.Tooltip("desvio:Q", title="Desvio (%)", format="+.1f"),
            ],
        )
    )
    st.altair_chart(theme.base(bars), width="stretch")

    st.divider()
    _basis(station)
    st.divider()
    _decomposition(price)


def _breakeven(station):
    """Cost per saca: the farmer's own figure first, a CONAB reference second."""
    records = queries.get_farm_records()
    priced = records.dropna(subset=["cost_brl_ha"]) if not records.empty else records
    if not priced.empty:
        row = priced.sort_values("season_year").iloc[-1]
        return {
            "value": float(row["cost_brl_ha"]) / float(row["yield_sc_ha"]),
            "source": (
                f"Calculado dos seus dados: safra {int(row['season_year'])}, talhao "
                f"{row['field_name']}, custo dividido pela sua produtividade."
            ),
        }

    reference = queries.get_cost_reference(station["uf"])
    usable = reference.dropna(subset=["yield_sc_ha"]) if not reference.empty else reference
    if not usable.empty:
        row = usable.sort_values("season_year").iloc[-1]
        return {
            "value": float(row["cost_brl_ha"]) / float(row["yield_sc_ha"]),
            "source": (
                f"Referencia {row['source']} para {station['uf']}, safra "
                f"{int(row['season_year'])}. Nao e o seu custo: informe o seu em "
                "'Meus dados' para trocar esta linha pelo numero da sua area."
            ),
        }
    return None


def _basis(station):
    """Paranagua against what Parana producers were actually paid."""
    st.subheader("Porto e fazenda")

    parana = queries.get_price_monthly_pr()
    price = queries.get_price()
    if parana.empty or price.empty:
        st.info("Sem a serie do Parana. Rode `make ingest-deral`.")
        return

    port = price.copy()
    port["month"] = port["date"].values.astype("datetime64[M]")
    port = port.groupby("month", as_index=False)["price_brl"].mean()

    merged = port.merge(parana, on="month", how="inner").rename(
        columns={
            "price_brl": "Paranagua (CEPEA)",
            "price_brl_sc": "Parana recebido (DERAL)",
        }
    )
    if merged.empty:
        st.info("As duas series nao tem meses em comum.")
        return

    long = merged.melt("month", var_name="serie", value_name="brl")
    chart = (
        alt.Chart(long)
        .mark_line(strokeWidth=2)
        .encode(
            x=alt.X("month:T", title=None),
            y=alt.Y("brl:Q", title="R$/saca", scale=alt.Scale(zero=False)),
            color=alt.Color(
                "serie:N",
                scale=alt.Scale(
                    domain=["Paranagua (CEPEA)", "Parana recebido (DERAL)"],
                    range=[theme.SERIES_1, theme.SERIES_2],
                ),
                legend=alt.Legend(title=None, orient="top"),
            ),
            tooltip=[
                alt.Tooltip("month:T", title="Mes", format="%m/%Y"),
                alt.Tooltip("serie:N", title=None),
                alt.Tooltip("brl:Q", title="R$/saca", format=".2f"),
            ],
        )
    )
    st.altair_chart(theme.base(chart), width="stretch")

    last = merged.iloc[-1]
    gap = last["Paranagua (CEPEA)"] - last["Parana recebido (DERAL)"]
    share = gap / last["Paranagua (CEPEA)"] * 100
    left, right = st.columns(2)
    left.metric(f"Diferenca em {last['month']:%m/%Y}", f"R$ {gap:,.2f}".replace(",", "."))
    right.metric("Como fracao do preco do porto", f"{share:.1f}%")

    note = (
        "O indicador CEPEA e um preco de porto, em Paranagua. O produtor recebe menos: a "
        "diferenca paga frete, margem de quem compra e descontos de classificacao. A serie "
        "do DERAL e a media efetivamente recebida pelos produtores do Parana, que e a "
        "referencia verificavel mais proxima de um preco de fazenda."
    )
    if station["uf"] != "PR":
        note += (
            f" **A sua estacao fica em {station['uf']}.** Nao existe fonte publica e "
            "automatizavel equivalente para esse estado nesta ferramenta, entao a serie "
            "acima e do Parana e serve como ilustracao do tamanho da diferenca, nao como o "
            "preco da sua regiao. No seu estado o frete ate o porto e maior, entao a "
            "diferenca tende a ser maior ainda."
        )
    st.info(note)


def _decomposition(price):
    """How much of each move was the bean and how much was the dollar."""
    st.subheader("Foi a soja ou foi o dolar?")

    monthly = price.dropna(subset=["price_brl", "price_usd"]).copy()
    monthly = monthly[monthly["price_usd"] > 0]
    monthly["month"] = monthly["date"].values.astype("datetime64[M]")
    monthly = monthly.groupby("month", as_index=False)[["price_brl", "price_usd"]].mean()
    # CEPEA publishes the same indicator in both currencies, so their ratio is the rate it
    # was converted at. No exchange rate source is needed.
    monthly["fx"] = monthly["price_brl"] / monthly["price_usd"]

    for column, name in (("price_brl", "total"), ("price_usd", "soja"), ("fx", "cambio")):
        monthly[name] = np.log(monthly[column] / monthly[column].shift(1)) * 100
    monthly = monthly.dropna().tail(DECOMPOSITION_MONTHS)
    if monthly.empty:
        return

    long = monthly.melt(
        "month", value_vars=["soja", "cambio"], var_name="parte", value_name="pct"
    )
    bars = (
        alt.Chart(long)
        .mark_bar()
        .encode(
            x=alt.X("month:T", title=None),
            y=alt.Y("pct:Q", title="variacao mensal (%)"),
            color=alt.Color(
                "parte:N",
                scale=alt.Scale(
                    domain=["soja", "cambio"], range=[theme.SERIES_1, theme.SERIES_2]
                ),
                legend=alt.Legend(title=None, orient="top"),
            ),
            tooltip=[
                alt.Tooltip("month:T", title="Mes", format="%m/%Y"),
                alt.Tooltip("parte:N", title=None),
                alt.Tooltip("pct:Q", title="%", format="+.1f"),
            ],
        )
    )
    st.altair_chart(theme.base(bars), width="stretch")

    recent = monthly.tail(12)
    moved = recent["soja"].abs().sum() + recent["cambio"].abs().sum()
    fx_share = recent["cambio"].abs().sum() / moved * 100 if moved else 0
    st.metric("Parcela do movimento que veio do cambio, 12 meses", f"{fx_share:.0f}%")
    st.caption(
        "As duas barras de cada mes somam exatamente a variacao do preco em reais. A parte "
        "'soja' e a variacao do indicador em dolar; a parte 'cambio' e a variacao da taxa "
        "usada pelo CEPEA na conversao, obtida da razao entre as duas series publicadas. "
        "Serve para separar o que foi mercado do que foi moeda, e nao diz nada sobre o mes "
        "que vem."
    )
