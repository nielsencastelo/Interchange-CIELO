"""
notebooks/exploratory_analysis.py
==================================
Análise exploratória completa das regras de intercâmbio.

Execute diretamente:
    python notebooks/exploratory_analysis.py

Ou converta para Jupyter Notebook:
    pip install jupytext
    jupytext --to notebook notebooks/exploratory_analysis.py
    jupyter notebook notebooks/exploratory_analysis.ipynb

Seções:
    1. Carregamento e visão geral dos dados
    2. Análise por bandeira
    3. Comparativo de taxas base (Visa vs MC vs Amex vs Elo vs Hipercard)
    4. Distribuição de ajustes por tipo
    5. Análise de parcelamento
    6. Análise regulatória BCB
    7. Score de confiança das extrações
    8. Simulações de exemplo
    9. Exportação de resultados
"""
from __future__ import annotations

# %% [markdown]
# # 💳 Interchange AI — Análise Exploratória
# **Desafio Bolsista Doutor | PUCPR Digital**
# Pipeline de IA para Extração e Estruturação de Taxas de Intercâmbio

# %% Imports e Setup
import sys
import os
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

import pandas as pd
import warnings
warnings.filterwarnings("ignore")

# Tenta importar plotly para gráficos interativos
try:
    import plotly.express as px
    import plotly.graph_objects as go
    from plotly.subplots import make_subplots
    HAS_PLOTLY = True
except ImportError:
    HAS_PLOTLY = False
    print("⚠️  plotly não instalado. Instale com: pip install plotly")

print("=" * 60)
print("INTERCHANGE AI — ANÁLISE EXPLORATÓRIA")
print("=" * 60)

# %% [markdown]
# ## 1. Carregamento dos Dados

# %%
CSV_PATH = PROJECT_ROOT / "data" / "sample_interchange_rules.csv"

df = pd.read_csv(CSV_PATH)

# Renomear para facilitar análise
df = df.rename(columns={
    "rate_pct": "taxa_pct",
    "fixed_fee_brl": "taxa_fixa_brl",
    "cap_brl": "teto_brl",
    "installment_band": "parcelas",
    "card_family": "familia",
    "merchant_group": "segmento",
    "rule_type": "tipo_regra",
})

print(f"\n📊 Dataset carregado: {len(df)} regras")
print(f"   Bandeiras: {sorted(df['network'].unique())}")
print(f"   Tipos de regra: {sorted(df['tipo_regra'].unique())}")
print(f"   Famílias de cartão: {sorted(df['familia'].dropna().unique())}")
print(f"\nColunas:\n{df.dtypes}")

# %% [markdown]
# ## 2. Visão Geral por Bandeira

# %%
print("\n" + "=" * 60)
print("2. VISÃO GERAL POR BANDEIRA")
print("=" * 60)

por_bandeira = df.groupby("network").agg(
    total_regras=("taxa_pct", "count"),
    taxa_base_media=("taxa_pct", lambda x: x[df.loc[x.index, "tipo_regra"] == "base_rate"].mean()),
    taxa_min=("taxa_pct", "min"),
    taxa_max=("taxa_pct", "max"),
).reset_index()

print("\nResumo por Bandeira:")
print(por_bandeira.to_string(index=False))

# %% [markdown]
# ## 3. Comparativo de Taxas Base — Crédito PF À Vista

# %%
print("\n" + "=" * 60)
print("3. COMPARATIVO TAXAS BASE — CRÉDITO PF À VISTA")
print("=" * 60)

base_credit = df[
    (df["tipo_regra"] == "base_rate") &
    (df["familia"] == "credit") &
    (df["audience"] == "PF") &
    (df["taxa_pct"].notna())
].copy()

print("\nTaxas base por produto e bandeira (crédito PF, à vista, CP):")
pivot = base_credit.pivot_table(
    index="product", columns="network", values="taxa_pct", aggfunc="mean"
).round(2)
print(pivot.to_string())

print("\nEstatísticas por bandeira (crédito PF base_rate):")
stats = base_credit.groupby("network")["taxa_pct"].agg(["min", "mean", "max"]).round(2)
print(stats.to_string())

if HAS_PLOTLY:
    fig = px.bar(
        base_credit.sort_values("taxa_pct"),
        x="product",
        y="taxa_pct",
        color="network",
        barmode="group",
        title="Taxas Base por Produto — Crédito PF À Vista (CP)",
        labels={"taxa_pct": "Taxa (%)", "product": "Produto", "network": "Bandeira"},
        color_discrete_map={
            "Visa": "#1a73e8",
            "Mastercard": "#ea4335",
            "AmericanExpress": "#1e8e3e",
            "Elo": "#f9ab00",
            "Hipercard": "#8430ce",
        }
    )
    fig.update_layout(xaxis_tickangle=-30)
    fig.write_html(str(PROJECT_ROOT / "analise_taxas_base.html"))
    print("\n✅ Gráfico salvo: analise_taxas_base.html")

# %% [markdown]
# ## 4. Análise de Ajustes por Tipo

# %%
print("\n" + "=" * 60)
print("4. ANÁLISE DE AJUSTES POR TIPO")
print("=" * 60)

adjustments = df[df["tipo_regra"].str.contains("adjustment", na=False)].copy()
print(f"\nTotal de regras de ajuste: {len(adjustments)}")

adj_summary = adjustments.groupby(["network", "tipo_regra"])["taxa_pct"].agg(
    ["count", "min", "mean", "max"]
).round(3)
print("\nAjustes por bandeira e tipo:")
print(adj_summary.to_string())

print("\nComparativo de ajustes de canal:")
channel_adj = df[df["tipo_regra"].isin(["contactless_adjustment", "cnp_adjustment",
                                         "cnp_authenticated_adjustment"])].copy()
if not channel_adj.empty:
    canal_pivot = channel_adj.pivot_table(
        index="tipo_regra", columns="network", values="taxa_pct", aggfunc="mean"
    ).round(3)
    print(canal_pivot.to_string())

# %% [markdown]
# ## 5. Análise de Parcelamento

# %%
print("\n" + "=" * 60)
print("5. ANÁLISE DE PARCELAMENTO")
print("=" * 60)

parcel = df[df["tipo_regra"] == "installment_adjustment"].copy()
print(f"\nRegras de parcelamento encontradas: {len(parcel)}")

if not parcel.empty:
    parcel_pivot = parcel.pivot_table(
        index="parcelas", columns="network", values="taxa_pct", aggfunc="mean"
    ).round(3)
    print("\nAjuste médio por banda de parcelamento e bandeira:")
    print(parcel_pivot.to_string())

    print("\n📌 Destaque Mastercard: permite parcelamento até 21x (único no mercado BR)")
    mc_parcelas = df[
        (df["network"] == "Mastercard") &
        (df["tipo_regra"] == "installment_adjustment")
    ]["parcelas"].unique()
    print(f"   Bandas Mastercard: {sorted(mc_parcelas)}")

# %% [markdown]
# ## 6. Análise Regulatória BCB

# %%
print("\n" + "=" * 60)
print("6. ANÁLISE REGULATÓRIA — BANCO CENTRAL DO BRASIL")
print("=" * 60)

BCB_DEBIT_MAX = 0.50
BCB_PREPAID_MAX = 0.70
BCB_DEBIT_CAP = 0.35

print(f"""
Limites Regulatórios (Resolução BCB nº 35/2020):
  Débito doméstico:    máx {BCB_DEBIT_MAX:.2f}% | teto BRL R$ {BCB_DEBIT_CAP:.2f}
  Pré-pago doméstico:  máx {BCB_PREPAID_MAX:.2f}%
  Crédito PF:          SEM teto regulatório
""")

debit_rules = df[(df["familia"] == "debit") & (df["tipo_regra"] == "base_rate") &
                 (df["network"] != "BCB_Limite")].copy()
prepaid_rules = df[(df["familia"] == "prepaid") & (df["tipo_regra"] == "base_rate") &
                   (df["network"] != "BCB_Limite")].copy()

print("Taxas de Débito por Bandeira:")
if not debit_rules.empty:
    print(debit_rules[["network", "product", "taxa_pct", "channel"]].to_string(index=False))
    violations_debit = debit_rules[debit_rules["taxa_pct"] > BCB_DEBIT_MAX]
    if not violations_debit.empty:
        print(f"\n⚠️  VIOLAÇÕES BCB (débito > {BCB_DEBIT_MAX}%):")
        print(violations_debit[["network", "product", "taxa_pct"]].to_string(index=False))
    else:
        print(f"\n✅ Todas as taxas de débito estão dentro do limite BCB ({BCB_DEBIT_MAX}%)")

print("\nTaxas de Pré-Pago por Bandeira:")
if not prepaid_rules.empty:
    print(prepaid_rules[["network", "product", "taxa_pct"]].to_string(index=False))
    violations_prepaid = prepaid_rules[prepaid_rules["taxa_pct"] > BCB_PREPAID_MAX]
    if not violations_prepaid.empty:
        print(f"\n⚠️  VIOLAÇÕES BCB (pré-pago > {BCB_PREPAID_MAX}%):")
        print(violations_prepaid[["network", "product", "taxa_pct"]].to_string(index=False))
    else:
        print(f"\n✅ Todas as taxas de pré-pago estão dentro do limite BCB ({BCB_PREPAID_MAX}%)")

# %% [markdown]
# ## 7. Distribuição de Scores de Confiança (Pipeline)

# %%
print("\n" + "=" * 60)
print("7. SCORES DE CONFIANÇA — QUALIDADE DAS EXTRAÇÕES")
print("=" * 60)

# Testa o pipeline com os arquivos de amostra
sample_files = [
    (PROJECT_ROOT / "data" / "visa_sample.txt", "Visa"),
    (PROJECT_ROOT / "data" / "mastercard_sample.txt", "Mastercard"),
    (PROJECT_ROOT / "data" / "amex_bcb_sample.txt", "AmericanExpress"),
]

pipeline_results = []
for path, network in sample_files:
    if path.exists():
        try:
            from src.pipeline import extract_from_document
            result = extract_from_document(path, network=network)
            for rule in result.rules:
                pipeline_results.append({
                    "network": network,
                    "rule_type": rule.rule_type,
                    "confidence_score": rule.confidence_score,
                    "rate_pct": rule.rate_pct,
                    "has_product": rule.product is not None,
                    "has_merchant_group": rule.merchant_group is not None,
                })
        except Exception as e:
            print(f"  ⚠️  Erro em {path.name}: {e}")

if pipeline_results:
    df_pipeline = pd.DataFrame(pipeline_results)
    print(f"\nRegras extraídas pelo pipeline: {len(df_pipeline)}")
    print("\nDistribuição de confiança:")
    bins = [0, 0.50, 0.70, 0.80, 1.01]
    labels = ["Baixa (<0.50)", "Média (0.50-0.70)", "Alta (0.70-0.80)", "Muito Alta (>0.80)"]
    df_pipeline["faixa_confianca"] = pd.cut(df_pipeline["confidence_score"], bins=bins, labels=labels, right=False)
    print(df_pipeline["faixa_confianca"].value_counts().to_string())

    print(f"\nScore médio: {df_pipeline['confidence_score'].mean():.3f}")
    print(f"Score mínimo: {df_pipeline['confidence_score'].min():.3f}")
    print(f"Score máximo: {df_pipeline['confidence_score'].max():.3f}")

    print(f"\n✅ Alta confiança (>=0.70): {(df_pipeline['confidence_score'] >= 0.70).sum()} regras")
    print(f"⚠️  Baixa confiança (<0.50): {(df_pipeline['confidence_score'] < 0.50).sum()} regras")
else:
    print("Nenhum resultado de pipeline disponível.")

# %% [markdown]
# ## 8. Simulações de Exemplo

# %%
print("\n" + "=" * 60)
print("8. SIMULAÇÕES DE TAXA EFETIVA")
print("=" * 60)

try:
    from src.database import init_db
    from src.repository import get_all_rules
    from src.schemas import SimulationRequest
    from src.simulator import compare_networks, simulate

    init_db()
    all_rules = get_all_rules()

    if all_rules:
        scenarios = [
            {
                "descricao": "Visa Platinum | Supermercado | CP | À vista",
                "params": dict(network="Visa", region="BR", audience="PF",
                               card_family="credit", product="Platinum",
                               merchant_group="supermercados", channel="cp",
                               installment_band="avista", transaction_amount=500.0),
            },
            {
                "descricao": "Mastercard Gold | Restaurante | CP | 6x",
                "params": dict(network="Mastercard", region="BR", audience="PF",
                               card_family="credit", product="Gold",
                               merchant_group="outros", channel="cp",
                               installment_band="2-6", transaction_amount=300.0),
            },
            {
                "descricao": "Amex Platinum | Hotel | CP | À vista",
                "params": dict(network="AmericanExpress", region="BR", audience="PF",
                               card_family="credit", product="Platinum",
                               merchant_group="hoteis_aluguel_carros_turismo_joalherias_telemarketing",
                               channel="cp", installment_band="avista", transaction_amount=1000.0),
            },
            {
                "descricao": "Elo Débito | Supermercado | CP | À vista",
                "params": dict(network="Elo", region="BR", card_family="debit",
                               merchant_group="supermercados", channel="cp",
                               installment_band="avista", transaction_amount=150.0),
            },
        ]

        print("\nSimulações de Taxa Efetiva:")
        print("-" * 80)
        for s in scenarios:
            req = SimulationRequest(**s["params"])
            result = simulate(all_rules, req)
            fee_str = f"R$ {result.estimated_fee_amount:.2f}" if result.estimated_fee_amount else "N/A"
            print(f"\n📍 {s['descricao']}")
            print(f"   Taxa efetiva: {result.total_rate_pct:.2f}%")
            if result.total_fixed_fee:
                print(f"   Taxa fixa:    R$ {result.total_fixed_fee:.2f}")
            print(f"   Fee estimado: {fee_str}")
            print(f"   Regras usadas: {len(result.matched_rules)}")

        # Comparativo entre bandeiras
        print("\n" + "-" * 80)
        print("\n🔄 COMPARATIVO MULTI-BANDEIRA — Platinum | CP | À Vista | R$500")
        req_base = SimulationRequest(
            network="Visa", region="BR", audience="PF", card_family="credit",
            product="Platinum", merchant_group="base", channel="cp",
            installment_band="avista", transaction_amount=500.0,
        )
        comparison = compare_networks(all_rules, req_base,
                                      networks=["Visa", "Mastercard", "AmericanExpress", "Elo"])
        for net, resp in sorted(comparison.items()):
            fee = f"R$ {resp.estimated_fee_amount:.2f}" if resp.estimated_fee_amount else "N/A"
            print(f"   {net:<20} {resp.total_rate_pct:.2f}%   {fee}")
    else:
        print("Banco de dados vazio. Execute: python -m src.seed_sample_data")

except Exception as e:
    print(f"⚠️  Erro na simulação: {e}")
    print("   Execute primeiro: python -m src.seed_sample_data")

# %% [markdown]
# ## 9. Exportação de Resultados

# %%
print("\n" + "=" * 60)
print("9. EXPORTAÇÃO DE RESULTADOS")
print("=" * 60)

output_csv = PROJECT_ROOT / "analise_exploratoria_resultado.csv"
df.to_csv(output_csv, index=False, encoding="utf-8-sig")
print(f"\n✅ CSV exportado: {output_csv}")

# Sumário executivo
sumario = {
    "total_regras": len(df),
    "bandeiras": list(df["network"].unique()),
    "tipos_regra": list(df["tipo_regra"].unique()),
    "taxa_credito_media": df[df["tipo_regra"] == "base_rate"]["taxa_pct"].mean().round(3),
    "taxa_credito_max": df[df["tipo_regra"] == "base_rate"]["taxa_pct"].max(),
    "taxa_credito_min": df[df["tipo_regra"] == "base_rate"]["taxa_pct"].min(),
}

print("\n📋 Sumário Executivo:")
for k, v in sumario.items():
    print(f"   {k}: {v}")

print("\n" + "=" * 60)
print("✅ ANÁLISE EXPLORATÓRIA CONCLUÍDA")
print("=" * 60)
print("""
Próximos passos:
  1. python -m src.seed_sample_data          # Popula o banco
  2. uvicorn src.api.main:app --reload       # Inicia API REST
  3. streamlit run src/dashboard.py          # Dashboard interativo
  4. python -m src.reports.generator        # Gera relatório HTML
  5. pytest tests/ -v                        # Executa os testes
""")
