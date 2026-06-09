
# Immune Cell Population Analysis
### Exploratory immune profiling for a miraclib clinical trial

This was my first time building an end-to-end data pipeline for a clinical dataset, and it turned out to be more interesting than I expected. The individual steps：loading data, running queries, making charts were each manageable on their own. The harder part was figuring out how to connect them in a way that actually made sense.

I used:
- **SQLite** for structured data storage
- **Python** for data processing and statistics
- **Plotly / Dash** for the interactive dashboard

---

## How to run

Tested on Python 3.11.

```bash
make setup      # install dependencies
make pipeline   # initialise database, run analysis, save outputs to ./outputs/
make dashboard  # start dashboard at http://localhost:8050
```

`make dashboard` will initialise the database automatically if it does not already exist, so the two commands can be run independently.

---

## Database schema

The CSV has one row per sample, mixing patient-level info (age, sex, condition) with sample-level info (time point, cell counts). My first instinct was to load it into one table and be done with it, but that felt wrong once I noticed that each patient appears multiple times across different time points. Keeping all the patient info duplicated in every row seemed like it would create problems later if anything needed to be updated or filtered.

So I split it into three tables:

```
subjects        one row per patient
  subject_id, project, condition, age, sex, treatment, response

samples         one row per biological sample
  sample_id, subject_id, sample_type, time_from_treatment_start

cell_counts     one row per sample, five cell population columns
  sample_id, b_cell, cd8_t_cell, cd4_t_cell, nk_cell, monocyte
```

For scalability, I added four indexes to support the joins and filters that show up repeatedly in Parts 3 and 4:

```sql
idx_samples_subject_id      ON samples(subject_id)
idx_cell_counts_sample_id   ON cell_counts(sample_id)
idx_subjects_filter         ON subjects(condition, treatment, response)
idx_samples_filter          ON samples(sample_type, time_from_treatment_start)
```

With hundreds of projects and millions of rows, full table scans would get slow，these indexes help avoid that. I kept `cell_counts` in wide format (one column per population) because the five populations are fixed in this dataset and it makes the frequency math simpler. If new cell types were added later, switching to a long format (`sample_id, population, count`) would be more flexible, and I noted that tradeoff in the schema design.

---

## Code structure

```
load_data.py    initialise SQLite schema and load cell-count.csv
analysis.py     query functions for Parts 2-4, returns DataFrames
pipeline.py     runs the full pipeline and saves outputs to ./outputs/
app.py          Dash dashboard
```

I kept `analysis.py` as pure query functions with no file I/O or plotting, so the same code could be called from both `pipeline.py` (which saves CSVs and images) and `app.py` (which renders charts interactively) without duplicating logic. `load_data.py` is standalone so `pipeline.py` can call it as a subprocess without import issues.

I picked Dash over Streamlit partly because I wanted to better understand how callback-driven applications work. As the dashboard grew, I found Dash's explicit separation between inputs, outputs, and callbacks easier to reason about and debug. Streamlit would have been quicker to prototype, but Dash felt like a better fit once the interactions became more complex.

---

## Analysis summary

**Part 2: Relative frequencies**

For each sample, I summed the five population counts to get `total_count`, then divided each population's count by that total to get a percentage. The result is 52,500 rows (10,500 samples × 5 populations).

**Part 3: Statistical analysis**

I filtered to melanoma PBMC samples treated with miraclib, then compared responders vs non-responders using a two-sided Mann-Whitney U test for each population. I used Mann-Whitney rather than a t-test because it doesn't assume normality, which felt safer here without knowing the underlying distribution.

Only CD4+ T cells showed a significant difference (p = 0.013). Responders had a slightly higher median frequency (30.22% vs 29.66%). The difference is small, so I wouldn't call it a strong biomarker signal on its own, but it's probably worth looking at in combination with other variables.

**Part 4: Subset analysis**

Filtering to melanoma, PBMC, time = 0, miraclib gave 656 samples across two projects： prj1 (384) and prj3 (272). The cohort has 331 responders and 325 non-responders, with 344 males and 312 females.

Among male responders at baseline, the mean B cell count is **10,401.28 cells per sample**.

---
## Reflection

The part I spent the most time on wasn't the statistics or the dashboard， it was figuring out where each piece of logic should live. Should the frequency calculation happen in SQL or in pandas? Should the filtering be done in the database or in the application layer? I didn't have a strong intuition for this at the start, and I revised the structure a few times before it felt clean.

The schema design was also less obvious than I expected. My first version just mirrored the CSV structure, but once I started writing the Part 3 and 4 queries I kept running into awkward joins, which told me the data wasn't organized in a way that matched the questions being asked. Splitting subjects, samples, and counts into separate tables made the queries much more natural.

The dataset is synthetic, but the questions felt realistic — the kind of thing someone would actually want to know early in a clinical trial. That made it easier to think about what "useful" looked like, rather than just getting the numbers out.

---
## Dashboard

Local dashboard URL: **http://localhost:8050**

```bash
make dashboard
```

Three tabs:
- **Frequency table**： filterable table of all 52,500 rows, plus a mean frequency bar chart
- **Statistical analysis**： Mann-Whitney results with boxplots comparing responders vs non-responders
- **Subset analysis**： project/response/sex breakdowns for the baseline cohort, and the B cell result
