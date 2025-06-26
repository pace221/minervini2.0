import streamlit as st
import pandas as pd
import numpy as np
import time
from datetime import datetime
import plotly.graph_objects as go
from plotly.subplots import make_subplots

from utils.data_loader import DataLoader
from utils.screener import StockScreener
from utils.journal import TradingJournal
from utils.technical_analysis import TechnicalAnalyzer
from utils.fair_value_gaps import FairValueGapDetector
from utils.pdf_export import PDFExporter

# Page configuration
st.set_page_config(
    page_title="Enhanced S&P 500 Stock Screener",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Initialize session state
if 'journal' not in st.session_state:
    st.session_state.journal = TradingJournal()
if 'screening_results' not in st.session_state:
    st.session_state.screening_results = pd.DataFrame()
if 'selected_stocks' not in st.session_state:
    st.session_state.selected_stocks = set()

# Initialize components
data_loader = DataLoader()
screener = StockScreener()
technical_analyzer = TechnicalAnalyzer()
fvg_detector = FairValueGapDetector()
pdf_exporter = PDFExporter()

def main():
    # Header
    st.title("📈 Enhanced Stock Screener & Trading Journal")
    st.markdown("### Minervini Criteria + EMA Filtering + Fair Value Gaps + Backtesting")
    
    # Create main layout with sidebar for settings and main area split between results and journal
    with st.sidebar:
        st.header("Screening Settings")
        
        # Index selection
        st.subheader("Index Selection")
        selected_indices = st.multiselect(
            "Select Indices to Screen",
            options=["S&P 500", "NASDAQ 100", "EURO STOXX 50", "DAX"],
            default=["S&P 500"],
            help="Choose which stock indices to include in the screening"
        )
        
        st.subheader("Technical Criteria")
        
        # Minervini criteria (always enabled)
        st.markdown("**Core Minervini Criteria (Always Active):**")
        st.write("✓ Price > 50-day MA")
        st.write("✓ Price > 200-day MA") 
        st.write("✓ Near 52-week high (≥90%)")
        st.write("✓ Elevated volume")
        st.write("✓ CRV ≥ 2:1")
        
        st.divider()
        
        # EMA filtering options
        st.markdown("**Additional EMA Filters:**")
        ema10_filter = st.checkbox(
            "Price above EMA 10",
            value=False,
            help="Filter stocks where current price is above 10-period EMA"
        )
        
        ema20_filter = st.checkbox(
            "Price above EMA 20", 
            value=False,
            help="Filter stocks where current price is above 20-period EMA"
        )
        
        st.divider()
        
        # Fair Value Gap settings
        st.markdown("**Fair Value Gap Settings:**")
        fvg_enabled = st.checkbox(
            "Include Fair Value Gap Analysis",
            value=True,
            help="Detect and display Fair Value Gaps as entry opportunities"
        )
        
        fvg_lookback = st.slider(
            "FVG Lookback Period (days)",
            min_value=5,
            max_value=50,
            value=20,
            help="Number of days to look back for FVG detection"
        )
        
        st.divider()
        
        # Volume filter settings
        st.markdown("**Volume Filter:**")
        volume_multiplier = st.slider(
            "Volume Multiplier (x average)",
            min_value=1.0,
            max_value=3.0,
            value=1.0,
            step=0.1,
            help="Minimum volume as multiple of average volume (1x = normal, 2x = double volume, etc.)"
        )
        
        st.divider()
        
        # Risk management
        st.markdown("**Risk Management:**")
        portfolio_size = st.number_input(
            "Portfolio Size (EUR)",
            min_value=1000,
            max_value=1000000,
            value=10000,
            step=1000,
            help="Total portfolio value for position sizing"
        )
        
        risk_per_trade = st.slider(
            "Risk per Trade (%)",
            min_value=0.5,
            max_value=5.0,
            value=1.0,
            step=0.1,
            help="Maximum risk per individual trade"
        ) / 100
        
        # Screening button
        if st.button("🔍 Run Screening", type="primary", use_container_width=True):
            run_screening(selected_indices, ema10_filter, ema20_filter, 
                         fvg_enabled, fvg_lookback, volume_multiplier, portfolio_size, risk_per_trade)
    
    # Main content area with two columns
    col1, col2 = st.columns([2, 1])
    
    with col1:
        # Show data freshness info
        if 'screening_results' in st.session_state and st.session_state.screening_results is not None:
            if not st.session_state.screening_results.empty and 'Data_Date' in st.session_state.screening_results.columns:
                latest_data_date = st.session_state.screening_results['Data_Date'].iloc[0]
                st.info(f"📅 **Datenbasis des Screenings:** {latest_data_date} (aktuellste verfügbare Daten)")
        
        display_screening_results()
    
    with col2:
        display_trading_journal()

def run_screening(indices, ema10_filter, ema20_filter, fvg_enabled, fvg_lookback, volume_multiplier, portfolio_size, risk_per_trade):
    """Run the stock screening process"""
    
    with st.spinner("Loading stock data and running screening..."):
        progress_bar = st.progress(0)
        status_text = st.empty()
        
        try:
            # Load tickers for selected indices
            all_tickers = []
            for index_name in indices:
                status_text.text(f"Loading {index_name} tickers...")
                tickers = data_loader.get_index_tickers(index_name)
                all_tickers.extend(tickers)
                time.sleep(0.1)  # Small delay for UI update
            
            # Remove duplicates while preserving order
            unique_tickers = list(dict.fromkeys(all_tickers))
            total_stocks = len(unique_tickers)
            
            if total_stocks == 0:
                st.error("No tickers found for selected indices!")
                return
            
            status_text.text(f"Screening {total_stocks} stocks...")
            
            # Screen stocks in batches for better performance
            results = []
            batch_size = 20  # Process in smaller batches for better performance
            
            for i in range(0, total_stocks, batch_size):
                batch = unique_tickers[i:i + batch_size]
                batch_results = screener.screen_batch(
                    batch, ema10_filter, ema20_filter, 
                    fvg_enabled, fvg_lookback, volume_multiplier, portfolio_size, risk_per_trade
                )
                results.extend(batch_results)
                
                # Update progress
                progress = min((i + batch_size) / total_stocks, 1.0)
                progress_bar.progress(progress)
                status_text.text(f"Processed {min(i + batch_size, total_stocks)} of {total_stocks} stocks...")
            
            # Filter successful results
            successful_results = [r for r in results if r is not None]
            
            if successful_results:
                df = pd.DataFrame(successful_results)
                # Filter only stocks that meet all criteria
                df_filtered = df[df['Criteria_Met'] == True].copy()
                
                # Sort by CRV descending
                if not df_filtered.empty:
                    df_filtered = df_filtered.sort_values('CRV', ascending=False)
                
                st.session_state.screening_results = df_filtered
                
                # Store screening parameters for PDF export
                st.session_state.last_selected_indices = indices
                st.session_state.last_ema10_filter = ema10_filter
                st.session_state.last_ema20_filter = ema20_filter
                st.session_state.last_fvg_enabled = fvg_enabled
                st.session_state.last_volume_multiplier = volume_multiplier
                
                progress_bar.progress(1.0)
                status_text.text(f"✅ Screening complete! Found {len(df_filtered)} qualifying stocks out of {total_stocks} screened.")
                
                time.sleep(1)
                progress_bar.empty()
                status_text.empty()
                
            else:
                st.warning("No stocks met the screening criteria.")
                st.session_state.screening_results = pd.DataFrame()
                
        except Exception as e:
            st.error(f"Error during screening: {str(e)}")
            progress_bar.empty()
            status_text.empty()

def display_screening_results():
    """Display the screening results table"""
    st.header("🎯 Screening Results")
    
    if st.session_state.screening_results.empty:
        st.info("No screening results yet. Use the sidebar to configure settings and run a screening.")
        return
    
    df = st.session_state.screening_results.copy()
    
    # Display summary metrics
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("Stocks Found", len(df))
    with col2:
        avg_crv = df['CRV'].mean() if len(df) > 0 else 0
        st.metric("Avg CRV", f"{avg_crv:.2f}")
    with col3:
        total_investment = df['Position_Value_EUR'].sum() if len(df) > 0 else 0
        st.metric("Total Investment", f"€{total_investment:,.0f}")
    with col4:
        if 'FVG_Present' in df.columns:
            fvg_count = df['FVG_Present'].sum()
            st.metric("Stocks with FVG", fvg_count)
    
    # Prepare display dataframe
    display_columns = [
        'Ticker', 'Company_Name', 'Index', 'Earnings_Date', 'Days_to_Earnings', 'Close', 'Entry_Price', 
        'Stop_Loss', 'Take_Profit_1', 'Take_Profit_2', 'Target', 'CRV', 'Pattern', 'Strategy', 
        'Data_Date', 'Position_Size', 'Position_Value_EUR', 'KO_Investment_EUR'
    ]
    
    # Add FVG columns if available
    if 'FVG_Range' in df.columns:
        display_columns.insert(-2, 'FVG_Range')
        display_columns.insert(-2, 'FVG_Present')
    
    # Add EMA columns if they exist
    if 'EMA10' in df.columns:
        display_columns.insert(2, 'EMA10')
    if 'EMA20' in df.columns:
        display_columns.insert(3, 'EMA20')
    
    display_df = df[display_columns].copy()
    
    # Format currency columns
    currency_columns = ['Close', 'Entry_Price', 'Stop_Loss', 'Take_Profit_1', 'Take_Profit_2', 'Target', 'Position_Value_EUR', 'KO_Investment_EUR']
    if 'EMA10' in display_df.columns:
        currency_columns.extend(['EMA10'])
    if 'EMA20' in display_df.columns:
        currency_columns.extend(['EMA20'])
    
    for col in currency_columns:
        if col in display_df.columns:
            display_df[col] = display_df[col].apply(lambda x: f"€{x:.2f}" if pd.notna(x) else "")
    
    # Add selection checkboxes
    st.subheader("Select Stocks for Journal")
    
    # Display the table with selection capabilities
    selected_rows = []
    for idx, row in display_df.iterrows():
        col1, col2 = st.columns([0.1, 0.9])
        
        with col1:
            key = f"select_{row['Ticker']}"
            if st.checkbox("Select", key=key, label_visibility="collapsed"):
                selected_rows.append(idx)
        
        with col2:
            # Display row data in a nice format
            tp1 = row.get('Take_Profit_1', 'N/A')
            tp2 = row.get('Take_Profit_2', 'N/A')
            st.write(f"**{row['Ticker']}** - Entry: {row['Entry_Price']} | TP1: {tp1} | TP2: {tp2} | CRV: {row['CRV']} | Pattern: {row['Pattern']}")
    
    # Add selected stocks to journal
    if selected_rows and st.button("➕ Add Selected to Journal", type="secondary"):
        for idx in selected_rows:
            stock_data = df.loc[idx].to_dict()
            st.session_state.journal.add_trade(stock_data)
        st.success(f"Added {len(selected_rows)} stocks to trading journal!")
        st.rerun()
    
    # Full results table
    col1, col2 = st.columns([3, 1])
    with col1:
        st.subheader("Complete Results")
    with col2:
        if not display_df.empty:
            # Create filters info for PDF export
            filters_info = {
                'indices': st.session_state.get('last_selected_indices', ['Unknown']),
                'ema10': st.session_state.get('last_ema10_filter', False),
                'ema20': st.session_state.get('last_ema20_filter', False),
                'fvg': st.session_state.get('last_fvg_enabled', False),
                'volume_multiplier': st.session_state.get('last_volume_multiplier', 1.0)
            }
            
            # Generate PDF
            pdf_buffer = pdf_exporter.export_screening_results(df, filters_info)
            st.download_button(
                label="📄 Export as PDF",
                data=pdf_buffer.getvalue(),
                file_name=f"screening_results_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf",
                mime="application/pdf",
                use_container_width=True
            )
    
    st.dataframe(
        display_df,
        use_container_width=True,
        height=400,
        column_config={
            "Ticker": st.column_config.TextColumn("Symbol", width="small"),
            "CRV": st.column_config.NumberColumn("CRV", format="%.2f"),
            "Pattern": st.column_config.TextColumn("Pattern", width="medium"),
            "FVG_Present": st.column_config.CheckboxColumn("FVG"),
            "FVG_Range": st.column_config.TextColumn("FVG Range", width="medium"),
            "Take_Profit_1": st.column_config.TextColumn("TP1", width="small"),
            "Take_Profit_2": st.column_config.TextColumn("TP2", width="small")
        }
    )

def display_trading_journal():
    """Display the persistent trading journal"""
    st.header("📊 Trading Journal")
    
    journal_df = st.session_state.journal.get_journal_dataframe()
    
    if journal_df.empty:
        st.info("Journal is empty. Select stocks from screening results to add trades.")
        return
    
    # Journal summary
    total_trades = len(journal_df)
    open_trades = len(journal_df[journal_df['Status'] == 'Open'])
    closed_trades = len(journal_df[journal_df['Status'] == 'Closed'])
    
    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("Total Trades", total_trades)
    with col2:
        st.metric("Open", open_trades)
    with col3:
        st.metric("Closed", closed_trades)
    
    # Performance metrics for closed trades
    if closed_trades > 0:
        closed_df = journal_df[journal_df['Status'] == 'Closed']
        winning_trades = len(closed_df[closed_df['P&L'] > 0])
        win_rate = (winning_trades / closed_trades) * 100
        total_pnl = closed_df['P&L'].sum()
        
        st.subheader("Performance Metrics")
        col1, col2 = st.columns(2)
        with col1:
            st.metric("Win Rate", f"{win_rate:.1f}%")
        with col2:
            st.metric("Total P&L", f"€{total_pnl:.2f}")
    
    # Trade management
    st.subheader("Trade Management")
    
    for idx, trade in journal_df.iterrows():
        with st.expander(f"{trade['Ticker']} - {trade['Status']} - Entry: €{trade['Entry_Price']:.2f}"):
            # Manual adjustment section for new trades
            if trade['Status'] == 'Open':
                st.markdown("**📝 Adjust Trade Details:**")
                adj_col1, adj_col2, adj_col3 = st.columns(3)
                
                with adj_col1:
                    # Trade type selection
                    trade_type = st.selectbox(
                        "Trade Type",
                        options=["Direct", "KO"],
                        index=0 if trade.get('Trade_Type', 'Direct') == 'Direct' else 1,
                        key=f"trade_type_{idx}"
                    )
                
                with adj_col2:
                    # Position size adjustment
                    actual_pos_size = st.number_input(
                        "Actual Position Size",
                        min_value=1,
                        value=int(trade.get('Actual_Position_Size', trade['Position_Size'])),
                        key=f"pos_size_{idx}"
                    )
                
                with adj_col3:
                    # KO investment adjustment
                    actual_ko_investment = st.number_input(
                        "Actual KO Investment €",
                        min_value=0.0,
                        value=float(trade.get('Actual_KO_Investment', trade.get('KO_Investment_EUR', 0))),
                        step=10.0,
                        key=f"ko_inv_{idx}"
                    )
                
                if st.button(f"💾 Update Trade Details", key=f"update_{idx}"):
                    st.session_state.journal.update_trade_details(
                        idx, actual_pos_size, actual_ko_investment, trade_type
                    )
                    st.success("Trade details updated!")
                    st.rerun()
                
                st.divider()
            
            # Trade details display
            col1, col2, col3 = st.columns(3)
            
            with col1:
                st.write(f"**Entry Date:** {trade['Entry_Date']}")
                st.write(f"**Entry Price:** €{trade['Entry_Price']:.2f}")
                st.write(f"**Position Size:** {trade.get('Actual_Position_Size', trade['Position_Size'])}")
                st.write(f"**Stop Loss:** €{trade['Stop_Loss']:.2f}")
                if 'Take_Profit_1' in trade and pd.notna(trade['Take_Profit_1']):
                    st.write(f"**Take Profit 1:** €{trade['Take_Profit_1']:.2f}")
                if 'Take_Profit_2' in trade and pd.notna(trade['Take_Profit_2']):
                    st.write(f"**Take Profit 2:** €{trade['Take_Profit_2']:.2f}")
                st.write(f"**Target:** €{trade['Target']:.2f}")
            
            with col2:
                st.write(f"**Trade Type:** {trade.get('Trade_Type', 'Direct')}")
                st.write(f"**CRV:** {trade['CRV']:.2f}")
                st.write(f"**Pattern:** {trade['Pattern']}")
                if trade.get('Trade_Type') == 'KO':
                    st.write(f"**KO Investment:** €{trade.get('Actual_KO_Investment', 0):,.0f}")
                    st.write(f"**KO Leverage:** {trade.get('KO_Leverage', 1):.1f}x")
                    st.write(f"**KO Barrier:** €{trade.get('KO_Barrier', 0):.2f}")
                if 'FVG_Range' in trade and pd.notna(trade['FVG_Range']):
                    st.write(f"**FVG Range:** {trade['FVG_Range']}")
            
            with col3:
                if trade['Status'] == 'Open':
                    # Allow manual trade closing
                    st.write("**Close Trade:**")
                    exit_price = st.number_input(
                        "Exit Price",
                        min_value=0.01,
                        value=float(trade['Entry_Price']),
                        step=0.01,
                        key=f"exit_{trade['Ticker']}_{idx}"
                    )
                    
                    col_a, col_b = st.columns(2)
                    with col_a:
                        if 'Take_Profit_1' in trade and pd.notna(trade['Take_Profit_1']):
                            if st.button(f"Close at TP1", key=f"tp1_{idx}"):
                                st.session_state.journal.close_trade(idx, trade['Take_Profit_1'])
                                st.rerun()
                        if st.button(f"Close at Target", key=f"target_{idx}"):
                            st.session_state.journal.close_trade(idx, trade['Target'])
                            st.rerun()
                    with col_b:
                        if 'Take_Profit_2' in trade and pd.notna(trade['Take_Profit_2']):
                            if st.button(f"Close at TP2", key=f"tp2_{idx}"):
                                st.session_state.journal.close_trade(idx, trade['Take_Profit_2'])
                                st.rerun()
                        if st.button(f"Close at Stop", key=f"stop_{idx}"):
                            st.session_state.journal.close_trade(idx, trade['Stop_Loss'])
                            st.rerun()
                    
                    if st.button(f"Close at €{exit_price:.2f}", key=f"manual_{idx}"):
                        st.session_state.journal.close_trade(idx, exit_price)
                        st.rerun()
                else:
                    st.write(f"**Exit Date:** {trade['Exit_Date']}")
                    st.write(f"**Exit Price:** €{trade['Exit_Price']:.2f}")
                    st.write(f"**P&L:** €{trade['P&L']:.2f}")
                    st.write(f"**P&L %:** {trade.get('P&L_Pct', 0):.2f}%")
    
    # Journal export
    if not journal_df.empty:
        st.subheader("Export Journal")
        col1, col2 = st.columns(2)
        
        with col1:
            # CSV Export
            csv = journal_df.to_csv(index=False)
            st.download_button(
                label="📥 Download as CSV",
                data=csv,
                file_name=f"trading_journal_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
                mime="text/csv",
                use_container_width=True
            )
        
        with col2:
            # PDF Export
            pdf_buffer = pdf_exporter.export_trading_journal(journal_df)
            st.download_button(
                label="📄 Download as PDF",
                data=pdf_buffer.getvalue(),
                file_name=f"trading_journal_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf",
                mime="application/pdf",
                use_container_width=True
            )

if __name__ == "__main__":
    main()
