"""Model scores that cross a service boundary.

Each branch publishes a small reading on MQTT. The service that owns the
branch reads that reading and applies its rule. Training code stays on the
cold path. Adding arch.sqi or arch.trend means filling the same fields;
fusion and NEWS2 do not change.
"""

from services.branches.contract import BranchReading
from services.branches.snn import ARCHITECTURE as SNN
from services.branches.sqi import ARCHITECTURE as SQI
from services.branches.trend import ARCHITECTURE as TREND

__all__ = ["BranchReading", "SNN", "SQI", "TREND"]
