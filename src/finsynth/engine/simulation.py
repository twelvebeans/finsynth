"""
Core simulation engine.

Ticks forward day by day, fires generators, applies transactions to
account balances, and enforces the coherence constraint:
  balance = Σ deposits − Σ withdrawals at every point in time.
"""

from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal

import numpy as np

from finsynth.accounts.factory import build_account_set
from finsynth.accounts.models import AccountSet
from finsynth.categories.generators import (
    generate_big_occasional,
    generate_irregular,
    generate_recurring,
)
from finsynth.engine.config import PersonaConfig
from finsynth.engine.income import IncomeState, process_income
from finsynth.transactions.models import Transaction, TransactionCategory


class Simulation:
    """
    Run a full personal-finance simulation for one persona.

    Usage::

        sim = Simulation(PersonaConfig(seed=42))
        transactions, snapshots = sim.run()
    """

    def __init__(self, config: PersonaConfig) -> None:
        self.config = config
        self.rng = np.random.default_rng(config.seed)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def run(self) -> tuple[list[Transaction], list[dict]]:
        """
        Execute the simulation from config.start_date to config.end_date.

        Returns:
            transactions: All ledger rows in chronological order.
            snapshots:    Daily balance snapshot per account.
        """
        config = self.config
        accounts = build_account_set(
            start_date=config.start_date,
            monthly_income=config.monthly_income,
            has_credit_card=config.has_credit_card,
            currency=config.currency,
        )
        account_ids = self._account_id_map(accounts)
        income_state = IncomeState(monthly_income=config.monthly_income)

        all_transactions: list[Transaction] = []
        snapshots: list[dict] = []

        current_date = config.start_date

        while current_date <= config.end_date:
            months_elapsed = self._months_elapsed(config.start_date, current_date)

            # 1. Income deposits + life events
            income_txns = process_income(
                current_date,
                months_elapsed,
                income_state,
                config,
                account_ids,
                self.rng,
            )
            for t in income_txns:
                self._apply(t, accounts)
            all_transactions.extend(income_txns)

            # 2. Recurring bills
            for t in generate_recurring(
                current_date, months_elapsed, config, account_ids, self.rng
            ):
                if self._can_afford(t, accounts):
                    self._apply(t, accounts)
                    all_transactions.append(t)

            # 3. Irregular / discretionary
            for t in generate_irregular(
                current_date, months_elapsed, config, account_ids, self.rng
            ):
                if self._can_afford(t, accounts):
                    self._apply(t, accounts)
                    all_transactions.append(t)

            # 4. Big occasional (savings-gated inside generator)
            savings_bal = accounts.savings.balance
            for t in generate_big_occasional(
                current_date, months_elapsed, config, account_ids, savings_bal, self.rng
            ):
                if self._can_afford(t, accounts):
                    self._apply(t, accounts)
                    all_transactions.append(t)

            # 5. Monthly savings transfer (on the 20th)
            if current_date.day == 20:
                transfer_txns = self._savings_transfer(
                    current_date, accounts, account_ids, income_state
                )
                for t in transfer_txns:
                    self._apply(t, accounts)
                all_transactions.extend(transfer_txns)

            # 6. Credit card payment (on the 28th)
            if current_date.day == 28 and accounts.credit_card is not None:
                cc_txns = self._pay_credit_card(current_date, accounts, account_ids)
                for t in cc_txns:
                    self._apply(t, accounts)
                all_transactions.extend(cc_txns)

            # 7. Daily snapshot
            for acc in accounts.all_accounts():
                if acc.account_type.value in ("income_source", "external"):
                    continue
                snapshots.append(
                    {
                        "account_id": acc.id,
                        "account_name": acc.name,
                        "account_type": acc.account_type.value,
                        "date": current_date.isoformat(),
                        "balance": float(acc.balance),
                    }
                )

            current_date += timedelta(days=1)

        return all_transactions, snapshots

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _account_id_map(self, accounts: AccountSet) -> dict[str, str]:
        ids = {
            "income": accounts.income_source.id,
            "checking": accounts.checking.id,
            "savings": accounts.savings.id,
        }
        if accounts.credit_card:
            ids["credit_card"] = accounts.credit_card.id
        return ids

    @staticmethod
    def _months_elapsed(start: date, current: date) -> float:
        return (
            (current.year - start.year) * 12
            + (current.month - start.month)
            + (current.day - start.day) / 30.0
        )

    def _can_afford(self, txn: Transaction, accounts: AccountSet) -> bool:
        """
        Check if the source account has enough funds.
        Income source and external accounts are always solvent.
        """
        try:
            src = accounts.by_id(txn.from_account_id)
        except KeyError:
            return True  # acc_external etc.
        if src.account_type.value in ("income_source", "external"):
            return True
        # Allow credit card to go up to a reasonable limit
        if src.account_type.value == "credit_card":
            return src.balance > Decimal("-5000")
        return src.balance >= txn.amount

    def _apply(self, txn: Transaction, accounts: AccountSet) -> None:
        """Apply a transaction to account balances."""
        try:
            src = accounts.by_id(txn.from_account_id)
            if src.account_type.value not in ("income_source", "external"):
                src.debit(txn.amount)
        except KeyError:
            pass

        try:
            dst = accounts.by_id(txn.to_account_id)
            if dst.account_type.value not in ("income_source", "external"):
                dst.credit(txn.amount)
        except KeyError:
            pass

    def _savings_transfer(
        self,
        current_date: date,
        accounts: AccountSet,
        account_ids: dict[str, str],
        income_state: IncomeState,
    ) -> list[Transaction]:
        """Transfer a fraction of income from checking to savings."""
        savings_rate = self.config.lifestyle_params["savings_rate"]
        transfer_amount = Decimal(str(round(income_state.monthly_income * savings_rate, 2)))

        if accounts.checking.balance < transfer_amount + Decimal("200"):
            # Keep a floor in checking — don't transfer if it would leave too little
            return []

        return [
            Transaction(
                date=current_date,
                from_account_id=account_ids["checking"],
                to_account_id=account_ids["savings"],
                amount=transfer_amount,
                category=TransactionCategory.SAVINGS_DEPOSIT,
                description="Monthly savings transfer",
                is_recurring=True,
            )
        ]

    def _pay_credit_card(
        self,
        current_date: date,
        accounts: AccountSet,
        account_ids: dict[str, str],
    ) -> list[Transaction]:
        """Pay off the credit card balance from checking on the 28th."""
        if accounts.credit_card is None:
            return []
        cc_balance = accounts.credit_card.balance
        if cc_balance >= Decimal("0"):
            return []  # Nothing owed

        owed = abs(cc_balance)
        # Pay in full if checking can cover it, otherwise pay as much as possible
        available = max(Decimal("0"), accounts.checking.balance - Decimal("200"))
        payment = min(owed, available)
        if payment <= Decimal("1"):
            return []

        return [
            Transaction(
                date=current_date,
                from_account_id=account_ids["checking"],
                to_account_id=account_ids["credit_card"],
                amount=payment,
                category=TransactionCategory.CREDIT_CARD_PAYMENT,
                description="Credit card payment",
                is_recurring=True,
            )
        ]
