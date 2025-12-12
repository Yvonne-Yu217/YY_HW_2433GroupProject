"""Mock data module.

Contains in-memory mock datasets for states, plans, plan details, and analytics base rates.
This file centralizes mock data so it can later be replaced with a cloud data retrieval layer.
"""
from typing import List, Dict

STATE_OPTIONS: List[str] = ["NY", "NJ", "CA", "FL"]

PLAN_OPTIONS: Dict[str, List[str]] = {
    "NY": ["Basic", "Plus"],
    "NJ": ["Standard", "Premium"],
    "CA": ["Bronze", "Silver", "Gold"],
    "FL": ["Basic", "Plus", "Premium"],
}

PLAN_DETAILS = {
    ("NY", "Basic"): {
        "deductibles": [500, 1000, 2000],
        "tiers": ["Bronze", "Silver"],
        "base_rate": 280.0,
    },
    ("NY", "Plus"): {
        "deductibles": [250, 500, 1000],
        "tiers": ["Silver", "Gold"],
        "base_rate": 350.0,
    },
    ("NJ", "Standard"): {
        "deductibles": [500, 1500],
        "tiers": ["Bronze", "Silver"],
        "base_rate": 310.0,
    },
    ("NJ", "Premium"): {
        "deductibles": [250, 500],
        "tiers": ["Gold"],
        "base_rate": 420.0,
    },
    ("CA", "Bronze"): {
        "deductibles": [1000, 2000],
        "tiers": ["Bronze"],
        "base_rate": 260.0,
    },
    ("CA", "Silver"): {
        "deductibles": [500, 1000],
        "tiers": ["Silver"],
        "base_rate": 330.0,
    },
    ("CA", "Gold"): {
        "deductibles": [250, 500],
        "tiers": ["Gold"],
        "base_rate": 390.0,
    },
    ("FL", "Basic"): {
        "deductibles": [500, 1000],
        "tiers": ["Bronze"],
        "base_rate": 290.0,
    },
    ("FL", "Plus"): {
        "deductibles": [250, 500],
        "tiers": ["Silver"],
        "base_rate": 360.0,
    },
    ("FL", "Premium"): {
        "deductibles": [100, 250],
        "tiers": ["Gold"],
        "base_rate": 450.0,
    },
}

ANALYTICS_BASE_RATE = {
    "NY": {2024: 300.0, 2025: 315.0, 2026: 330.0},
    "NJ": {2024: 320.0, 2025: 335.0, 2026: 350.0},
    "CA": {2024: 280.0, 2025: 295.0, 2026: 310.0},
    "FL": {2024: 310.0, 2025: 325.0, 2026: 340.0},
}


# Percentage options (e.g., coverage percent)
PERCENTAGE_OPTIONS = [80, 90, 100]


def compute_current_premium(state_code: str, plan_name: str, deductible: int, coverage_tier: str, percentage: int = 100, age: int | None = None) -> float:
    """Compute the current fixed monthly premium for the selected options.

    This mirrors the simple deterministic logic used in the app but lives in mock_data
    so later cloud/data-layer implementations can provide real price tables.
    """
    details = PLAN_DETAILS.get((state_code, plan_name))
    if not details:
        return 0.0

    base = float(details.get("base_rate", 0.0))

    ded_map = {100: 1.2, 250: 1.1, 500: 1.0, 1000: 0.9, 1500: 0.85, 2000: 0.8}
    ded_factor = ded_map.get(deductible, 1.0)

    tier_map = {"Bronze": 1.0, "Silver": 1.15, "Gold": 1.3}
    tier_factor = tier_map.get(coverage_tier, 1.0)

    pct_factor = float(percentage) / 100.0 if percentage else 1.0

    age_factor = 1.0
    if age is not None:
        age_factor += ((age - 40) / 10.0) * 0.005

    premium = base * ded_factor * tier_factor * pct_factor * age_factor
    return round(premium, 2)

