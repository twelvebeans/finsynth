# finsynth

A Python library for generating synthetic personal finance data. Transactions, account balances, and income streams are statistically realistic and internally consistent, making the output useful for testing financial tools, building demos, or seeding development databases.

## What it generates

Each simulation produces a ledger of transactions and a daily balance history across four account types: an income source, a checking account, a savings account, and an optional credit card.

**Income** arrives on a fixed payday each month. The amount is stable for salary profiles and variable for freelance. Over time, income can change through raises (a percentage step up), job transitions (a gap with no income followed by a new salary), or one-off bonuses.

**Recurring spending** covers rent, utilities, groceries, phone, internet, insurance, subscriptions, and gym. Each fires on a fixed day of the month with small amount jitter. Amounts drift upward over time at configurable per-category inflation rates, so a grocery run in month 24 costs more than one in month 1.

**Irregular spending** covers dining, coffee, clothing, transport, and entertainment. Transactions arrive at a Poisson rate with log-normal amounts and seasonal shaping, so restaurant spending peaks in December and clothing spikes in November.

**Big occasional spending** covers travel, electronics, appliances, medical bills, home improvement, car repair, and education. These arrive rarely (modelled as a Poisson process with a long mean inter-arrival time) and cost anywhere from a few hundred to a few thousand. Purchases that require drawing on savings are deferred if the savings balance isn't sufficient.

**Coherence** is enforced throughout: no account goes deeply negative, big purchases wait until savings can cover them, and the credit card balance is paid from checking on the 28th of each month.

The same `seed` always produces the same output.

---

## Setup

You'll need [mise](https://mise.jdx.dev) for Python version management and [uv](https://docs.astral.sh/uv/) for packages.

```bash
# Install mise
curl https://mise.run | sh

# Install uv
curl -LsSf https://astral.sh/uv/install.sh | sh
```

Then clone and install:

```bash
git clone <repo>
cd finsynth
mise install       # pins Python 3.12, sets UV_PROJECT_ENVIRONMENT
mise run install   # uv sync
```

---

## Usage

### CLI

```bash
# 24 months, average earner, CAD 4,500/month
finsynth generate --months 24 --seed 42

# Spender profile, higher income, JSON output
finsynth generate --months 36 --income 7000 --lifestyle spender --format json --output ./data

# Print a summary without writing any files
finsynth demo
```

**All CLI options:**

| Option          | Default  | Description                         |
| --------------- | -------- | ----------------------------------- |
| `--months`      | 24       | Simulation length in months         |
| `--seed`        | 42       | Random seed (same seed = same data) |
| `--income`      | 4500     | Monthly income                      |
| `--lifestyle`   | average  | `frugal` / `average` / `spender`    |
| `--income-type` | salary   | `salary` / `freelance`              |
| `--currency`    | CAD      | ISO currency code                   |
| `--output`      | ./output | Output directory                    |
| `--format`      | csv      | `csv` / `json` / `both`             |

### Python API

```python
from finsynth import Simulation, PersonaConfig, LifestyleProfile
from finsynth.output import export_csv, summary
from datetime import date

config = PersonaConfig(
    monthly_income=5500.0,
    lifestyle=LifestyleProfile.AVERAGE,
    income_category="salary",
    start_date=date(2022, 1, 1),
    end_date=date(2023, 12, 31),
    seed=99,
    inflation={
        "rent": 0.05,
        "utilities": 0.08,
        "groceries": 0.06,
        "fuel": 0.07,
        "general": 0.03,
    },
)

sim = Simulation(config)
transactions, snapshots = sim.run()

stats = summary(transactions, snapshots)
print(f"Transactions: {stats['transaction_count']}")
print(f"Total income: {stats['total_income']:,.2f}")

export_csv(transactions, snapshots, output_dir="./data", prefix="persona_1")
```

### Output schema

`finsynth_transactions.csv`

| Column            | Type  | Description               |
| ----------------- | ----- | ------------------------- |
| `id`              | UUID  | Unique transaction ID     |
| `date`            | date  | Transaction date          |
| `from_account_id` | str   | Source account            |
| `to_account_id`   | str   | Destination account       |
| `amount`          | float | Always positive           |
| `category`        | str   | See categories below      |
| `description`     | str   | Human-readable label      |
| `is_recurring`    | bool  | Scheduled vs. spontaneous |

`finsynth_snapshots.csv`

| Column         | Type  | Description                      |
| -------------- | ----- | -------------------------------- |
| `account_id`   | str   | Account identifier               |
| `account_name` | str   | Human-readable name              |
| `account_type` | str   | checking / savings / credit_card |
| `date`         | date  | Snapshot date                    |
| `balance`      | float | End-of-day balance               |

### Transaction categories

| Category                                                                                        | Type            |
| ----------------------------------------------------------------------------------------------- | --------------- |
| `salary`, `bonus`, `freelance`                                                                  | Income          |
| `transfer`, `savings_deposit`, `credit_card_payment`                                            | Internal        |
| `rent`, `utilities`, `internet`, `phone`, `insurance`, `subscriptions`, `gym`                   | Recurring bills |
| `groceries`, `dining`, `coffee`, `transport`, `fuel`                                            | Daily spending  |
| `clothing`, `personal_care`, `entertainment`                                                    | Lifestyle       |
| `travel`, `electronics`, `appliances`, `medical`, `home_improvement`, `car_repair`, `education` | Big occasional  |

---

## Development

```bash
mise run test   # pytest
mise run lint   # ruff check
mise run fmt    # ruff format
```

### Project structure

```
finsynth/
├── .mise.toml              # Python version + task runner
├── pyproject.toml          # uv project config
└── src/finsynth/
    ├── accounts/
    │   ├── models.py       # Account, AccountSet, AccountType
    │   └── factory.py      # Build AccountSet from config
    ├── transactions/
    │   └── models.py       # Transaction, TransactionCategory
    ├── categories/
    │   └── generators.py   # Recurring, irregular, big-occasional generators
    ├── engine/
    │   ├── config.py       # PersonaConfig, LifestyleProfile
    │   ├── income.py       # Payday logic, life events (raise/job change)
    │   └── simulation.py   # Day-by-day simulation loop
    ├── output/
    │   └── serialisers.py  # DataFrame, CSV, JSON export + summary stats
    └── cli.py              # Typer CLI
```

---

## Design notes

The simulation ticks forward one day at a time. This gives exact control over scheduling: bills fall on their configured day of month, payday is always the 15th, and the savings transfer always happens on the 20th. It also keeps the coherence check simple — the balance on day N is just the balance on day N-1 plus or minus that day's transactions.

Amounts are stored as `Decimal` rather than `float`. Floating-point rounding compounds across thousands of transactions; `Decimal` keeps everything accurate to the cent.

Big purchases are gated on savings balance rather than firing unconditionally. Without this, a Poisson event could fire at the start of the simulation and immediately produce an incoherent balance. Deferring until savings can absorb the cost produces more realistic trajectories.

Inflation rates are set per category because different goods inflate at different speeds. Utilities and groceries tend to rise faster than general goods. A single flat rate would produce a time series that looks too uniform.
