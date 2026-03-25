"""
src/dashboard.py
================
Dashboard interativo de regras de intercâmbio usando Streamlit + Plotly.

Funcionalidades:
    - Tabela consolidada de todas as regras
    - Gráficos comparativos entre Bandeiras
    - Boxplot de distribuição de taxas por produto
    - Filtros interativos dinâmicos
    - Simulador de taxa integrado
    - Export CSV das regras filtradas

Uso:
    streamlit run src/dashboard.py

Acesse: http://localhost:8501
"""
from __future__ import annotations

import sys
from pathlib import Path

# Garante que o módulo pai está no path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from src.config import BASE_DIR, settings
from src.database import init_db
from src.repository import get_all_rules, get_stats
from src.schemas import SimulationRequest
from src.simulator import compare_networks, simulate

# ---------------------------------------------------------------------------
# Configuração da página
# ---------------------------------------------------------------------------

st.set_page_config(
    page_title="Interchange AI Dashboard",
    page_icon="💳",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ---------------------------------------------------------------------------
# Inicialização
# ---------------------------------------------------------------------------

@st.cache_data(ttl=30)
def load_data() -> pd.DataFrame:
    """Carrega dados do banco e retorna como DataFrame."""
    init_db()
    rules = get_all_rules()
    if not rules:
        # Fallback: lê direto do CSV
        csv_path = BASE_DIR / settings.sample_csv_path
        if csv_path.exists():
            return pd.read_csv(csv_path)
        return pd.DataFrame()

    records = []
    for r in rules:
        records.append({
            "network": r.network,
            "region": r.region,
            "rule_type": r.rule_type,
            "audience": r.audience or "ALL",
            "card_family": r.card_family or "—",
            "product": r.product or "—",
            "merchant_group": r.merchant_group or "—",
            "channel": r.channel or "—",
            "installment_band": r.installment_band or "avista",
            "rate_pct": r.rate_pct,
            "fixed_fee_amount": r.fixed_fee_amount,
            "cap_amount": r.cap_amount,
            "confidence_score": r.confidence_score,
        })
    return pd.DataFrame(records)


# ---------------------------------------------------------------------------
# Sidebar — Filtros
# ---------------------------------------------------------------------------

st.sidebar.title("💳 Interchange AI")
st.sidebar.markdown("**Filtros Globais**")

df_full = load_data()

if df_full.empty:
    st.error(
        "⚠️ Base de dados vazia. Execute: `python -m src.seed_sample_data`"
    )
    st.stop()

networks_available = sorted(df_full["network"].unique().tolist())
selected_networks = st.sidebar.multiselect(
    "Bandeiras",
    options=networks_available,
    default=networks_available,
)

card_families = sorted(df_full["card_family"].dropna().unique().tolist())
selected_families = st.sidebar.multiselect(
    "Família de Cartão",
    options=card_families,
    default=card_families,
)

rule_types = sorted(df_full["rule_type"].unique().tolist())
selected_rule_types = st.sidebar.multiselect(
    "Tipo de Regra",
    options=rule_types,
    default=rule_types,
)

min_conf = st.sidebar.slider("Score mínimo de confiança", 0.0, 1.0, 0.0, 0.05)

# Aplica filtros
df = df_full[
    df_full["network"].isin(selected_networks)
    & df_full["card_family"].isin(selected_families)
    & df_full["rule_type"].isin(selected_rule_types)
    & (df_full["confidence_score"] >= min_conf)
].copy()

st.sidebar.markdown(f"**{len(df)} de {len(df_full)} regras exibidas**")

# ---------------------------------------------------------------------------
# Cabeçalho principal
# ---------------------------------------------------------------------------

st.title("📊 Interchange AI — Dashboard de Taxas de Intercâmbio")
st.markdown(
    "Análise comparativa de regras de intercâmbio: "
    "**Visa · Mastercard · American Express · Elo · Hipercard · BCB**"
)

# Métricas rápidas
col1, col2, col3, col4, col5 = st.columns(5)
col1.metric("Total de Regras", len(df_full))
col2.metric("Bandeiras", len(df_full["network"].unique()))
col3.metric("Tipos de Regra", len(df_full["rule_type"].unique()))
col4.metric("Regras Filtradas", len(df))
avg_rate = df_full[df_full["rate_pct"].notna()]["rate_pct"].mean()
col5.metric("Taxa Média (base_rate)", f"{avg_rate:.2f}%")

st.divider()

# ---------------------------------------------------------------------------
# Aba 1: Exploração de Dados
# ---------------------------------------------------------------------------

tab1, tab2, tab3, tab4, tab5 = st.tabs([
    "📋 Tabela de Regras",
    "📊 Comparativos Visuais",
    "💹 Análise por Produto",
    "🔄 Simulador de Taxa",
    "📈 Análise BCB / Regulatória",
])

with tab1:
    st.subheader("Base Consolidada de Regras")

    # Download CSV
    csv_export = df.to_csv(index=False).encode("utf-8")
    st.download_button(
        "⬇️ Exportar CSV",
        data=csv_export,
        file_name="interchange_rules_filtered.csv",
        mime="text/csv",
    )

    # Tabela interativa
    st.dataframe(
        df.sort_values(["network", "card_family", "product"]),
        use_container_width=True,
        height=500,
        column_config={
            "rate_pct": st.column_config.NumberColumn("Taxa (%)", format="%.2f%%"),
            "fixed_fee_amount": st.column_config.NumberColumn("Fee Fixo (R$)", format="R$ %.2f"),
            "confidence_score": st.column_config.ProgressColumn(
                "Confiança", min_value=0, max_value=1, format="%.2f"
            ),
        },
    )

with tab2:
    st.subheader("Comparativos entre Bandeiras")

    col_a, col_b = st.columns(2)

    with col_a:
        # Taxa base média por bandeira
        df_base = df[df["rule_type"] == "base_rate"].dropna(subset=["rate_pct"])
        if not df_base.empty:
            fig_bar = px.bar(
                df_base.groupby("network")["rate_pct"].mean().reset_index(),
                x="network",
                y="rate_pct",
                color="network",
                title="Taxa Base Média por Bandeira (crédito PF)",
                labels={"rate_pct": "Taxa Média (%)", "network": "Bandeira"},
                text_auto=".2f",
            )
            fig_bar.update_layout(showlegend=False)
            st.plotly_chart(fig_bar, use_container_width=True)

    with col_b:
        # Distribuição de regras por tipo
        fig_pie = px.pie(
            df["rule_type"].value_counts().reset_index(),
            names="rule_type",
            values="count",
            title="Distribuição por Tipo de Regra",
        )
        st.plotly_chart(fig_pie, use_container_width=True)

    # Heatmap de taxas por bandeira x família
    df_heat = df[df["rate_pct"].notna()].groupby(
        ["network", "card_family"]
    )["rate_pct"].mean().reset_index()
    if not df_heat.empty:
        fig_heat = px.density_heatmap(
            df_heat,
            x="card_family",
            y="network",
            z="rate_pct",
            title="Heatmap: Taxa Média por Bandeira × Família de Cartão",
            color_continuous_scale="RdYlGn_r",
            labels={"rate_pct": "Taxa Média (%)"},
        )
        st.plotly_chart(fig_heat, use_container_width=True)

    # Comparativo de ajustes por tipo
    df_adj = df[df["rule_type"].str.contains("adjustment") & df["rate_pct"].notna()]
    if not df_adj.empty:
        fig_adj = px.box(
            df_adj,
            x="rule_type",
            y="rate_pct",
            color="network",
            title="Distribuição de Ajustes por Tipo e Bandeira",
            labels={"rate_pct": "Ajuste (%)", "rule_type": "Tipo de Ajuste"},
        )
        fig_adj.update_layout(xaxis_tickangle=-30)
        st.plotly_chart(fig_adj, use_container_width=True)

with tab3:
    st.subheader("Análise por Produto")

    df_prod = df[
        df["rule_type"].isin(["base_rate"]) & df["rate_pct"].notna()
    ].copy()

    if not df_prod.empty:
        # Boxplot por produto e bandeira
        fig_box = px.box(
            df_prod,
            x="product",
            y="rate_pct",
            color="network",
            title="Distribuição de Taxas Base por Produto",
            labels={"rate_pct": "Taxa (%)", "product": "Produto"},
        )
        fig_box.update_layout(xaxis_tickangle=-45)
        st.plotly_chart(fig_box, use_container_width=True)

        # Tabela comparativa Visa × Mastercard
        st.subheader("Comparativo Visa × Mastercard (Taxas Base Crédito PF)")
        df_comp = df_prod[
            df_prod["network"].isin(["Visa", "Mastercard"])
            & (df_prod["audience"].isin(["PF", "ALL"]))
            & (df_prod["card_family"] == "credit")
        ].groupby(["network", "product"])["rate_pct"].mean().unstack("network")

        if not df_comp.empty:
            st.dataframe(
                df_comp.style.format("{:.2f}%").background_gradient(cmap="RdYlGn_r"),
                use_container_width=True,
            )

    # Parcelamento comparativo
    st.subheader("Ajustes de Parcelamento por Bandeira")

    df_inst = df[
        (df["rule_type"] == "installment_adjustment")
        & (df["rate_pct"].notna())
    ].copy()

    if not df_inst.empty:
        fig_inst = px.bar(
            df_inst,
            x="installment_band",
            y="rate_pct",
            color="network",
            barmode="group",
            title="Ajuste de Parcelamento por Faixa e Bandeira",
            labels={"rate_pct": "Ajuste (%)", "installment_band": "Parcelas"},
            text_auto=".2f",
        )
        st.plotly_chart(fig_inst, use_container_width=True)

with tab4:
    st.subheader("🔄 Simulador de Taxa de Intercâmbio")
    st.markdown(
        "Calcule a taxa efetiva para uma transação específica. "
        "O simulador aplica as regras do banco na mesma lógica usada pelos sistemas de produção."
    )

    col_s1, col_s2, col_s3 = st.columns(3)

    with col_s1:
        sim_network = st.selectbox("Bandeira", options=networks_available)
        sim_family = st.selectbox("Família", options=["credit", "debit", "prepaid", "cash_withdrawal"])
        sim_product = st.text_input("Produto (ex: Platinum, Black)", value="")

    with col_s2:
        sim_audience = st.selectbox("Público", options=["PF", "PJ", "ALL"])
        sim_channel = st.selectbox("Canal", options=["cp", "cnp", "cp_contactless", "atm"])
        sim_merchant = st.text_input("Segmento (ex: supermercados)", value="")

    with col_s3:
        sim_band = st.selectbox("Parcelamento", options=["avista", "2-6", "7-12", "7-21"])
        sim_amount = st.number_input("Valor da transação (R$)", min_value=0.0, value=500.0, step=10.0)

    if st.button("▶️ Simular", type="primary"):
        all_rules = get_all_rules()
        req = SimulationRequest(
            network=sim_network,
            region="BR",
            audience=sim_audience,
            card_family=sim_family,
            product=sim_product or None,
            merchant_group=sim_merchant or None,
            channel=sim_channel,
            installment_band=None if sim_band == "avista" else sim_band,
            transaction_amount=sim_amount if sim_amount > 0 else None,
        )
        result = simulate(all_rules, req)

        st.success(f"**Taxa efetiva: {result.total_rate_pct:.4f}%**")

        c1, c2, c3 = st.columns(3)
        c1.metric("Taxa Percentual", f"{result.total_rate_pct:.2f}%")
        c2.metric("Fee Fixo", f"R$ {result.total_fixed_fee:.2f}")
        if result.estimated_fee_amount is not None:
            c3.metric(
                f"Fee em R$ (sobre R$ {sim_amount:.0f})",
                f"R$ {result.estimated_fee_amount:.4f}",
            )

        for note in result.notes:
            st.info(f"ℹ️ {note}")

        if result.matched_rules:
            st.subheader("Regras Aplicadas")
            df_matched = pd.DataFrame([r.model_dump() for r in result.matched_rules])
            st.dataframe(df_matched[[
                "rule_type", "product", "merchant_group", "channel",
                "installment_band", "rate_pct", "fixed_fee_amount", "confidence_score"
            ]], use_container_width=True)

        # Comparativo entre bandeiras
        st.subheader("Comparativo Rápido entre Bandeiras")
        comparison = compare_networks(all_rules, req)
        comp_data = [
            {
                "Bandeira": net,
                "Taxa (%)": resp.total_rate_pct,
                "Fee Fixo (R$)": resp.total_fixed_fee,
                "Fee Estimado (R$)": resp.estimated_fee_amount or 0,
                "Regras Aplicadas": len(resp.matched_rules),
            }
            for net, resp in comparison.items()
        ]
        df_comp_sim = pd.DataFrame(comp_data).sort_values("Taxa (%)")
        st.dataframe(df_comp_sim, use_container_width=True)

        fig_comp = px.bar(
            df_comp_sim,
            x="Bandeira",
            y="Taxa (%)",
            color="Bandeira",
            title="Taxa Efetiva por Bandeira (mesma transação)",
            text_auto=".2f",
        )
        st.plotly_chart(fig_comp, use_container_width=True)

with tab5:
    st.subheader("📈 Análise Regulatória — Banco Central do Brasil")

    st.markdown("""
    ### Regulamentação BCB — Intercâmbio Doméstico

    | Resolução | Modalidade | Limite |
    |-----------|-----------|--------|
    | BCB nº 35/2020 | Débito doméstico | Máx. **0,50%** do valor |
    | BCB nº 35/2020 | Débito baixo valor | Teto **R$ 0,35** por transação |
    | BCB nº 35/2020 | Pré-pago doméstico | Máx. **0,70%** do valor |
    | Sem teto | Crédito PF | Mercado livre |
    | CMN nº 4.282/2013 | Geral | Transparência e divulgação |

    **Fonte:** [bcb.gov.br](https://www.bcb.gov.br/estabilidadefinanceira/arranjos_pagamento)
    """)

    # Comparativo BCB × Taxas praticadas
    df_debit = df_full[
        (df_full["card_family"] == "debit")
        & (df_full["rule_type"] == "base_rate")
        & df_full["rate_pct"].notna()
    ].copy()

    if not df_debit.empty:
        fig_bcb = px.bar(
            df_debit,
            x="network",
            y="rate_pct",
            color="merchant_group",
            barmode="group",
            title="Taxas de Débito por Bandeira vs. Teto BCB (0,50%)",
            labels={"rate_pct": "Taxa (%)", "network": "Bandeira"},
        )
        fig_bcb.add_hline(
            y=0.50,
            line_dash="dash",
            line_color="red",
            annotation_text="Teto BCB: 0,50%",
            annotation_position="top right",
        )
        st.plotly_chart(fig_bcb, use_container_width=True)

    st.markdown("""
    ### Diferenças Estruturais entre Bandeiras no Brasil

    | Característica | Visa | Mastercard | AmericanExpress | Elo | Hipercard |
    |----------------|------|-----------|-----------------|-----|-----------|
    | Modelo | Open Loop | Open Loop | Closed Loop (híbrido) | Open Loop | Open Loop |
    | Origem | EUA (global) | EUA (global) | EUA (global) | Brasil | Brasil (Itaú) |
    | Parcelamento máx. | 12x | 21x | 12x | 12x | 12x |
    | VbV/ID Check | ✅ | ✅ | SafeKey | ✅ | ✅ |
    | Contactless | ✅ | ✅ (ajuste +0,05%) | ✅ | ✅ (ajuste +0,03%) | ✅ |
    | Regulado BCB | ✅ | ✅ | ✅ | ✅ | ✅ |
    """)

# ---------------------------------------------------------------------------
# Footer
# ---------------------------------------------------------------------------

st.divider()
st.caption(
    "💳 Interchange AI Dashboard v2.0 — Desafio Bolsista Doutor PUCPR Digital | "
    "Dados de referência pública Visa, Mastercard, AmericanExpress, Elo, Hipercard, BCB"
)
