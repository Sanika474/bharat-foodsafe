"""CLI entry point for audit-chain integrity verification in Bharat FoodSafe.

Usage:
    python -m app.cli.verify_audit
    python -m app.cli.verify_audit --restaurant-id <UUID>
"""

import sys
from app.core.audit import main

if __name__ == "__main__":
    sys.exit(main())
