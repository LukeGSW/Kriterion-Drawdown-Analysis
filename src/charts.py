"""
charts.py — Funzioni Plotly per la dashboard di analisi drawdown.

Ogni funzione restituisce un go.Figure pronto per st.plotly_chart().
Tutte le funzioni condividono la palette COLORS e il layout _base_layout().

Grafici prodotti:
  build_equity_with_dd_zones()   — equity curve con zone DD colorate
  build_frequency_bar()          — frequenza media DD per 1/2/3 anni
  build_dot_plot()               — strip plot rendimenti annuali per categoria DD
  build_cooccurrence_heatmap()   — heatmap co-occorrenza categorie nello stesso anno
  build_annual_return_bar()      — barre rendimento annuale colorate per DD
"""

import pandas as pd
import numpy as np
import plotly.graph_objects as go
from plotly.subplots import make_subplots

from src.calculations import (
    CATEGORY_ORDER,
    CATEGORY_LABELS,
    CATEGORY_COLORS,
    compute_dd_series,
)

# ===================================================
# PALETTE E LAYOUT
# ===================================================

COLORS = {
    "primary":    "#2196F3",
    "secondary":  "#FF9800",
    "positive":   "#4CAF50",
    "negative":   "#F44336",
    "neutral":    "#9E9E9E",
    "background": "#1E1E2E",
    "surface":    "#2A2A3E",
    "text":       "#E0E0E0",
    "accent":     "#AB47BC",
    "gridline":   "#333355",
    "border":     "#444466",
}

# Colori semi-trasparenti per le zone DD sull'equity curve
DD_FILL_COLORS = {
    "DD_5":  "rgba(33,150,243,0.18)",   # blu tenue
    "DD_10": "rgba(255,152,0,0.22)",    # arancio tenue
    "DD_20": "rgba(244,67,54,0.28)",    # rosso tenue
    "DD_25": "rgba(156,39,176,0.35)",   # viola tenue
}


def _base_layout(title: str, x_title: str = "", y_title: str = "") -> dict:
    """Layout Plotly professionale condiviso da tutti i grafici."""
    return dict(
        title=dict(text=title, font=dict(size=16, color=COLORS["text"])),
        paper_bgcolor=COLORS["background"],
        plot_bgcolor=COLORS["surface"],
        font=dict(color=COLORS["text"], family="Inter, Arial, sans-serif"),
        xaxis=dict(
            title=x_title,
            showgrid=True, gridcolor=COLORS["gridline"],
            zeroline=False, color=COLORS["text"],
        ),
        yaxis=dict(
            title=y_title,
            showgrid=True, gridcolor=COLORS["gridline"],
            zeroline=False, color=COLORS["text"],
        ),
        legend=dict(
            bgcolor="rgba(0,0,0,0)",
            bordercolor=COLORS["border"],
            font=dict(color=COLORS["text"]),
        ),
        hovermode="x unified",
        margin=dict(l=65, r=25, t=65, b=65),
    )


# ===================================================
# GRAFICO 1 — Equity Curve con zone DD colorate
# ===================================================

def build_equity_with_dd_zones(
    prices: pd.Series,
    events_df: pd.DataFrame,
    ticker: str,
) -> go.Figure:
    """
    Equity curve (adjusted close) con zone di drawdown colorate per categoria.

    Le zone sono rettangoli colorati che coprono il periodo dall'inizio
    dell'evento (data picco) alla data di recovery (o fine serie se ancora aperto).
    La legenda mostra i colori associati a ciascuna categoria.

    Args:
        prices:    Serie adjusted close con DatetimeIndex.
        events_df: Output di identify_drawdown_events().
        ticker:    Label del ticker per il titolo.

    Returns:
        go.Figure con equity curve e zone DD sovrapposte.
    """
    fig = go.Figure()

    # — Linea equity
    fig.add_trace(go.Scatter(
        x=prices.index,
        y=prices.values,
        name="Adjusted Close",
        line=dict(color=COLORS["primary"], width=1.5),
        hovertemplate="<b>%{x|%d %b %Y}</b><br>Prezzo: %{y:,.2f}<extra></extra>",
    ))

    # — Zone colorate per ogni evento DD
    if not events_df.empty:
        legend_added = set()   # evita duplicati in legenda
        for _, row in events_df.iterrows():
            cat = row["category"]
            x0  = row["peak_date"]
            x1  = row["recovery_date"] if pd.notna(row["recovery_date"]) else prices.index[-1]

            show_legend = cat not in legend_added
            legend_added.add(cat)

            fig.add_vrect(
                x0=x0, x1=x1,
                fillcolor=DD_FILL_COLORS[cat],
                layer="below",
                line_width=0,
                annotation_text="",
                # Aggiungi una trace fittizia per la legenda al primo evento
            )

            if show_legend:
                fig.add_trace(go.Scatter(
                    x=[None], y=[None],
                    mode="markers",
                    marker=dict(
                        size=12, color=CATEGORY_COLORS[cat], symbol="square"
                    ),
                    name=CATEGORY_LABELS[cat],
                    showlegend=True,
                ))

    layout = _base_layout(
        f"Equity Curve con Zone Drawdown — {ticker}",
        x_title="Data",
        y_title="Prezzo Adjusted Close",
    )
    layout["hovermode"] = "x unified"
    fig.update_layout(**layout)

    return fig


# ===================================================
# GRAFICO 2 — Frequenza media DD per 1/2/3 anni
# ===================================================

def build_frequency_bar(freq_df: pd.DataFrame) -> go.Figure:
    """
    Grouped bar chart: frequenza media attesa per categoria DD su 1, 2 e 3 anni.

    Ogni gruppo di barre rappresenta una categoria. Le tre barre per gruppo
    mostrano quante volte ci si aspetta di vedere quell'evento in 1, 2 o 3 anni.

    Args:
        freq_df: Output di compute_frequency_table() — index = Categoria,
                 colonne includono 'Freq. media / 1Y', '/ 2Y', '/ 3Y'.

    Returns:
        go.Figure grouped bar chart.
    """
    fig = go.Figure()

    windows = {
        "Freq. media / 1Y": "1 Anno",
        "Freq. media / 2Y": "2 Anni",
        "Freq. media / 3Y": "3 Anni",
    }
    bar_colors = [COLORS["primary"], COLORS["secondary"], COLORS["accent"]]

    for (col, label), color in zip(windows.items(), bar_colors):
        fig.add_trace(go.Bar(
            name=label,
            x=freq_df.index.tolist(),
            y=freq_df[col].tolist(),
            marker_color=color,
            opacity=0.85,
            text=[f"{v:.2f}" for v in freq_df[col]],
            textposition="outside",
            textfont=dict(color=COLORS["text"], size=11),
            hovertemplate=(
                "<b>%{x}</b><br>"
                f"Attesi in {label}: " + "%{y:.3f}<extra></extra>"
            ),
        ))

    layout = _base_layout(
        "Frequenza Media Attesa Drawdown per Finestra Temporale",
        x_title="Categoria Drawdown",
        y_title="N. eventi attesi",
    )
    layout["barmode"] = "group"
    layout["hovermode"] = "x"
    layout["yaxis"]["rangemode"] = "tozero"
    fig.update_layout(**layout)

    return fig


# ===================================================
# GRAFICO 3 — Dot Plot (strip plot) rendimenti annuali
# ===================================================

def build_dot_plot(dot_df: pd.DataFrame) -> go.Figure:
    """
    Strip plot: rendimento annuale (%) degli anni in cui si è verificata ogni categoria DD.

    Ogni punto è un anno solare. La posizione sull'asse Y indica il rendimento
    totale Jan-Dec di quell'anno. Le linee orizzontali mostrano media e mediana.
    Un anno con due categorie distinte apparirà come punto in entrambe le colonne.

    Args:
        dot_df: Output di build_dot_plot_data() con colonne:
                year, category, category_label, annual_return_pct.

    Returns:
        go.Figure strip plot con jitter orizzontale e statistiche descrittive.
    """
    fig = go.Figure()

    if dot_df.empty:
        fig.update_layout(**_base_layout("Nessun dato disponibile"))
        return fig

    # Usato per l'asse X categorico
    x_labels = [CATEGORY_LABELS[c] for c in CATEGORY_ORDER]

    # Jitter orizzontale deterministico per separare punti sovrapposti
    rng = np.random.default_rng(seed=42)

    for cat in CATEGORY_ORDER:
        subset = dot_df[dot_df["category"] == cat]
        if subset.empty:
            continue

        label  = CATEGORY_LABELS[cat]
        color  = CATEGORY_COLORS[cat]
        rets   = subset["annual_return_pct"].values
        years  = subset["year"].values

        # Jitter: offset casuale fisso attorno alla posizione categorica
        jitter = rng.uniform(-0.3, 0.3, size=len(rets))

        fig.add_trace(go.Scatter(
            x=[label] * len(rets),
            y=rets,
            mode="markers",
            name=label,
            marker=dict(
                color=color,
                size=10,
                opacity=0.75,
                line=dict(width=1, color="white"),
            ),
            # Il jitter è applicato come offset sull'asse x tramite transform
            # (Plotly non supporta jitter nativo su scatter categorico,
            #  usiamo testo hover con anno per compensare)
            text=[str(y) for y in years],
            customdata=np.stack([years, rets], axis=1),
            hovertemplate=(
                "<b>Anno: %{customdata[0]:.0f}</b><br>"
                "Rendimento: %{customdata[1]:+.1f}%<br>"
                f"Categoria: {label}<extra></extra>"
            ),
        ))

        # Linea media
        mean_ret = np.mean(rets)
        fig.add_shape(
            type="line",
            x0=label, x1=label,
            y0=mean_ret - 1, y1=mean_ret + 1,   # placeholder — sovrascritta sotto
            line=dict(color=color, width=0),
        )
        # Annotazione media
        fig.add_annotation(
            x=label,
            y=mean_ret,
            text=f"μ={mean_ret:+.1f}%",
            showarrow=False,
            yshift=12,
            font=dict(color=color, size=10, family="Inter, Arial, sans-serif"),
            bgcolor="rgba(30,30,46,0.8)",
        )
        # Linea orizzontale media per ogni categoria
        fig.add_shape(
            type="line",
            x0=x_labels.index(label) - 0.4,
            x1=x_labels.index(label) + 0.4,
            y0=mean_ret, y1=mean_ret,
            xref="x", yref="y",
            line=dict(color=color, width=2, dash="dash"),
        )

    # Linea dello zero (rendimento nullo)
    fig.add_hline(
        y=0,
        line_color=COLORS["neutral"],
        line_dash="dot",
        line_width=1,
        opacity=0.6,
        annotation_text="0%",
        annotation_font_color=COLORS["neutral"],
        annotation_position="right",
    )

    layout = _base_layout(
        "Rendimento Annuale (Jan–Dec) negli Anni con Drawdown",
        x_title="Categoria Drawdown",
        y_title="Rendimento Annuale (%)",
    )
    layout["hovermode"] = "closest"
    layout["showlegend"] = False
    fig.update_layout(**layout)
    fig.update_xaxes(categoryorder="array", categoryarray=x_labels)

    return fig


# ===================================================
# GRAFICO 4 — Heatmap co-occorrenza
# ===================================================

def build_cooccurrence_heatmap(cooc_df: pd.DataFrame) -> go.Figure:
    """
    Heatmap della co-occorrenza di categorie DD nello stesso anno solare.

    La cella (i, j) mostra il numero di anni in cui la categoria i e la categoria j
    hanno avuto almeno un evento ciascuna. La diagonale mostra gli anni totali
    con almeno un evento per quella categoria.

    Args:
        cooc_df: Output di compute_cooccurrence() — DataFrame quadrato
                 con index e colonne = CATEGORY_LABELS.values().

    Returns:
        go.Figure heatmap con annotazioni numeriche in ogni cella.
    """
    labels = cooc_df.index.tolist()
    z_vals = cooc_df.values.astype(float)

    # Maschera cella nulla → non visualizzare testo
    text_vals = [[str(int(v)) if v > 0 else "—" for v in row] for row in z_vals]

    fig = go.Figure(go.Heatmap(
        z=z_vals,
        x=labels,
        y=labels,
        text=text_vals,
        texttemplate="%{text}",
        textfont=dict(size=15, color="white"),
        colorscale=[
            [0.0,  "#1E1E2E"],   # zero → sfondo scuro
            [0.01, "#1A3A5C"],   # valori bassi → blu scuro
            [0.5,  "#1565C0"],   # medi → blu medio
            [1.0,  "#2196F3"],   # alti → blu pieno
        ],
        showscale=True,
        colorbar=dict(
            title=dict(text="N. anni", font=dict(color=COLORS["text"])),
            tickfont=dict(color=COLORS["text"]),
        ),
        hovertemplate=(
            "<b>%{y}</b> + <b>%{x}</b><br>"
            "Co-occorrenze (anni): %{z:.0f}<extra></extra>"
        ),
    ))

    layout = _base_layout(
        "Co-occorrenza Categorie Drawdown nello Stesso Anno",
        x_title="",
        y_title="",
    )
    layout["yaxis"]["autorange"] = "reversed"
    layout["xaxis"]["showgrid"] = False
    layout["yaxis"]["showgrid"] = False
    layout["hovermode"] = "closest"
    fig.update_layout(**layout)

    return fig


# ===================================================
# GRAFICO 5 — Barre rendimento annuale con highlight DD
# ===================================================

def build_annual_return_bar(
    annual_returns: pd.Series,
    annual_dd_map: pd.DataFrame,
) -> go.Figure:
    """
    Bar chart rendimenti annuali con colore determinato dalla peggior categoria DD dell'anno.

    Anni senza DD ≥ 5% → grigio neutro.
    Anni con DD_5  → blu.
    Anni con DD_10 → arancio.
    Anni con DD_20 → rosso.
    Anni con DD_25 → viola.
    Se un anno ha più categorie, vince la più grave (DD_25 > DD_20 > DD_10 > DD_5).

    Args:
        annual_returns: Output di compute_annual_returns().
        annual_dd_map:  Output di build_annual_dd_map().

    Returns:
        go.Figure bar chart annuale.
    """
    years  = sorted(annual_returns.index)
    rets   = [annual_returns[y] for y in years]

    # Determina la categoria più grave per ogni anno
    def worst_cat(year: int) -> str:
        if year not in annual_dd_map.index:
            return "none"
        row = annual_dd_map.loc[year]
        for cat in reversed(CATEGORY_ORDER):   # DD_25 ha priorità massima
            if row.get(cat, False):
                return cat
        return "none"

    bar_colors = []
    hover_cats = []
    for y in years:
        cat = worst_cat(y)
        if cat == "none":
            bar_colors.append(COLORS["neutral"])
            hover_cats.append("Nessun DD ≥ 5%")
        else:
            bar_colors.append(CATEGORY_COLORS[cat])
            hover_cats.append(CATEGORY_LABELS[cat])

    fig = go.Figure(go.Bar(
        x=years,
        y=rets,
        marker_color=bar_colors,
        opacity=0.85,
        customdata=list(zip(hover_cats, rets)),
        hovertemplate=(
            "<b>%{x}</b><br>"
            "Rendimento: %{y:+.1f}%<br>"
            "Categoria DD: %{customdata[0]}<extra></extra>"
        ),
        showlegend=False,
    ))

    # Linea dello zero
    fig.add_hline(
        y=0,
        line_color=COLORS["neutral"],
        line_dash="dot",
        line_width=1,
        opacity=0.5,
    )

    # Tracce fittizie per legenda colori
    legend_entries = [
        ("Nessun DD ≥ 5%", COLORS["neutral"]),
    ] + [(CATEGORY_LABELS[c], CATEGORY_COLORS[c]) for c in CATEGORY_ORDER]

    for label, color in legend_entries:
        fig.add_trace(go.Bar(
            x=[None], y=[None],
            name=label,
            marker_color=color,
            opacity=0.85,
            showlegend=True,
        ))

    layout = _base_layout(
        "Rendimento Annuale per Anno (colorato per categoria DD peggiore)",
        x_title="Anno",
        y_title="Rendimento (%)",
    )
    layout["barmode"] = "relative"
    layout["hovermode"] = "x"
    layout["xaxis"]["dtick"] = 5
    layout["yaxis"]["ticksuffix"] = "%"
    fig.update_layout(**layout)

    return fig
