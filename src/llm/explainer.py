"""RAG-based explanation composer.

Inputs:
- `ModelService` (from src.serving.inference) — produces P(default) + top-K SHAP drivers
- A FAISS retriever — narrows the policy corpus to relevant sections
- An LLM — composes the plain-English explanation

Output:
- decision + probability + plain-English explanation + cited policy sections
"""

from __future__ import annotations

import os
from dataclasses import dataclass

from src.serving.schemas import FeatureContribution, LoanApplication
from src.utils import get_logger, load_params

log = get_logger(__name__)

SYSTEM_PROMPT = """\
You are a compliance-aware credit-risk explainer. Given a loan application's
predicted probability of default, its top SHAP drivers, and a few relevant
sections from the lender's policy corpus, write a short plain-English
explanation of the decision.

Rules:
1. Never cite SEX, AGE, MARRIAGE, EDUCATION, or any protected attribute as a
   driver of the decision, even if it appears in the SHAP list. Replace any
   such driver with a paraphrase of the closest legally-permissible feature
   from the SHAP list.
2. Cite policy sections by their section identifier in square brackets, e.g.
   [CP-01 §1.1].
3. Keep the explanation under 130 words.
4. If the decision is "review", note that a human underwriter will follow up.
5. Do not invent policy text — only cite from the supplied policy sections.
"""

USER_TEMPLATE = """\
Decision: {decision}
Predicted probability of default: {probability:.3f}

Top SHAP drivers (feature, SHAP value):
{drivers}

Relevant policy sections:
{policy_sections}

Write the applicant-facing explanation now.
"""

PROTECTED_FEATURES = {
    "SEX",
    "AGE",
    "MARRIAGE",
    "EDUCATION",
    "AGE_BIN",
    # one-hot encoded variants the transformer may produce
    "SEX_1",
    "SEX_2",
    "MARRIAGE_1",
    "MARRIAGE_2",
    "MARRIAGE_3",
    "EDUCATION_1",
    "EDUCATION_2",
    "EDUCATION_3",
    "EDUCATION_4",
}


@dataclass
class LLMExplanation:
    decision: str
    probability: float
    explanation: str
    drivers: list[FeatureContribution]
    citations: list[dict]


def _format_drivers(drivers: list[FeatureContribution]) -> str:
    lines = []
    for d in drivers:
        protected = " (PROTECTED — DO NOT CITE)" if d.feature in PROTECTED_FEATURES else ""
        lines.append(f"- {d.feature}: {d.shap_value:+.3f}{protected}")
    return "\n".join(lines)


def _format_sections(docs) -> str:
    parts = []
    for d in docs:
        sec = d.metadata.get("section", "")
        pid = d.metadata.get("policy_id", "")
        parts.append(f"[{pid} {sec}]\n{d.page_content}")
    return "\n\n".join(parts)


def _select_llm():
    """Pick an LLM by config. Falls back to a deterministic fake so tests + CI
    work without API credentials.
    """
    provider = load_params().get("llm", {}).get("provider", "fake")
    if provider == "openai" and os.environ.get("OPENAI_API_KEY"):
        from langchain_openai import ChatOpenAI

        return ChatOpenAI(model="gpt-4o-mini", temperature=0.2)
    if provider == "bedrock":
        from langchain_aws import ChatBedrock

        return ChatBedrock(
            model_id="anthropic.claude-3-haiku-20240307-v1:0", region_name="us-east-1"
        )
    # fake — deterministic responses for tests / smoke
    from langchain_core.language_models.fake import FakeListLLM

    return FakeListLLM(
        responses=[
            "The application falls into the {decision} band based on recent "
            "payment behaviour and balance trends. The strongest drivers were "
            "delinquency frequency and revolving-credit utilisation; please "
            "see [AA-01 §3.2] and [CP-01 §1.1]. {{review_note}}"
        ]
    )


def explain(
    application: LoanApplication,
    model_service,
    retriever,
    llm=None,
    top_k_drivers: int = 5,
    top_k_docs: int = 4,
) -> LLMExplanation:
    prob, drivers = model_service.explain(application, top_k=top_k_drivers)
    decision = model_service.thresholds.classify(prob)

    # Retrieval query: combine decision + non-protected feature names
    visible_drivers = [d for d in drivers if d.feature not in PROTECTED_FEATURES]
    query_terms = [decision] + [d.feature for d in visible_drivers]
    query = " ".join(query_terms)
    docs = retriever.invoke(query)[:top_k_docs]

    llm = llm or _select_llm()

    prompt_user = USER_TEMPLATE.format(
        decision=decision,
        probability=prob,
        drivers=_format_drivers(drivers),
        policy_sections=_format_sections(docs),
    )

    from langchain_core.messages import HumanMessage, SystemMessage

    messages = [SystemMessage(content=SYSTEM_PROMPT), HumanMessage(content=prompt_user)]
    response = llm.invoke(messages)
    text = response.content if hasattr(response, "content") else str(response)

    citations = [
        {
            "policy_id": d.metadata.get("policy_id", ""),
            "section": d.metadata.get("section", ""),
            "source": d.metadata.get("source", ""),
        }
        for d in docs
    ]

    log.info(
        "llm.explain.done",
        probability=round(prob, 4),
        decision=decision,
        n_citations=len(citations),
    )

    return LLMExplanation(
        decision=decision,
        probability=prob,
        explanation=text,
        drivers=drivers,
        citations=citations,
    )
