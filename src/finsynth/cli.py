"""
finsynth CLI

Usage:
    finsynth generate --months 24 --seed 42 --lifestyle average --output ./data
    finsynth generate --income 6000 --lifestyle spender --format json
    finsynth summary ./data/finsynth_transactions.csv
"""

from __future__ import annotations

from datetime import date
from pathlib import Path

import typer
from rich import box
from rich.console import Console
from rich.table import Table

from finsynth.engine.config import LifestyleProfile, PersonaConfig
from finsynth.engine.simulation import Simulation
from finsynth.output.serialisers import export_csv, export_json, summary

app = typer.Typer(
    name="finsynth",
    help="Generate organic, consistent synthetic personal finance data.",
    add_completion=False,
)
console = Console()


@app.command()
def generate(
    months: int = typer.Option(24, help="Number of months to simulate"),
    seed: int = typer.Option(42, help="Random seed for reproducibility"),
    income: float = typer.Option(4500.0, help="Monthly income in currency units"),
    lifestyle: LifestyleProfile = typer.Option(
        LifestyleProfile.AVERAGE, help="frugal | average | spender"
    ),
    income_type: str = typer.Option("salary", help="salary | freelance"),
    currency: str = typer.Option("CAD", help="ISO currency code"),
    output: Path = typer.Option(Path("./output"), help="Output directory"),
    fmt: str = typer.Option("csv", "--format", help="csv | json | both"),
) -> None:
    """Generate a synthetic transaction history for one persona."""

    start = date(2023, 1, 1)
    end_year = start.year + (start.month + months - 2) // 12
    end_month = (start.month + months - 2) % 12 + 1
    end = date(end_year, end_month, 28)

    config = PersonaConfig(
        monthly_income=income,
        lifestyle=lifestyle,
        income_category=income_type,
        currency=currency,
        start_date=start,
        end_date=end,
        seed=seed,
    )

    console.print(f"\n[bold]finsynth[/bold] — generating {months} months of data")
    console.print(f"  Persona   : income={income} {currency}, lifestyle={lifestyle}, seed={seed}")
    console.print(f"  Date range: {start} → {end}\n")

    with console.status("Running simulation…"):
        sim = Simulation(config)
        transactions, snapshots = sim.run()

    stats = summary(transactions, snapshots)

    # Write output
    output.mkdir(parents=True, exist_ok=True)
    if fmt in ("csv", "both"):
        t_path, s_path = export_csv(transactions, snapshots, output)
        console.print(f"[green]✓[/green] Transactions → {t_path}")
        console.print(f"[green]✓[/green] Snapshots    → {s_path}")
    if fmt in ("json", "both"):
        t_path, s_path = export_json(transactions, snapshots, output)
        console.print(f"[green]✓[/green] Transactions → {t_path}")
        console.print(f"[green]✓[/green] Snapshots    → {s_path}")

    _print_summary(stats)


@app.command()
def demo() -> None:
    """Run a quick demo simulation and print a summary (no files written)."""
    config = PersonaConfig(seed=42)
    with console.status("Running demo simulation (24 months)…"):
        sim = Simulation(config)
        transactions, snapshots = sim.run()

    stats = summary(transactions, snapshots)
    _print_summary(stats)


def _print_summary(stats: dict) -> None:
    console.print()
    console.rule("[bold]Simulation summary[/bold]")
    console.print(f"  Transactions : {stats['transaction_count']}")
    console.print(f"  Date range   : {stats['date_range']}")
    console.print(f"  Total income : {stats['total_income']:,.2f}")
    console.print(f"  Total spending: {stats['total_spending']:,.2f}")
    if stats.get("savings_rate_actual") is not None:
        console.print(f"  Net savings rate: {stats['savings_rate_actual']:.1%}")

    # Spending by category table
    table = Table(title="\nSpending by category", box=box.SIMPLE_HEAVY, show_edge=False)
    table.add_column("Category", style="cyan")
    table.add_column("Transactions", justify="right")
    table.add_column("Total", justify="right", style="bold")

    for cat, vals in list(stats.get("spending_by_category", {}).items())[:15]:
        table.add_row(cat, str(vals["txn_count"]), f"{vals['total']:,.2f}")
    console.print(table)

    # Final balances
    table2 = Table(title="Final account balances", box=box.SIMPLE_HEAVY, show_edge=False)
    table2.add_column("Account", style="cyan")
    table2.add_column("Balance", justify="right", style="bold")
    for acc_id, vals in stats.get("final_balances", {}).items():
        balance = vals["balance"]
        color = "red" if balance < 0 else "green"
        table2.add_row(vals["account_name"], f"[{color}]{balance:,.2f}[/{color}]")
    console.print(table2)
    console.print()


if __name__ == "__main__":
    app()
