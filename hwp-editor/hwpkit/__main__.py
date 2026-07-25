"""`python -m hwpkit` 진입점."""

from __future__ import annotations

import sys

from .cli import 주실행

if __name__ == "__main__":
    sys.exit(주실행())
