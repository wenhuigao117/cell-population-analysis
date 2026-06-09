# Immune Cell Population Analysis

### Exploratory immune profiling for a miraclib clinical trial

This was my first time building an end-to-end data pipeline for a clinical dataset, and it turned out to be more interesting than I expected.

At first, the assignment looked fairly straightforward: load a CSV file, run some analyses, and build a dashboard. The individual tasks were manageable on their own. The harder part was figuring out how to connect everything together in a way that felt clean, reusable, and easy to extend.

To support that workflow, I used:

* **SQLite** for structured data storage
* **Python** for data processing and statistical analysis
* **Plotly / Dash** for visualization and interactive exploration

The final result is a reproducible pipeline that transforms raw cell count measurements into analytical outputs that can be explored through an interactive dashboard.

---

## How to run

Tested on Python 3.11.

```bash
make setup      # install dependencies
make pipeline   # initialise database, run analysis, save outputs to ./outputs/
make dashboard  # start dashboard at http://localhost:8050
```

`make dashboard` will initialise the database automatically if it does not already exist, so the pipeline and dashboard can be run independently.

---

## Database schema

The source CSV contains one row per sample and mixes patient-level information (age, sex, condition, treatment) with sample-level information (time point and cell counts).

My first instinct was to load everything into a single table. After exploring the data, that approach started to feel limiting because each patient appears multiple times across different samples and time points. Repeating all patient attributes in every row would introduce redundancy and make future extensions more difficult.

To better reflect the underlying relationships, I split the data into three tables:

```text
subjects        one row per patient
  subject_id, project, condition, age, sex, treatment, response

samples         one row per biological sample
  sample_id, subject_id, sample_type, time_from_treatment_start

cell_counts     one row per sample
  sample_id, b_cell, cd8_t_cell, cd4_t_cell, nk_cell, monocyte
```

In this dataset, treatment and response are modeled as subject-level attributes because each subject belongs to a single treatment arm and has a single response label across collected samples. If treatment assignments varied over time, those fields could be moved into a visit-level or sample-level table.

To support the analytical queries used throughout Parts 3 and 4, I created four indexes:

```sql
idx_samples_subject_id      ON samples(subject_id)
idx_cell_counts_sample_id   ON cell_counts(sample_id)
idx_subjects_filter         ON subjects(condition, treatment, response)
idx_samples_filter          ON samples(sample_type, time_from_treatment_start)
```

With larger datasets, full table scans become increasingly expensive. These indexes help keep filtering and joins efficient as the number of projects, subjects, and samples grows.

I kept `cell_counts` in a wide format because the five immune populations are fixed in this dataset and the frequency calculations become straightforward. If future studies introduced many additional populations, a long-format structure (`sample_id`, `population`, `count`) would likely be more flexible.

---

## Code structure

```text
load_data.py    initialise SQLite schema and load cell-count.csv
analysis.py     query functions for Parts 2–4 and return DataFrames
pipeline.py     run the complete pipeline and save outputs
app.py          Dash dashboard
```

I intentionally separated computation from presentation.

`analysis.py` contains reusable query and analysis functions with no file I/O or plotting logic. These same functions are used by both `pipeline.py` and `app.py`, which avoids duplicating calculations across different parts of the project.

`pipeline.py` orchestrates the entire workflow and generates all required outputs.

`app.py` focuses entirely on visualization and user interaction.

`load_data.py` remains standalone so it can be executed independently or called by the pipeline without creating import dependencies.

---

## Why Dash?

I originally considered using Streamlit because it would have been faster to get something working.

In the end, I chose Dash because I wanted to better understand how callback-driven applications are structured. As the dashboard became more interactive, I found Dash's explicit separation between inputs, outputs, and callbacks easier to reason about and debug.

Streamlit would have been quicker to prototype, but Dash felt like a better fit once the application started growing beyond a few simple visualizations.

---

## Analysis summary

### Part 2: Relative frequencies

For each sample, I calculated the total cell count by summing the five immune populations.

The relative frequency of each population was then computed as:

```text
population count / total sample count
```

The resulting frequency table contains 52,500 rows:

```text
10,500 samples × 5 populations
```

Each row includes:

* Sample ID
* Population
* Raw count
* Total sample count
* Relative frequency (%)

---

### Part 3: Statistical analysis

To investigate whether immune cell composition is associated with treatment response, I filtered the dataset to:

* Melanoma patients
* PBMC samples
* Miraclib treatment

For each population, I compared responders and non-responders using a two-sided Mann-Whitney U test.

I chose the Mann-Whitney test instead of a t-test because it does not assume normally distributed data and is generally more robust for biological measurements where the underlying distribution is unknown.

Among the five populations examined, only CD4+ T cells showed a statistically significant difference:

```text
p = 0.013
```

Responders had a slightly higher median CD4+ T-cell frequency:

```text
30.22% vs 29.66%
```

The effect size is modest, so I would not interpret this as a strong predictive biomarker by itself. However, if this were a real clinical study, CD4+ T-cell abundance would likely be one of the first features worth investigating further alongside additional clinical variables and longitudinal measurements.

---

### Part 4: Subset analysis

I filtered the data to:

* Melanoma patients
* PBMC samples
* Miraclib treatment
* Baseline samples (`time_from_treatment_start = 0`)

This subset contains:

```text
656 samples
```

distributed across:

```text
prj1: 384 samples
prj3: 272 samples
```

The cohort includes:

```text
331 responders
325 non-responders

344 males
312 females
```

Among male responders at baseline, the mean B-cell count is:

```text
10,401.28 cells per sample
```

---

## Dashboard

Local dashboard URL:

```text
http://localhost:8050
```

Start the dashboard with:

```bash
make dashboard
```

The dashboard is organized into three tabs:

### Frequency table

* Interactive table of all 52,500 frequency records
* Search and filtering functionality
* Mean frequency summary chart

### Statistical analysis

* Mann-Whitney U test results
* Significance highlighting
* Boxplots comparing responders and non-responders

### Subset analysis

* Baseline cohort summary
* Project distribution
* Response distribution
* Sex distribution
* Mean B-cell count result

---

## Reflection

The part I spent the most time thinking about was not the statistics or the dashboard itself. It was figuring out where each piece of logic should live.

Should frequency calculations happen in SQL or in pandas?

Should filtering happen in the database layer or in the application layer?

At the beginning of the project, I did not have strong answers to those questions. I revised the structure several times before it started to feel clean and consistent.

The schema design was also less obvious than I expected. My first version closely mirrored the CSV structure. Once I started writing the Part 3 and Part 4 queries, I found myself repeatedly working around awkward joins and duplicated information. That was a useful signal that the data model was not aligned with the questions being asked.

Separating subjects, samples, and measurements ultimately made both the analysis code and the SQL queries much easier to understand.

Although the dataset is synthetic, the analytical questions felt realistic. They resemble the kinds of exploratory questions that researchers might ask early in a clinical study when trying to understand potential treatment effects and identify signals worth investigating further.

More than anything, this project reinforced the idea that organizing data well is often just as important as analyzing it.
