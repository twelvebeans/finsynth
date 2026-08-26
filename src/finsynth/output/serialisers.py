"""
Output serialisers.

Converts raw simulation output (lists of Transactions + snapshot dicts)
into pandas DataFrames, CSV files, or JSON.
"""

from __future__ import annotations

import json
from decimal import Decimal
from pathlib import Path

import pandas as pd

from finsynth.transactions.models import Transaction

# ---------------------------------------------------------------------------
# DataFrames
# ---------------------------------------------------------------------------


def transactions_to_df(transactions: list[Transaction]) -> pd.DataFrame:
    """Convert a transaction list to a tidy DataFrame."""
    rows = [
        {
            "id": t.id,
            "date": t.date,
            "from_account_id": t.from_account_id,
            "to_account_id": t.to_account_id,
            "amount": float(t.amount),
            "category": t.category.value,
            "description": t.description,
            "is_recurring": t.is_recurring,
        }
        for t in transactions
    ]
    df = pd.DataFrame(rows)
    if not df.empty:
        df["date"] = pd.to_datetime(df["date"])
        df = df.sort_values("date").reset_index(drop=True)
    return df


def snapshots_to_df(snapshots: list[dict]) -> pd.DataFrame:
    """Convert daily balance snapshots to a tidy DataFrame."""
    df = pd.DataFrame(snapshots)
    if not df.empty:
        df["date"] = pd.to_datetime(df["date"])
        df = df.sort_values(["account_id", "date"]).reset_index(drop=True)
    return df


# ---------------------------------------------------------------------------
# File I/O
# ---------------------------------------------------------------------------


def export_csv(
    transactions: list[Transaction],
    snapshots: list[dict],
    output_dir: str | Path = ".",
    prefix: str = "finsynth",
) -> tuple[Path, Path]:
    """
    Write transactions and snapshots to CSV files.

    Returns:
        (transactions_path, snapshots_path)
    """
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)

    txn_path = out / f"{prefix}_transactions.csv"
    snap_path = out / f"{prefix}_snapshots.csv"

    transactions_to_df(transactions).to_csv(txn_path, index=False)
    snapshots_to_df(snapshots).to_csv(snap_path, index=False)

    return txn_path, snap_path


def export_json(
    transactions: list[Transaction],
    snapshots: list[dict],
    output_dir: str | Path = ".",
    prefix: str = "finsynth",
) -> tuple[Path, Path]:
    """Write transactions and snapshots to JSON files."""
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)

    txn_path = out / f"{prefix}_transactions.json"
    snap_path = out / f"{prefix}_snapshots.json"

    txn_data = [
        {
            "id": t.id,
            "date": t.date.isoformat(),
            "from_account_id": t.from_account_id,
            "to_account_id": t.to_account_id,
            "amount": float(t.amount),
            "category": t.category.value,
            "description": t.description,
            "is_recurring": t.is_recurring,
        }
        for t in transactions
    ]
    txn_path.write_text(json.dumps(txn_data, indent=2))
    snap_path.write_text(json.dumps(snapshots, indent=2))

    return txn_path, snap_path


def export_ledger(
    transactions: list[Transaction],
    snapshots: list[dict],
    output_dir: str | Path = ".",
    prefix: str = "finsynth",
    currency: str = "CAD",
) -> Path:
    """Write a Rustledger-compatible Beancount ledger file."""
    del snapshots

    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)
    path = out / f"{prefix}.beancount"

    lines = [
        'option "title" "finsynth synthetic ledger"',
        f'option "operating_currency" "{currency}"',
        "",
    ]

    if not transactions:
        path.write_text("\n".join(lines))
        return path

    txns = sorted(transactions, key=lambda t: (t.date, t.id))
    open_date = txns[0].date.isoformat()
    accounts = sorted({account for t in txns for account, _ in _postings(t)})

    # Accounts must be opened before Rustledger can post to them.
    for account in accounts:
        lines.append(f"{open_date} open {account} {currency}")
    lines.append("")

    for txn in txns:
        lines.append(f'{txn.date.isoformat()} * "{_escape(txn.description)}"')
        for account, amount in _postings(txn):
            lines.append(f"  {account:<32} {_amount(amount)} {currency}")
        lines.append("")

    path.write_text("\n".join(lines))
    return path


def _postings(txn: Transaction) -> list[tuple[str, Decimal]]:
    amount = txn.amount
    category = txn.category.value

    if category in {"salary", "bonus", "freelance"}:
        return [
            (_account(txn.to_account_id, category), amount),
            (_income_account(category), -amount),
        ]

    if txn.to_account_id == "acc_external":
        return [
            (_expense_account(category), amount),
            (_account(txn.from_account_id, category), -amount),
        ]

    return [
        (_account(txn.to_account_id, category), amount),
        (_account(txn.from_account_id, category), -amount),
    ]


def _account(account_id: str, category: str) -> str:
    accounts = {
        "acc_checking": "Assets:Checking",
        "acc_savings": "Assets:Savings",
        "acc_cc": "Liabilities:CreditCard",
        "acc_income": _income_account(category),
        "acc_external": _expense_account(category),
    }
    return accounts.get(account_id, _expense_account(category))


def _income_account(category: str) -> str:
    return f"Income:{_account_part(category)}"


def _expense_account(category: str) -> str:
    return f"Expenses:{_account_part(category)}"


def _account_part(value: str) -> str:
    return "".join(part.capitalize() for part in value.split("_"))


def _amount(amount: Decimal) -> str:
    return f"{amount.quantize(Decimal('0.01'))}"


def _escape(value: str) -> str:
    return value.replace("\\", "\\\\").replace('"', '\\"')


# ---------------------------------------------------------------------------
# Summary stats (useful for quick validation)
# ---------------------------------------------------------------------------


def summary(transactions: list[Transaction], snapshots: list[dict]) -> dict:
    """Return a dict of summary statistics for quick sanity-checking."""
    df = transactions_to_df(transactions)
    snap_df = snapshots_to_df(snapshots)

    if df.empty:
        return {"error": "No transactions generated"}

    income = df[df["category"].isin(["salary", "bonus", "freelance"])]["amount"].sum()
    spending = df[
        ~df["category"].isin(
            [
                "salary",
                "bonus",
                "freelance",
                "transfer",
                "savings_deposit",
                "savings_withdrawal",
                "credit_card_payment",
            ]
        )
    ]["amount"].sum()

    by_category = (
        df[
            ~df["category"].isin(
                [
                    "salary",
                    "bonus",
                    "freelance",
                    "transfer",
                    "savings_deposit",
                    "savings_withdrawal",
                    "credit_card_payment",
                ]
            )
        ]
        .groupby("category")["amount"]
        .agg(["sum", "count"])
        .rename(columns={"sum": "total", "count": "txn_count"})
        .sort_values("total", ascending=False)
        .round(2)
        .to_dict(orient="index")
    )

    final_balances = (
        snap_df.sort_values("date")
        .groupby("account_id")
        .last()[["account_name", "balance"]]
        .to_dict(orient="index")
    )

    return {
        "transaction_count": len(df),
        "date_range": f"{df['date'].min().date()} → {df['date'].max().date()}",
        "total_income": round(income, 2),
        "total_spending": round(spending, 2),
        "savings_rate_actual": round(1 - spending / income, 3) if income > 0 else None,
        "spending_by_category": by_category,
        "final_balances": final_balances,
    }
