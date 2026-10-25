"""B-SMART research reset: no old trained model is available.

Keep the operational API stable with transparent heuristic fallbacks.
These functions deliberately return no model predictions until a new,
versioned pipeline is trained on the explicitly synthetic integrated data.
"""
from __future__ import annotations
from typing import Any

def load_demand_model(organization_id: str) -> None: return None
def load_churn_model(organization_id: str) -> None: return None
def load_segment_model(organization_id: str) -> None: return None
def load_return_risk_model(organization_id: str) -> None: return None

def predict_daily_rates(organization_id: str, sales: Any) -> dict: return {}
def predict_churn_proba(organization_id: str, sales: Any) -> dict: return {}
def predict_segments(organization_id: str, sales: Any) -> None: return None
def predict_return_risk(organization_id: str, sales: Any) -> dict: return {}
