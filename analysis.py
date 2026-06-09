"""
analysis.py

Core analytical functions for Parts 2-4.
All functions read from the SQLite database created by load_data.py.
"""

import os
import sqlite3
import pandas as pd
from scipy import stats


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


# ── Part 2: Relative Frequency Table ─────────────────────────────────────────

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



# ── Part 3: Statistical Analysis ─────────────────────────────────────────────
def get_melanoma_miraclib_pbmc() -> pd.DataFrame:
    """
    Melanoma PBMC samples treated with miraclib that have a known response.
    Returns wide DataFrame with raw counts, total_count, and *_pct columns.
    """
    query = """
        SELECT s.sample_id AS sample,
               subj.response,
               cc.b_cell, cc.cd8_t_cell, cc.cd4_t_cell, cc.nk_cell, cc.monocyte
        FROM   samples s
        JOIN   subjects subj ON s.subject_id = subj.subject_id
        JOIN   cell_counts cc ON s.sample_id = cc.sample_id
        WHERE  subj.condition = 'melanoma'
          AND  subj.treatment = 'miraclib'
          AND  s.sample_type  = 'PBMC'
          AND  subj.response  IS NOT NULL
    """
    conn = get_connection()
    try:
        df = pd.read_sql_query(query, conn)
    finally:
        conn.close()

    df["total_count"] = df[CELL_POPS].sum(axis=1)
    df = df[df["total_count"] > 0].copy()

    for pop in CELL_POPS:
        df[f"{pop}_pct"] = (df[pop] / df["total_count"] * 100).round(4)
    return df


def run_statistical_tests(df: pd.DataFrame) -> pd.DataFrame:
    """
    Mann-Whitney U (two-sided) for each cell population pct,
    responders vs non-responders.
    Returns one row per population with sample sizes, medians,
    median difference, direction, U statistic, p-value, significance.
    """
    resp = df[df["response"] == "yes"]
    non  = df[df["response"] == "no"]

    rows = []
    for pop in CELL_POPS:
        col     = f"{pop}_pct"
        r_vals  = resp[col].dropna()
        nr_vals = non[col].dropna()

        # Skip if either group is empty
        if len(r_vals) == 0 or len(nr_vals) == 0:
            continue

        u_stat, p_val = stats.mannwhitneyu(r_vals, nr_vals, alternative="two-sided")

        r_med  = round(r_vals.median(), 3)
        nr_med = round(nr_vals.median(), 3)
        diff   = round(r_med - nr_med, 3)

        if diff > 0:
            higher_in = "responders"
        elif diff < 0:
            higher_in = "non_responders"
        else:
            higher_in = "equal"

        rows.append({
            "population":               pop,
            "n_responders":             len(r_vals),
            "n_non_responders":         len(nr_vals),
            "responder_median_pct":     r_med,
            "non_responder_median_pct": nr_med,
            "median_diff_pct":          diff,
            "higher_in":                higher_in,
            "mann_whitney_u":           round(u_stat, 1),
            "p_value":                  round(p_val, 6),
            "significant":              p_val < 0.05,
        })
    result = pd.DataFrame(rows)
    result = result.sort_values("p_value").reset_index(drop=True)
    return result


# ── Part 4: Subset Analysis ───────────────────────────────────────────────────

def get_baseline_subset() -> pd.DataFrame:
    """
    Part 4 Query 1.

    Identify all melanoma PBMC samples at baseline from patients treated
    with miraclib.

    Filter:
        condition = melanoma
        sample_type = PBMC
        time_from_treatment_start = 0
        treatment = miraclib
    """
    query = """
        SELECT
            s.sample_id,
            subj.subject_id,
            subj.project,
            subj.sex,
            subj.response,
            cc.b_cell,
            cc.cd8_t_cell,
            cc.cd4_t_cell,
            cc.nk_cell,
            cc.monocyte
        FROM samples s
        JOIN subjects subj
            ON s.subject_id = subj.subject_id
        JOIN cell_counts cc
            ON s.sample_id = cc.sample_id
        WHERE subj.condition = 'melanoma'
          AND s.sample_type = 'PBMC'
          AND s.time_from_treatment_start = 0
          AND subj.treatment = 'miraclib'
    """

    conn = get_connection()
    try:
        df = pd.read_sql_query(query, conn)
    finally:
        conn.close()

    return df


def get_subset_summary(df: pd.DataFrame) -> dict:
    """
    Part 4 Query 2.

    Summarize the baseline subset.

    Returns:
        total_samples:
            Number of melanoma PBMC baseline miraclib samples.

        samples_per_project:
            Number of samples from each project.

        response_counts:
            Number of unique subjects who were responders/non-responders.

        sex_counts:
            Number of unique subjects who were male/female.

        avg_bcell_male_responders:
            Average B cell count among melanoma male responders at baseline.
    """
    subjects = df.drop_duplicates("subject_id")

    male_responders = df[
        (df["sex"] == "M") &
        (df["response"] == "yes")
    ]

    summary = {
        "total_samples": len(df),

        "samples_per_project": (
            df.groupby("project")["sample_id"]
            .count()
            .sort_index()
            .to_dict()
        ),

        "response_counts": (
            subjects["response"]
            .value_counts()
            .sort_index()
            .to_dict()
        ),

        "sex_counts": (
            subjects["sex"]
            .value_counts()
            .sort_index()
            .to_dict()
        ),

        "avg_bcell_male_responders": round(
            male_responders["b_cell"].mean(), 2
        ),
    }

    return summary


if __name__ == "__main__":
    frequency_table = get_frequency_table()
    print("Part 2: Relative Frequency Table")
    print(f"Rows: {len(frequency_table):,}")
    print(frequency_table.head(10).to_string(index=False))

    print("\nPart 3 — statistical tests:")
    mmp = get_melanoma_miraclib_pbmc()
    print(run_statistical_tests(mmp).to_string(index=False))

    print("\nPart 4 — subset summary:")
    baseline = get_baseline_subset()
    for k, v in get_subset_summary(baseline).items():
        print(f"  {k}: {v}")