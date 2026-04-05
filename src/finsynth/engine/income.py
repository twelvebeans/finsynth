"""
Income engine.

Manages the income stream: regular payday deposits plus life events
(raises, bonuses, job changes) that create realistic income trajectories.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal

import numpy as np

from finsynth.engine.config import PersonaConfig
from finsynth.transactions.models import Transaction, TransactionCategory


@dataclass
class IncomeState:
    """Mutable income state that evolves through life events."""

    monthly_income: float
    is_employed: bool = True
    gap_days_remaining: int = 0
    event_log: list[dict] = field(default_factory=list)


def _is_payday(current_date: date, config: PersonaConfig) -> bool:
    """True on the configured payday day-of-month."""
    return current_date.day == config.payday_dom


def process_income(
    current_date: date,
    months_elapsed: float,
    state: IncomeState,
    config: PersonaConfig,
    account_ids: dict[str, str],
    rng: np.random.Generator,
) -> list[Transaction]:
    """
    Process income events for current_date and mutate IncomeState.

    Returns transactions to record (may be empty on non-payday days or
    during unemployment gaps).
    """
    txns: list[Transaction] = []

    # --- Life events (evaluated once per month on the 1st) ---
    if current_date.day == 1:
        _maybe_trigger_life_event(current_date, state, config, rng)

    # --- Employment gap countdown ---
    if not state.is_employed:
        state.gap_days_remaining -= 1
        if state.gap_days_remaining <= 0:
            state.is_employed = True
            state.event_log.append(
                {
                    "date": str(current_date),
                    "event": "re_employed",
                    "new_income": state.monthly_income,
                }
            )
        return txns  # No income while between jobs

    # --- Regular payday ---
    if _is_payday(current_date, config):
        # Freelance gets variable income; salary is stable
        if config.income_category == "freelance":
            jitter = 1 + rng.normal(0, 0.15)
            deposit = Decimal(str(round(state.monthly_income * max(0.5, jitter), 2)))
        else:
            deposit = Decimal(str(round(state.monthly_income, 2)))

        txns.append(
            Transaction(
                date=current_date,
                from_account_id=account_ids["income"],
                to_account_id=account_ids["checking"],
                amount=deposit,
                category=TransactionCategory.SALARY,
                description="Monthly salary deposit",
                is_recurring=True,
            )
        )

    return txns


def _maybe_trigger_life_event(
    current_date: date,
    state: IncomeState,
    config: PersonaConfig,
    rng: np.random.Generator,
) -> None:
    """Draw life events and mutate state in-place."""

    # Raise
    if state.is_employed and rng.random() < config.prob_raise_per_month:
        pct = max(0.01, rng.normal(config.raise_pct_mean, config.raise_pct_std))
        old = state.monthly_income
        state.monthly_income *= 1 + pct
        state.event_log.append(
            {
                "date": str(current_date),
                "event": "raise",
                "old_income": round(old, 2),
                "new_income": round(state.monthly_income, 2),
                "pct": round(pct * 100, 1),
            }
        )
        return  # Don't stack events in the same month

    # Job change (gap then new salary)
    if state.is_employed and rng.random() < config.prob_job_change_per_month:
        gap_days = int(rng.integers(14, 45))
        # New salary ± 15% vs old
        salary_change = rng.uniform(-0.05, 0.20)
        old = state.monthly_income
        state.is_employed = False
        state.gap_days_remaining = gap_days
        state.monthly_income *= 1 + salary_change
        state.event_log.append(
            {
                "date": str(current_date),
                "event": "job_change",
                "gap_days": gap_days,
                "old_income": round(old, 2),
                "new_income": round(state.monthly_income, 2),
            }
        )
        return

    # Bonus (one-time, handled at the call site via metadata)
    # Returned via the transaction list in process_income — handled separately
    # to keep life event logic and transaction generation decoupled.
