# finsynth

Organic, internally consistent synthetic personal finance data — for testing, prototyping, and demos.

## Features

- **Accounts**: income source, checking, savings, optional credit card  
- **Income**: salary or freelance with configurable payday; step-function raises, job gaps, and bonuses  
- **Recurring spending**: rent, utilities, groceries, phone, subscriptions — all with per-category inflation drift  
- **Irregular spending**: dining, coffee, clothing, transport — Poisson arrivals with seasonal shaping  
- **Big occasional**: travel, appliances, electronics, medical — Poisson events gated on savings availability  
- **Coherence**: balances never go deeply negative; big purchases defer until savings can cover them  
- **Reproducible**: same `seed` always produces identical output  

---

## Setup (local)

### Prerequisites

- [mise](https://mise.jdx.dev) for Python version management  
- [uv](https://docs.astral.sh/uv/) for package management  

```bash
# Install mise (if not already)
curl https://mise.run | sh

# Install uv (if not already)
curl -LsSf https://astral.sh/uv/install.sh | sh
```

### Install

```bash
git clone <repo>
cd finsynth

# mise pins Python 3.12 and sets UV_PROJECT_ENVIRONMENT
mise install

# Install all dependencies into .venv
mise run install
```

---

## Usage

### CLI

```bash
# Generate 24 months of data for an average earner (CAD 4,500/month)
finsynth generate --months 24 --seed 42

# Spender profile, higher income, JSON output
finsynth generate --months 36 --income 7000 --lifestyle spender --format json --output ./data

# Quick demo — prints summary, no files
finsynth demo
```

**All CLI options:**

| Option | Default | Description |
|---|---|---|
| `--months` | 24 | Simulation length in months |
| `--seed` | 42 | Random seed (same seed = same data) |
| `--income` | 4500 | Monthly income |
| `--lifestyle` | average | `frugal` / `average` / `spender` |
| `--income-type` | salary | `salary` / `freelance` |
| `--currency` | CAD | ISO currency code |
| `--output` | ./output | Output directory |
| `--format` | csv | `csv` / `json` / `both` |

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

# Quick stats
stats = summary(transactions, snapshots)
print(f"Transactions: {stats['transaction_count']}")
print(f"Total income: {stats['total_income']:,.2f}")

# Export to CSV
export_csv(transactions, snapshots, output_dir="./data", prefix="persona_1")
```

### Output schema

**`finsynth_transactions.csv`**

| Column | Type | Description |
|---|---|---|
| `id` | UUID | Unique transaction ID |
| `date` | date | Transaction date |
| `from_account_id` | str | Source account |
| `to_account_id` | str | Destination account |
| `amount` | float | Always positive |
| `category` | str | See categories below |
| `description` | str | Human-readable label |
| `is_recurring` | bool | Scheduled vs. spontaneous |

**`finsynth_snapshots.csv`**

| Column | Type | Description |
|---|---|---|
| `account_id` | str | Account identifier |
| `account_name` | str | Human-readable name |
| `account_type` | str | checking / savings / credit_card |
| `date` | date | Snapshot date |
| `balance` | float | End-of-day balance |

### Transaction categories

| Category | Type |
|---|---|
| `salary`, `bonus`, `freelance` | Income |
| `transfer`, `savings_deposit`, `credit_card_payment` | Internal |
| `rent`, `utilities`, `internet`, `phone`, `insurance`, `subscriptions`, `gym` | Recurring bills |
| `groceries`, `dining`, `coffee`, `transport`, `fuel` | Daily spending |
| `clothing`, `personal_care`, `entertainment` | Lifestyle |
| `travel`, `electronics`, `appliances`, `medical`, `home_improvement`, `car_repair`, `education` | Big occasional |

---

## Development

```bash
# Run tests
mise run test

# Lint
mise run lint

# Auto-format
mise run fmt
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

## Design decisions

**Why day-by-day ticking?** It gives precise control over scheduling — bills fall on their exact day-of-month, payday is always the 15th, etc. It also makes the coherence check trivial: balance after day N is just balance after day N-1 ± that day's transactions.

**Why Decimal for amounts?** Floating-point rounding errors compound over thousands of transactions. `Decimal` keeps cent-level accuracy throughout.

**Why gate big purchases on savings?** Without this, a Poisson event might fire and immediately bankrupt the persona — which is incoherent for testing purposes. Deferral until savings are available mirrors real behaviour.

**Why per-category inflation rates?** Utilities and groceries inflate faster than general goods. Using a single rate would flatten the time series unnaturally.
