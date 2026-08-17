"""
ingest.py

Step 1 of the IntentEngine pipeline: raw data loading from a Google
Takeout export. Reads JSON/CSV off disk into plain Python lists of
dicts. Does NOT clean or normalize anything — that's preprocess.py.

Data contract:
    Core (required, raises if both missing/empty):
        - data/history/watch-history.json
        - data/history/search-history.json

    Optional (missing/empty falls back to [], never raises):
        - data/playlists/*.csv                    (globbed)
        - data/subscriptions/subscriptions.csv     (fixed filename)
        - data/comments/comments.csv               (fixed filename)

Glob vs. fixed filename: playlists/ is globbed because playlist CSV
filenames are user-defined and their count varies per account — there
is no fixed name to target. subscriptions/ and comments/ instead load
their known, fixed Takeout filename directly. This is a deliberate
data-integrity choice: globbing those folders would silently absorb
any unexpected file Google adds there in the future, changing pipeline
input without a deliberate decision to support it.
"""

import json
import csv
from pathlib import Path


DATA_DIR = Path("data")

HISTORY_DIR = DATA_DIR / "history"
PLAYLISTS_DIR = DATA_DIR / "playlists"
SUBSCRIPTIONS_DIR = DATA_DIR / "subscriptions"
COMMENTS_DIR = DATA_DIR / "comments"

SUBSCRIPTIONS_FILENAME = "subscriptions.csv"
COMMENTS_FILENAME = "comments.csv"


def load_json_file(filepath: Path) -> list:
    """Load a JSON file expected to contain a top-level list. Returns
    [] on missing/invalid file instead of raising."""
    if not filepath.exists():
        print(f"  [missing] {filepath} — returning empty list")
        return []

    try:
        with open(filepath, "r", encoding="utf-8") as f:
            data = json.load(f)
    except (json.JSONDecodeError, OSError) as e:
        print(f"  [error] Could not read {filepath}: {e}")
        return []

    if not isinstance(data, list):
        print(f"  [warning] {filepath} was not a list — returning empty list")
        return []

    return data


def load_csv_file(filepath: Path) -> list:
    """Load a CSV file as a list of dicts. Returns [] on missing/
    unreadable file. Used both directly (fixed-filename sources) and
    internally by load_csv_directory (globbed sources)."""
    if not filepath.exists():
        print(f"  [missing] {filepath} — returning empty list")
        return []

    try:
        with open(filepath, "r", encoding="utf-8", newline="") as f:
            rows = list(csv.DictReader(f))
    except (OSError, csv.Error) as e:
        print(f"  [error] Could not read {filepath}: {e}")
        return []

    return rows


def load_csv_directory(directory: Path) -> list:
    """Load and combine every .csv file in `directory`. Used only for
    playlists/ — filenames there are user-defined and unpredictable.
    Do NOT reuse for subscriptions/ or comments/, which have fixed
    filenames (see module docstring). Returns [] if the directory or
    any CSVs are missing."""
    if not directory.exists():
        print(f"  [missing] {directory} — returning empty list")
        return []

    csv_files = sorted(directory.glob("*.csv"))
    if not csv_files:
        print(f"  [empty] {directory} — no .csv files found")
        return []

    combined_rows = []
    for csv_file in csv_files:
        rows = load_csv_file(csv_file)
        print(f"  [loaded] {csv_file.name}: {len(rows)} row(s)")
        combined_rows.extend(rows)

    return combined_rows


def load_history() -> dict:
    """Load watch/search history. Raises if BOTH are empty — the
    pipeline has nothing to analyze without at least one."""
    print("Loading history/ (core data)...")
    watch_history = load_json_file(HISTORY_DIR / "watch-history.json")
    search_history = load_json_file(HISTORY_DIR / "search-history.json")

    print(f"  watch-history.json: {len(watch_history)} record(s)")
    print(f"  search-history.json: {len(search_history)} record(s)")

    if not watch_history and not search_history:
        raise RuntimeError(
            "Both watch-history.json and search-history.json are missing or "
            "empty. Check that data/history/ contains your Takeout export."
        )

    return {"watch_history": watch_history, "search_history": search_history}


def load_all_data() -> dict:
    """Load all data sources per the data contract and return a single
    combined dict. Optional sources default to [] rather than raising."""
    history = load_history()

    print("Loading playlists/ (optional)...")
    playlists = load_csv_directory(PLAYLISTS_DIR)

    print("Loading subscriptions/ (optional)...")
    subscriptions = load_csv_file(SUBSCRIPTIONS_DIR / SUBSCRIPTIONS_FILENAME)
    print(f"  [loaded] {SUBSCRIPTIONS_FILENAME}: {len(subscriptions)} row(s)")

    print("Loading comments/ (optional)...")
    comments = load_csv_file(COMMENTS_DIR / COMMENTS_FILENAME)
    print(f"  [loaded] {COMMENTS_FILENAME}: {len(comments)} row(s)")

    return {
        **history,
        "playlists": playlists,
        "subscriptions": subscriptions,
        "comments": comments,
    }


if __name__ == "__main__":
    # Standalone test: confirms ingest.py reads the real data/ folder
    # correctly before anything downstream depends on it.
    print("=== IntentEngine ingest.py — standalone test run ===\n")

    result = load_all_data()

    print("\n=== Summary ===")
    for key, records in result.items():
        print(f"{key}: {len(records)} record(s)")

    print("\n=== Sample record from each non-empty category ===")
    for key, records in result.items():
        if records:
            print(f"\n--- {key} (first record) ---")
            print(records[0])
        else:
            print(f"\n--- {key}: (empty, nothing to sample) ---")