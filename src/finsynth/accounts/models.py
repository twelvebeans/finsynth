"""Account definitions and type system."""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from enum import StrEnum

from pydantic import BaseModel, model_validator


class AccountType(StrEnum):
    INCOME_SOURCE = "income_source"  # External payer — not a real bank account
    CHECKING = "checking"
    SAVINGS = "savings"
    CREDIT_CARD = "credit_card"
    EXTERNAL = "external"  # Generic merchant / payee


class Account(BaseModel):
    """A financial account participating in the simulation."""

    id: str
    name: str
    account_type: AccountType
    currency: str = "CAD"
    open_date: date
    initial_balance: Decimal = Decimal("0.00")

    # Runtime state — not serialised as config input
    _balance: Decimal = Decimal("0.00")

    model_config = {"arbitrary_types_allowed": True}

    def model_post_init(self, __context: object) -> None:
        self._balance = self.initial_balance

    @property
    def balance(self) -> Decimal:
        return self._balance

    def credit(self, amount: Decimal) -> None:
        """Add funds (income deposit, transfer in, refund)."""
        if amount <= 0:
            raise ValueError(f"Credit amount must be positive, got {amount}")
        self._balance += amount

    def debit(self, amount: Decimal) -> None:
        """Remove funds (spending, transfer out)."""
        if amount <= 0:
            raise ValueError(f"Debit amount must be positive, got {amount}")
        self._balance -= amount

    @property
    def is_ovdrawn(self) -> bool:
        return self._balance < Decimal("0.00")


class AccountSet(BaseModel):
    """The complete set of accounts for one persona."""

    income_source: Account
    checking: Account
    savings: Account
    credit_card: Account | None = None

    @model_validator(mode="after")
    def validate_types(self) -> AccountSet:
        assert self.income_source.account_type == AccountType.INCOME_SOURCE
        assert self.checking.account_type == AccountType.CHECKING
        assert self.savings.account_type == AccountType.SAVINGS
        if self.credit_card is not None:
            assert self.credit_card.account_type == AccountType.CREDIT_CARD
        return self

    def all_accounts(self) -> list[Account]:
        accounts = [self.income_source, self.checking, self.savings]
        if self.credit_card:
            accounts.append(self.credit_card)
        return accounts

    def by_id(self, account_id: str) -> Account:
        for acc in self.all_accounts():
            if acc.id == account_id:
                return acc
        raise KeyError(f"No account with id={account_id!r}")
