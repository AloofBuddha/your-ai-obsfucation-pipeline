"""Authored text sources for fixture documents."""
from tests.fixtures.sources import financial_statement, legal_memo, medical_intake

ALL_SOURCES = [medical_intake, legal_memo, financial_statement]

__all__ = ["ALL_SOURCES", "financial_statement", "legal_memo", "medical_intake"]
