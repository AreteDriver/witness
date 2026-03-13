"""One-time fix: backfill solar_systems names for orphaned sys-* killmail IDs.

Run on Fly.io:
  flyctl ssh console -a watchtower-evefrontier -C "python3 /app/scripts/fix_system_names.py"

Or locally:
  python scripts/fix_system_names.py [--db PATH]
"""

import sqlite3
import sys


def fix(db_path: str) -> None:
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row

    orphaned = conn.execute(
        """SELECT DISTINCT k.solar_system_id
           FROM killmails k
           LEFT JOIN solar_systems s ON k.solar_system_id = s.solar_system_id
           WHERE s.solar_system_id IS NULL
             AND k.solar_system_id != ''"""
    ).fetchall()

    if not orphaned:
        print("No orphaned system IDs found. All killmail systems have names.")
        conn.close()
        return

    print(f"Found {len(orphaned)} orphaned system IDs:")
    count = 0
    for row in orphaned:
        sys_id = row[0]
        if sys_id.startswith("sys-"):
            name = sys_id[4:].upper()
        else:
            name = sys_id
        print(f"  {sys_id} -> {name}")
        conn.execute(
            "INSERT OR IGNORE INTO solar_systems (solar_system_id, name) VALUES (?, ?)",
            (sys_id, name),
        )
        count += 1

    conn.commit()
    print(f"\nBackfilled {count} system names.")

    # Verify
    total = conn.execute("SELECT COUNT(*) FROM solar_systems").fetchone()[0]
    print(f"Total solar_systems entries: {total}")
    conn.close()


if __name__ == "__main__":
    db_path = sys.argv[1] if len(sys.argv) > 1 else "/app/data/watchtower.db"
    fix(db_path)
