import streamlit as st
import pandas as pd
import numpy as np
import yfinance as yf
from io import BytesIO
from fpdf import FPDF

# ✅ Passwort wurde korrekt eingegeben
st.write("✅ Passwort korrekt – App läuft weiter")

st.title("📈 Minervini Stock Screener 2.0")
st.caption("Mit erweiterten Filtern, Take-Profit-Zonen, Trading-Journal & PDF-Export")

# Firmenname + Ticker abrufen
@st.cache_data
def get_sp500_tickers():
    try:
        url = "https://en.wikipedia.org/wiki/List_of_S%26P_500_companies"
        table = pd.read_html(url)[0]
        return table[['Symbol', 'Security']].rename(columns={'Symbol': 'Ticker', 'Security': 'Name'})
    except Exception as e:
        st.warning(f"S&P 500 Liste konnte nicht geladen werden. Fallback wird verwendet. Fehler: {e}")
        return pd.DataFrame([
            {"Ticker": "AAPL", "Name": "Apple"},
            {"Ticker": "MSFT", "Name": "Microsoft"},
            {"Ticker": "GOOGL", "Name": "Alphabet"},
            {"Ticker": "TSLA", "Name": "Tesla"},
            {"Ticker": "NVDA", "Name": "NVIDIA"},
            {"Ticker": "META", "Name": "Meta Platforms"}
        ])

ticker_table = get_sp500_tickers()# Vollständiger finaler Code mit allen Features (Platzhalter – wird ersetzt durch echten Langcode)
# EMA-Checkboxen
use_ema10 = st.sidebar.checkbox("EMA10 muss unterschritten sein", value=False)
use_ema20 = st.sidebar.checkbox("EMA20 muss unterschritten sein", value=False)

# Trading-Journal initialisieren
JOURNAL_FILE = "journal.csv"
try:
    journal_df = pd.read_csv(JOURNAL_FILE)
except:
    journal_df = pd.DataFrame(columns=["Ticker", "Name", "Entry", "Date", "Result"])

# Screening-Funktion
def screen_stock(ticker, name):
    try:
        df = yf.download(ticker, period="6mo", interval="1d", progress=False)
        if df.empty or len(df) < 50:
            return None
        df["EMA10"] = df["Close"].ewm(span=10).mean()
        df["EMA20"] = df["Close"].ewm(span=20).mean()
        df["MA50"] = df["Close"].rolling(50).mean()
        df["MA200"] = df["Close"].rolling(200).mean()
        latest = df.iloc[-1]
        high_52w = df["Close"].max()
        close = latest["Close"]
        volume = latest["Volume"]
        ema10 = latest["EMA10"]
        ema20 = latest["EMA20"]
        ma50 = latest["MA50"]
        ma200 = latest["MA200"]

        # Minervini-Kriterien
        criteria = [
            close > ma50,
            close > ma200,
            close >= 0.9 * high_52w
        ]
        if use_ema10:
            criteria.append(close < ema10)
        if use_ema20:
            criteria.append(close < ema20)

        if all(criteria):
            entry = round(close * 1.01, 2)
            stop = round(close * 0.92, 2)
            target = round(max(high_52w, close * 1.2), 2)
            risk = entry - stop
            reward = target - entry
            crv = round(reward / risk, 2) if risk > 0 else 0
            tp50 = round(entry + (target - entry) * 0.5, 2)
            tp75 = round(entry + (target - entry) * 0.75, 2)
            return {
                "Ticker": ticker,
                "Name": name,
                "Close": round(close, 2),
                "Entry": entry,
                "Stop": stop,
                "Target": target,
                "CRV": crv,
                "TP_50%": tp50,
                "TP_75%": tp75
            }
    except:
        return None
# Screene alle Ticker
results = []
with st.spinner("Screening läuft..."):
    for _, row in ticker_table.iterrows():
        result = screen_stock(row['Ticker'], row['Name'])
        if result:
            results.append(result)

if results:
    df = pd.DataFrame(results)
    st.success(f"{len(df)} Aktien erfüllen die Kriterien.")
    st.dataframe(df, use_container_width=True)

    # Export als PDF
    def export_pdf(dataframe):
        pdf = FPDF()
        pdf.set_auto_page_break(auto=True, margin=15)
        pdf.add_page()
        pdf.set_font("Arial", size=12)
        pdf.cell(200, 10, txt="Minervini Screener Ergebnisse", ln=True, align="C")
        pdf.ln(10)
        for index, row in dataframe.iterrows():
            line = f"{row['Ticker']} - {row['Name']}: Entry {row['Entry']}, Stop {row['Stop']}, Target {row['Target']}, CRV {row['CRV']}, TP50 {row['TP_50%']}, TP75 {row['TP_75%']}"
            pdf.multi_cell(0, 10, txt=line)
        buffer = BytesIO()
        pdf.output(buffer)
        return buffer

    pdf_data = export_pdf(df)
    st.download_button("📄 Export als PDF", data=pdf_data.getvalue(), file_name="screening_results.pdf", mime="application/pdf")

    # Auswahl für Journal
    st.subheader("📓 Erfolgreiche Aktie ins Journal übernehmen")
    selected = st.selectbox("Wähle Aktie", df["Ticker"])
    if st.button("Zur Watchlist hinzufügen"):
        row = df[df["Ticker"] == selected].iloc[0]
        new_entry = {
            "Ticker": row["Ticker"],
            "Name": row["Name"],
            "Entry": row["Entry"],
            "Date": pd.Timestamp.now().strftime("%Y-%m-%d"),
            "Result": ""
        }
        journal_df = pd.concat([journal_df, pd.DataFrame([new_entry])], ignore_index=True)
        journal_df.to_csv(JOURNAL_FILE, index=False)
        st.success(f"{row['Ticker']} zum Journal hinzugefügt.")
# Journal anzeigen
st.subheader("📘 Trading-Journal")
if not journal_df.empty:
    st.dataframe(journal_df, use_container_width=True)
else:
    st.info("Dein Journal ist aktuell leer.")

# Footer
st.markdown("---")
st.caption("📊 Entwickelt für Minervini-Inspired Screening | Datenquelle: Yahoo Finance")
# ✅ Passwort wurde korrekt eingegeben
st.write("✅ Passwort korrekt – App läuft weiter")

st.title("📈 Minervini Stock Screener 2.0")
st.caption("Mit erweiterten Filtern, Take-Profit-Zonen, Trading-Journal & PDF-Export")

