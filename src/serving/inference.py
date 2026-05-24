"""Inference service: feature engineering + transform + model + SHAP.

Loads the joblib artifacts produced by the Phase 1 pipeline. In production this
loader can be swapped for an MLflow-registry-backed loader; the public
ModelService API stays identical.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

import joblib
import numpy as np
import pandas as pd
import shap

from src.features.build import (
    PROTECTED_RAW,
    assemble,
    coerce_categorical_ints,
)
from src.serving.schemas import (
    Decision,
    FeatureContribution,
    LoanApplication,
)

UCI_FIELD_MAP = {
    "limit_bal": "LIMIT_BAL",
    "sex": "SEX",
    "education": "EDUCATION",
    "marriage": "MARRIAGE",
    "age": "AGE",
    "pay_0": "PAY_0", "pay_2": "PAY_2", "pay_3": "PAY_3",
    "pay_4": "PAY_4", "pay_5": "PAY_5", "pay_6": "PAY_6",
    "bill_amt1": "BILL_AMT1", "bill_amt2": "BILL_AMT2", "bill_amt3": "BILL_AMT3",
    "bill_amt4": "BILL_AMT4", "bill_amt5": "BILL_AMT5", "bill_amt6": "BILL_AMT6",
    "pay_amt1": "PAY_AMT1", "pay_amt2": "PAY_AMT2", "pay_amt3": "PAY_AMT3",
    "pay_amt4": "PAY_AMT4", "pay_amt5": "PAY_AMT5", "pay_amt6": "PAY_AMT6",
}


@dataclass
class DecisionThresholds:
    deny: float
    review: float

    def classify(self, prob: float) -> Decision:
        if prob >= self.deny:
            return "deny"
        if prob >= self.review:
            return "review"
        return "approve"


def applications_to_frame(apps: Iterable[LoanApplication]) -> pd.DataFrame:
    rows = []
    for app in apps:
        payload = app.model_dump()
        rows.append({UCI_FIELD_MAP[k]: v for k, v in payload.items()})
    return pd.DataFrame(rows)


class ModelService:
    def __init__(
        self,
        model,
        feature_names: list[str],
        transformer,
        transformer_input_cols: list[str],
        thresholds: DecisionThresholds,
        version: str,
    ):
        self.model = model
        self.feature_names = feature_names
        self.transformer = transformer
        self.transformer_input_cols = transformer_input_cols
        self.thresholds = thresholds
        self.version = version
        self._explainer: shap.TreeExplainer | None = None

    @classmethod
    def load(
        cls,
        model_path: Path,
        transformer_path: Path,
        thresholds: DecisionThresholds,
        version: str = "local",
    ) -> "ModelService":
        bundle = joblib.load(model_path)
        artifacts = joblib.load(transformer_path)
        input_cols = list(artifacts["numeric_columns"]) + list(artifacts["categorical_columns"])
        return cls(
            model=bundle["model"],
            feature_names=list(bundle["feature_names"]),
            transformer=artifacts["transformer"],
            transformer_input_cols=input_cols,
            thresholds=thresholds,
            version=version,
        )

    @property
    def explainer(self) -> shap.TreeExplainer:
        if self._explainer is None:
            self._explainer = shap.TreeExplainer(self.model)
        return self._explainer

    def _prepare(self, apps: Iterable[LoanApplication]) -> np.ndarray:
        raw = applications_to_frame(apps)
        engineered = coerce_categorical_ints(assemble(raw))
        # Drop protected + ID-like cols not seen by transformer
        drop = [c for c in PROTECTED_RAW if c in engineered.columns]
        engineered = engineered.drop(columns=drop, errors="ignore")
        # Keep only the columns the transformer was fit on, in fit order
        missing = [c for c in self.transformer_input_cols if c not in engineered.columns]
        for c in missing:
            engineered[c] = np.nan  # rare; transformer's imputer will fill
        ordered = engineered[self.transformer_input_cols]
        return self.transformer.transform(ordered)

    def predict_proba(self, apps: Iterable[LoanApplication]) -> np.ndarray:
        x = self._prepare(apps)
        return self.model.predict_proba(x)[:, 1]

    def predict(self, apps: list[LoanApplication]) -> list[tuple[float, Decision]]:
        probs = self.predict_proba(apps)
        return [(float(p), self.thresholds.classify(float(p))) for p in probs]

    def explain(self, app: LoanApplication, top_k: int) -> tuple[float, list[FeatureContribution]]:
        x = self._prepare([app])
        prob = float(self.model.predict_proba(x)[:, 1][0])
        sv = self.explainer.shap_values(x)
        if isinstance(sv, list):
            sv = sv[1] if len(sv) == 2 else sv[0]
        sv = np.asarray(sv).reshape(-1)
        order = np.argsort(-np.abs(sv))[:top_k]
        drivers = [
            FeatureContribution(feature=self.feature_names[i], shap_value=float(sv[i]))
            for i in order
        ]
        return prob, drivers
