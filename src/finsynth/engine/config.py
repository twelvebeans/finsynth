"""Persona configuration — the seed for an entire simulation."""

from __future__ import annotations

from datetime import date
from enum import StrEnum

from pydantic import BaseModel, Field


class LifestyleProfile(StrEnum):
    FRUGAL = "frugal"  # Low discretionary, high savings rate
    AVERAGE = "average"  # Moderate spending across all categories
    SPENDER = "spender"  # High discretionary, low savings rate


# Multipliers applied on top of base category amounts per profile
LIFESTYLE_MULTIPLIERS: dict[LifestyleProfile, dict[str, float]] = {
    LifestyleProfile.FRUGAL: {
        "dining": 0.4,
        "clothing": 0.3,
        "entertainment": 0.3,
        "coffee": 0.5,
        "travel": 0.4,
        "savings_rate": 0.20,
        "big_occasion_rate": 0.5,
    },
    LifestyleProfile.AVERAGE: {
        "dining": 1.0,
        "clothing": 1.0,
        "entertainment": 1.0,
        "coffee": 1.0,
        "travel": 1.0,
        "savings_rate": 0.12,
        "big_occasion_rate": 1.0,
    },
    LifestyleProfile.SPENDER: {
        "dining": 1.8,
        "clothing": 1.9,
        "entertainment": 1.7,
        "coffee": 1.5,
        "travel": 2.0,
        "savings_rate": 0.05,
        "big_occasion_rate": 1.8,
    },
}


class PersonaConfig(BaseModel):
    """
    Full configuration for one synthetic persona.

    All randomness in the simulation is derived from ``seed``, so the
    same config always produces the same output — critical for test
    reproducibility.
    """

    # Identity
    name: str = "Synthetic User"
    locale: str = "en_CA"
    currency: str = "CAD"

    # Income
    monthly_income: float = 4500.0
    income_category: str = "salary"  # "salary" | "freelance"
    payday_dom: int = 15  # Day-of-month for salary deposit
    has_credit_card: bool = True

    # Lifestyle
    lifestyle: LifestyleProfile = LifestyleProfile.AVERAGE

    # Date range
    start_date: date = Field(default_factory=lambda: date(2023, 1, 1))
    end_date: date = Field(default_factory=lambda: date(2024, 12, 31))

    # Inflation (annual rates per broad category)
    inflation: dict[str, float] = Field(
        default_factory=lambda: {
            "rent": 0.04,
            "utilities": 0.07,
            "groceries": 0.05,
            "fuel": 0.06,
            "general": 0.03,
        }
    )

    # Life-event probabilities (per month)
    prob_raise_per_month: float = 0.03  # ~3% chance of raise each month
    prob_job_change_per_month: float = 0.008  # ~once per ~10 years
    prob_bonus_per_month: float = 0.04  # Bonus months
    raise_pct_mean: float = 0.06  # 6% average raise
    raise_pct_std: float = 0.03

    # Reproducibility
    seed: int = 42

    @property
    def lifestyle_params(self) -> dict[str, float]:
        return LIFESTYLE_MULTIPLIERS[self.lifestyle]
