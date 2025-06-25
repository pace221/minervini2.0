import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
import datetime
from io import BytesIO
from fpdf import FPDF
import altair as alt

# ⛔️ Passwortschutz
def password_check():
    password = st.text_input("🔒 Bitte Passwort eingeben:", type="password")
    if password == "yolotrading":
        st.session_state["authenticated"] = True
    elif password:
        st.error("❌ Falsches Passwort")

if "authenticated" not in st.session_state:
    st.session_state["authenticated"] = False

if not st.session_state["authenticated"]:
    password_check()
    st.stop()

# ✅ App läuft weiter nach Passwort
st.set_page_config(page_title="Minervini Screener 2.0", layout="wide")
st.title("📈 Minervini Stock Screener 2.0")
st.caption("Mit erweiterten Filtern, Take-Profit-Zonen, Trading-Journal & PDF-Export")

# 🗓️ Letztes Kursdatum
@st.cache_data(ttl=3600)
def get_data_date():
    try:
        data = yf.download("AAPL", period="5d", progress=False)
        return data.index[-1].strftime("%d.%m.%Y")
    except:
        return datetime.datetime.now().strftime("%d.%m.%Y")

st.markdown(f"**📅 Letzter Datenstand:** {get_data_date()}")
# 📥 S&P 500 Ticker + Unternehmen laden
@st.cache_data
def get_sp500_tickers():
    try:
        url = "https://en.wikipedia.org/wiki/List_of_S%26P_500_companies"
        table = pd.read_html(url)[0]
        return table[['Symbol', 'Security']].rename(columns={'Symbol': 'Ticker', 'Security': 'Name'})
    except:
        return pd.DataFrame([
            {"Ticker": "AAPL", "Name": "Apple"},
            {"Ticker": "MSFT", "Name": "Microsoft"},
            {"Ticker": "GOOGL", "Name": "Alphabet"},
            {"Ticker": "TSLA", "Name": "Tesla"},
            {"Ticker": "NVDA", "Name": "NVIDIA"},
            {"Ticker": "META", "Name": "Meta Platforms"}
        ])

ticker_df = get_sp500_tickers()
all_tickers = ticker_df['Ticker'].tolist()

# 🔧 Sidebar Filter
st.sidebar.header("🧪 Screening-Einstellungen")

anzahl = st.sidebar.selectbox(
    "Wie viele Aktien analysieren?",
    options=["10", "50", "100", "Alle"],
    index=2
)

anzahl_mapping = {
    "10": 10,
    "50": 50,
    "100": 100,
    "Alle": len(all_tickers)
}
auswahl = all_tickers[:anzahl_mapping[anzahl]]

min_price = st.sidebar.slider("📉 Mindestkurs ($)", 5.0, 1000.0, 20.0, 5.0)
min_volume_ratio = st.sidebar.slider("📊 Volumen vs Schnitt (min)", 0.5, 5.0, 1.5, 0.1)
min_crv = st.sidebar.slider("📈 Mindest-CRV (Chance/Risiko)", 1.0, 10.0, 2.0, 0.5)
def screen_stock(ticker):
    try:
        data = yf.download(ticker, period="1y", progress=False, auto_adjust=True)
        if data.empty or len(data) < 200:
            return None

        close = data['Close']
        volume = data['Volume']

        ma50 = close.rolling(50).mean()
        ma200 = close.rolling(200).mean()
        high52 = close.rolling(252, min_periods=20).max()

        latest = close.index[-1]
        c = close.loc[latest]
        v = volume.tail(3).mean()
        v_avg = volume.mean()

        cond_1 = c > ma50.loc[latest]
        cond_2 = c > ma200.loc[latest]
        cond_3 = c >= 0.9 * high52.loc[latest]
        cond_4 = v > v_avg
        pattern = ""
        idea = ""

        if cond_1 and cond_2:
            if cond_3 and cond_4:
                pattern = "Breakout"
                idea = "Volume + High"
            elif cond_3:
                pattern = "Near High"
                idea = "Momentum"

        # CRV-Berechnung
        entry = c * 1.01
        stop = max(ma50.loc[latest] * 0.99, c * 0.92)
        target = max(high52.loc[latest], c * 1.20)
        crv = (target - entry) / (entry - stop) if entry > stop else 0

        take_profit_50 = entry + (target - entry) * 0.5
        take_profit_75 = entry + (target - entry) * 0.75

        if c < min_price or v / v_avg < min_volume_ratio or crv < min_crv:
            return None

        name = ticker_df.loc[ticker_df['Ticker'] == ticker, 'Name'].values[0] if ticker in ticker_df['Ticker'].values else ""

        return {
            "Ticker": ticker,
            "Name": name,
            "Close": round(c, 2),
            "Entry": round(entry, 2),
            "Stop": round(stop, 2),
            "Target": round(target, 2),
            "CRV": round(crv, 2),
            "TakeProfit50": round(take_profit_50, 2),
            "TakeProfit75": round(take_profit_75, 2),
            "Pattern": pattern,
            "Idea": idea
        }

    except Exception as e:
        return None
        st.header("🔍 Screening Ergebnisse")

results = []
with st.spinner("Analysiere Aktien..."):
    for t in auswahl:
        res = screen_stock(t)
        if res:
            results.append(res)

if results:
    df = pd.DataFrame(results)

    st.success(f"{len(df)} Aktien erfüllen alle Bedingungen.")
    st.dataframe(df[[
        "Ticker", "Name", "Close", "Entry", "Stop", "Target",
        "CRV", "TakeProfit50", "TakeProfit75", "Pattern", "Idea"
    ]], use_container_width=True)

    # 📈 Charts
    st.subheader("📊 Charts der Top-Aktien")
    top5 = df.sort_values("CRV", ascending=False).head(5)
    for _, row in top5.iterrows():
        chart_data = yf.download(row["Ticker"], period="6mo", progress=False)
        chart_data["MA50"] = chart_data["Close"].rolling(50).mean()
        chart_data["MA200"] = chart_data["Close"].rolling(200).mean()
        chart_data = chart_data.reset_index()

        base = alt.Chart(chart_data).encode(x='Date:T')

        lines = base.mark_line().encode(
            y=alt.Y('Close:Q', title="Kurs"),
            color=alt.value('#2E86C1')
        )
        ma50 = base.mark_line(strokeDash=[4, 2], color='orange').encode(y='MA50:Q')
        ma200 = base.mark_line(strokeDash=[2, 2], color='red').encode(y='MA200:Q')

        st.altair_chart((lines + ma50 + ma200).interactive(), use_container_width=True)
        # 📤 PDF Export
def export_pdf(dataframe):
    pdf = FPDF()
    pdf.set_auto_page_break(auto=True, margin=15)
    pdf.add_page()
    pdf.set_font("Arial", size=10)

    pdf.cell(200, 10, txt="Minervini Stock Screener Ergebnisse", ln=True, align='C')
    pdf.ln(5)

    for i, row in dataframe.iterrows():
        line = f"{row['Ticker']} - {row['Name']} | Close: {row['Close']}$ | CRV: {row['CRV']} | TP50: {row['TakeProfit50']}$ | TP75: {row['TakeProfit75']}$"
        pdf.multi_cell(0, 10, txt=line)
        pdf.ln(1)

    buffer = BytesIO()
    pdf.output(buffer)
    buffer.seek(0)
    return buffer

st.subheader("📥 Exportieren")

if st.button("📄 Ergebnisse als PDF speichern"):
    pdf_buffer = export_pdf(df)
    st.download_button("📥 PDF herunterladen",
                       data=pdf_buffer,
                       file_name="minervini_results.pdf",
                       mime="application/pdf")

# ℹ️ Footer
st.markdown("---")
st.caption("© 2025 Minervini Screener. Daten via Yahoo Finance. Nur zu Bildungszwecken.")
