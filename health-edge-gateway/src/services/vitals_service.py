"""Compatibility entry: NEWS2 branch."""

from __future__ import annotations

import sys
from pathlib import Path

SRC = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SRC))

from services.news2_service import main

if __name__ == "__main__":
    main()
