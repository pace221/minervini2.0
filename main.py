import streamlit as st
import pandas as pd
import numpy as np
import yfinance as yf
from io import BytesIO
from fpdf import FPDF

# Passwortschutz
def password_check():
    st.session_state['authenticated'] = False
    password = st.text_input("🔒 Bitte Passwort eingeben:", type="password")
    if password == "yolotrading":
        st.session_state['authenticated'] = True
    elif password:
        st.error("Falsches Passwort")

if 'authenticated' not in st.session_state:
    password_check()

if not st.session_state.get('authenticated', False):
    st.stop()
# ✅ Passwort erfolgreich
st.write("✅ Passwort korrekt – App läuft weiter")

# 🧪 Schrittweiser Test: Ticker laden
st.write("⏳ Versuche Ticker zu laden...")

try:
    import pandas as pd
    url = "https://en.wikipedia.org/wiki/List_of_S%26P_500_companies"
    table = pd.read_html(url)[0]
    tickers_df = table[['Symbol', 'Security']].rename(columns={'Symbol': 'Ticker', 'Security': 'Name'})
    st.write("📊 Erfolgreich geladen:", tickers_df.head())
except Exception as e:
    st.error(f"❌ Fehler beim Laden der Ticker: {e}")
