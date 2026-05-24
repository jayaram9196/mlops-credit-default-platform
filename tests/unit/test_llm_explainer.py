"""Unit tests for the LLM/RAG composer.

We don't pull a real model or build a real index — the explainer is composed of
pure functions plus a single LLM invocation, both of which we mock.
"""

from __future__ import annotations

from dataclasses import dataclass

import pytest

from src.llm.explainer import (
    PROTECTED_FEATURES,
    _format_drivers,
    _format_sections,
    explain,
)
from src.serving.schemas import FeatureContribution, LoanApplication


@dataclass
class _FakeDoc:
    page_content: str
    metadata: dict


class _FakeRetriever:
    def __init__(self, docs):
        self._docs = docs

    def invoke(self, _query: str):
        return self._docs


class _FakeLLM:
    def __init__(self, text: str):
        self._text = text

    def invoke(self, _messages):
        # mimic the langchain message API
        class _Resp:
            def __init__(self, text):
                self.content = text

        return _Resp(self._text)


class _FakeModelService:
    version = "test"

    class _Thresholds:
        def classify(self, prob):
            return "deny" if prob >= 0.6 else ("review" if prob >= 0.3 else "approve")

    thresholds = _Thresholds()

    def __init__(self, prob, drivers):
        self._prob = prob
        self._drivers = drivers

    def explain(self, _application, top_k):
        return self._prob, self._drivers[:top_k]


def _sample_app() -> LoanApplication:
    return LoanApplication(
        limit_bal=50000,
        sex=1,
        education=2,
        marriage=1,
        age=35,
        pay_0=2,
        pay_2=2,
        pay_3=1,
        pay_4=0,
        pay_5=0,
        pay_6=0,
        bill_amt1=48000,
        bill_amt2=47000,
        bill_amt3=46000,
        bill_amt4=45000,
        bill_amt5=44000,
        bill_amt6=43000,
        pay_amt1=100,
        pay_amt2=100,
        pay_amt3=100,
        pay_amt4=100,
        pay_amt5=100,
        pay_amt6=100,
    )


@pytest.mark.unit
def test_format_drivers_flags_protected():
    drivers = [
        FeatureContribution(feature="PAY_DELAY_MAX", shap_value=1.1),
        FeatureContribution(feature="SEX", shap_value=0.5),
    ]
    out = _format_drivers(drivers)
    assert "PAY_DELAY_MAX" in out
    assert "SEX" in out
    assert "PROTECTED" in out


@pytest.mark.unit
def test_format_sections_includes_policy_id_and_section():
    docs = [
        _FakeDoc("body", {"policy_id": "CP-01", "section": "1.1", "source": "x.md"}),
        _FakeDoc("body2", {"policy_id": "FL-01", "section": "2.1", "source": "y.md"}),
    ]
    out = _format_sections(docs)
    assert "[CP-01 1.1]" in out
    assert "[FL-01 2.1]" in out


@pytest.mark.unit
def test_explain_skips_protected_in_retrieval_query_and_returns_citations():
    drivers = [
        FeatureContribution(feature="PAY_DELAY_MAX", shap_value=1.0),
        FeatureContribution(feature="SEX", shap_value=0.5),
        FeatureContribution(feature="UTILISATION_LAST", shap_value=0.3),
    ]
    svc = _FakeModelService(prob=0.78, drivers=drivers)
    docs = [
        _FakeDoc(
            "Top deny reasons must follow §3.2",
            {
                "policy_id": "AA-01",
                "section": "3.2",
                "source": "data/policies/03-adverse-action.md",
            },
        ),
        _FakeDoc(
            "Utilisation > 70% denied",
            {"policy_id": "CP-01", "section": "1.1", "source": "data/policies/01-credit-policy.md"},
        ),
    ]
    retriever = _FakeRetriever(docs)
    llm = _FakeLLM("This is the explanation citing [AA-01 §3.2] and [CP-01 §1.1].")

    result = explain(_sample_app(), svc, retriever, llm=llm)

    assert result.decision == "deny"
    assert result.probability == pytest.approx(0.78)
    assert len(result.drivers) == 3
    assert len(result.citations) == 2
    assert result.citations[0]["policy_id"] == "AA-01"
    assert "AA-01" in result.explanation


@pytest.mark.unit
def test_protected_set_contains_canonical_features():
    for f in ("SEX", "AGE", "MARRIAGE", "EDUCATION", "AGE_BIN"):
        assert f in PROTECTED_FEATURES
