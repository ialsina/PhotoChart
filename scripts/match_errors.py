"""
Match and compare photograph errors between database and log files.

This script reads photograph errors from two sources:
1. SQLite database: Reads photograph paths that have been marked with errors
2. Log files: Extracts file paths from log files using regex pattern matching

The script then matches errors between these two sources and displays:
- Errors found only in the database
- Errors found only in log files
- Errors found in both sources

This helps identify discrepancies and verify error tracking consistency.

Example:
    python match_errors.py ~/pCloudDrive/PHOTO/logs/log_*.txt --shield 'Extreme SSD' > errors.txt
"""

from pathlib import Path
from textwrap import dedent
import uuid
import argparse
import re
import sqlite3
import typing as T
from glob import glob
import pandas as pd
from tabulate import tabulate

# Columns to display in the output tables
PRINT_COLUMNS = [
    "path_id",
    "photograph_id",
    "path",
    "device",
]

# Default SQLite database path for photograph data
SQLITE_DB = Path("~/pCloudDrive/PHOTO/database/db.sqlite3").expanduser().resolve()

# Regular expression to match file paths in log files
# Matches paths like /path/to/file or /path/to/directory
RE_EXPR = re.compile(r"(/[-A-Za-z0-9_$\.]+(?:/[-A-Za-z0-9_$\.]+)+)")

# Keywords used to filter log lines to reduce false positives
# Only lines containing these words will be processed for path extraction
FILTER_WORDS = [
    "Failed to",
]


def _get_parser():
    """
    Create and configure the command-line argument parser.

    Returns:
        argparse.ArgumentParser: Configured argument parser with the following options:
            --db: Path to SQLite database (default: ~/pCloudDrive/PHOTO/database/db.sqlite3)
            input: One or more glob patterns to search for log files
            --shield: Words/phrases with spaces that should be temporarily replaced
                     to prevent regex from breaking on paths containing spaces
            --no-filter: Disable filtering log lines by FILTER_WORDS keywords
    """
    parser = argparse.ArgumentParser(
        description="Read errors from database and log files"
    )
    parser.add_argument(
        "--db",
        type=Path,
        default=SQLITE_DB,
        required=False,
        help="Read errors from the SQLite database",
    )
    parser.add_argument(
        "input",
        type=str,
        nargs="*",
        help="Glob pattern to search for log files",
    )
    parser.add_argument(
        "--shield",
        type=str,
        nargs="*",
        help="Shield words with spaces in expected paths",
    )
    parser.add_argument(
        "--no-filter",
        action="store_false",
        dest="filter",
        help="Disable filtering log errors by selected keywords to reduce false positives",
    )
    return parser


def read_dataframes(path):
    """
    Read and join photograph path and photograph data from SQLite database.

    Reads data from PHOTOGRAPH_PHOTOPATH and PHOTOGRAPH_PHOTOGRAPH tables,
    joins them, and normalizes device names by removing parenthetical information.

    Args:
        path: Path to the SQLite database file

    Returns:
        pd.DataFrame: Joined dataframe with path and photograph information.
                     Includes a 'path_id' column set to the index.
    """
    with sqlite3.connect(str(path)) as conn:
        df_paths = pd.read_sql_query(
            "SELECT * FROM PHOTOGRAPH_PHOTOPATH", conn, index_col="id"
        )
        # Normalize device names by removing parenthetical information (e.g., "Device (extra info)" -> "Device")
        df_paths["device"] = df_paths["device"].str.split("(").str[0].str.strip()
        df_photographs = pd.read_sql_query(
            "SELECT * FROM PHOTOGRAPH_PHOTOGRAPH", conn, index_col="id"
        )
        joined = df_paths.merge(
            df_photographs, left_on="photograph_id", right_on="id", how="left"
        )
        joined["path_id"] = joined.index
        return joined


def read_db_errors(path):
    """
    Read photograph paths that have errors from the SQLite database.

    Args:
        path: Path to the SQLite database file

    Returns:
        pd.DataFrame: Dataframe containing only photograph paths where has_errors == 1
    """
    df = read_dataframes(path)
    df_errors = df[df["has_errors"] == 1]
    return df_errors


def _clean_log_errors(
    paths: T.List[str], devices: T.List[str]
) -> T.List[T.Tuple[str, str]]:
    """
    Extract relative paths from full log paths by matching device names.

    Given a list of full file paths from logs and a list of device names,
    this function identifies which device each path belongs to and extracts
    the relative path portion after the device name.

    Args:
        paths: List of full file paths extracted from log files
        devices: List of device names to match against paths

    Returns:
        List of tuples: Each tuple contains (relative_path, device_name)
                       where relative_path is the portion after the device name
    """
    output = []
    for path in paths:
        for device in devices:
            if device in path:
                # Extract the path portion after the device name
                output.append((path.split(device)[1][1:], device))
    return output


def read_log_errors(path, shield=None, filter_=True):
    """
    Extract file paths from a log file using regex pattern matching.

    This function:
    1. Optionally shields words/phrases with spaces (replaces them with UUIDs)
    2. Optionally filters log lines to only those containing FILTER_WORDS
    3. Extracts file paths using RE_EXPR regex pattern
    4. Restores shielded words back to their original form
    5. Returns unique, sorted paths

    Args:
        path: Path to the log file to read
        shield: Optional list of words/phrases with spaces to temporarily replace.
                This prevents regex from breaking on paths containing spaces.
                Can be a string (single item) or list of strings.
        filter_: If True, only process lines containing FILTER_WORDS keywords.
                This reduces false positives from unrelated log entries.

    Returns:
        List[str]: Sorted list of unique file paths extracted from the log file.
                   Returns empty list if file cannot be decoded as UTF-8.
    """
    paths_encoded = []
    if shield is None:
        shield = []
    if isinstance(shield, str):
        shield = [shield]
    # Create a mapping of shield words to UUIDs for temporary replacement
    shield_dct = {}
    for element in shield:
        shield_dct[element] = str(uuid.uuid4())
    try:
        with open(path, "r", encoding="utf-8") as file:
            content = file.read()
    except UnicodeDecodeError:
        print(f"Failed to decode {path} with utf-8 encoding, skipping")
        return []
    # Replace shield words with UUIDs to prevent regex issues with spaces
    for key, encoded in shield_dct.items():
        content = content.replace(key, encoded)
    # Filter out lines containing any of the filter words
    if filter_:
        content = "\n".join(
            line
            for line in content.split("\n")
            if any(word.lower() in line.lower() for word in FILTER_WORDS)
        )
    # Extract paths using regex pattern
    for match in RE_EXPR.finditer(content):
        paths_encoded.append(match.group(0))
    # Restore shield words from UUIDs back to original form
    paths_decoded = []
    for path in paths_encoded:
        for key, encoded in shield_dct.items():
            path = path.replace(encoded, key)
        paths_decoded.append(path)
    return sorted(set(paths_decoded))


def read_glob_errors(glob_pattern, shield=None, filter_=True):
    """
    Extract file paths from all log files matching a glob pattern.

    Args:
        glob_pattern: Glob pattern to match log files (e.g., "logs/*.log")
        shield: Optional list of words/phrases with spaces to shield (see read_log_errors)
        filter_: If True, filter log lines by FILTER_WORDS (see read_log_errors)

    Returns:
        List[str]: Combined list of all file paths extracted from matching log files
    """
    log_errors = []
    for path in glob(glob_pattern):
        log_errors.extend(read_log_errors(path, shield=shield, filter_=filter_))
    return log_errors


def match_errors(
    log_errors: T.List[T.Tuple[str, str]], df_db: pd.DataFrame
) -> pd.DataFrame:
    """
    Match errors between log files and database, identifying discrepancies.

    Performs an outer join between log errors and database errors on path and device.
    Categorizes each error as:
    - "<< log >>": Found only in log files
    - "<< db >>": Found only in database
    - "== BOTH ==": Found in both sources

    Args:
        log_errors: List of tuples (path, device) extracted from log files
        df_db: DataFrame containing database errors with 'path' and 'device' columns

    Returns:
        pd.DataFrame: Joined dataframe with all errors, sorted by source, device, and path.
                     Includes a 'source' column indicating where each error was found.
    """
    df_log = pd.DataFrame(log_errors, columns=["path", "device"])
    # Outer join to find errors in both, only in logs, or only in database
    joined = df_log.merge(df_db, on=["path", "device"], how="outer", indicator=True)
    # Map merge indicator to human-readable source labels
    joined["source"] = joined["_merge"].map(
        {"left_only": "<< log >>", "right_only": "<< db >>", "both": "== BOTH =="}
    )
    return joined.sort_values(by=["source", "device", "path"]).reset_index(drop=True)


def main():
    """
    Main entry point for the error matching script.

    Orchestrates the process of:
    1. Reading errors from the SQLite database
    2. Reading and extracting errors from log files (using glob patterns)
    3. Cleaning log errors to extract relative paths
    4. Matching errors between the two sources
    5. Displaying formatted results showing discrepancies

    Output includes three sections:
    - DB errors: All errors found in the database
    - Log errors: All errors extracted from log files
    - Matched errors: Comparison showing which errors are in which source
    """
    args = _get_parser().parse_args()
    db_path = args.db

    # Read errors from database
    db_errors = read_db_errors(db_path)
    print(db_errors.columns)
    print("=" * 80)
    print("DB errors")
    print(tabulate(db_errors[PRINT_COLUMNS], headers="keys", tablefmt="heavy_outline"))
    print("=" * 80)

    # Read errors from log files
    log_errors = []
    for element in args.input:
        log_errors.extend(
            read_glob_errors(element, shield=args.shield, filter_=args.filter)
        )
    # Clean log errors to extract relative paths matched to devices
    log_errors = _clean_log_errors(log_errors, devices=db_errors["device"].unique())
    print("=" * 80)
    print("Log errors")
    print("\n".join([f"{device} - {path}" for path, device in log_errors]))
    print("=" * 80)

    # Match and compare errors from both sources
    matched_errors = match_errors(log_errors, db_errors)
    print("=" * 80)
    print("Matched errors")
    print(
        tabulate(
            matched_errors[PRINT_COLUMNS + ["source"]],
            headers="keys",
            tablefmt="heavy_outline",
        )
    )
    print("=" * 80)


if __name__ == "__main__":
    main()
