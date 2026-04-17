"""
app.py — Dashboard Analisi Drawdown | Kriterion Quant

Entry point Streamlit. Struttura:
  1. Configurazione pagina e API key
  2. Sidebar: ticker input + info storico
  3. Fetch dati e calcoli
  4. Sezione A: Equity Curve con zone DD
  5. Sezione B: Tabella frequenza + bar chart frequenze
  6. Sezione C: Dot plot rendimenti annuali per categoria DD
  7. Sezione D: Bar chart rendimenti annuali colorati per DD
  8. Sezione E: Heatmap co-occorrenza

Nota: le categorie DD sono mutualmente esclusive e classificate sul bottom dell'evento.
"""

import streamlit as st
import pandas as pd
import numpy as np
from datetime import datetime

# ===================================================
# CONFIGURAZIONE PAGINA (deve essere il primo comando Streamlit)
# ===================================================
st.set_page_config(
    page_title="Drawdown Analysis | Kriterion Quant",
    page_icon="📉",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ===================================================
# IMPORT MODULI INTERNI
# ===================================================
from src.data_fetcher import fetch_ohlcv, validate_ticker_format
from src.calculations import (
    compute_dd_series,
    identify_drawdown_events,
    compute_annual_returns,
    build_annual_dd_map,
    compute_frequency_table,
    compute_cooccurrence,
    build_dot_plot_data,
    CATEGORY_ORDER,
    CATEGORY_LABELS,
    CATEGORY_COLORS,
)
from src.charts import (
    build_equity_with_dd_zones,
    build_frequency_bar,
    build_dot_plot,
    build_cooccurrence_heatmap,
    build_annual_return_bar,
)

# ===================================================
# API KEY
# ===================================================
try:
    EODHD_API_KEY = st.secrets["EODHD_API_KEY"]
except KeyError:
    st.error(
        "❌ **EODHD_API_KEY non trovata nei secrets.**\n\n"
        "In locale: crea il file `.streamlit/secrets.toml` con:\n"
        "```\nEODHD_API_KEY = \"la-tua-chiave\"\n```\n\n"
        "Su Streamlit Cloud: impostala in Settings → Secrets."
    )
    st.stop()

# ===================================================
# SIDEBAR
# ===================================================
with st.sidebar:
    st.title("⚙️ Parametri")
    st.divider()

    ticker_input = st.text_input(
        "Ticker EODHD",
        value="GSPC.INDX",
        help=(
            "Formato: SIMBOLO.EXCHANGE\n"
            "Esempi: GSPC.INDX (S&P 500), SPY.US, DAX.INDX, ENI.MI"
        ),
    ).strip().upper()

    st.divider()
    st.markdown("**Categorie Drawdown**")
    st.markdown(
        "Le categorie sono **mutualmente esclusive**: "
        "ogni evento è classificato in base alla profondità massima raggiunta."
    )
    for cat in CATEGORY_ORDER:
        color = CATEGORY_COLORS[cat]
        st.markdown(
            f"<span style='color:{color}'>■</span> **{CATEGORY_LABELS[cat]}**",
            unsafe_allow_html=True,
        )

    st.divider()
    st.caption(f"📡 Dati: EODHD Historical Data")
    st.caption(f"🕒 Aggiornato: {datetime.now().strftime('%d/%m/%Y %H:%M')}")

# ===================================================
# HEADER
# ===================================================
st.title("📉 Drawdown Analysis Dashboard")
st.markdown(
    """
    Studio statistico e qualitativo dei drawdown sull'intero storico disponibile.
    La dashboard classifica ogni episodio di calo in **4 categorie mutualmente esclusive**,
    ne analizza la frequenza storica, e mette in relazione i drawdown con i rendimenti
    dell'anno solare in cui si sono verificati.

    > **Come si usa:** inserisci il ticker nella sidebar (formato EODHD) e attendi il caricamento
    > dell'intero storico. I calcoli vengono eseguiti automaticamente.
    """
)
st.divider()

# ===================================================
# VALIDAZIONE TICKER E FETCH DATI
# ===================================================
is_valid, err_msg = validate_ticker_format(ticker_input)
if not is_valid:
    st.warning(f"⚠️ {err_msg}")
    st.stop()

with st.spinner(f"⏳ Caricamento storico completo per **{ticker_input}**..."):
    try:
        df_raw = fetch_ohlcv(ticker_input, EODHD_API_KEY)
    except Exception as e:
        st.error(f"❌ Errore API EODHD: `{e}`\nVerifica il ticker e la chiave API.")
        st.stop()

if df_raw.empty or "adjusted_close" not in df_raw.columns:
    st.warning(
        f"⚠️ Nessun dato trovato per **{ticker_input}**. "
        "Verifica che il ticker esista su EODHD e che la chiave API sia valida."
    )
    st.stop()

prices = df_raw["adjusted_close"].dropna()

if len(prices) < 252:
    st.warning("⚠️ Storico insufficiente (< 252 giorni). L'analisi potrebbe non essere significativa.")

# ===================================================
# CALCOLI PRINCIPALI
# ===================================================
total_years     = (prices.index[-1] - prices.index[0]).days / 365.25
all_years       = pd.Index(sorted(prices.index.year.unique()))

events_df       = identify_drawdown_events(prices)
annual_returns  = compute_annual_returns(prices)
annual_dd_map   = build_annual_dd_map(events_df, all_years)
freq_df         = compute_frequency_table(events_df, total_years)
cooc_df         = compute_cooccurrence(annual_dd_map)
dot_df          = build_dot_plot_data(events_df, annual_returns)
dd_series       = compute_dd_series(prices)

# ===================================================
# KPI SUMMARY
# ===================================================
st.subheader("📊 Riepilogo Storico")

n_events_total = len(events_df) if not events_df.empty else 0
worst_dd       = dd_series.min() * 100
worst_dd_date  = dd_series.idxmin().strftime("%b %Y") if not dd_series.empty else "—"
years_with_any = int(annual_dd_map.any(axis=1).sum()) if not annual_dd_map.empty else 0

c1, c2, c3, c4, c5 = st.columns(5)
c1.metric("Ticker", ticker_input)
c2.metric("Storico", f"{total_years:.1f} anni")
c3.metric("N. eventi DD totali", n_events_total)
c4.metric("Max Drawdown Storico", f"{worst_dd:.1f}%", worst_dd_date)
c5.metric("Anni con almeno 1 DD", years_with_any)

st.divider()

# ===================================================
# SEZIONE A — Equity Curve con zone DD
# ===================================================
st.subheader("📈 Equity Curve con Zone di Drawdown")
st.markdown(
    """
    Il grafico mostra l'andamento storico dei prezzi adjusted close. Le zone colorate
    evidenziano i periodi di drawdown: ogni zona copre dall'inizio dell'evento (picco)
    alla data di completo recupero. Il colore indica la categoria del drawdown:

    - 🔵 **DD 5–10%**: correzione moderata
    - 🟠 **DD 10–20%**: correzione rilevante
    - 🔴 **DD 20–25%**: drawdown severo (zona di bear market)
    - 🟣 **DD > 25%**: drawdown estremo

    **Come leggere il grafico:** cerca la correlazione tra le zone di colore più intenso
    e i periodi di crisi noti. Più lunga è la zona, maggiore è stata la durata dell'evento.
    """
)

fig_equity = build_equity_with_dd_zones(prices, events_df, ticker_input)
st.plotly_chart(fig_equity, use_container_width=True)

with st.expander("ℹ️ Nota metodologica — Equity Curve"):
    st.markdown(
        """
        - **Prezzi:** adjusted close (aggiustati per dividendi e split).
        - **Definizione evento:** un drawdown inizia quando il prezzo scende ≥ 5% dal massimo
          storico precedente e termina quando il prezzo recupera quel massimo.
        - **Categoria:** determinata dal punto più basso raggiunto dall'evento (mutualmente esclusiva).
        - Fonte dati: EODHD Historical Data API.
        """
    )

st.divider()

# ===================================================
# SEZIONE B — Frequenza drawdown
# ===================================================
st.subheader("📐 Frequenza Storica dei Drawdown")
st.markdown(
    """
    La tabella e il grafico mostrano **quante volte in media** ci si aspetta un evento
    di ciascuna categoria in finestre temporali di 1, 2 e 3 anni, calcolate sull'intero
    storico disponibile.

    **Come leggere:** un valore di 0.5 nella colonna "1 Anno" significa che, storicamente,
    quell'evento si è verificato una volta ogni 2 anni in media. Un valore di 1.8 nella
    colonna "2 Anni" significa che in un arco di 2 anni ci si possono aspettare quasi 2 eventi.

    > La frequenza non è una garanzia: è una stima probabilistica basata sul passato.
    """
)

col_tab, col_bar = st.columns([1, 2])

with col_tab:
    st.markdown("**Tabella Frequenze**")
    st.dataframe(
        freq_df.style
        .format({
            "Freq. media / 1Y": "{:.3f}",
            "Freq. media / 2Y": "{:.3f}",
            "Freq. media / 3Y": "{:.3f}",
        })
        .background_gradient(
            subset=["Freq. media / 1Y", "Freq. media / 2Y", "Freq. media / 3Y"],
            cmap="Blues",
        ),
        use_container_width=True,
    )

with col_bar:
    fig_freq = build_frequency_bar(freq_df)
    st.plotly_chart(fig_freq, use_container_width=True)

with st.expander("ℹ️ Nota metodologica — Frequenza"):
    st.markdown(
        f"""
        - **Anni totali analizzati:** {total_years:.1f}
        - **Formula:** freq_NY = (n° eventi categoria) / (anni totali) × N
        - Gli eventi sono contati per data del **bottom** (punto più basso dell'episodio).
        - Un anno può contenere più eventi di categorie diverse.
        """
    )

st.divider()

# ===================================================
# SEZIONE C — Dot plot rendimenti annuali
# ===================================================
st.subheader("🎯 Rendimenti Annuali negli Anni con Drawdown")
st.markdown(
    """
    Ogni punto rappresenta un anno solare (Jan–Dec) in cui si è verificato
    almeno un evento di quella categoria di drawdown. L'asse Y mostra il rendimento
    totale di quell'anno solare.

    **Come leggere:** se i punti di una colonna sono prevalentemente sotto lo zero,
    quella categoria di drawdown è tipicamente associata ad anni negativi. La linea
    tratteggiata con il simbolo **μ** indica la media dei rendimenti per quella categoria.

    > Un anno con eventi di due categorie diverse (es. DD_5 in marzo e DD_10 in ottobre)
    > compare come punto sia nella colonna DD_5 sia nella colonna DD_10.
    """
)

fig_dot = build_dot_plot(dot_df)
st.plotly_chart(fig_dot, use_container_width=True)

# Tabella dettaglio anni per categoria
if not dot_df.empty:
    with st.expander("📋 Dettaglio anni per categoria"):
        for cat in CATEGORY_ORDER:
            subset = dot_df[dot_df["category"] == cat].sort_values("year")
            if subset.empty:
                continue
            st.markdown(f"**{CATEGORY_LABELS[cat]}**")
            detail = subset[["year", "annual_return_pct"]].copy()
            detail.columns = ["Anno", "Rendimento Annuale (%)"]
            detail["Rendimento Annuale (%)"] = detail["Rendimento Annuale (%)"].map("{:+.2f}%".format)
            st.dataframe(detail.set_index("Anno"), use_container_width=True)
            st.markdown("---")

st.divider()

# ===================================================
# SEZIONE D — Bar chart rendimenti annuali
# ===================================================
st.subheader("📅 Rendimenti Annuali con Evidenza della Categoria DD")
st.markdown(
    """
    Ogni barra rappresenta il rendimento solare (Jan–Dec) di un anno.
    Il colore della barra indica la **categoria più grave** di drawdown registrata
    in quell'anno (DD_25 ha priorità su DD_20, che ha priorità su DD_10, ecc.).
    Gli anni in grigio non hanno avuto drawdown ≥ 5%.

    **Come leggere:** anni con barre rosse o viola (drawdown severi) tendono a coincidere
    con rendimenti negativi, ma non sempre — un anno può avere un drawdown profondo
    a inizio anno e poi recuperare, chiudendo positivo. Questa è proprio l'informazione
    che il dot plot nella sezione precedente cattura analiticamente.
    """
)

fig_annual = build_annual_return_bar(annual_returns, annual_dd_map)
st.plotly_chart(fig_annual, use_container_width=True)

st.divider()

# ===================================================
# SEZIONE E — Heatmap co-occorrenza
# ===================================================
st.subheader("🔁 Co-occorrenza Categorie Drawdown nello Stesso Anno")
st.markdown(
    """
    La matrice mostra **quanti anni solari** hanno visto almeno un evento di entrambe
    le categorie indicate su riga e colonna. La diagonale indica il numero totale di
    anni con almeno un evento di quella categoria.

    **Come leggere:** se la cella "DD 10–20%" × "DD 5–10%" vale 12, significa che in
    12 anni distinti si è verificato almeno un episodio di DD 10–20% **e** almeno uno
    di DD 5–10% nello stesso anno solare. Celle con "—" indicano zero co-occorrenze.

    > Questo tipo di analisi risponde alla domanda: *"Quando il mercato scende del 10%,
    > quante volte ha anche subito una correzione separata del 5% nello stesso anno?"*
    """
)

fig_heatmap = build_cooccurrence_heatmap(cooc_df)
st.plotly_chart(fig_heatmap, use_container_width=True)

# Tabella numerica leggibile affiancata
with st.expander("📋 Matrice numerica co-occorrenza"):
    st.dataframe(cooc_df, use_container_width=True)

st.divider()

# ===================================================
# FOOTER
# ===================================================
st.caption(
    "Dashboard sviluppata per **Kriterion Quant** · "
    f"Dati: EODHD Historical Data · "
    f"Storico analizzato: {prices.index[0].strftime('%d/%m/%Y')} — "
    f"{prices.index[-1].strftime('%d/%m/%Y')}"
)
