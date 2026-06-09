# Immune Cell Population Analysis
### Loblaw Bio: miraclib clinical trial

This assignment combines several pieces of a typical analytical workflow: data ingestion, data modeling, statistical analysis, and visualization.

What I found most interesting was that the questions resemble the kinds of exploratory analyses that often arise early in a clinical study. The challenge is not simply calculating numbers, but organizing the data in a way that makes biological questions easy to ask and answer repeatedly.

To support that workflow, I built a small analytical stack:

- **SQLite** for structured data management
- **Python** for data transformation and statistical analysis
- **Plotly / Dash** for visualization and interactive exploration

The result is a reproducible pipeline that takes raw cell-count measurements and turns them into a set of analyses that Bob and his colleague Yah D'yada can explore through an interactive dashboard.

---

## How to run

Tested on Python 3.11. Requires no manual setup beyond the three make commands.

```bash
make setup      # install dependencies
make pipeline   # initialise database, run analysis, save outputs to ./outputs/
make dashboard  # start dashboard at http://localhost:8050
```

`make dashboard` will initialise the database automatically if it does not already exist, so the two commands can be run independently.

---

## Database schema

The source data is a flat CSV where every row contains both patient-level metadata and sample-level measurements. Although the entire dataset could fit comfortably in a single table, I chose not to model it that way. The assignment hints at longitudinal clinical data, where patients contribute multiple samples at different time points, and separating subjects, samples, and measurements better reflects the underlying relationships and keeps the schema adaptable as the study grows.

```
subjects        one row per patient
  subject_id, project, condition, age, sex, treatment, response

samples         one row per biological sample
  sample_id, subject_id, sample_type, time_from_treatment_start

cell_counts     one row per sample, five cell population columns
  sample_id, b_cell, cd8_t_cell, cd4_t_cell, nk_cell, monocyte
```

**Scalability**

Four indexes are defined at load time to support the joins and filters used in Parts 3 and 4:

```sql
idx_samples_subject_id      ON samples(subject_id)
idx_cell_counts_sample_id   ON cell_counts(sample_id)
idx_subjects_filter         ON subjects(condition, treatment, response)
idx_samples_filter          ON samples(sample_type, time_from_treatment_start)
```

With hundreds of projects and millions of samples, these indexes keep the analytical queries fast without scanning every row. If new cell populations were added in future panels, an EAV-style `cell_counts(sample_id, population, count)` table would be more flexible. I chose the wide format here because the five populations are fixed and it makes frequency calculations straightforward. The same schema migrates cleanly to PostgreSQL with no structural changes.

---

## Code structure

```
load_data.py    initialise SQLite schema and load cell-count.csv
analysis.py     analytical functions for Parts 2-4
pipeline.py     orchestrates the full pipeline, saves outputs to ./outputs/
app.py          Dash dashboard
```

**Design decisions**

I intentionally separated computation from presentation. `analysis.py` contains only functions that query the database and return DataFrames, with no file I/O and no plotting. The same functions are reused by both `pipeline.py` (which saves static outputs) and `app.py` (which renders them interactively), with no duplication. `load_data.py` is kept entirely standalone so it can be called as a subprocess by `pipeline.py` without creating circular imports.

Data are loaded once at dashboard startup and reused across all interactions, so navigating between tabs does not re-query the database.

**Why Dash over Streamlit?**

Dash separates layout from callbacks, which makes the data flow explicit. For a clinical data tool where the distinction between what is displayed and what triggers an update matters, that structure is worth the extra boilerplate. Streamlit would have been faster to prototype but harder to reason about as the dashboard grew.

---

## Analysis summary

**Part 2: Relative frequencies**

Frequencies were computed by melting the wide cell count table into long format (52,500 rows: 10,500 samples x 5 populations) and expressing each population as a percentage of the sample total.

**Part 3: Statistical analysis**

To compare responders and non-responders among melanoma PBMC samples treated with miraclib, I used a two-sided Mann-Whitney U test for each population. This test was chosen over a t-test because it makes no assumption about normality and is appropriate for the sample sizes here.

Among the five populations examined, only CD4+ T cells showed a statistically significant difference between groups (p = 0.013). Responders had a higher median CD4+ T-cell frequency (30.22% vs 29.66%). The magnitude of the difference is relatively small, so I would not interpret this as evidence of a predictive biomarker on its own. However, if this were a real clinical study, CD4+ T-cell abundance would likely be one of the first features to prioritize for follow-up analysis, particularly in combination with additional clinical covariates or longitudinal measurements.

**Part 4: Subset analysis**

Baseline PBMC samples (t = 0, melanoma, miraclib) span two projects: prj1 (384 samples) and prj3 (272 samples). The baseline cohort contains 656 samples in total, representing 331 responders and 325 non-responders.

Among male responders at baseline, the mean B cell count is **10,401.28 cells per sample**.

---

## Dashboard

Local dashboard URL: **http://localhost:8050**

Start the dashboard with:

```bash
make dashboard
```

Three tabs mirror the analytical parts:

- **Frequency table**: searchable and filterable table of all 52,500 frequency rows, plus mean frequency bar chart
- **Statistical analysis**: Mann-Whitney results with significance highlighting and comparative boxplots
- **Subset analysis**: baseline cohort breakdowns and the key B cell result

---

## Reflection

Building the individual components was not particularly difficult. The more interesting challenge was deciding where each responsibility should live: what should be handled by the database, what should be calculated in analysis code, and what should be left to the dashboard. Thinking through those boundaries ultimately had a bigger impact on the project than any individual visualization or statistical test.

While the dataset is synthetic, the workflow resembles many real problems in translational research, where raw measurements need to be transformed into something interpretable for researchers and decision makers.

Reproducibility was also a major consideration throughout. The same commands should produce the same outputs regardless of who runs the code, which is why the entire workflow is exposed through a small set of Makefile targets rather than requiring manual execution steps.
