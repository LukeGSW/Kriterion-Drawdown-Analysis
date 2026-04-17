"""
data_fetcher.py — Fetch e caching dei dati EODHD via API REST.

Tutte le funzioni usano @st.cache_data per evitare chiamate ridondanti.
TTL default: 3600 secondi (1 ora).
"""

import requests
import pandas as pd
import streamlit as st


@st.cache_data(ttl=3600, show_spinner=False)
def fetch_ohlcv(ticker: str, api_key: str) -> pd.DataFrame:
    """
    Scarica l'intera serie storica OHLCV giornaliera da EODHD per il ticker dato.

    Scarica dal 1970-01-01 a oggi per massimizzare lo storico disponibile.
    I dati sono cachati per 1 ora per evitare chiamate API ridondanti.

    Args:
        ticker:  Simbolo nel formato EODHD (es. 'GSPC.INDX', 'SPY.US', 'ENI.MI').
        api_key: Chiave API EODHD letta dai secrets di Streamlit.

    Returns:
        DataFrame con DatetimeIndex e colonne:
          open, high, low, close, volume, adjusted_close
        Ordinato cronologicamente (ascending).
        Restituisce DataFrame vuoto se la risposta API non contiene dati.

    Raises:
        requests.exceptions.HTTPError: se la risposta HTTP non è 2xx.
        requests.exceptions.Timeout:   se la richiesta supera 30 secondi.
    """
    url = (
        f"https://eodhd.com/api/eod/{ticker}"
        f"?from=1970-01-01"
        f"&period=d"
        f"&api_token={api_key}"
        f"&fmt=json"
    )

    resp = requests.get(url, timeout=30)
    resp.raise_for_status()

    data = resp.json()
    if not data:
        return pd.DataFrame()

    df = pd.DataFrame(data)
    df["date"] = pd.to_datetime(df["date"])
    df.set_index("date", inplace=True)
    df.sort_index(inplace=True)

    # Mantieni solo le colonne OHLCV standard
    cols_wanted = ["open", "high", "low", "close", "volume", "adjusted_close"]
    cols_present = [c for c in cols_wanted if c in df.columns]
    df = df[cols_present].apply(pd.to_numeric, errors="coerce")

    return df


def validate_ticker_format(ticker: str) -> tuple[bool, str]:
    """
    Verifica che il ticker rispetti il formato EODHD (SIMBOLO.EXCHANGE).

    Non effettua chiamate API: è una validazione sintattica di base.

    Args:
        ticker: Stringa ticker inserita dall'utente.

    Returns:
        Tuple (is_valid: bool, message: str).
        Se is_valid è True, message è una stringa vuota.
    """
    ticker = ticker.strip().upper()
    if not ticker:
        return False, "Il ticker non può essere vuoto."
    if "." not in ticker:
        return False, (
            "Formato non valido. Usa il formato EODHD: SIMBOLO.EXCHANGE "
            "(es. GSPC.INDX, SPY.US, ENI.MI, DAX.INDX)."
        )
    parts = ticker.split(".")
    if len(parts) != 2 or not parts[0] or not parts[1]:
        return False, "Formato non valido. Esempio corretto: GSPC.INDX"
    return True, ""
