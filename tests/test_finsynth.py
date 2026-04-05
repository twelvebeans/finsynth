"""Test suite for finsynth."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from finsynth.accounts.factory import build_account_set
from finsynth.accounts.models import AccountType
from finsynth.engine.config import PersonaConfig, LifestyleProfile
from finsynth.engine.simulation import Simulation
from finsynth.output.serialisers import transactions_to_df, snapshots_to_df, summary


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def default_config() -> PersonaConfig:
    return PersonaConfig(
        monthly_income=4500.0,
        lifestyle=LifestyleProfile.AVERAGE,
        start_date=date(2023, 1, 1),
        end_date=date(2023, 6, 30),
        seed=42,
    )


@pytest.fixture
def simulation(default_config: PersonaConfig) -> Simulation:
    return Simulation(default_config)


@pytest.fixture
def run_output(simulation: Simulation):
    return simulation.run()


# ---------------------------------------------------------------------------
# Account model tests
# ---------------------------------------------------------------------------

class TestAccounts:
    def test_build_account_set_creates_four_accounts(self):
        accs = build_account_set(date(2023, 1, 1), 4500.0, has_credit_card=True)
        assert accs.income_source.account_type == AccountType.INCOME_SOURCE
        assert accs.checking.account_type == AccountType.CHECKING
        assert accs.savings.account_type == AccountType.SAVINGS
        assert accs.credit_card is not None
        assert accs.credit_card.account_type == AccountType.CREDIT_CARD

    def test_build_account_set_no_credit_card(self):
        accs = build_account_set(date(2023, 1, 1), 4500.0, has_credit_card=False)
        assert accs.credit_card is None

    def test_initial_balances_scale_with_income(self):
        low = build_account_set(date(2023, 1, 1), 2000.0)
        high = build_account_set(date(2023, 1, 1), 8000.0)
        assert high.checking.initial_balance > low.checking.initial_balance
        assert high.savings.initial_balance > low.savings.initial_balance

    def test_credit_debit_updates_balance(self):
        accs = build_account_set(date(2023, 1, 1), 4500.0)
        initial = accs.checking.balance
        accs.checking.credit(Decimal("100.00"))
        assert accs.checking.balance == initial + Decimal("100.00")
        accs.checking.debit(Decimal("50.00"))
        assert accs.checking.balance == initial + Decimal("50.00")

    def test_by_id_raises_on_unknown(self):
        accs = build_account_set(date(2023, 1, 1), 4500.0)
        with pytest.raises(KeyError):
            accs.by_id("nonexistent")


# ---------------------------------------------------------------------------
# Simulation output shape tests
# ---------------------------------------------------------------------------

class TestSimulationOutput:
    def test_run_returns_two_sequences(self, run_output):
        transactions, snapshots = run_output
        assert isinstance(transactions, list)
        assert isinstance(snapshots, list)

    def test_transactions_non_empty(self, run_output):
        transactions, _ = run_output
        assert len(transactions) > 0

    def test_snapshots_non_empty(self, run_output):
        _, snapshots = run_output
        assert len(snapshots) > 0

    def test_all_amounts_positive(self, run_output):
        transactions, _ = run_output
        for t in transactions:
            assert t.amount > 0, f"Non-positive amount in {t}"

    def test_transactions_in_date_range(self, run_output, default_config):
        transactions, _ = run_output
        for t in transactions:
            assert default_config.start_date <= t.date <= default_config.end_date

    def test_snapshots_cover_all_real_accounts(self, run_output):
        _, snapshots = run_output
        account_ids = {s["account_id"] for s in snapshots}
        assert "acc_checking" in account_ids
        assert "acc_savings" in account_ids

    def test_income_source_not_in_snapshots(self, run_output):
        _, snapshots = run_output
        account_ids = {s["account_id"] for s in snapshots}
        assert "acc_income" not in account_ids


# ---------------------------------------------------------------------------
# Coherence / financial integrity tests
# ---------------------------------------------------------------------------

class TestCoherence:
    def test_checking_never_deeply_negative(self, run_output):
        _, snapshots = run_output
        checking = [s for s in snapshots if s["account_id"] == "acc_checking"]
        for snap in checking:
            assert snap["balance"] > -500, (
                f"Checking went too negative: {snap['balance']} on {snap['date']}"
            )

    def test_savings_generally_non_negative(self, run_output):
        _, snapshots = run_output
        savings = [s for s in snapshots if s["account_id"] == "acc_savings"]
        # Allow occasional dip but not deep or prolonged
        deeply_negative = [s for s in savings if s["balance"] < -200]
        assert len(deeply_negative) == 0, f"Savings deeply negative: {deeply_negative[:3]}"

    def test_salary_transactions_present(self, run_output):
        transactions, _ = run_output
        salary_txns = [t for t in transactions if t.category.value == "salary"]
        assert len(salary_txns) >= 5  # At least 5 months of salary in 6 months

    def test_recurring_transactions_present(self, run_output):
        transactions, _ = run_output
        recurring = [t for t in transactions if t.is_recurring]
        assert len(recurring) > 0

    def test_reproducibility(self, default_config):
        """Same seed must produce identical output."""
        sim1 = Simulation(default_config)
        txns1, snaps1 = sim1.run()

        sim2 = Simulation(default_config)
        txns2, snaps2 = sim2.run()

        assert len(txns1) == len(txns2)
        for t1, t2 in zip(txns1, txns2):
            assert t1.amount == t2.amount
            assert t1.category == t2.category
            assert t1.date == t2.date

    def test_different_seeds_differ(self, default_config):
        sim1 = Simulation(PersonaConfig(**{**default_config.model_dump(), "seed": 1}))
        sim2 = Simulation(PersonaConfig(**{**default_config.model_dump(), "seed": 2}))
        txns1, _ = sim1.run()
        txns2, _ = sim2.run()
        amounts1 = [t.amount for t in txns1]
        amounts2 = [t.amount for t in txns2]
        assert amounts1 != amounts2


# ---------------------------------------------------------------------------
# Lifestyle profile tests
# ---------------------------------------------------------------------------

class TestLifestyleProfiles:
    def _total_discretionary(self, lifestyle: LifestyleProfile) -> float:
        config = PersonaConfig(
            lifestyle=lifestyle,
            start_date=date(2023, 1, 1),
            end_date=date(2023, 12, 31),
            seed=99,
        )
        txns, _ = Simulation(config).run()
        discretionary_cats = {"dining", "clothing", "entertainment", "coffee"}
        return sum(float(t.amount) for t in txns if t.category.value in discretionary_cats)

    def test_spender_spends_more_than_frugal(self):
        frugal_total = self._total_discretionary(LifestyleProfile.FRUGAL)
        spender_total = self._total_discretionary(LifestyleProfile.SPENDER)
        assert spender_total > frugal_total * 2, (
            f"Spender ({spender_total:.0f}) should be >2× frugal ({frugal_total:.0f})"
        )


# ---------------------------------------------------------------------------
# Output serialiser tests
# ---------------------------------------------------------------------------

class TestSerialisers:
    def test_transactions_to_df_columns(self, run_output):
        transactions, _ = run_output
        df = transactions_to_df(transactions)
        expected_cols = {"id", "date", "from_account_id", "to_account_id",
                         "amount", "category", "description", "is_recurring"}
        assert expected_cols.issubset(set(df.columns))

    def test_snapshots_to_df_columns(self, run_output):
        _, snapshots = run_output
        df = snapshots_to_df(snapshots)
        expected_cols = {"account_id", "date", "balance"}
        assert expected_cols.issubset(set(df.columns))

    def test_summary_keys_present(self, run_output):
        transactions, snapshots = run_output
        stats = summary(transactions, snapshots)
        for key in ("transaction_count", "total_income", "total_spending",
                    "spending_by_category", "final_balances"):
            assert key in stats

    def test_inflation_raises_grocery_cost(self):
        """
        Average grocery spend in year 2 should be higher than year 1.
        Uses full-year averages so per-transaction jitter (±8%) doesn't
        swamp the 5% annual inflation signal.
        """
        config = PersonaConfig(
            start_date=date(2022, 1, 1),
            end_date=date(2023, 12, 31),
            seed=7,
            lifestyle=LifestyleProfile.AVERAGE,
            inflation={
                "rent": 0.04, "utilities": 0.07,
                "groceries": 0.05, "fuel": 0.06, "general": 0.03,
            },
        )
        txns, _ = Simulation(config).run()
        groceries = [t for t in txns if t.category.value == "groceries"]

        year1 = [t for t in groceries if t.date.year == 2022]
        year2 = [t for t in groceries if t.date.year == 2023]

        assert year1 and year2, "Expected grocery transactions in both years"
        avg_year1 = sum(float(t.amount) for t in year1) / len(year1)
        avg_year2 = sum(float(t.amount) for t in year2) / len(year2)
        assert avg_year2 > avg_year1, (
            f"Expected inflation: year2 avg {avg_year2:.2f} should exceed year1 avg {avg_year1:.2f}"
        )
