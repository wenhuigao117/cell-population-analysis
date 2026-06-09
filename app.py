"""
app.py
Immune cell population dashboard — Loblaw Bio clinical trial.

Run:
    python3 app.py
Then open http://localhost:8050

Triggered by:
    make dashboard
"""

import os
import sys
import subprocess

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from dash import Dash, dcc, html, dash_table, Input, Output
import dash_bootstrap_components as dbc

# Auto-initialise DB if not present, so `make dashboard` works standalone
_db = os.path.join(os.path.dirname(os.path.abspath(__file__)), "immune_data.db")
if not os.path.exists(_db):
    subprocess.run([sys.executable, "load_data.py"], check=True)

from analysis import (
    get_connection,
    get_frequency_table,
    get_melanoma_miraclib_pbmc,
    run_statistical_tests,
    get_baseline_subset,
    get_subset_summary,
    CELL_POPS,
)

# ── Brand colours ─────────────────────────────────────────────────────────────
NAVY       = "#0D1B2A"
NAVY_LIGHT = "#1A2E42"
TEAL       = "#0E8C6E"
TEAL_LIGHT = "rgba(14,140,110,0.18)"
RED        = "#C94F38"
RED_LIGHT  = "rgba(201,79,56,0.18)"
BORDER     = "#E4E8EE"
BG         = "#F5F7FA"
TEXT       = "#1A1A2E"
MUTED      = "#6B7A8D"

POP_LABELS = {
    "b_cell":     "B cell",
    "cd8_t_cell": "CD8+ T cell",
    "cd4_t_cell": "CD4+ T cell",
    "nk_cell":    "NK cell",
    "monocyte":   "Monocyte",
}

PLOT_BASE = dict(
    plot_bgcolor="white",
    paper_bgcolor="white",
    font_family="Inter, system-ui, sans-serif",
    font_color=TEXT,
    margin=dict(l=48, r=24, t=48, b=40),
)

# ── Load data once at startup ─────────────────────────────────────────────────
freq_df  = get_frequency_table()
mmp_df   = get_melanoma_miraclib_pbmc()
stats_df = run_statistical_tests(mmp_df)
baseline = get_baseline_subset()
summary  = get_subset_summary(baseline)

# Derived counts — all dynamic, nothing hard-coded
conn       = get_connection()
N_SUBJECTS = pd.read_sql_query(
    "SELECT COUNT(DISTINCT subject_id) FROM subjects", conn
).iloc[0, 0]
conn.close()

N_SAMPLES  = freq_df["sample"].nunique()
N_ROWS     = len(freq_df)
TOTAL_MMP  = len(mmp_df)
N_RESP     = int((mmp_df["response"] == "yes").sum())
N_NRESP    = int((mmp_df["response"] == "no").sum())

# ── App ───────────────────────────────────────────────────────────────────────
app = Dash(
    __name__,
    external_stylesheets=[dbc.themes.BOOTSTRAP],
    title="Loblaw Bio — Immune Cell Dashboard",
    suppress_callback_exceptions=True,
)
server = app.server


# ── UI helpers ────────────────────────────────────────────────────────────────

def kpi(label, value, sub=None, accent=False):
    return html.Div([
        html.P(label, style={
            "margin": 0, "fontSize": 10, "fontWeight": 700,
            "textTransform": "uppercase", "letterSpacing": ".08em",
            "color": TEAL if accent else MUTED,
        }),
        html.P(str(value), style={
            "margin": "2px 0 0", "fontSize": 24, "fontWeight": 700,
            "color": TEAL if accent else NAVY, "lineHeight": 1.1,
        }),
        html.P(sub, style={
            "margin": "2px 0 0", "fontSize": 11, "color": MUTED,
        }) if sub else None,
    ], style={
        "background": "white",
        "border": f"1px solid {BORDER}",
        "borderTop": f"3px solid {TEAL if accent else BORDER}",
        "borderRadius": 4,
        "padding": "14px 18px",
        "minWidth": 140,
    })


def section(title):
    return html.P(title, style={
        "fontSize": 10, "fontWeight": 700, "color": MUTED,
        "textTransform": "uppercase", "letterSpacing": ".08em",
        "margin": "0 0 12px",
    })


# ── Sidebar ───────────────────────────────────────────────────────────────────
sidebar = html.Div([
    html.Div([
        html.P("LOBLAW BIO", style={
            "fontSize": 10, "fontWeight": 700, "color": "#4A90A4",
            "letterSpacing": ".12em", "margin": "0 0 2px",
        }),
        html.P("Immune Cell Analysis", style={
            "fontSize": 14, "fontWeight": 600, "color": "white",
            "margin": 0, "lineHeight": 1.3,
        }),
        html.P("miraclib clinical trial", style={
            "fontSize": 11, "color": "#8BA5B8", "margin": "4px 0 0",
        }),
    ], style={"padding": "24px 20px 20px", "borderBottom": "1px solid #1E3448"}),

    html.Div([
        html.P("ANALYSIS", style={
            "fontSize": 9, "fontWeight": 700, "color": "#4A6478",
            "letterSpacing": ".1em", "margin": "20px 0 8px 20px",
        }),
        *[
            html.Div(
                html.Span(label, style={"fontSize": 13}),
                id=f"nav-{val}",
                n_clicks=0,
                style={
                    "padding": "10px 20px",
                    "cursor": "pointer",
                    "color": "#B0C4D8",
                    "borderLeft": "3px solid transparent",
                    "transition": "all .15s",
                },
            )
            for val, label in [
                ("freq",   "Frequency table"),
                ("stats",  "Statistical analysis"),
                ("subset", "Subset analysis"),
            ]
        ],
    ]),

    html.Div([
        html.P(f"{len(CELL_POPS)} populations · {N_SAMPLES:,} samples", style={
            "fontSize": 10, "color": "#4A6478", "margin": 0,
        }),
        html.P("PBMC + whole blood", style={
            "fontSize": 10, "color": "#4A6478", "margin": "2px 0 0",
        }),
    ], style={
        "padding": "20px", "borderTop": "1px solid #1E3448",
        "position": "absolute", "bottom": 0, "width": "100%",
    }),

], style={
    "width": 200, "minWidth": 200, "background": NAVY,
    "minHeight": "100vh", "position": "relative", "flexShrink": 0,
})


# ── Tab content ───────────────────────────────────────────────────────────────

def tab_frequency():
    display = freq_df.copy()
    display["population"] = display["population"].map(POP_LABELS)

    mean_pct = (
        freq_df.groupby("population")["percentage"]
        .mean().reindex(CELL_POPS).reset_index()
        .rename(columns={"percentage": "mean_pct"})
    )
    mean_pct["label"] = mean_pct["population"].map(POP_LABELS)

    fig = px.bar(
        mean_pct, x="label", y="mean_pct",
        color="label",
        color_discrete_sequence=["#4A90A4","#E07B54","#6BAE8E","#9B7EC8","#C4A35A"],
        labels={"label": "", "mean_pct": "Mean frequency (%)"},
        title="Mean relative frequency — all samples",
    )
    fig.update_layout(**PLOT_BASE, showlegend=False, height=280)
    fig.update_yaxes(gridcolor="#F0F0F0", ticksuffix="%", title_font_size=12)
    fig.update_xaxes(title_text="")

    return html.Div([
        html.H2("Frequency table", style={
            "fontSize": 18, "fontWeight": 700, "color": NAVY, "margin": "0 0 20px",
        }),

        dbc.Row([
            dbc.Col(kpi("Samples",     f"{N_SAMPLES:,}"),  md=3),
            dbc.Col(kpi("Subjects",    f"{N_SUBJECTS:,}"), md=3),
            dbc.Col(kpi("Populations", len(CELL_POPS)),    md=3),
            dbc.Col(kpi("Table rows",  f"{N_ROWS:,}"),     md=3),
        ], className="g-2 mb-4"),

        section("Relative frequency per sample"),
        dbc.Row([
            dbc.Col(dbc.Input(
                id="freq-search", placeholder="Search by sample ID…",
                debounce=True, size="sm",
                style={"fontSize": 13, "borderColor": BORDER},
            ), md=4),
            dbc.Col(dcc.Dropdown(
                id="pop-filter",
                options=[{"label": "All populations", "value": ""}]
                       + [{"label": POP_LABELS[p], "value": p} for p in CELL_POPS],
                value="", clearable=False,
                style={"fontSize": 13},
            ), md=3),
        ], className="mb-2"),

        dash_table.DataTable(
            id="freq-table",
            columns=[
                {"name": "Sample",        "id": "sample"},
                {"name": "Population",    "id": "population"},
                {"name": "Count",         "id": "count",
                 "type": "numeric", "format": dash_table.Format.Format(group=True)},
                {"name": "Total count",   "id": "total_count",
                 "type": "numeric", "format": dash_table.Format.Format(group=True)},
                {"name": "Frequency (%)", "id": "percentage", "type": "numeric"},
            ],
            data=display.head(200).to_dict("records"),
            page_size=15,
            sort_action="native",
            style_table={"overflowX": "auto", "border": f"1px solid {BORDER}",
                         "borderRadius": 4},
            style_header={"backgroundColor": BG, "fontWeight": "700",
                          "fontSize": 11, "color": MUTED,
                          "textTransform": "uppercase", "letterSpacing": ".05em",
                          "borderBottom": f"1px solid {BORDER}"},
            style_cell={"fontSize": 13, "padding": "8px 12px",
                        "borderBottom": f"1px solid {BG}", "color": TEXT},
            style_data_conditional=[
                {"if": {"row_index": "odd"}, "backgroundColor": "#FAFBFD"},
            ],
        ),
        html.P("Showing up to 200 rows. Use the filters above to narrow results.",
               style={"fontSize": 11, "color": MUTED, "marginTop": 6}),

        html.Hr(style={"borderColor": BORDER, "margin": "28px 0 20px"}),
        dcc.Graph(figure=fig, config={"displayModeBar": False}),
    ])


def tab_statistics():
    tbl = stats_df.copy()
    tbl["population"]  = tbl["population"].map(POP_LABELS)
    tbl["significant"] = tbl["significant"].map({True: "Yes", False: "No"})

    # Dynamic significant population — not hard-coded
    sig_pops  = stats_df[stats_df["significant"]]["population"].map(POP_LABELS).tolist()
    sig_label = ", ".join(sig_pops) if sig_pops else "none"
    sig_pval  = stats_df[stats_df["significant"]]["p_value"].min()

    fig_box = make_subplots(
        rows=1, cols=5,
        subplot_titles=[POP_LABELS[p] for p in CELL_POPS],
        horizontal_spacing=0.04,
    )
    shown = set()
    for i, pop in enumerate(CELL_POPS, 1):
        for resp, color, fill, name in [
            ("yes", TEAL, TEAL_LIGHT, "Responder"),
            ("no",  RED,  RED_LIGHT,  "Non-responder"),
        ]:
            vals = mmp_df[mmp_df["response"] == resp][f"{pop}_pct"].dropna().tolist()
            fig_box.add_trace(go.Box(
                y=vals, name=name, legendgroup=resp,
                showlegend=(resp not in shown),
                marker_color=color, line_color=color,
                fillcolor=fill, boxmean=False, line_width=1.5,
            ), row=1, col=i)
            shown.add(resp)

    fig_box.update_layout(
        **PLOT_BASE, height=400, boxmode="group",
        title_text="Relative frequency by response — melanoma PBMC (miraclib)",
        title_font_size=14,
        legend=dict(orientation="h", yanchor="top", y=-0.18,
                    xanchor="center", x=0.5, font_size=12),
    )
    for i in range(1, 6):
        fig_box.update_yaxes(gridcolor="#F0F0F0", ticksuffix="%",
                              tickfont_size=10, row=1, col=i)
    fig_box.update_annotations(font_size=11)

    return html.Div([
        html.H2("Statistical analysis", style={
            "fontSize": 18, "fontWeight": 700, "color": NAVY, "margin": "0 0 20px",
        }),

        dbc.Row([
            dbc.Col(kpi("Samples analysed", f"{TOTAL_MMP:,}"), md=3),
            dbc.Col(kpi("Responders", N_RESP,
                        f"{N_RESP/TOTAL_MMP*100:.1f}% of cohort"), md=3),
            dbc.Col(kpi("Non-responders", N_NRESP,
                        f"{N_NRESP/TOTAL_MMP*100:.1f}% of cohort"), md=3),
            dbc.Col(kpi("Significant", sig_label,
                        f"p = {sig_pval:.3f} · {len(sig_pops)} of {len(CELL_POPS)} populations",
                        accent=True), md=3),
        ], className="g-2 mb-4"),

        section("Mann-Whitney U test — two-sided, α = 0.05"),
        dash_table.DataTable(
            columns=[
                {"name": "Population",          "id": "population"},
                {"name": "Resp. median (%)",     "id": "responder_median_pct",     "type": "numeric"},
                {"name": "Non-resp. median (%)", "id": "non_responder_median_pct", "type": "numeric"},
                {"name": "Diff (%)",             "id": "median_diff_pct",          "type": "numeric"},
                {"name": "Higher in",            "id": "higher_in"},
                {"name": "U statistic",          "id": "mann_whitney_u",           "type": "numeric"},
                {"name": "p-value",              "id": "p_value",                  "type": "numeric"},
                {"name": "Sig.",                 "id": "significant"},
            ],
            data=tbl.to_dict("records"),
            style_table={"overflowX": "auto", "border": f"1px solid {BORDER}",
                         "borderRadius": 4},
            style_header={"backgroundColor": BG, "fontWeight": "700",
                          "fontSize": 11, "color": MUTED,
                          "textTransform": "uppercase", "letterSpacing": ".05em",
                          "borderBottom": f"1px solid {BORDER}"},
            style_cell={"fontSize": 13, "padding": "8px 12px",
                        "borderBottom": f"1px solid {BG}", "color": TEXT},
            style_data_conditional=[
                {"if": {"filter_query": '{significant} = "Yes"'},
                 "backgroundColor": "rgba(14,140,110,0.08)",
                 "color": "#0A6B53", "fontWeight": "600"},
                {"if": {"row_index": "odd"}, "backgroundColor": "#FAFBFD"},
            ],
        ),

        html.Div(style={"height": 24}),
        dcc.Graph(figure=fig_box, config={"displayModeBar": False}),

        html.Div([
            html.Span("Finding — ", style={"fontWeight": 700, "color": NAVY}),
            (
                f"{sig_label} showed a statistically significant frequency difference "
                f"between miraclib responders and non-responders (p = {sig_pval:.3f}). "
                f"Responders had a higher median frequency in this population, "
                f"suggesting it may warrant further investigation as a candidate "
                f"predictive biomarker for treatment response."
            ) if sig_pops else (
                "No cell population showed a statistically significant frequency "
                "difference between responders and non-responders at α = 0.05."
            ),
        ], style={
            "background": "rgba(14,140,110,0.06)",
            "border": "1px solid rgba(14,140,110,0.25)",
            "borderLeft": f"3px solid {TEAL}",
            "borderRadius": 4, "padding": "14px 18px",
            "fontSize": 13, "lineHeight": 1.75, "color": TEXT, "marginTop": 8,
        }),
    ])


def tab_subset():
    fig_proj = px.bar(
        pd.DataFrame(list(summary["samples_per_project"].items()),
                     columns=["Project", "Samples"]),
        x="Project", y="Samples", color="Project",
        color_discrete_sequence=["#4A90A4", "#0E8C6E"],
        title="Samples per project",
    )
    fig_proj.update_layout(**PLOT_BASE, showlegend=False, height=240)
    fig_proj.update_yaxes(gridcolor="#F0F0F0")

    fig_resp = px.bar(
        pd.DataFrame([
            {"Group": "Responders",     "Count": summary["response_counts"].get("yes", 0)},
            {"Group": "Non-responders", "Count": summary["response_counts"].get("no",  0)},
        ]),
        x="Group", y="Count", color="Group",
        color_discrete_map={"Responders": TEAL, "Non-responders": RED},
        title="Response (unique subjects)",
    )
    fig_resp.update_layout(**PLOT_BASE, showlegend=False, height=240)
    fig_resp.update_yaxes(gridcolor="#F0F0F0")

    fig_sex = px.bar(
        pd.DataFrame([
            {"Group": "Male",   "Count": summary["sex_counts"].get("M", 0)},
            {"Group": "Female", "Count": summary["sex_counts"].get("F", 0)},
        ]),
        x="Group", y="Count", color="Group",
        color_discrete_map={"Male": "#6C63CC", "Female": "#C4A35A"},
        title="Sex (unique subjects)",
    )
    fig_sex.update_layout(**PLOT_BASE, showlegend=False, height=240)
    fig_sex.update_yaxes(gridcolor="#F0F0F0")

    return html.Div([
        html.H2("Subset analysis", style={
            "fontSize": 18, "fontWeight": 700, "color": NAVY, "margin": "0 0 8px",
        }),
        html.Span(
            "melanoma · PBMC · time from treatment start = 0 · miraclib",
            style={
                "fontSize": 11, "color": MUTED, "background": BG,
                "padding": "3px 12px", "borderRadius": 99,
                "border": f"1px solid {BORDER}",
                "display": "inline-block", "marginBottom": 20,
            },
        ),

        dbc.Row([
            dbc.Col(kpi("Baseline samples", summary["total_samples"]), md=3),
            dbc.Col(kpi("Projects",
                        len(summary["samples_per_project"]),
                        " · ".join(summary["samples_per_project"].keys())), md=3),
            dbc.Col(kpi("Responders",
                        summary["response_counts"].get("yes", 0),
                        "unique subjects"), md=3),
            dbc.Col(kpi("Non-responders",
                        summary["response_counts"].get("no", 0),
                        "unique subjects"), md=3),
        ], className="g-2 mb-4"),

        dbc.Row([
            dbc.Col(dcc.Graph(figure=fig_proj, config={"displayModeBar": False}), md=4),
            dbc.Col(dcc.Graph(figure=fig_resp, config={"displayModeBar": False}), md=4),
            dbc.Col(dcc.Graph(figure=fig_sex,  config={"displayModeBar": False}), md=4),
        ], className="g-2 mb-2"),

        html.Hr(style={"borderColor": BORDER, "margin": "24px 0 20px"}),
        section("Key result"),

        dbc.Row([
            dbc.Col(html.Div([
                html.P("Mean B cell count", style={
                    "fontSize": 10, "fontWeight": 700, "color": TEAL,
                    "textTransform": "uppercase", "letterSpacing": ".08em",
                    "margin": "0 0 4px",
                }),
                html.P(f"{summary['avg_bcell_male_responders']:,.2f}", style={
                    "fontSize": 32, "fontWeight": 700, "color": NAVY,
                    "margin": 0, "lineHeight": 1,
                }),
                html.P("cells per PBMC sample", style={
                    "fontSize": 11, "color": MUTED, "margin": "4px 0 0",
                }),
                html.Hr(style={"borderColor": BORDER, "margin": "12px 0"}),
                html.P("male · responder · melanoma · miraclib · t = 0",
                       style={"fontSize": 11, "color": MUTED, "margin": 0}),
            ], style={
                "background": "white", "border": f"1px solid {BORDER}",
                "borderTop": f"3px solid {TEAL}",
                "borderRadius": 4, "padding": "18px 20px",
            }), md=4),

            dbc.Col(html.P(
                f"Mean B cell count among male melanoma patients who responded to "
                f"miraclib at baseline (t = 0): "
                f"{summary['avg_bcell_male_responders']:,.2f} cells per PBMC sample. "
                f"Data from {' and '.join(summary['samples_per_project'].keys())}.",
                style={"fontSize": 13, "color": TEXT, "lineHeight": 1.8,
                       "paddingTop": 8},
            ), md=8),
        ]),
    ])


# ── Layout ────────────────────────────────────────────────────────────────────
app.layout = html.Div([
    sidebar,
    html.Div([
        html.Div(id="page-content",
                 style={"padding": "32px 36px", "maxWidth": 1100}),
    ], style={"flex": 1, "background": BG, "overflowY": "auto"}),
    dcc.Store(id="current-tab", data="freq"),
], style={"display": "flex", "minHeight": "100vh"})


# ── Callbacks ─────────────────────────────────────────────────────────────────

@app.callback(
    Output("page-content", "children"),
    Output("current-tab", "data"),
    Input("nav-freq",   "n_clicks"),
    Input("nav-stats",  "n_clicks"),
    Input("nav-subset", "n_clicks"),
    prevent_initial_call=False,
)
def navigate(c1, c2, c3):
    from dash import ctx
    tab = ctx.triggered_id.replace("nav-", "") if ctx.triggered_id else "freq"
    pages = {"freq": tab_frequency, "stats": tab_statistics, "subset": tab_subset}
    return pages.get(tab, tab_frequency)(), tab


@app.callback(
    Output("freq-table", "data"),
    Input("freq-search", "value"),
    Input("pop-filter",  "value"),
)
def filter_table(search, pop):
    df = freq_df.copy()
    df["population"] = df["population"].map(POP_LABELS)
    if search:
        df = df[df["sample"].str.contains(search, case=False, na=False)]
    if pop:
        df = df[df["population"] == POP_LABELS.get(pop, pop)]
    return df.head(200).to_dict("records")


# ── CSS ───────────────────────────────────────────────────────────────────────
_CSS = f"""
body {{ margin: 0; background: {BG}; }}

#nav-freq, #nav-stats, #nav-subset {{
    padding: 10px 20px;
    cursor: pointer;
    color: #8BA5B8;
    border-left: 3px solid transparent;
    font-size: 13px;
    transition: all .15s;
}}
#nav-freq:hover, #nav-stats:hover, #nav-subset:hover {{
    background: {NAVY_LIGHT};
    color: white;
}}

.Select-control {{ border-color: {BORDER} !important; border-radius: 4px !important; }}
.Select-control:hover {{ border-color: #4A90A4 !important; }}
"""

_assets = os.path.join(os.path.dirname(os.path.abspath(__file__)), "assets")
os.makedirs(_assets, exist_ok=True)
with open(os.path.join(_assets, "custom.css"), "w", encoding="utf-8") as _f:
    _f.write(_CSS)


if __name__ == "__main__":
    app.run(debug=False, host="0.0.0.0", port=8050)