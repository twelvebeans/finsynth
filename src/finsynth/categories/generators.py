"""
Category-specific transaction generators.

Each generator is a callable that accepts the current simulation date,
the elapsed months since start, and an RNG, and returns zero or more
Transaction objects to record on that day.
"""

from __future__ import annotations

import math
from datetime import date
from decimal import Decimal

import numpy as np

from finsynth.engine.config import PersonaConfig
from finsynth.transactions.models import Transaction, TransactionCategory

# ---------------------------------------------------------------------------
# Inflation helpers
# ---------------------------------------------------------------------------


def _inflation_factor(config: PersonaConfig, category_key: str, months_elapsed: float) -> float:
    """Compound inflation multiplier for a given category after N months."""
    annual_rate = config.inflation.get(category_key, config.inflation["general"])
    return (1 + annual_rate) ** (months_elapsed / 12)


# ---------------------------------------------------------------------------
# Recurring spending
# ---------------------------------------------------------------------------

RECURRING_SCHEDULE: list[dict] = [
    # (category, dom, base_amount, inflation_key, description, jitter_pct)
    {
        "cat": TransactionCategory.RENT,
        "dom": 1,
        "base": 1400,
        "inf": "rent",
        "desc": "Monthly rent",
        "jitter": 0.0,
    },
    {
        "cat": TransactionCategory.UTILITIES,
        "dom": 3,
        "base": 95,
        "inf": "utilities",
        "desc": "Electricity bill",
        "jitter": 0.12,
    },
    {
        "cat": TransactionCategory.INTERNET,
        "dom": 5,
        "base": 75,
        "inf": "general",
        "desc": "Internet service",
        "jitter": 0.0,
    },
    {
        "cat": TransactionCategory.PHONE,
        "dom": 7,
        "base": 55,
        "inf": "general",
        "desc": "Mobile phone plan",
        "jitter": 0.0,
    },
    {
        "cat": TransactionCategory.INSURANCE,
        "dom": 10,
        "base": 130,
        "inf": "general",
        "desc": "Home / tenant insurance",
        "jitter": 0.02,
    },
    {
        "cat": TransactionCategory.SUBSCRIPTIONS,
        "dom": 12,
        "base": 45,
        "inf": "general",
        "desc": "Streaming & software",
        "jitter": 0.04,
    },
    {
        "cat": TransactionCategory.GYM,
        "dom": 15,
        "base": 50,
        "inf": "general",
        "desc": "Gym membership",
        "jitter": 0.0,
    },
]

GROCERY_RUN_DAYS = {1, 8, 15, 22}  # ~4 runs/month


def generate_recurring(
    current_date: date,
    months_elapsed: float,
    config: PersonaConfig,
    account_ids: dict[str, str],
    rng: np.random.Generator,
) -> list[Transaction]:
    """Generate recurring bill payments that fall on current_date."""
    txns: list[Transaction] = []
    dom = current_date.day
    spend_account = account_ids.get("credit_card") or account_ids["checking"]

    for item in RECURRING_SCHEDULE:
        if item["dom"] != dom:
            continue
        base = item["base"]
        inf_factor = _inflation_factor(config, item["inf"], months_elapsed)
        jitter = 1 + rng.normal(0, item["jitter"]) if item["jitter"] > 0 else 1.0
        amount = Decimal(str(round(base * inf_factor * jitter, 2)))
        txns.append(
            Transaction(
                date=current_date,
                from_account_id=spend_account,
                to_account_id="acc_external",
                amount=amount,
                category=item["cat"],
                description=item["desc"],
                is_recurring=True,
            )
        )

    # Grocery runs
    if dom in GROCERY_RUN_DAYS:
        base_grocery = 120.0
        inf_factor = _inflation_factor(config, "groceries", months_elapsed)
        seasonal_factor = 1 + 0.1 * math.sin(2 * math.pi * current_date.month / 12)
        jitter = 1 + rng.normal(0, 0.08)
        amount = Decimal(str(round(base_grocery * inf_factor * seasonal_factor * jitter, 2)))
        txns.append(
            Transaction(
                date=current_date,
                from_account_id=spend_account,
                to_account_id="acc_external",
                amount=abs(amount),
                category=TransactionCategory.GROCERIES,
                description="Grocery shopping",
                is_recurring=True,
            )
        )

    return txns


# ---------------------------------------------------------------------------
# Irregular / discretionary spending
# ---------------------------------------------------------------------------

IRREGULAR_CATEGORIES: list[dict] = [
    # (category, mean_per_month, std, inf_key, descriptions, seasonal_peak_month)
    {
        "cat": TransactionCategory.DINING,
        "mean_txns": 6.0,
        "amount_mean": 35,
        "amount_std": 15,
        "inf": "general",
        "seasonal_peak": 12,
        "descs": ["Restaurant dinner", "Takeout", "Lunch out", "Brunch", "Fast food"],
    },
    {
        "cat": TransactionCategory.COFFEE,
        "mean_txns": 10.0,
        "amount_mean": 7,
        "amount_std": 2,
        "inf": "general",
        "seasonal_peak": None,
        "descs": ["Coffee shop", "Café", "Coffee & snack"],
    },
    {
        "cat": TransactionCategory.TRANSPORT,
        "mean_txns": 8.0,
        "amount_mean": 12,
        "amount_std": 5,
        "inf": "fuel",
        "seasonal_peak": None,
        "descs": ["Transit pass top-up", "Rideshare", "Parking"],
    },
    {
        "cat": TransactionCategory.CLOTHING,
        "mean_txns": 1.2,
        "amount_mean": 80,
        "amount_std": 40,
        "inf": "general",
        "seasonal_peak": 11,
        "descs": ["Clothing store", "Online fashion", "Shoes"],
    },
    {
        "cat": TransactionCategory.ENTERTAINMENT,
        "mean_txns": 2.0,
        "amount_mean": 25,
        "amount_std": 15,
        "inf": "general",
        "seasonal_peak": 7,
        "descs": ["Movie tickets", "Concert", "Event tickets", "Video game"],
    },
    {
        "cat": TransactionCategory.PERSONAL_CARE,
        "mean_txns": 1.5,
        "amount_mean": 40,
        "amount_std": 15,
        "inf": "general",
        "seasonal_peak": None,
        "descs": ["Haircut", "Pharmacy", "Personal care products"],
    },
]


def _seasonal_multiplier(month: int, peak_month: int | None) -> float:
    """Boost spending in the peak month and neighbour months."""
    if peak_month is None:
        return 1.0
    distance = min(abs(month - peak_month), 12 - abs(month - peak_month))
    return 1 + 0.5 * math.exp(-0.5 * distance**2)


def generate_irregular(
    current_date: date,
    months_elapsed: float,
    config: PersonaConfig,
    account_ids: dict[str, str],
    rng: np.random.Generator,
) -> list[Transaction]:
    """Generate irregular discretionary spending for current_date."""
    txns: list[Transaction] = []
    spend_account = account_ids.get("credit_card") or account_ids["checking"]
    lifestyle = config.lifestyle_params
    days_in_month = 30  # Approximation for daily rate calculation

    for item in IRREGULAR_CATEGORIES:
        cat_key = item["cat"].value.split("_")[0]  # e.g. "dining"
        lm = lifestyle.get(cat_key, 1.0)
        seasonal = _seasonal_multiplier(current_date.month, item["seasonal_peak"])
        daily_rate = item["mean_txns"] * lm * seasonal / days_in_month
        inf_factor = _inflation_factor(config, item["inf"], months_elapsed)

        # Bernoulli draw: does a transaction happen today?
        if rng.random() > daily_rate:
            continue

        raw_amount = rng.normal(item["amount_mean"], item["amount_std"])
        amount = Decimal(str(round(max(1.0, raw_amount) * inf_factor, 2)))
        desc = rng.choice(item["descs"])
        txns.append(
            Transaction(
                date=current_date,
                from_account_id=spend_account,
                to_account_id="acc_external",
                amount=amount,
                category=item["cat"],
                description=str(desc),
                is_recurring=False,
            )
        )

    return txns


# ---------------------------------------------------------------------------
# Big occasional spending
# ---------------------------------------------------------------------------

BIG_OCCASIONAL_EVENTS: list[dict] = [
    {
        "cat": TransactionCategory.TRAVEL,
        "mean_per_year": 1.5,
        "min": 400,
        "max": 4000,
        "descs": ["Flight booking", "Hotel stay", "Vacation package"],
        "requires_savings": True,
    },
    {
        "cat": TransactionCategory.ELECTRONICS,
        "mean_per_year": 1.0,
        "min": 200,
        "max": 2000,
        "descs": ["New laptop", "Smartphone upgrade", "Tablet", "Monitor"],
        "requires_savings": True,
    },
    {
        "cat": TransactionCategory.APPLIANCES,
        "mean_per_year": 0.5,
        "min": 300,
        "max": 2500,
        "descs": ["Washing machine", "Refrigerator", "Dishwasher", "Vacuum robot"],
        "requires_savings": True,
    },
    {
        "cat": TransactionCategory.MEDICAL,
        "mean_per_year": 1.2,
        "min": 100,
        "max": 1500,
        "descs": ["Dental work", "Eye exam & glasses", "Physiotherapy", "Specialist visit"],
        "requires_savings": False,  # Medical can overdraw slightly
    },
    {
        "cat": TransactionCategory.HOME_IMPROVEMENT,
        "mean_per_year": 0.8,
        "min": 200,
        "max": 3000,
        "descs": ["Furniture", "Paint & supplies", "Contractor work"],
        "requires_savings": True,
    },
    {
        "cat": TransactionCategory.CAR_REPAIR,
        "mean_per_year": 0.6,
        "min": 200,
        "max": 1800,
        "descs": ["Car service", "Tyre replacement", "Brake repair"],
        "requires_savings": False,
    },
]


def generate_big_occasional(
    current_date: date,
    months_elapsed: float,
    config: PersonaConfig,
    account_ids: dict[str, str],
    savings_balance: Decimal,
    rng: np.random.Generator,
) -> list[Transaction]:
    """
    Generate big occasional events with Poisson-distributed arrivals.
    Purchases that require savings are deferred if savings are insufficient.
    """
    txns: list[Transaction] = []
    lm = config.lifestyle_params.get("big_occasion_rate", 1.0)
    inf_factor = _inflation_factor(config, "general", months_elapsed)

    for event in BIG_OCCASIONAL_EVENTS:
        daily_rate = event["mean_per_year"] * lm / 365.0
        if rng.random() > daily_rate:
            continue

        amount_raw = rng.uniform(event["min"], event["max"]) * inf_factor
        amount = Decimal(str(round(amount_raw, 2)))

        if event["requires_savings"] and savings_balance < amount * Decimal("1.2"):
            # Not enough savings buffer — skip this event
            continue

        desc = rng.choice(event["descs"])
        source = (
            account_ids["savings"]
            if event["requires_savings"]
            else (account_ids.get("credit_card") or account_ids["checking"])
        )

        txns.append(
            Transaction(
                date=current_date,
                from_account_id=source,
                to_account_id="acc_external",
                amount=amount,
                category=event["cat"],
                description=str(desc),
                is_recurring=False,
                metadata={"big_occasional": True},
            )
        )

    return txns
