"""
calculations.py — Logica quantitativa per l'analisi dei drawdown.

Contiene:
  - identify_drawdown_events(): identifica episodi discreti di drawdown
  - build_annual_dd_map():      mappa anno → categorie DD presenti
  - compute_frequency_table():  frequenza media per 1/2/3 anni
  - compute_cooccurrence():     matrice di co-occorrenza per anno
  - compute_annual_returns():   rendimento solare Jan-Dec per ogni anno
  - compute_dd_series():        serie continua di drawdown dal picco

Categorie drawdown (mutualmente esclusive, basate sul punto più basso):
  DD_5  → massimo calo ≥ 5%  e < 10%
  DD_10 → massimo calo ≥ 10% e < 20%
  DD_20 → massimo calo ≥ 20% e < 25%
  DD_25 → massimo calo ≥ 25%
"""

import pandas as pd
import numpy as np
from typing import Optional

# ===================================================
# COSTANTI — soglie e label categorie
# ===================================================

THRESHOLDS = {
    "DD_5":  (-0.10, -0.05),   # [low_bound, high_bound) — entrambi negativi
    "DD_10": (-0.20, -0.10),
    "DD_20": (-0.25, -0.20),
    "DD_25": (-1.00, -0.25),   # lower bound arbitrario, copre tutto il resto
}

CATEGORY_ORDER = ["DD_5", "DD_10", "DD_20", "DD_25"]

CATEGORY_LABELS = {
    "DD_5":  "DD 5–10%",
    "DD_10": "DD 10–20%",
    "DD_20": "DD 20–25%",
    "DD_25": "DD > 25%",
}

# Colori di ogni categoria per i grafici
CATEGORY_COLORS = {
    "DD_5":  "#2196F3",   # blu   — moderato
    "DD_10": "#FF9800",   # arancio — rilevante
    "DD_20": "#F44336",   # rosso — severo
    "DD_25": "#9C27B0",   # viola — estremo
}


# ===================================================
# FUNZIONI CORE
# ===================================================

def classify_dd(dd_pct: float) -> Optional[str]:
    """
    Classifica un drawdown percentuale nella categoria mutualmente esclusiva.

    Args:
        dd_pct: Valore del drawdown in formato decimale (es. -0.12 per -12%).
                Deve essere negativo o zero.

    Returns:
        Stringa categoria ('DD_5', 'DD_10', 'DD_20', 'DD_25') oppure None
        se il calo è inferiore al 5%.
    """
    if dd_pct <= -0.25:
        return "DD_25"
    elif dd_pct <= -0.20:
        return "DD_20"
    elif dd_pct <= -0.10:
        return "DD_10"
    elif dd_pct <= -0.05:
        return "DD_5"
    return None


def compute_dd_series(prices: pd.Series) -> pd.Series:
    """
    Calcola la serie continua di drawdown dal massimo storico progressivo.

    Il drawdown in ogni giorno t è: (P_t - max(P_0..P_t)) / max(P_0..P_t)
    Il valore è sempre ≤ 0; 0 significa che il prezzo è al suo massimo storico.

    Args:
        prices: Serie di prezzi adjusted close con DatetimeIndex.

    Returns:
        pd.Series con stessi indici di prices, valori in formato decimale.
    """
    running_peak = prices.cummax()
    return (prices - running_peak) / running_peak


def identify_drawdown_events(prices: pd.Series) -> pd.DataFrame:
    """
    Identifica tutti gli episodi discreti di drawdown ≥ 5% dal picco.

    Algoritmo:
      1. Traccia il picco corrente aggiornato in rolling.
      2. Quando il prezzo scende ≥ 5% dal picco, inizia un evento.
      3. L'evento termina quando il prezzo recupera il picco precedente.
      4. Ogni evento viene classificato nella categoria corrispondente al
         suo punto più basso (mutuamente esclusiva).
      5. Gli eventi ancora aperti alla fine della serie vengono registrati
         con recovery_date = NaT.

    Args:
        prices: Serie adjusted close, DatetimeIndex, frequenza giornaliera.

    Returns:
        DataFrame con colonne:
          peak_date      — data del picco che precede l'evento
          bottom_date    — data del punto più basso dell'evento
          recovery_date  — data di recupero del picco (NaT se ancora aperto)
          max_dd_pct     — profondità massima (%) con segno negativo
          category       — stringa categoria ('DD_5' … 'DD_25')
          bottom_year    — anno solare del punto più basso
    """
    events = []

    peak_price = prices.iloc[0]
    peak_date  = prices.index[0]
    in_dd      = False

    # Variabili stato evento corrente
    dd_start_date   = None
    dd_bottom_price = None
    dd_bottom_date  = None
    dd_max_decimal  = 0.0   # valore più negativo raggiunto (es. -0.18)

    for date, price in prices.items():
        current_dd = (price - peak_price) / peak_price

        if not in_dd:
            if current_dd <= -0.05:
                # Inizia un nuovo evento di drawdown
                in_dd           = True
                dd_start_date   = peak_date
                dd_bottom_price = price
                dd_bottom_date  = date
                dd_max_decimal  = current_dd
            elif price > peak_price:
                # Nuovo massimo storico, aggiorna il picco
                peak_price = price
                peak_date  = date
        else:
            # Siamo in drawdown
            if current_dd < dd_max_decimal:
                # Nuovo minimo dell'evento
                dd_max_decimal  = current_dd
                dd_bottom_price = price
                dd_bottom_date  = date

            if price >= peak_price:
                # Recupero completo: evento concluso
                cat = classify_dd(dd_max_decimal)
                if cat:
                    events.append({
                        "peak_date":     dd_start_date,
                        "bottom_date":   dd_bottom_date,
                        "recovery_date": date,
                        "max_dd_pct":    dd_max_decimal * 100,
                        "category":      cat,
                        "bottom_year":   dd_bottom_date.year,
                    })
                # Ricomincia dal nuovo picco
                in_dd      = False
                peak_price = price
                peak_date  = date

    # Evento ancora aperto a fine serie
    if in_dd:
        cat = classify_dd(dd_max_decimal)
        if cat:
            events.append({
                "peak_date":     dd_start_date,
                "bottom_date":   dd_bottom_date,
                "recovery_date": pd.NaT,
                "max_dd_pct":    dd_max_decimal * 100,
                "category":      cat,
                "bottom_year":   dd_bottom_date.year,
            })

    if not events:
        return pd.DataFrame()

    df = pd.DataFrame(events)
    df["peak_date"]     = pd.to_datetime(df["peak_date"])
    df["bottom_date"]   = pd.to_datetime(df["bottom_date"])
    df["recovery_date"] = pd.to_datetime(df["recovery_date"])
    return df


def compute_annual_returns(prices: pd.Series) -> pd.Series:
    """
    Calcola il rendimento percentuale solare (Jan–Dec) per ogni anno.

    Usa il primo e l'ultimo adjusted close disponibile nell'anno solare.
    Anni con un solo giorno di dati vengono esclusi.

    Args:
        prices: Serie adjusted close con DatetimeIndex.

    Returns:
        pd.Series indicizzata per anno (int), valori = rendimento % Jan-Dec.
    """
    annual = {}
    for year, group in prices.groupby(prices.index.year):
        if len(group) < 2:
            continue
        ret = (group.iloc[-1] / group.iloc[0] - 1) * 100
        annual[year] = ret
    return pd.Series(annual, name="annual_return_pct")


def build_annual_dd_map(events_df: pd.DataFrame, all_years: pd.Index) -> pd.DataFrame:
    """
    Per ogni anno solare, determina quali categorie DD sono presenti.

    Un anno ha la categoria X se almeno un evento di categoria X ha il suo
    bottom_date (punto più basso) all'interno di quell'anno solare.

    Args:
        events_df:  Output di identify_drawdown_events().
        all_years:  Tutti gli anni disponibili nella serie storica.

    Returns:
        DataFrame con index = anno (int) e colonne booleane DD_5/DD_10/DD_20/DD_25.
    """
    records = []
    for year in sorted(all_years):
        year_events = events_df[events_df["bottom_year"] == year] if not events_df.empty else pd.DataFrame()
        row = {"year": year}
        for cat in CATEGORY_ORDER:
            row[cat] = (year_events["category"] == cat).any() if not year_events.empty else False
        records.append(row)

    result = pd.DataFrame(records).set_index("year")
    return result


def compute_frequency_table(events_df: pd.DataFrame, total_years: float) -> pd.DataFrame:
    """
    Calcola la frequenza media di ogni categoria DD per finestre di 1, 2 e 3 anni.

    La frequenza è espressa come numero atteso di eventi nella finestra temporale:
      freq_Ny = (n_eventi / anni_totali) × N

    Args:
        events_df:   Output di identify_drawdown_events().
        total_years: Numero totale di anni coperti dalla serie storica.

    Returns:
        DataFrame con righe = categorie, colonne = conteggio totale e frequenze.
    """
    rows = []
    for cat in CATEGORY_ORDER:
        if events_df.empty:
            count = 0
        else:
            count = (events_df["category"] == cat).sum()

        base_freq = count / total_years if total_years > 0 else 0.0
        rows.append({
            "Categoria":          CATEGORY_LABELS[cat],
            "N. eventi totali":   int(count),
            "Freq. media / 1Y":   round(base_freq, 3),
            "Freq. media / 2Y":   round(base_freq * 2, 3),
            "Freq. media / 3Y":   round(base_freq * 3, 3),
        })

    return pd.DataFrame(rows).set_index("Categoria")


def compute_cooccurrence(annual_dd_map: pd.DataFrame) -> pd.DataFrame:
    """
    Calcola la matrice di co-occorrenza tra categorie DD nello stesso anno solare.

    La cella [i, j] contiene il numero di anni in cui la categoria i e la
    categoria j si sono verificate entrambe (almeno un evento ciascuna).
    La diagonale [i, i] contiene il numero totale di anni con almeno
    un evento della categoria i.

    Args:
        annual_dd_map: Output di build_annual_dd_map().

    Returns:
        DataFrame quadrato con index e colonne = CATEGORY_LABELS.
    """
    labels = [CATEGORY_LABELS[c] for c in CATEGORY_ORDER]
    matrix = pd.DataFrame(0, index=labels, columns=labels)

    for cat_i in CATEGORY_ORDER:
        for cat_j in CATEGORY_ORDER:
            if cat_i not in annual_dd_map.columns or cat_j not in annual_dd_map.columns:
                continue
            both = (annual_dd_map[cat_i] & annual_dd_map[cat_j]).sum()
            matrix.loc[CATEGORY_LABELS[cat_i], CATEGORY_LABELS[cat_j]] = int(both)

    return matrix


def build_dot_plot_data(events_df: pd.DataFrame, annual_returns: pd.Series) -> pd.DataFrame:
    """
    Costruisce il DataFrame per il dot plot: anno, categoria DD, rendimento annuale.

    Ogni riga rappresenta un anno che ha avuto almeno un evento di quella categoria.
    Un anno può comparire in più righe se ha avuto eventi di categorie diverse.

    Args:
        events_df:      Output di identify_drawdown_events().
        annual_returns: Output di compute_annual_returns().

    Returns:
        DataFrame con colonne: year, category, category_label, annual_return_pct.
    """
    if events_df.empty:
        return pd.DataFrame()

    rows = []
    for cat in CATEGORY_ORDER:
        cat_events = events_df[events_df["category"] == cat]
        years_with_cat = cat_events["bottom_year"].unique()
        for year in years_with_cat:
            if year in annual_returns.index:
                rows.append({
                    "year":             year,
                    "category":         cat,
                    "category_label":   CATEGORY_LABELS[cat],
                    "annual_return_pct": annual_returns[year],
                })

    return pd.DataFrame(rows) if rows else pd.DataFrame()
