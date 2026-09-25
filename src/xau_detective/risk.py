"""Capital-aware position sizing and hard risk gates."""
from __future__ import annotations

from decimal import Decimal, ROUND_DOWN

from .models import RiskRequest, RiskResult

def