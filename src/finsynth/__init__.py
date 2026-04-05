"""
finsynth — synthetic personal finance data generator.

Quick start::

    from finsynth import Simulation, PersonaConfig

    sim = Simulation(PersonaConfig(seed=42))
    transactions, snapshots = sim.run(months=24)
"""

from finsynth.accounts.models import Account, AccountType
from finsynth.engine.config import LifestyleProfile, PersonaConfig
from finsynth.engine.simulation import Simulation

__all__ = [
    "Simulation",
    "PersonaConfig",
    "LifestyleProfile",
    "Account",
    "AccountType",
]
