# Drawdown Analysis Dashboard — Kriterion Quant

Dashboard Streamlit per l'analisi statistica e qualitativa dei drawdown su serie storiche giornaliere scaricate via EODHD.

## Struttura repository

```
drawdown-analysis/
├── app.py                      # Entry point Streamlit
├── requirements.txt
├── .streamlit/
│   ├── config.toml             # Tema dark mode
│   └── secrets.toml            # API key — NON committare (vedi .gitignore)
├── src/
│   ├── __init__.py
│   ├── data_fetcher.py         # Fetch EODHD con caching
│   ├── calculations.py         # Algoritmi drawdown
│   └── charts.py               # Grafici Plotly
└── .gitignore
```

## Setup locale

```bash
# 1. Clona il repo
git clone https://github.com/TUO_USERNAME/drawdown-analysis.git
cd drawdown-analysis

# 2. Crea virtualenv e installa dipendenze
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r requirements.txt

# 3. Configura la chiave API
# Crea il file .streamlit/secrets.toml (già in .gitignore):
echo 'EODHD_API_KEY = "la-tua-chiave-eodhd"' > .streamlit/secrets.toml

# 4. Avvia l'app
streamlit run app.py
```

## Deploy su Streamlit Cloud

1. Pusha il repo su GitHub (il file `secrets.toml` è escluso dal `.gitignore`)
2. Vai su [streamlit.io/cloud](https://streamlit.io/cloud) → **New app**
3. Connetti il repository e imposta `app.py` come entry point
4. In **Advanced settings → Secrets** incolla:
   ```toml
   EODHD_API_KEY = "la-tua-chiave-eodhd"
   ```
5. Clicca **Deploy**

## Ticker supportati (formato EODHD)

| Asset | Ticker EODHD |
|-------|-------------|
| S&P 500 | `GSPC.INDX` |
| NASDAQ 100 | `NDX.INDX` |
| DAX | `DAX.INDX` |
| SPY ETF | `SPY.US` |
| QQQ ETF | `QQQ.US` |
| Qualsiasi indice/ETF/azione | `SIMBOLO.EXCHANGE` |

## Logica drawdown

Le categorie sono **mutualmente esclusive**, classificate sul punto più basso raggiunto dall'evento:

| Categoria | Soglia |
|-----------|--------|
| DD 5–10% | Calo ≥ 5% e < 10% dal picco |
| DD 10–20% | Calo ≥ 10% e < 20% dal picco |
| DD 20–25% | Calo ≥ 20% e < 25% dal picco |
| DD > 25% | Calo ≥ 25% dal picco |

Un evento inizia quando il prezzo scende ≥ 5% dal massimo storico progressivo e termina quando il prezzo recupera quel massimo. Ogni evento è assegnato all'anno solare del suo punto più basso (bottom_year).
