"""
analysis.py

Part 2: Initial Analysis - Data Overview

This module reads from the SQLite database created by load_data.py
and computes the relative frequency of each immune cell population
within each biological sample.
"""

import os
import sqlite3
import pandas as pd


DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "immune_data.db")

CELL_POPS = [
    "b_cell",
    "cd8_t_cell",
    "cd4_t_cell",
    "nk_cell",
    "monocyte",
]


def get_connection() -> sqlite3.Connection:
    """
    Create a connection to the SQLite database.

    Note:
    The database should already be created by running:
        python load_data.py
    """
    if not os.path.exists(DB_PATH):
        raise FileNotFoundError(
            f"Database not found at {DB_PATH}. "
            "Please run `python load_data.py` first."
        )

    return sqlite3.connect(DB_PATH)


def get_frequency_table() -> pd.DataFrame:
    """
    Compute the relative frequency of each immune cell population
    for every sample.

    For each sample:
        total_count = b_cell + cd8_t_cell + cd4_t_cell + nk_cell + monocyte

    For each population:
        percentage = count / total_count * 100

    Returns:
        pandas.DataFrame with columns:
            sample:
                Sample ID from the original cell-count.csv file.
            total_count:
                Total cell count across all five immune populations.
            population:
                Name of the immune cell population.
            count:
                Raw cell count for that population.
            percentage:
                Relative frequency of that population within the sample.

    Expected output size:
        10,500 samples × 5 populations = 52,500 rows.
    """
    query = """
        SELECT
            sample_id AS sample,
            b_cell,
            cd8_t_cell,
            cd4_t_cell,
            nk_cell,
            monocyte
        FROM cell_counts
    """

    conn = get_connection()
    try:
        df = pd.read_sql_query(query, conn)
    finally:
        conn.close()

    # Calculate total cells per sample across the five immune populations.
    df["total_count"] = df[CELL_POPS].sum(axis=1)

    # Defensive check: avoid division by zero if a malformed sample has no cells.
    df = df[df["total_count"] > 0].copy()

    # Convert from wide format to long format.
    # Before:
    #   sample | b_cell | cd8_t_cell | cd4_t_cell | nk_cell | monocyte
    #
    # After:
    #   sample | population | count
    long_df = df.melt(
        id_vars=["sample", "total_count"],
        value_vars=CELL_POPS,
        var_name="population",
        value_name="count",
    )

    # Compute relative frequency as a percentage of total cells in that sample.
    long_df["percentage"] = (
        long_df["count"] / long_df["total_count"] * 100
    ).round(2)

    # Return exactly the columns requested in the assignment.
    return long_df[
        ["sample", "total_count", "population", "count", "percentage"]
    ].reset_index(drop=True)


if __name__ == "__main__":
    frequency_table = get_frequency_table()

    print("Part 2: Relative Frequency Table")
    print(f"Rows: {len(frequency_table):,}")
    print(frequency_table.head(10).to_string(index=False))