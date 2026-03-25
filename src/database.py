"""
src/database.py
===============
Camada de persistência com SQLAlchemy.

Entidades:
    RuleRecord      — Regra de intercâmbio persistida no banco
    ExtractionLog   — Log de execuções do pipeline

A engine suporta:
    - SQLite  (desenvolvimento, zero-config, padrão)
    - PostgreSQL via psycopg3 (produção, requer Docker ou servidor)

Uso:
    from src.database import init_db, SessionLocal

    init_db()   # Cria as tabelas (idempotente)

    with SessionLocal() as session:
        session.add(record)
        session.commit()
"""
from __future__ import annotations

import logging
from datetime import datetime

from sqlalchemy import (
    JSON,
    DateTime,
    Float,
    Integer,
    String,
    Text,
    create_engine,
    func,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column, sessionmaker

from .config import settings

logger = logging.getLogger(__name__)


class Base(DeclarativeBase):
    """Base para todos os modelos ORM."""
    pass


class RuleRecord(Base):
    """
    Registro de uma regra de intercâmbio no banco de dados.

    Corresponde à tabela `interchange_rule_app`.
    Versionamento é feito pelo campo `version_tag` (ex: "2025-Q1").
    """

    __tablename__ = "interchange_rule_app"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)

    # Identificação da regra
    network: Mapped[str] = mapped_column(String(32), index=True)
    region: Mapped[str] = mapped_column(String(16), index=True, default="BR")
    rule_type: Mapped[str] = mapped_column(String(64), index=True)

    # Segmentação
    audience: Mapped[str | None] = mapped_column(String(16), nullable=True, index=True)
    card_family: Mapped[str | None] = mapped_column(String(32), nullable=True, index=True)
    product: Mapped[str | None] = mapped_column(String(128), nullable=True, index=True)
    merchant_group: Mapped[str | None] = mapped_column(String(256), nullable=True)
    channel: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    installment_band: Mapped[str | None] = mapped_column(String(32), nullable=True)

    # Valores
    rate_pct: Mapped[float | None] = mapped_column(Float, nullable=True)
    fixed_fee_amount: Mapped[float | None] = mapped_column(Float, nullable=True)
    currency: Mapped[str | None] = mapped_column(String(8), nullable=True)
    cap_amount: Mapped[float | None] = mapped_column(Float, nullable=True)
    floor_amount: Mapped[float | None] = mapped_column(Float, nullable=True)

    # Vigência
    effective_from: Mapped[str | None] = mapped_column(String(16), nullable=True)
    effective_to: Mapped[str | None] = mapped_column(String(16), nullable=True)

    # Rastreabilidade
    evidence_text: Mapped[str] = mapped_column(Text)
    page_number: Mapped[int | None] = mapped_column(Integer, nullable=True)
    confidence_score: Mapped[float] = mapped_column(Float, default=0.5)
    metadata_json: Mapped[dict] = mapped_column(JSON, default=dict)

    # Versionamento / auditoria
    version_tag: Mapped[str | None] = mapped_column(String(32), nullable=True, index=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=func.now(), nullable=False
    )

    def __repr__(self) -> str:
        return (
            f"<RuleRecord id={self.id} network={self.network!r} "
            f"rule_type={self.rule_type!r} rate_pct={self.rate_pct}>"
        )


class ExtractionLog(Base):
    """
    Log de execuções do pipeline de extração.

    Permite auditoria e acompanhamento das extrações.
    """

    __tablename__ = "extraction_log"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    source_path: Mapped[str] = mapped_column(Text)
    network: Mapped[str] = mapped_column(String(32))
    region: Mapped[str] = mapped_column(String(16), default="BR")
    total_rules: Mapped[int] = mapped_column(Integer, default=0)
    high_confidence: Mapped[int] = mapped_column(Integer, default=0)
    low_confidence: Mapped[int] = mapped_column(Integer, default=0)
    warnings: Mapped[str] = mapped_column(Text, default="")
    status: Mapped[str] = mapped_column(String(32), default="success")
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=func.now(), nullable=False
    )


# ---------------------------------------------------------------------------
# Engine e SessionFactory
# ---------------------------------------------------------------------------

def _create_engine_safe():
    """
    Cria a engine SQLAlchemy com fallback automático para SQLite.

    Se DATABASE_URL aponta para PostgreSQL mas psycopg não está instalado
    (comum no Windows sem Docker), cai automaticamente para SQLite local
    com um aviso claro — sem travar a aplicação.
    """
    db_url = settings.database_url

    # Se for PostgreSQL, verifica se o driver está disponível
    if "postgresql" in db_url or "postgres" in db_url:
        try:
            import psycopg  # psycopg v3
        except ImportError:
            try:
                import psycopg2  # psycopg v2 fallback
                # Adapta URL de psycopg3 para psycopg2
                db_url = db_url.replace("postgresql+psycopg://", "postgresql+psycopg2://")
                db_url = db_url.replace("postgresql+psycopg2://", "postgresql+psycopg2://")
            except ImportError:
                fallback = "sqlite+pysqlite:///./interchange_ai.db"
                logger.warning(
                    "Driver PostgreSQL não encontrado (psycopg/psycopg2). "
                    "Usando SQLite: %s\n"
                    "Para PostgreSQL, instale: pip install psycopg2-binary",
                    fallback,
                )
                db_url = fallback

    return create_engine(
        db_url,
        future=True,
        echo=False,
        pool_pre_ping=True,
    )


engine = _create_engine_safe()
SessionLocal = sessionmaker(engine, expire_on_commit=False, class_=Session)


def init_db() -> None:
    """
    Cria todas as tabelas no banco de dados (idempotente).

    Deve ser chamado na inicialização da aplicação.
    """
    logger.info("Inicializando banco de dados: %s", str(engine.url)[:60])
    Base.metadata.create_all(bind=engine)
    logger.info("Tabelas criadas/verificadas com sucesso.")
