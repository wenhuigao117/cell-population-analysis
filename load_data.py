"""
load_data.py
Initializes a SQLite database from cell-count.csv.
Run: python load_data.py
"""

import sqlite3
import csv
import os

DB_PATH  = os.path.join(os.path.dirname(os.path.abspath(__file__)), "immune_data.db")
CSV_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "cell-count.csv")

SCHEMA = """
CREATE TABLE IF NOT EXISTS subjects (
    subject_id  TEXT PRIMARY KEY,
    project     TEXT NOT NULL,
    condition   TEXT NOT NULL,
    age         INTEGER,
    sex         TEXT,
    treatment   TEXT NOT NULL,
    response    TEXT
);

CREATE TABLE IF NOT EXISTS samples (
    sample_id                 TEXT PRIMARY KEY,
    subject_id                TEXT NOT NULL REFERENCES subjects(subject_id),
    sample_type               TEXT NOT NULL,
    time_from_treatment_start INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS cell_counts (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    sample_id  TEXT NOT NULL UNIQUE REFERENCES samples(sample_id),
    b_cell     INTEGER NOT NULL,
    cd8_t_cell INTEGER NOT NULL,
    cd4_t_cell INTEGER NOT NULL,
    nk_cell    INTEGER NOT NULL,
    monocyte   INTEGER NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_samples_subject_id
    ON samples(subject_id);

CREATE INDEX IF NOT EXISTS idx_cell_counts_sample_id
    ON cell_counts(sample_id);

CREATE INDEX IF NOT EXISTS idx_subjects_filter
    ON subjects(condition, treatment, response);

CREATE INDEX IF NOT EXISTS idx_samples_filter
    ON samples(sample_type, time_from_treatment_start);
"""


def init_db(conn):
    conn.executescript(SCHEMA)
    conn.commit()


def load_csv(conn, csv_path):
    if not os.path.exists(csv_path):
        raise FileNotFoundError(f"CSV file not found: {csv_path}")

    cursor = conn.cursor()
    with open(csv_path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        subjects_seen = set()
        for row in reader:
            subj = row["subject"]
            if subj not in subjects_seen:
                cursor.execute(
                    """
                    INSERT OR IGNORE INTO subjects
                        (subject_id, project, condition, age, sex, treatment, response)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        subj,
                        row["project"],
                        row["condition"],
                        int(row["age"]) if row["age"] else None,
                        row["sex"] if row["sex"] else None,
                        row["treatment"],
                        row["response"] if row["response"] else None,
                    ),
                )
                subjects_seen.add(subj)

            cursor.execute(
                """
                INSERT OR IGNORE INTO samples
                    (sample_id, subject_id, sample_type, time_from_treatment_start)
                VALUES (?, ?, ?, ?)
                """,
                (
                    row["sample"],
                    subj,
                    row["sample_type"],
                    int(row["time_from_treatment_start"]),
                ),
            )

            cursor.execute(
                """
                INSERT OR IGNORE INTO cell_counts
                    (sample_id, b_cell, cd8_t_cell, cd4_t_cell, nk_cell, monocyte)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    row["sample"],
                    int(row["b_cell"]),
                    int(row["cd8_t_cell"]),
                    int(row["cd4_t_cell"]),
                    int(row["nk_cell"]),
                    int(row["monocyte"]),
                ),
            )

    conn.commit()
    print(f"Database created: {DB_PATH}")
    cur = conn.cursor()
    cur.execute("SELECT COUNT(*) FROM subjects");    print(f"  Subjects:   {cur.fetchone()[0]}")
    cur.execute("SELECT COUNT(*) FROM samples");     print(f"  Samples:    {cur.fetchone()[0]}")
    cur.execute("SELECT COUNT(*) FROM cell_counts"); print(f"  Cell rows:  {cur.fetchone()[0]}")


if __name__ == "__main__":
    if os.path.exists(DB_PATH):
        os.remove(DB_PATH)
    conn = sqlite3.connect(DB_PATH)
    conn.execute("PRAGMA foreign_keys = ON")
    init_db(conn)
    load_csv(conn, CSV_PATH)
    conn.close()