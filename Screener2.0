
# Streamlit App: Minervini Screener 2.0 (final)
# Enthält Passwortschutz, Klarname, EMA10/20 Filter, CRV, Take-Profit, PDF-Export

import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
from io import BytesIO
from fpdf import FPDF
import altair as alt
import datetime

# Passwortschutz
def password_check():
    if "auth" not in st.session_state:
        st.session_state.auth = False
    if not st.session_state.auth:
        pw = st.text_input("🔐 Passwort eingeben:", type="password")
        if pw == "yolotrading":
            st.session_state.auth = True
            st.experimental_rerun()
        elif pw:
            st.error("Falsches Passwort")
        st.stop()

password_check()

# Seitenlayout
st.set_page_config(page_title="Minervini Screener 2.0", layout="wide")
st.title("📈 Minervini Stock Screener 2.0")
st.caption("Erweiterte Version mit Take-Profit, EMA-Filtern, PDF-Export")

# Datum
@st.cache_data(ttl=300)
def get_data_date():
    try:
        d = yf.download("AAPL", period="5d", progress=False)
        return d.index[-1].strftime("%d.%m.%Y")
    except:
        return datetime.datetime.now().strftime("%d.%m.%Y")

st.markdown(f"**📅 Letzter Datenstand:** {get_data_date()}")

# Ticker laden
@st.cache_data
def get_sp500_tickers():
    df = pd.read_html("https://en.wikipedia.org/wiki/List_of_S%26P_500_companies")[0]
    return df[['Symbol', 'Security']].rename(columns={'Symbol': 'Ticker', 'Security': 'Name'})

ticker_df = get_sp500_tickers()
all_tickers = ticker_df['Ticker'].tolist()
ticker_map = dict(zip(ticker_df['Ticker'], ticker_df['Name']))

# Sidebar-Filter
st.sidebar.header("🔧 Filter")
anzahl = st.sidebar.selectbox("Wie viele Aktien analysieren?", ["10", "50", "100", "Alle"], index=2)
anzahl_dict = {"10": 10, "50": 50, "100": 100, "Alle": len(all_tickers)}
auswahl = all_tickers[:anzahl_dict[anzahl]]

min_price = st.sidebar.slider("📉 Mindestkurs ($)", 5.0, 1000.0, 20.0, 5.0)
min_vol = st.sidebar.slider("📊 Volumen vs Ø", 0.5, 5.0, 1.5, 0.1)
min_crv = st.sidebar.slider("📈 Mindest-CRV", 1.0, 10.0, 2.0, 0.5)
use_ema10 = st.sidebar.checkbox("Nur wenn Kurs über EMA10", value=False)
use_ema20 = st.sidebar.checkbox("Nur wenn Kurs über EMA20", value=False)


# Screening-Funktion
def screen_stock(ticker):
    try:
        data = yf.download(ticker, period="1y", progress=False, auto_adjust=True)
        if data.empty or len(data) < 150:
            return None
        close = data['Close']
        volume = data['Volume']
        ma50 = close.rolling(50).mean()
        ma200 = close.rolling(200).mean()
        ema10 = close.ewm(span=10).mean()
        ema20 = close.ewm(span=20).mean()
        high52 = close.rolling(252).max()
        latest = close.index[-1]
        c = close.loc[latest]
        v = volume.tail(3).mean()
        v_avg = volume.mean()
        if c < min_price or (v / v_avg) < min_vol:
            return None
        if use_ema10 and c < ema10.loc[latest]:
            return None
        if use_ema20 and c < ema20.loc[latest]:
            return None
        if c < ma50.loc[latest] or c < ma200.loc[latest] or c < 0.9 * high52.loc[latest]:
            return None
        entry = c * 1.01
        stop = max(ma50.loc[latest] * 0.99, c * 0.92)
        target = max(high52.loc[latest], c * 1.20)
        if entry <= stop:
            return None
        crv = (target - entry) / (entry - stop)
        if crv < min_crv:
            return None
        tp50 = entry + (target - entry) * 0.5
        tp75 = entry + (target - entry) * 0.75
        return {
            "Ticker": ticker,
            "Name": ticker_map.get(ticker, ""),
            "Close": round(c, 2),
            "Entry": round(entry, 2),
            "Stop": round(stop, 2),
            "Target": round(target, 2),
            "CRV": round(crv, 2),
            "TP_50%": round(tp50, 2),
            "TP_75%": round(tp75, 2)
        }
    except:
        return None

# Ergebnisse
st.header("🔍 Screening Ergebnisse")
if st.button("🚀 Run Screening"):
    with st.spinner("Bitte warten..."):
        results = []
        for t in auswahl:
            res = screen_stock(t)
            if res:
                results.append(res)
        if results:
            df = pd.DataFrame(results)
            st.success(f"{len(df)} Aktien gefunden.")
            st.dataframe(df, use_container_width=True)

            def to_pdf(df):
                pdf = FPDF()
                pdf.set_auto_page_break(auto=True, margin=10)
                pdf.add_page()
                pdf.set_font("Arial", size=10)
                for i, row in df.iterrows():
                    line = f"{row['Ticker']} - {row['Name']} | Close: ${row['Close']} | Entry: ${row['Entry']} | Stop: ${row['Stop']} | Target: ${row['Target']} | CRV: {row['CRV']} | TP50: ${row['TP_50%']} | TP75: ${row['TP_75%']}"
                    pdf.multi_cell(0, 10, line)
                b = BytesIO()
                pdf.output(b)
                b.seek(0)
                return b

            pdf_buffer = to_pdf(df)
            st.download_button("📄 PDF Exportieren", data=pdf_buffer, file_name="minervini_results.pdf", mime="application/pdf")
        else:
            st.warning("Keine Aktien erfüllt die Kriterien.")
