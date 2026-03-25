"""
src/schemas.py
==============
Modelos Pydantic que representam as entidades do domínio de intercâmbio.

Classes:
    RuleCandidate       — Uma regra extraída e validada de um documento.
    ExtractResult       — Resultado completo de uma extração de documento.
    SimulationRequest   — Parâmetros de entrada para simulação de taxa.
    SimulationResponse  — Resultado da simulação com regras e totais.
    UploadResponse      — Resposta do endpoint de upload.
"""
from __future__ import annotations

from datetime import date
from typing import Any

from pydantic import BaseModel, Field


class RuleCandidate(BaseModel):
    """
    Representa uma regra de intercâmbio extraída de um documento das Bandeiras.

    Campos de identificação:
        network          — Bandeira: "Visa" | "Mastercard"
        region           — Região: "BR" (padrão)
        rule_type        — Tipo da regra (ver RULE_TYPES abaixo)

    Campos de segmentação:
        audience         — Público: "PF" | "PJ" | "ALL"
        card_family      — Família: "credit" | "debit" | "prepaid" | "cash_withdrawal"
        product          — Produto específico: "Platinum", "Black", etc.
        merchant_group   — Segmento de comércio: "supermercados", etc.
        channel          — Canal: "cp" | "cp_contactless" | "cnp" | "atm"
        installment_band — Banda de parcelamento: "2-6" | "7-12" | "7-21"

    Campos de valor:
        rate_pct         — Taxa percentual (ex: 1.73 para 1,73%)
        fixed_fee_amount — Taxa fixa em reais (ex: 8.00)
        currency         — Moeda: "BRL"
        cap_amount       — Teto por transação (ex: 0.35)
        floor_amount     — Piso por transação

    Campos de rastreabilidade:
        effective_from   — Vigência inicial
        effective_to     — Vigência final
        evidence_text    — Trecho original do documento
        page_number      — Página de origem no PDF
        confidence_score — Score de confiança [0.0 – 1.0]
        metadata         — Dados extras (uso livre)
    """

    # --- Identificação ---
    network: str  # "Visa" | "Mastercard"
    region: str = "BR"
    rule_type: str  # base_rate | merchant_adjustment | installment_adjustment | etc.

    # --- Segmentação ---
    audience: str | None = None  # PF | PJ | ALL
    card_family: str | None = None  # credit | debit | prepaid | cash_withdrawal
    product: str | None = None  # Classic | Gold | Platinum | Black | ...
    merchant_group: str | None = None  # supermercados | postos | outros | ...
    channel: str | None = None  # cp | cp_contactless | cnp | atm
    installment_band: str | None = None  # "2-6" | "7-12" | "avista"

    # --- Valores ---
    rate_pct: float | None = None
    fixed_fee_amount: float | None = None
    currency: str | None = None  # BRL
    cap_amount: float | None = None
    floor_amount: float | None = None

    # --- Vigência ---
    effective_from: date | None = None
    effective_to: date | None = None

    # --- Rastreabilidade ---
    evidence_text: str = ""
    page_number: int | None = None
    confidence_score: float = Field(default=0.5, ge=0.0, le=1.0)
    metadata: dict[str, Any] = Field(default_factory=dict)


# Tipos de regra aceitos pelo sistema
RULE_TYPES = [
    "base_rate",                    # Taxa base do produto
    "merchant_adjustment",          # Ajuste por segmento de comércio
    "installment_adjustment",       # Ajuste por parcelamento
    "contactless_adjustment",       # Ajuste contactless
    "cnp_adjustment",               # Ajuste CNP (cartão não-presente)
    "cnp_authenticated_adjustment", # Ajuste CNP autenticado (VbV / ECI5)
    "capture_adjustment",           # Ajuste por modalidade de captura
    "special_product_adjustment",   # Ajuste por produto especial
    "fixed_fee",                    # Taxa fixa (ex: saque ATM)
    "cap",                          # Regra de teto
    "floor",                        # Regra de piso
]


class ExtractResult(BaseModel):
    """Resultado completo de uma extração de documento."""

    source_path: str
    network: str
    region: str = "BR"
    rules: list[RuleCandidate]
    warnings: list[str] = Field(default_factory=list)

    @property
    def high_confidence_rules(self) -> list[RuleCandidate]:
        """Retorna apenas regras com score >= 0.70."""
        return [r for r in self.rules if r.confidence_score >= 0.70]

    @property
    def low_confidence_rules(self) -> list[RuleCandidate]:
        """Retorna regras que precisam de revisão humana (score < 0.50)."""
        return [r for r in self.rules if r.confidence_score < 0.50]


class SimulationRequest(BaseModel):
    """
    Parâmetros para simular a taxa de intercâmbio de uma transação.

    Exemplo:
        {
          "network": "Visa",
          "region": "BR",
          "audience": "PF",
          "card_family": "credit",
          "product": "Platinum",
          "merchant_group": "supermercados",
          "channel": "cp",
          "installment_band": null
        }
    """

    network: str
    region: str = "BR"
    audience: str | None = None
    card_family: str | None = None
    product: str | None = None
    merchant_group: str | None = None
    channel: str | None = None
    installment_band: str | None = None
    transaction_amount: float | None = None  # Para cálculo de taxa absoluta


class SimulationResponse(BaseModel):
    """Resultado de uma simulação de taxa."""

    matched_rules: list[RuleCandidate]
    total_rate_pct: float = 0.0
    total_fixed_fee: float = 0.0
    effective_cap: float | None = None
    estimated_fee_amount: float | None = None  # Baseado em transaction_amount
    notes: list[str] = Field(default_factory=list)


class UploadResponse(BaseModel):
    """Resposta do endpoint POST /extract."""

    message: str
    extracted_rules: int
    high_confidence: int = 0
    low_confidence: int = 0
    warnings: list[str] = Field(default_factory=list)
