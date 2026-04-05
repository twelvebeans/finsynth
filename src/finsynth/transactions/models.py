"""Transaction schema — the atomic unit of the ledger."""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from enum import StrEnum
from uuid import uuid4

from pydantic import BaseModel, Field


class TransactionCategory(StrEnum):
    # Income
    SALARY = "salary"
    BONUS = "bonus"
    FREELANCE = "freelance"

    # Transfers
    TRANSFER = "transfer"
    SAVINGS_DEPOSIT = "savings_deposit"
    SAVINGS_WITHDRAWAL = "savings_withdrawal"
    CREDIT_CARD_PAYMENT = "credit_card_payment"

    # Recurring bills
    RENT = "rent"
    MORTGAGE = "mortgage"
    UTILITIES = "utilities"
    INTERNET = "internet"
    PHONE = "phone"
    INSURANCE = "insurance"
    SUBSCRIPTIONS = "subscriptions"

    # Daily spending
    GROCERIES = "groceries"
    DINING = "dining"
    COFFEE = "coffee"
    TRANSPORT = "transport"
    FUEL = "fuel"

    # Lifestyle
    CLOTHING = "clothing"
    PERSONAL_CARE = "personal_care"
    ENTERTAINMENT = "entertainment"
    GYM = "gym"

    # Big occasional
    ELECTRONICS = "electronics"
    APPLIANCES = "appliances"
    TRAVEL = "travel"
    MEDICAL = "medical"
    HOME_IMPROVEMENT = "home_improvement"
    CAR_REPAIR = "car_repair"
    EDUCATION = "education"


RECURRING_CATEGORIES = {
    TransactionCategory.RENT,
    TransactionCategory.MORTGAGE,
    TransactionCategory.UTILITIES,
    TransactionCategory.INTERNET,
    TransactionCategory.PHONE,
    TransactionCategory.INSURANCE,
    TransactionCategory.SUBSCRIPTIONS,
    TransactionCategory.GROCERIES,
    TransactionCategory.GYM,
}

BIG_OCCASIONAL_CATEGORIES = {
    TransactionCategory.ELECTRONICS,
    TransactionCategory.APPLIANCES,
    TransactionCategory.TRAVEL,
    TransactionCategory.MEDICAL,
    TransactionCategory.HOME_IMPROVEMENT,
    TransactionCategory.CAR_REPAIR,
    TransactionCategory.EDUCATION,
}


class Transaction(BaseModel):
    """A single movement of money between two accounts."""

    id: str = Field(default_factory=lambda: str(uuid4()))
    date: date
    from_account_id: str
    to_account_id: str
    amount: Decimal  # Always positive; direction given by from/to
    category: TransactionCategory
    description: str
    is_recurring: bool = False
    metadata: dict = Field(default_factory=dict)

    model_config = {"arbitrary_types_allowed": True}
