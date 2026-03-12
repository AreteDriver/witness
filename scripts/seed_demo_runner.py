"""Runner for seed_demo that handles the DB path from env."""

import os
import sys

# Ensure project root is on path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from scripts.seed_demo import seed

db_path = os.environ.get("WATCHTOWER_DB_PATH", "data/demo.db")
seed(db_path=db_path)
