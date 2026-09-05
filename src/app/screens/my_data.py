"""Screen 5: the farmer's own yield, and what it buys them immediately.

This is the point of the tool. Everything else exists to earn enough trust to reach this
screen, so it has to pay back on the first record entered rather than promising later
value. Nothing entered here leaves the machine it runs on.
"""

import altair as alt
import pandas as pd
import streamlit as st

from src import config
from src.app import queries, theme

FIRST_SEASON = 2000


def render(station):
    st.title("Meus dados")
    st.caption(
        "Sua produtividade por talhao e safra. Fica no banco local desta ferramenta, no "
        "seu computador, e nao e enviada para lugar nenhum."
    )

    records = queries.get_farm_records()
    _form(records)

    if records.empty:
        st.info(
            "**Por que vale a pena preencher.** As outras telas so conseguem falar da "
            "media do seu municipio, que mistura solos, cultivares e datas de plantio "
            "muito diferentes das suas. Com duas ou tres safras suas, a mesma conta passa "
            "a ser feita sobre a sua area: quanto os anos de solo seco custaram a voce, "
            "quais talhoes sofrem mais, e como o seu resultado se compara ao do municipio."
        )
        return

    st.divider()
    _records_table(records)
    st.divider()
    _comparison(station, records)


def _form(records):
    seasons_available = list(range(pd.Timestamp.today().year + 1, FIRST_SEASON, -1))

    with st.form("farm_record", clear_on_submit=True):
        st.subheader("Adicionar ou atualizar um talhao")
        first, second, third = st.columns(3)
        season_year = first.selectbox("Safra (ano da colheita)", seasons_available)
        field_name = second.text_input("Talhao", placeholder="Talhao 1")
        area_ha = third.number_input("Area (ha)", min_value=0.0, step=1.0, value=0.0)

        fourth, fifth = st.columns(2)
        yield_sc_ha = fourth.number_input(
            "Produtividade (sacas/ha)", min_value=0.0, step=1.0, value=0.0
        )
        cost_brl_ha = fifth.number_input(
            "Custo (R$/ha, opcional)", min_value=0.0, step=100.0, value=0.0
        )
        notes = st.text_input(
            "Observacoes (opcional)", placeholder="cultivar, data de plantio"
        )

        if st.form_submit_button("Salvar"):
            if not field_name.strip():
                st.error("Informe o nome do talhao.")
            elif yield_sc_ha <= 0:
                st.error("Informe a produtividade em sacas por hectare.")
            else:
                queries.save_farm_record(
                    (
                        int(season_year),
                        field_name.strip(),
                        area_ha or None,
                        yield_sc_ha,
                        cost_brl_ha or None,
                        notes.strip() or None,
                    )
                )
                queries.get_farm_records.clear()
                st.success(f"Talhao {field_name.strip()} salvo para a safra {season_year}.")
                st.rerun()


def _records_table(records):
    st.subheader("Seus registros")
    for _, row in records.iterrows():
        columns = st.columns([1, 2, 1, 1, 1, 1])
        columns[0].write(int(row["season_year"]))
        columns[1].write(row["field_name"])
        columns[2].write(f"{row['area_ha']:.0f} ha" if pd.notna(row["area_ha"]) else "-")
        columns[3].write(f"{row['yield_sc_ha']:.1f} sc/ha")
        columns[4].write(
            f"R$ {row['cost_brl_ha']:,.0f}/ha".replace(",", ".")
            if pd.notna(row["cost_brl_ha"])
            else "-"
        )
        if columns[5].button(
            "Remover", key=f"del-{row['season_year']}-{row['field_name']}"
        ):
            queries.delete_farm_record(int(row["season_year"]), row["field_name"])
            queries.get_farm_records.clear()
            st.rerun()


def _comparison(station, records):
    st.subheader("Seus talhoes e o seu municipio")

    mine = (
        records.groupby("season_year", as_index=False)["yield_sc_ha"]
        .mean()
        .rename(columns={"season_year": "year", "yield_sc_ha": "Seus talhoes"})
    )

    municipal = (
        queries.get_municipal_yield(station["ibge_code"])
        if station.get("ibge_code")
        else pd.DataFrame()
    )
    if not municipal.empty:
        municipal = municipal.assign(
            **{"Municipio": municipal["yield_kg_ha"].astype(float) / config.SACA_KG}
        )[["year", "Municipio"]]
        merged = mine.merge(municipal, on="year", how="left")
    else:
        merged = mine.assign(Municipio=float("nan"))
    # Keep it numeric so an unpublished season renders as an empty cell rather than "None".
    merged["Municipio"] = pd.to_numeric(merged["Municipio"], errors="coerce").round(1)

    long = merged.melt("year", var_name="serie", value_name="sc_ha").dropna(
        subset=["sc_ha"]
    )
    chart = (
        alt.Chart(long)
        .mark_bar(cornerRadiusEnd=3)
        .encode(
            x=alt.X("year:O", title=None),
            y=alt.Y("sc_ha:Q", title="sacas/ha"),
            xOffset="serie:N",
            color=alt.Color(
                "serie:N",
                scale=alt.Scale(
                    domain=["Seus talhoes", "Municipio"],
                    range=[theme.SERIES_1, theme.SERIES_2],
                ),
                legend=alt.Legend(title=None, orient="top"),
            ),
            tooltip=[
                alt.Tooltip("year:O", title="Safra"),
                alt.Tooltip("serie:N", title=None),
                alt.Tooltip("sc_ha:Q", title="sacas/ha", format=".1f"),
            ],
        )
    )
    st.altair_chart(theme.base(chart), width="stretch")

    seasons_frame = queries.get_seasons(station["code"])
    if not seasons_frame.empty:
        weather = seasons_frame[
            [
                "harvest_year",
                "rain_total_mm",
                "water_deficit_days",
                "heat_days",
                "frost_days",
            ]
        ].rename(
            columns={
                "harvest_year": "Safra",
                "rain_total_mm": "Chuva (mm)",
                "water_deficit_days": "Dias solo seco",
                "heat_days": f"Dias > {config.HEAT_STRESS_C:.0f} C",
                "frost_days": "Geadas",
            }
        )
        table = merged.rename(columns={"year": "Safra"}).merge(
            weather, on="Safra", how="left"
        )
        st.dataframe(table, width="stretch", hide_index=True)

    missing = merged[merged["Municipio"].isna()]["year"].tolist()
    if missing and not municipal.empty:
        latest = int(municipal["year"].max())
        st.caption(
            f"O IBGE publica a produtividade municipal uma vez por ano, com atraso: a "
            f"ultima disponivel e a de {latest}. Por isso "
            f"{', '.join(str(int(y)) for y in missing)} aparece sem a barra do municipio."
        )

    comparable = merged.dropna(subset=["Municipio"])
    if not comparable.empty:
        gap = (comparable["Seus talhoes"] - comparable["Municipio"]).mean()
        st.metric(
            "Diferenca media para o municipio",
            f"{gap:+.1f} sacas/ha",
            help="Media das suas safras menos a media do municipio nas mesmas safras.",
        )

    st.info(
        "**O que da e o que nao da para concluir.** Com poucas safras, esta diferenca "
        "descreve o passado registrado, nao a sua capacidade produtiva nem uma previsao. "
        "A media do municipio inclui areas com solo, cultivar e data de plantio diferentes "
        "das suas, entao ficar acima ou abaixo dela nao e, por si so, um diagnostico.\n\n"
        f"A partir de {config.MIN_SEASONS_FOR_COMPARISON} safras suas, da para repetir "
        "sobre os seus proprios numeros a mesma conta que a tela **Clima e producao** faz "
        "hoje com a media do municipio, e ai sim falar da sua area."
    )
