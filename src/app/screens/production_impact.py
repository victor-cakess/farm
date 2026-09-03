"""Screen 4: how weather affects soy production, qualitatively.

There is no yield data yet, so this screen explains mechanisms and counts the weather
events that occurred. It never estimates a loss, a percentage or a productivity figure.
"""

import pandas as pd
import streamlit as st

from src.app import queries

FULL_COVERAGE_HOURS = 20
HEAT_STRESS_C = 34.0
SEASON_START_MONTH = 10  # planting from October
SEASON_END_MONTH = 4  # harvest through April


def latest_season(weather):
    """Return (label, frame) for the most recent October-to-April window with data."""
    last = weather["date"].max()
    end_year = last.year if last.month > SEASON_END_MONTH else last.year - 1
    start = pd.Timestamp(year=end_year - 1, month=SEASON_START_MONTH, day=1)
    end = pd.Timestamp(year=end_year, month=SEASON_END_MONTH, day=30)
    window = weather[(weather["date"] >= start) & (weather["date"] <= end)]
    return f"{start:%m/%Y} a {end:%m/%Y}", window


def longest_dry_spell(frame):
    """Longest run of consecutive observed days that recorded no rain.

    A day the station did not report is unknown, not dry, so it ends the run rather
    than extending it. Otherwise a gap in the record would show up as a drought.
    """
    best = run = 0
    for value in frame["rain_mm"]:
        run = run + 1 if value == 0 else 0
        best = max(best, run)
    return best


def render(station):
    st.title("Clima e producao")
    st.caption(
        f"Estacao {station['code']} - {station['name']} ({station['uf']})"
    )

    weather = queries.get_weather(station["code"])
    if weather.empty:
        st.warning("Sem dados de clima para esta estacao.")
        return

    label, season = latest_season(weather)
    if season.empty:
        st.warning("Sem uma safra completa nos dados desta estacao.")
        return

    complete = season[season["hours_observed"] >= FULL_COVERAGE_HOURS]
    rain_days = int(season["rain_mm"].notna().sum())

    # Below this the station reported too little of the season for the counts to
    # describe it, and a partial record would read as a mild, dry, frost-free safra.
    if len(complete) < 0.5 * len(season) or rain_days < 0.5 * len(season):
        st.warning(
            f"A estacao {station['code']} registrou apenas {rain_days} dias de chuva e "
            f"{len(complete)} dias completos de temperatura na safra {label}, de "
            f"{len(season)} dias. E pouco para descrever a safra, entao os numeros nao "
            "sao mostrados aqui. Escolha outra estacao na barra lateral."
        )
        st.divider()
        _mechanisms()
        return

    st.subheader(f"O que aconteceu na safra {label}")
    first, second, third, fourth = st.columns(4)
    first.metric("Chuva na safra (mm)", f"{season['rain_mm'].sum():,.0f}".replace(",", "."))
    second.metric("Maior periodo sem chuva", f"{longest_dry_spell(season)} dias")
    third.metric("Dias de geada", int(complete["frost_flag"].sum()))
    fourth.metric(
        f"Dias acima de {HEAT_STRESS_C:.0f} C",
        int((complete["temp_max"] >= HEAT_STRESS_C).sum()),
    )
    st.caption(
        f"Safra de {len(season)} dias. Geada e calor contam os {len(complete)} dias com "
        f"registro horario completo; chuva e sequencia seca contam os {rain_days} dias com "
        "leitura de chuva. Dias sem registro nao entram como dias secos."
    )

    st.divider()
    _mechanisms()


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

**Seca.** O periodo mais sensivel a falta de agua e o enchimento de graos, tipicamente de
janeiro a marco. Uma sequencia longa sem chuva em dezembro atrapalha menos do que a mesma
sequencia em fevereiro, porque nesta fase a planta esta enchendo vagem e nao consegue
compensar depois. Por isso a sequencia seca importa mais do que o total de chuva da safra.

**Chuva em excesso.** Excesso de chuva prejudica em dois momentos distintos. Na semeadura,
solo encharcado compromete a germinacao e o estande. Na colheita, chuva sobre a lavoura
madura atrasa a entrada da maquina, favorece doenca de final de ciclo e derruba o padrao
do grao, o que aparece como desconto na hora da venda.

**Calor.** Temperatura alta durante o florescimento e o enchimento de graos aumenta o
aborto de flores e vagens, e ao mesmo tempo eleva a demanda de agua da planta. Calor junto
com sequencia seca e pior do que qualquer um dos dois isolado, e por isso vale olhar os
dois numeros acima na mesma janela de dias.
        """
    )

    st.divider()
    st.info(
        "**O que ainda nao da para dizer.** Esta tela descreve mecanismos conhecidos da "
        "cultura e conta os eventos registrados pela estacao. Ela nao estima perda, nao "
        "calcula produtividade e nao atribui a nenhum desses eventos um efeito em sacas "
        "por hectare, porque ainda nao existe aqui nenhum dado de colheita da sua area.\n\n"
        "Com o seu historico de produtividade por talhao, estas mesmas contagens passam a "
        "ser comparaveis: da para medir quanto os seus anos com sequencia seca no "
        "enchimento renderam a menos que os seus anos sem ela, quais talhoes sentem mais "
        "a mesma seca, e quanta chuva na colheita costuma custar em desconto de padrao. "
        "Ate la, o que esta acima e contexto, nao diagnostico."
    )
