"""Build an AccountSet from persona configuration."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

from finsynth.accounts.models import Account, AccountSet, AccountType


def build_account_set(
    start_date: date,
    monthly_income: float,
    has_credit_card: bool = True,
    currency: str = "CAD",
) -> AccountSet:
    """
    Create a realistic AccountSet for a persona.

    Initial balances are sized relative to income so the simulation
    starts in a plausible steady state rather than from zero.
    """
    monthly = Decimal(str(monthly_income))

    income_source = Account(
        id="acc_income",
        name="Employer",
        account_type=AccountType.INCOME_SOURCE,
        currency=currency,
        open_date=start_date,
        initial_balance=Decimal("0.00"),
    )

    checking = Account(
        id="acc_checking",
        name="Chequing Account",
        account_type=AccountType.CHECKING,
        currency=currency,
        open_date=start_date,
        # Roughly 0.5× monthly income as a starting buffer
        initial_balance=(monthly * Decimal("0.5")).quantize(Decimal("0.01")),
    )

    savings = Account(
        id="acc_savings",
        name="Savings Account",
        account_type=AccountType.SAVINGS,
        currency=currency,
        open_date=start_date,
        # Start with ~3× monthly income in savings (realistic emergency fund)
        initial_balance=(monthly * Decimal("3.0")).quantize(Decimal("0.01")),
    )

    credit_card = None
    if has_credit_card:
        credit_card = Account(
            id="acc_cc",
            name="Credit Card",
            account_type=AccountType.CREDIT_CARD,
            currency=currency,
            open_date=start_date,
            initial_balance=Decimal("0.00"),
        )

    return AccountSet(
        income_source=income_source,
        checking=checking,
        savings=savings,
        credit_card=credit_card,
    )
