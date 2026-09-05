"""Screen 4: what the weather did to production, as far as public data can show.

The season counts come from the station. The yield comes from IBGE and is the average of
the whole municipality, never a single farm. Putting the two together shows whether the
relationship this tool is built on actually appears in the farmer's own municipality,
before asking them for anything.

It never estimates a loss for a specific field and never claims cause.
"""

import altair as alt
import streamlit as st

from src import config
from src.app import queries, theme
from src.domain import analysis, seasons


def render(station):
    st.title("Clima e producao")
    st.caption(
        f"Estacao {station['code']} - {station['name']} ({station['uf']})"
        + (f", municipio de {station['municipio']}" if station.get("municipio") else "")
    )

    weather = queries.get_weather(station["code"])
    if weather.empty:
        st.warning("Sem dados de clima para esta estacao.")
        return

    _municipal_section(station)
    st.divider()
    _last_season(station, weather)
    st.divider()
    _mechanisms()


def _municipal_section(station):
    st.subheader("O que os numeros do seu municipio mostram")

    if not station.get("ibge_code") or station.get("municipio") is None:
        st.warning(
            "Esta estacao nao esta ligada a um municipio, entao nao da para comparar."
        )
        return

    municipal = queries.get_municipal_yield(station["ibge_code"])
    season_rows = queries.get_seasons(station["code"])
    joined = analysis.yield_with_seasons(municipal, season_rows)

    if municipal.empty:
        st.warning(f"O IBGE nao publica produtividade de soja para {station['municipio']}.")
        return

    st.caption(
        f"Produtividade media de soja de {station['municipio']}, do IBGE (PAM), em sacas "
        "por hectare. E a media do municipio inteiro, nao de uma lavoura. A linha mostra a "
        "tendencia de longo prazo, que sobe com tecnologia e manejo."
    )

    yields = analysis.detrend(
        municipal.assign(
            yield_sc_ha=municipal["yield_kg_ha"].astype(float) / config.SACA_KG
        )
    )
    bars = (
        alt.Chart(yields)
        .mark_bar(color=theme.SERIES_1, cornerRadiusEnd=3, size=14)
        .encode(
            x=alt.X("year:O", title=None),
            y=alt.Y("yield_sc_ha:Q", title="sacas/ha"),
            tooltip=[
                alt.Tooltip("year:O", title="Safra"),
                alt.Tooltip("yield_sc_ha:Q", title="sacas/ha", format=".1f"),
            ],
        )
    )
    trend = (
        alt.Chart(yields)
        .mark_line(color=theme.SERIES_2, strokeWidth=2)
        .encode(x=alt.X("year:O"), y=alt.Y("trend:Q"))
    )
    st.altair_chart(theme.base(alt.layer(bars, trend)), width="stretch")

    if joined.empty or len(joined) < config.MIN_SEASONS_FOR_COMPARISON:
        st.info(
            f"Para comparar clima e produtividade sao necessarias ao menos "
            f"{config.MIN_SEASONS_FOR_COMPARISON} safras em que a estacao registrou pelo "
            f"menos metade dos dias. Esta estacao tem {len(joined)}. O grafico acima "
            "continua valido; a comparacao aparece em estacoes com historico mais longo."
        )
        return

    label = st.radio("Medida do clima", list(analysis.FEATURES.values()), horizontal=True)
    feature = next(k for k, v in analysis.FEATURES.items() if v == label)

    local = analysis.feature_correlation(joined, feature)
    pooled = analysis.prepare_pooled(queries.get_pooled_seasons())
    regional = analysis.regional_consistency(pooled, feature)

    points = (
        alt.Chart(joined)
        .mark_point(color=theme.SERIES_1, size=90, filled=True, opacity=0.85)
        .encode(
            x=alt.X(f"{feature}:Q", title=label, scale=alt.Scale(zero=False)),
            y=alt.Y(
                "deviation_pct:Q",
                title="% em relacao a tendencia",
                scale=alt.Scale(zero=False),
            ),
            tooltip=[
                alt.Tooltip("year:O", title="Safra"),
                alt.Tooltip(f"{feature}:Q", title=label, format=".0f"),
                alt.Tooltip("deviation_pct:Q", title="Desvio (%)", format="+.1f"),
                alt.Tooltip("yield_sc_ha:Q", title="sacas/ha", format=".1f"),
            ],
        )
    )
    labels = points.mark_text(dy=-12, fontSize=10, color=theme.MUTED).encode(text="year:O")
    st.altair_chart(theme.base(alt.layer(points, labels)), width="stretch")

    left, right = st.columns(2)
    if local:
        left.metric(
            "Correlacao nesta estacao",
            f"{local['r']:+.2f}",
            help="Correlacao de Pearson entre a medida do clima e o desvio da tendencia.",
        )
        left.caption(
            f"{local['n']} safras, de {local['first_year']} a {local['last_year']}."
        )
    else:
        left.info(
            "Esta medida varia pouco nesta estacao, entao a correlacao nao e calculada."
        )

    if regional:
        right.metric(
            "Estacoes da regiao na mesma direcao",
            f"{regional['negative']} de {regional['stations']}",
            help="Estacoes dos cinco estados cuja correlacao tem o mesmo sinal negativo.",
        )
        right.caption(f"Mediana das correlacoes: {regional['median_r']:+.2f}.")

    _honesty_note(regional, local, label)


def _honesty_note(regional, local, label):
    consistency = ""
    if regional:
        consistency = (
            f" Sozinha, uma estacao tem poucas safras para convencer. Por isso ao lado "
            f"esta a regiao inteira: das {regional['stations']} estacoes com historico "
            f"suficiente, {regional['negative']} mostram correlacao negativa, ou seja "
            f"mais {label.lower()} com produtividade abaixo da tendencia, com mediana "
            f"{regional['median_r']:+.2f}."
        )
        # A local correlation that disagrees with the region is what noise looks like at
        # this sample size, and saying so is more honest than leaving the reader to
        # reconcile two numbers that point opposite ways.
        if local and local["r"] > 0:
            consistency += (
                f" Nesta estacao o numero deu positivo ({local['r']:+.2f}), ou seja o "
                f"contrario do que a regiao mostra. Com {local['n']} safras isso e "
                "esperado de vez em quando: uma unica estacao tem historico curto demais "
                "para decidir a questao sozinha, e e por isso que o numero dela nao deve "
                "ser lido como conclusao."
            )
    st.info(
        "**Como ler isto.** O ponto de cada safra compara a produtividade media do "
        f"municipio com a propria tendencia daquele municipio, e a coloca contra "
        f"'{label.lower()}' medido na sua estacao.{consistency}\n\n"
        "Isto e associacao, nao causa: uma safra ruim pode vir de praga, de preco de "
        "insumo, de doenca ou de manejo, e nada disso aparece aqui. E a produtividade e "
        "a media do municipio inteiro, que inclui solos, cultivares e datas de plantio "
        "muito diferentes dos seus. Serve para mostrar que a conta funciona, nao para "
        "dizer quanto a sua lavoura rendeu."
    )


def _last_season(station, weather):
    """The most recent finished season, from the stored season features."""
    season_rows = queries.get_seasons(station["code"])
    if season_rows.empty:
        return

    harvest_year = seasons.latest_harvest_year(weather["date"].max())
    row = season_rows[season_rows["harvest_year"] == harvest_year]
    if row.empty:
        return
    row = row.iloc[0]
    start, end = seasons.season_bounds(harvest_year)
    label = f"{start:%m/%Y} a {end:%m/%Y}"

    st.subheader(f"O que aconteceu na safra {label}")
    if not row["sufficient"]:
        st.warning(
            f"A estacao {station['code']} registrou {int(row['rain_days_observed'])} dias "
            f"de chuva e {int(row['complete_days'])} dias completos de temperatura nesta "
            f"safra, de {int(row['total_days'])} dias. E pouco para descrever a safra, "
            "entao os numeros nao sao mostrados aqui."
        )
        return

    first, second, third, fourth = st.columns(4)
    first.metric("Chuva na safra (mm)", f"{row['rain_total_mm']:,.0f}".replace(",", "."))
    second.metric("Dias com solo seco", int(row["water_deficit_days"]))
    third.metric("Dias de geada", int(row["frost_days"]))
    fourth.metric(f"Dias acima de {config.HEAT_STRESS_C:.0f} C", int(row["heat_days"]))
    st.caption(
        f"Safra de {int(row['total_days'])} dias. Geada e calor contam os "
        f"{int(row['complete_days'])} dias com registro horario completo; chuva conta os "
        f"{int(row['rain_days_observed'])} dias com leitura de chuva. Dias sem registro "
        "nao entram como dias secos. 'Solo seco' vem do balanco hidrico de referencia, "
        f"dias em que a reserva ficou abaixo de {config.SOIL_DEFICIT_MM:.0f} mm."
    )


def _mechanisms():
    st.subheader("Por que cada um desses numeros importa")

    st.markdown(
        """
**Geada.** A soja nao tolera geada. Antes da emergencia o risco e baixo, mas geada sobre
a planta ja estabelecida queima folhas e, perto do enchimento de graos, interrompe o
enchimento das vagens que estavam em formacao. O marcador desta ferramenta usa a
temperatura minima do abrigo meteorologico, a cerca de 1,5 m do solo. No nivel do solo
faz mais frio, entao pode ocorrer geada real em noites em que o termometro da estacao
ainda marca alguns graus acima de zero. Trate a contagem como um alerta, nao como um
laudo.

**Falta de agua.** O periodo mais sensivel e o enchimento de graos, tipicamente de janeiro
a marco. Vale reparar em como esta ferramenta mede seca: nao pelo numero de dias seguidos
sem chuva, e sim pelos dias em que o balanco hidrico indica reserva baixa no solo. Nos
dados dos cinco estados, a contagem de dias seguidos sem chuva quase nao acompanha a
produtividade, enquanto os dias de solo seco acompanham. Uma quinzena sem chuva sobre solo
cheio nao e seca; uma semana sem chuva sobre solo vazio, com calor, e.

**Chuva em excesso.** Excesso de chuva prejudica em dois momentos distintos. Na semeadura,
solo encharcado compromete a germinacao e o estande. Na colheita, chuva sobre a lavoura
madura atrasa a entrada da maquina, favorece doenca de final de ciclo e derruba o padrao
do grao, o que aparece como desconto na hora da venda.

**Calor.** Temperatura alta durante o florescimento e o enchimento de graos aumenta o
aborto de flores e vagens, e ao mesmo tempo eleva a demanda de agua da planta. Nos dados
desta ferramenta, a contagem de dias quentes e a medida que mais acompanha a queda de
produtividade. Calor junto com solo seco e pior do que qualquer um dos dois isolado.
        """
    )

    st.divider()
    st.info(
        "**O que ainda nao da para dizer.** Tudo acima usa a media do municipio. Ela nao "
        "sabe onde fica a sua lavoura, que cultivar voce plantou, em que data, nem em que "
        "solo. Por isso nada aqui estima a perda da sua area.\n\n"
        "Com o seu historico de produtividade por talhao, esta mesma conta passa a ser "
        "feita sobre os seus numeros: da para medir quanto os seus anos com solo seco no "
        "enchimento renderam a menos que os seus anos sem ele, quais talhoes sentem mais "
        "a mesma seca, e quanta chuva na colheita costuma custar em desconto de padrao. "
        "A tela **Meus dados** existe para isso."
    )
