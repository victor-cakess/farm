"""Screen 3: station weather and the Paranagua price on a shared time axis."""

import altair as alt
import streamlit as st

from src.app import queries, theme

# Two full annual cycles. Below this a correlation between two seasonal series is
# dominated by which months happen to be present, so no figure is shown at all.
MIN_MONTHS = 24

VARIABLES = {
    "Temperatura media mensal": ("temp_mean", "graus C"),
    "Chuva total mensal": ("rain_mm", "mm"),
}


def render(station):
    st.title("Clima e preco lado a lado")
    st.caption(
        f"Estacao {station['code']} - {station['name']} ({station['uf']}) "
        "e o indicador CEPEA/ESALQ Paranagua, nos meses em que as duas series existem."
    )

    monthly = queries.get_monthly(station["code"])
    if monthly.empty:
        st.warning("Sem meses em comum entre clima e preco para esta estacao.")
        return

    choice = st.radio("Variavel do clima", list(VARIABLES), horizontal=True)
    column, unit = VARIABLES[choice]

    frame = monthly.dropna(subset=[column, "price_brl"])

    # Two charts stacked on a shared time axis, never two y-scales on one chart:
    # a second scale can be stretched until any two series appear to move together.
    axis = alt.X("month:T", title=None)
    price_chart = (
        alt.Chart(frame)
        .mark_line(color=theme.SERIES_1, strokeWidth=2)
        .encode(
            x=axis,
            y=alt.Y("price_brl:Q", title="R$/saca", scale=alt.Scale(zero=False)),
            tooltip=[
                alt.Tooltip("month:T", title="Mes", format="%m/%Y"),
                alt.Tooltip("price_brl:Q", title="R$/saca", format=".2f"),
            ],
        )
        .properties(height=200, title="Preco medio mensal")
    )
    weather_chart = (
        alt.Chart(frame)
        .mark_line(color=theme.SERIES_2, strokeWidth=2)
        .encode(
            x=axis,
            y=alt.Y(f"{column}:Q", title=unit, scale=alt.Scale(zero=False)),
            tooltip=[
                alt.Tooltip("month:T", title="Mes", format="%m/%Y"),
                alt.Tooltip(f"{column}:Q", title=choice, format=".1f"),
            ],
        )
        .properties(height=200, title=choice)
    )
    st.altair_chart(
        theme.configure(alt.vconcat(price_chart, weather_chart).resolve_scale(x="shared")),
        width="stretch",
    )

    if len(frame) < MIN_MONTHS:
        st.warning(
            f"Esta estacao tem apenas {len(frame)} meses em comum com a serie de preco. "
            f"Abaixo de {MIN_MONTHS} meses, ou seja dois ciclos anuais completos, uma "
            "correlacao diria mais sobre o acaso do que sobre o clima, entao ela nao e "
            "calculada aqui. Os graficos acima continuam validos."
        )
    else:
        correlation = frame[column].corr(frame["price_brl"])
        st.metric(
            f"Correlacao mensal entre {choice.lower()} e preco",
            f"{correlation:+.2f}",
            help="Correlacao de Pearson sobre as medias mensais.",
        )
        st.caption(f"Calculada sobre {len(frame)} meses em comum.")

    st.info(
        "**Como ler este numero.** Ele mede apenas se as duas series subiram e desceram "
        "juntas nos mesmos meses. Nao mede causa. O clima de uma unica estacao nao forma "
        "o preco em Paranagua: esse preco responde a safra do Brasil inteiro, ao mercado "
        "internacional, ao cambio e ao frete. Quando as duas linhas parecem acompanhar "
        "uma a outra, a explicacao mais provavel e que ambas seguem o mesmo calendario "
        "anual, e nao que uma esteja movendo a outra. Use esta tela para conhecer o seu "
        "ano, nao para prever preco."
    )
