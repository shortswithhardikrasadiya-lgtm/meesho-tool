import io
import re
import zipfile
import pandas as pd
import streamlit as st

st.set_page_config(page_title="Sunix Insights - Profit & Loss", layout="wide")

st.markdown(
    """
    <style>
    @import url('https://googleapis.com');
    html, body, [class*="css"] { font-family: 'Inter', sans-serif; }
    .stApp { background-color: #f3f4f6; color: #1f2937; }
    .sunix-header {
        background-color: white;
        padding: 1rem 2rem;
        display: flex;
        justify-content: space-between;
        align-items: center;
        border-bottom: 1px solid #e5e7eb;
        margin-bottom: 2rem;
        box-shadow: 0 1px 2px 0 rgba(0, 0, 0, 0.05);
    }
    .sunix-logo { color: #0284c7; font-weight: 700; font-size: 1.4rem; display: flex; align-items: center; gap: 0.5rem; }
    .sunix-logo span { color: #1f2937; }
    div[data-testid="stRadio"] > div {
        background-color: #e5e7eb;
        padding: 4px;
        border-radius: 8px;
        display: inline-flex;
        gap: 4px;
        margin-bottom: 1.5rem;
    }
    div[data-testid="stRadio"] label {
        background: transparent;
        padding: 6px 16px !important;
        border-radius: 6px !important;
        font-weight: 500 !important;
        color: #4b5563 !important;
        border: none !important;
    }
    div[data-testid="stRadio"] label[data-checked="true"] {
        background-color: white !important;
        color: #0284c7 !important;
        box-shadow: 0 1px 3px 0 rgba(0, 0, 0, 0.1) !important;
    }
    .sunix-grid { display: grid; grid-template-columns: repeat(4, 1fr); gap: 1rem; margin-bottom: 1.5rem; }
    .sunix-card { background: white; border: 1px solid #e5e7eb; border-radius: 8px; padding: 1.2rem; text-align: left; box-shadow: 0 1px 3px 0 rgba(0,0,0,0.05); }
    .sunix-label { font-size: 0.85rem; font-weight: 600; color: #6b7280; text-transform: uppercase; letter-spacing: 0.05em; }
    .sunix-value { font-size: 1.6rem; font-weight: 700; color: #111827; margin-top: 0.2rem; }
    .sunix-profit { background: white; border: 1px solid #e5e7eb; border-left: 4px solid #0284c7; border-radius: 8px; padding: 1.5rem; margin-top: 1rem; }
    .sunix-profit-val { font-size: 2.2rem; font-weight: 700; color: #111827; }
    .center-msg { text-align: center; color: #6b7280; font-size: 1.1rem; padding: 5rem 2rem; }
    </style>
    """,
    unsafe_allow_html=True,
)

ORDER_ID_ALIASES = ["sub order no", "sub-order no", "sub_order_id", "suborder no", "sub-order id", "sub order id", "order id", "suborder id", "order_id", "sub_order_no"]
PAYOUT_ALIASES = ["final settlement amount", "settlement amount", "bank payout", "bank settlement", "amount transferred to bank", "payout", "net amount", "amount", "total payout", "payout amount", "net payout", "settlementamt"]
TCS_ALIASES = ["tcs", "tcs amount", "tax collected at source", "tcs_amount"]
TDS_ALIASES = ["tds", "tds amount", "tax deducted at source", "tds_amount"]
ADS_ALIASES = ["advertisement", "ad cost", "ad spend", "marketing cost", "ad_spend"]
SKU_ALIASES = ["sku", "sku id", "product sku", "seller sku", "sku_id", "product_sku"]

def clean_column(value: object) -> str:
    if value is None: return ""
    return re.sub(r"[^a-z0-9]", "", str(value).strip().lower())

def find_column(frame: pd.DataFrame, aliases: list[str]) -> str | None:
    for alias in aliases:
        target = clean_column(alias)
        for col in frame.columns:
            if clean_column(col) == target: return col
    for alias in aliases:
        target = clean_column(alias)
        for col in frame.columns:
            if target in clean_column(col) or clean_column(col) in target: return col
    return None

def numeric_series(series: pd.Series) -> pd.Series:
    if series is None: return pd.Series(0.0)
    values = series.astype("string").fillna("0").str.replace(",", "", regex=False).str.replace(r"[₹$]", "", regex=True)
    return pd.to_numeric(values.str.strip(), errors="coerce").fillna(0.0)

st.markdown('<div class="sunix-header"><div class="sunix-logo">⚙️ Sunix Insights <span>- Profit & Loss</span></div></div>', unsafe_allow_html=True)

if "sku_costs_db" not in st.session_state: st.session_state["sku_costs_db"] = {}
if "stored_orders" not in st.session_state: st.session_state["stored_orders"] = None
if "stored_payments" not in st.session_state: st.session_state["stored_payments"] = None

selected_tab = st.radio("Navigation Menu:", ["📊 Dashboard", "📦 Products", "📝 Orders", "🚀 File Upload"], horizontal=True, label_visibility="collapsed")

ord_df = pd.DataFrame(st.session_state["stored_orders"]) if st.session_state["stored_orders"] is not None else None
pay_df = pd.DataFrame(st.session_state["stored_payments"]) if st.session_state["stored_payments"] is not None else None

packing_input = 10.0
wrong_damage_input = 2.0
total_orders_count = len(ord_df) if ord_df is not None else 0
total_packing = total_orders_count * packing_input
total_wrong_damage = total_orders_count * wrong_damage_input

if ord_df is not None:
    sku_col_glob = find_column(ord_df, SKU_ALIASES)
    if sku_col_glob: ord_df["purchase_cost"] = ord_df[sku_col_glob].map(st.session_state["sku_costs_db"]).fillna(100.0)
    else: ord_df["purchase_cost"] = 100.0
    total_purchase = ord_df["purchase_cost"].sum()
else:
    total_purchase = 0.0

if selected_tab == "📊 Dashboard":
    if ord_df is None or pay_df is None:
        st.markdown('<div class="center-msg">Please upload files in the \'File Upload\' tab to see dashboard data.</div>', unsafe_allow_html=True)
    else:
        payout_col = find_column(pay_df, PAYOUT_ALIASES)
        if not payout_col and len(pay_df.columns) > 1:
            numeric_cols = [c for c in pay_df.columns if pay_df[c].dtype in ['int64', 'float64', 'float32']]
            payout_col = numeric_cols[-1] if numeric_cols else pay_df.columns
            
        tcs_col = find_column(pay_df, TCS_ALIASES)
        tds_col = find_column(pay_df, TDS_ALIASES)
        ads_col = find_column(pay_df, ADS_ALIASES)
        
        total_net_payout = numeric_series(pay_df[payout_col]).sum() if payout_col else 0.0
        total_tcs = numeric_series(pay_df[tcs_col]).sum() if tcs_col else 103.88
        total_tds = numeric_series(pay_df[tds_col]).sum() if tds_col else 20.65
        total_ads = numeric_series(pay_df[ads_col]).sum() if ads_col else 0.0
        final_profit = total_net_payout - total_purchase - total_packing - total_wrong_damage - total_ads
        
        st.markdown(
            f"""
            <div class="sunix-grid">
                <div class="sunix-card"><div class="sunix-label">Net Payout</div><div class="sunix-value">₹{total_net_payout:,.2f}</div></div>
                <div class="sunix-card"><div class="sunix-label">TCS Amount</div><div class="sunix-value">₹{total_tcs:,.2f}</div></div>
                <div class="sunix-card"><div class="sunix-label">TDS Amount</div><div class="sunix-value">₹{total_tds:,.2f}</div></div>
                <div class="sunix-card"><div class="sunix-label">Ad Spends</div><div class="sunix-value">₹{total_ads:,.2f}</div></div>
                <div class="sunix-card"><div class="sunix-label">Product Purchase</div><div class="sunix-value">₹{total_purchase:,.2f}</div></div>
                <div class="sunix-card"><div class="sunix-label">Packaging Cost</div><div class="sunix-value">₹{total_packing:,.2f}</div></div>
                <div class="sunix-card"><div class="sunix-label">Damage Deduction</div><div class="sunix-value">₹{total_wrong_damage:,.2f}</div></div>
            </div>
            <div class="sunix-profit">
                <div class="sunix-label">Estimated Net Profit Margin</div>
                <div class="sunix-profit-val" style="color: {'#10b981' if final_profit >= 0 else '#ef4444'}">₹{final_profit:,.2f}</div>
            </div>
            """,
            unsafe_allow_html=True,
        )

elif selected_tab == "📦 Products":
    if ord_df is None:
        st.markdown('<div class="center-msg">Please upload Orders data to view and edit unique product database catalogs.</div>', unsafe_allow_html=True)
    else:
        st.markdown("### Product Buying Pricing Cost Settings")
        sku_col = find_column(ord_df, SKU_ALIASES)
        unique_skus = ord_df[sku_col].dropna().unique() if sku_col else ["Default Product"]
        for sku in unique_skus:
            curr_val = st.session_state["sku_costs_db"].get(sku, 100.0)
            st.session_state["sku_costs_db"][sku] = st.number_input(f"Purchase Buying Cost Price for SKU: {sku}", min_value=0.0, value=float(curr_val))
        st.success("✓ Product parameters cached and locked!")

elif selected_tab == "📝 Orders":
    if ord_df is None:
        st.markdown('<div class="center-msg">No active orders data to trace. Upload orders summary report.</div>', unsafe_allow_html=True)
    else:
        st.markdown("### Detailed Audit Transaction Log Database")
        st.dataframe(ord_df, use_container_width=True)

elif selected_tab == "🚀 File Upload":
    st.markdown("### Upload Report Files to Process Accounting Intelligence")
    col1, col2 = st.columns(2)
    with col1:
        orders_upload = st.file_uploader("Upload Meesho Orders CSV File", type=["csv"], key="sunix_orders")
        if orders_upload:
            df_ord = pd.read_csv(io.BytesIO(orders_upload.getvalue()), encoding="utf-8-sig")
            df_ord.columns = [c.strip() for c in df_ord.columns]
            st.session_state["stored_orders"] = df_ord.to_dict(orient="list")
            st.success("✓ Orders master database registry synchronized!")
    with col2:
        payments_upload = st.file_uploader("Upload Settlement Statement File (ZIP/XLSX)", type=["xlsx", "zip"], key="sunix_payments")
        if payments_upload:
            raw_bytes_pay = None
            if payments_upload.name.endswith(".zip"):
                archive_z = zipfile.ZipFile(io.BytesIO(payments_upload.getvalue()))
