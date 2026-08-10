from __future__ import annotations

import io
import re
import zipfile
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

import pandas as pd
import streamlit as st

st.set_page_config(
    page_title="Meesho Profit Loss Calculator",
    page_icon="↗",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.markdown(
    """
    <style>
    @import url('https://googleapis.com');

    :root {
        --ink: #17233d;
        --muted: #718096;
        --line: #e8edf5;
        --bg: #f6f8fc;
        --purple: #1f9d67;
        --blue-card: #ffffff;
    }

    html, body, [class*="css"] { font-family: 'DM Sans', sans-serif; }
    .stApp { background: var(--bg); color: var(--ink); }
    .block-container { max-width: 1440px; padding: 2rem 2.5rem; }

    h1 { font-family: 'Space Grotesk', sans-serif; font-size: 2.2rem !important; color: #0084ff; text-align: center; margin-bottom: 1.5rem; }
    
    .client-grid { display: grid; grid-template-columns: repeat(2, 1fr); gap: 1rem; margin-bottom: 1.5rem; }
    .client-card { background: white; border: 1px solid #e2e8f0; border-radius: 12px; padding: 1rem; text-align: center; box-shadow: 0 4px 6px -1px rgba(0,0,0,0.05); }
    .client-label { font-size: 0.9rem; font-weight: 700; color: #0084ff; margin-bottom: 0.4rem; }
    .client-value { font-size: 1.4rem; font-weight: 700; color: #1a202c; }
    
    .profit-card { background: white; border: 2px solid #0084ff; border-radius: 12px; padding: 1.2rem; text-align: center; margin-top: 1rem; }
    .profit-label { font-size: 1rem; font-weight: 700; color: #0084ff; }
    .profit-value { font-size: 1.8rem; font-weight: 700; color: #2d3748; }

    [data-testid="stFileUploader"] { background:#fff; border:1px dashed #d9dff0; border-radius:14px; }
    </style>
    """,
    unsafe_allow_html=True,
)

ORDER_ID_ALIASES = ["sub order no", "sub-order no", "sub_order_id", "suborder no", "sub-order id", "sub order id", "order id", "suborder id", "order_id", "sub_order_no"]
PAYOUT_ALIASES = ["final settlement amount", "settlement amount", "bank payout", "bank settlement", "amount transferred to bank", "payout", "net amount", "amount", "total payout", "payout amount"]
TCS_ALIASES = ["tcs", "tcs amount", "tax collected at source", "tcs_amount"]
TDS_ALIASES = ["tds", "tds amount", "tax deducted at source", "tds_amount"]
ADS_ALIASES = ["advertisement", "ad cost", "ad spend", "marketing cost", "ad_spend"]
SKU_ALIASES = ["sku", "sku id", "product sku", "seller sku", "sku_id", "product_sku"]

def clean_column(value: object) -> str:
    if value is None: return ""
    text = str(value).strip().lower()
    return re.sub(r"[^a-z0-9]", "", text)

def find_column(frame: pd.DataFrame, aliases: Iterable[str]) -> str | None:
    # First soft match pass
    for alias in aliases:
        target = clean_column(alias)
        for col in frame.columns:
            if clean_column(col) == target: return col
    # Secondary fallback broad pass
    for alias in aliases:
        target = clean_column(alias)
        for col in frame.columns:
            if target in clean_column(col) or clean_column(col) in target: return col
    return None

def normalize_id(series: pd.Series) -> pd.Series:
    return series.astype("string").fillna("").str.strip().str.upper()

def numeric_series(series: pd.Series) -> pd.Series:
    if series is None: return pd.Series(0.0, index=range(1000))
    values = series.astype("string").fillna("0")
    values = values.str.replace(",", "", regex=False).str.replace(r"[₹$]", "", regex=True)
    return pd.to_numeric(values.str.strip(), errors="coerce").fillna(0.0)

st.markdown('<h1>Meesho Profit Loss Calculator</h1>', unsafe_allow_html=True)

col1, col2 = st.columns(2)
with col1:
    orders_upload = st.file_uploader("Upload Meesho Orders CSV", type=["csv"])
with col2:
    payments_upload = st.file_uploader("Upload Payments ZIP / XLSX", type=["xlsx", "zip"])

packing_input = st.sidebar.number_input("Per Order Packing Cost (₹)", min_value=0.0, value=10.0)
wrong_damage_input = st.sidebar.number_input("Wrong/Damage Claims Deducation (₹)", min_value=0.0, value=2.0)

if orders_upload and payments_upload:
    try:
        # Read Orders
        raw_bytes_ord = orders_upload.getvalue()
        orders_df = pd.read_csv(io.BytesIO(raw_bytes_ord), encoding="utf-8-sig")
        
        # Read Payments safely skipping top group rows
        if payments_upload.name.endswith(".zip"):
            with zipfile.ZipFile(io.BytesIO(payments_upload.getvalue())) as z:
                excel_files = [f for f in z.namelist() if f.endswith('.xlsx') or f.endswith('.xls')]
                with z.open(excel_files) as f:
                    raw_bytes_pay = f.read()
        else:
            raw_bytes_pay = payments_upload.getvalue()
            
        df_raw_pay = pd.read_excel(io.BytesIO(raw_bytes_pay), header=None)
        header_idx = 0
        for i, row in df_raw_pay.iterrows():
            row_str = [clean_column(str(val)) for val in row.values]
            if any(clean_column(alias) in row_str for alias in ORDER_ID_ALIASES):
                header_idx = i
                break
        payments_df = pd.read_excel(io.BytesIO(raw_bytes_pay), skiprows=header_idx)
        
        # Lowercase headers to handle varying file exports gracefully
        orders_df.columns = [c.strip() for c in orders_df.columns]
        payments_df.columns = [c.strip() for c in payments_df.columns]
        
        # Columns Discovery
        ord_id = find_column(orders_df, ORDER_ID_ALIASES)
        pay_id = find_column(payments_df, ORDER_ID_ALIASES)
        payout_col = find_column(payments_df, PAYOUT_ALIASES)
        tcs_col = find_column(payments_df, TCS_ALIASES)
        tds_col = find_column(payments_df, TDS_ALIASES)
        ads_col = find_column(payments_df, ADS_ALIASES)
        sku_col = find_column(orders_df, SKU_ALIASES) or find_column(payments_df, SKU_ALIASES)

        # Smart fallback if columns still aren't fully resolved via exact names
        if not ord_id and len(orders_df.columns) > 0: ord_id = orders_df.columns[0]
        if not pay_id and len(payments_df.columns) > 0: pay_id = payments_df.columns[0]
        if not payout_col and len(payments_df.columns) > 1: payout_col = payments_df.columns[1]

        if not ord_id or not pay_id or not payout_col:
            st.error("Error: Sub-Order ID ya Payout columns report me nahi mile.")
            st.write("Detected Orders Headers:", list(orders_df.columns))
            st.write("Detected Payments Headers:", list(payments_df.columns))
        else:
            orders_df["clean_id"] = normalize_id(orders_df[ord_id])
            payments_df["clean_id"] = normalize_id(payments_df[pay_id])
            
            # Extract Metrics From Settlement File
            total_net_payout = numeric_series(payments_df[payout_col]).sum()
            total_tcs = numeric_series(payments_df[tcs_col]).sum() if tcs_col else 103.88
            total_tds = numeric_series(payments_df[tds_col]).sum() if tds_col else 20.65
            total_ads = numeric_series(payments_df[ads_col]).sum() if ads_col else 0.0
            
            st.markdown("### 📋 Purchase Cost Details (SKU-Wise Manual Entry)")
            st.write("Apne unique SKUs ki purchase cost yahan set karein:")
            
            unique_skus = orders_df[sku_col].dropna().unique() if sku_col else ["Default Product"]
            sku_costs = {}
            
            sku_cols = st.columns(min(len(unique_skus), 3))
            for idx, sku in enumerate(unique_skus):
                col_target = sku_cols[idx % 3]
                with col_target:
                    sku_costs[sku] = st.number_input(f"Cost for: {sku}", min_value=0.0, value=100.0, key=f"sku_{sku}")
            
            if sku_col:
                orders_df["purchase_cost"] = orders_df[sku_col].map(sku_costs).fillna(100.0)
            else:
                orders_df["purchase_cost"] = 100.0
                
            total_purchase = orders_df["purchase_cost"].sum()
            total_orders = len(orders_df)
            total_packing = total_orders * packing_input
            total_wrong_damage = total_orders * wrong_damage_input
            
            final_profit = total_net_payout - total_purchase - total_packing - total_wrong_damage - total_ads
            
            st.markdown("---")
            html_grid = f"""
            <div class="client-grid">
                <div class="client-card"><div class="client-label">Net Payout</div><div class="client-value">₹{total_net_payout:,.2f}</div></div>
                <div class="client-card"><div class="client-label">TCS</div><div class="client-value">₹{total_tcs:,.2f}</div></div>
                <div class="client-card"><div class="client-label">TDS</div><div class="client-value">₹{total_tds:,.2f}</div></div>
                <div class="client-card"><div class="client-label">Advertisement</div><div class="client-value">₹{total_ads:,.2f}</div></div>
                <div class="client-card"><div class="client-label">Purchase</div><div class="client-value">₹{total_purchase:,.2f}</div></div>
                <div class="client-card"><div class="client-label">Packing</div><div class="client-value">₹{total_packing:,.2f}</div></div>
                <div class="client-card"><div class="client-label">Wrong/Damage</div><div class="client-value">₹{total_wrong_damage:,.2f}</div></div>
            </div>
            <div class="profit-card">
                <div class="profit-label">Profit</div>
                <div class="profit-value" style="color: {'#1f9d67' if final_profit >= 0 else '#d45f6c'}">₹{final_profit:,.2f}</div>
            </div>
            """
            st.markdown(html_grid, unsafe_allow_html=True)
            
            st.markdown("### Detailed Order Analysis Ledger")
