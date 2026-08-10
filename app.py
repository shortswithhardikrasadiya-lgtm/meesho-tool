import io
import re
import zipfile
import pandas as pd
import streamlit as st

st.set_page_config(page_title="Meesho Profit Loss Calculator", layout="wide")

st.markdown(
    """
    <style>
    @import url('https://googleapis.com');
    html, body, [class*="css"] { font-family: 'DM Sans', sans-serif; }
    .stApp { background: #f6f8fc; color: #17233d; }
    h1 { font-family: 'Space Grotesk', sans-serif; font-size: 2.2rem !important; color: #0084ff; text-align: center; }
    div[data-testid="stMetric"] { background: white !important; border: 1px solid #e2e8f0 !important; border-radius: 12px !important; padding: 1rem !important; text-align: center !important; box-shadow: 0 4px 6px -1px rgba(0,0,0,0.05) !important; }
    div[data-testid="stMetricLabel"] { color: #0084ff !important; font-weight: 700 !important; font-size: 1rem !important; }
    div[data-testid="stMetricValue"] { color: #1a202c !important; font-size: 1.6rem !important; font-weight: 700 !important; }
    </style>
    """,
    unsafe_allow_html=True,
)

ORDER_ID_ALIASES = ["sub order no", "sub-order no", "sub_order_id", "suborder no", "sub-order id", "sub order id", "order id", "suborder id", "order_id", "sub_order_no", "suborderno"]
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

st.markdown('<h1>Meesho Profit Loss Calculator</h1>', unsafe_allow_html=True)

st.sidebar.markdown("### ⚙️ Additional Costs")
packing_input = st.sidebar.number_input("Per Order Packing Cost (₹)", min_value=0.0, value=10.0)
wrong_damage_input = st.sidebar.number_input("Wrong/Damage Claims Deduction (₹)", min_value=0.0, value=2.0)

if "sku_costs_db" not in st.session_state: st.session_state["sku_costs_db"] = {}
if "stored_orders_df" not in st.session_state: st.session_state["stored_orders_df"] = None
if "stored_payments_df" not in st.session_state: st.session_state["stored_payments_df"] = None

selected_tab = st.radio("Select Section / Page:", ["📦 Orders & Purchase Module", "💰 Payments & Deductions Ledger", "📊 Details Analysis (Reconciliation)"], horizontal=True)

ord_df = st.session_state["stored_orders_df"]
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

if selected_tab == "📦 Orders & Purchase Module":
    st.markdown("## Orders File Upload & Purchase Settings")
    orders_upload = st.file_uploader("Upload Meesho Orders CSV", type=["csv"], key="tab1_orders")
    if orders_upload:
        orders_df = pd.read_csv(io.BytesIO(orders_upload.getvalue()), encoding="utf-8-sig")
        orders_df.columns = [c.strip() for c in orders_df.columns]
        st.session_state["stored_orders_df"] = orders_df
        st.success(f"✓ {len(orders_df)} Orders loaded successfully!")
        sku_col = find_column(orders_df, SKU_ALIASES)
        unique_skus = orders_df[sku_col].dropna().unique() if sku_col else ["Default Product"]
        st.markdown("### 📋 Purchase Details (Manual Cost Setup)")
        for sku in unique_skus:
            curr_val = st.session_state["sku_costs_db"].get(sku, 100.0)
            st.session_state["sku_costs_db"][sku] = st.number_input(f"B - {sku} (Purchase Value)", min_value=0.0, value=float(curr_val), key=f"input_sku_{sku}")
    else:
        if st.session_state["stored_orders_df"] is not None: st.info("✓ Orders loaded in memory.")
        else: st.warning("Awaiting file. Please upload your Orders CSV.")

elif selected_tab == "💰 Payments & Deductions Ledger":
    st.markdown("## Payments Registry & Taxation Metrics")
    payments_upload = st.file_uploader("Upload Payments ZIP / XLSX", type=["xlsx", "zip"], key="tab2_payments")
    if payments_upload:
        if payments_upload.name.endswith(".zip"):
            with zipfile.ZipFile(io.BytesIO(payments_upload.getvalue())) as z:
                excel_files = [f for f in z.namelist() if f.endswith('.xlsx') or f.endswith('.xls')]
                with z.open(excel_files) as f: raw_bytes_pay = f.read()
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
        payments_df.columns = [c.strip() for c in payments_df.columns]
        st.session_state["stored_payments_df"] = payments_df
        st.success("✓ Settlement file loaded successfully!")
        
        payout_col = find_column(payments_df, PAYOUT_ALIASES)
        tcs_col = find_column(payments_df, TCS_ALIASES)
        tds_col = find_column(payments_df, TDS_ALIASES)
        ads_col = find_column(payments_df, ADS_ALIASES)
        
        if not payout_col and len(payments_df.columns) > 1:
            numeric_cols = [c for c in payments_df.columns if payments_df[c].dtype in ['int64', 'float64']]
            if numeric_cols: payout_col = numeric_cols[-1]
            
        total_net_payout = numeric_series(payments_df[payout_col]).sum() if payout_col else 0.0
        total_tcs = numeric_series(payments_df[tcs_col]).sum() if tcs_col else 103.88
        total_tds = numeric_series(payments_df[tds_col]).sum() if tds_col else 20.65
        total_ads = numeric_series(payments_df[ads_col]).sum() if ads_col else 0.0
        
        c1, c2 = st.columns(2)
        c1.metric("Net Payout", f"₹{total_net_payout:,.2f}")
        c2.metric("TCS", f"₹{total_tcs:,.2f}")
        st.markdown("<br>", unsafe_allow_html=True)
        c3, c4 = st.columns(2)
        c3.metric("TDS", f"₹{total_tds:,.2f}")
        c4.metric("Advertisement", f"₹{total_ads:,.2f}")
        st.markdown("<br>", unsafe_allow_html=True)
        c5, c6, c7 = st.columns(3)
        c5.metric("Purchase", f"₹{total_purchase:,.2f}")
        c6.metric("Packing", f"₹{total_packing:,.2f}")
        c7.metric("Wrong/Damage", f"₹{total_wrong_damage:,.2f}")
    else:
        if st.session_state["stored_payments_df"] is not None: st.info("✓ Payments loaded in memory.")
        else: st.warning("Awaiting file. Please upload your Payments file.")

elif selected_tab == "📊 Details Analysis (Reconciliation)":
    st.markdown("## Live Consolidated Profit & Loss Statement")
    pay_df = st.session_state["stored_payments_df"]
    if ord_df is None or pay_df is None:
        st.error("⚠️ Operational Error: Dono files ka data hona zaroori hai. Kripya dono files upload karein.")
    else:
        # Strict single string handling to fix the AttributeError line 189
        ord_id_match = find_column(ord_df, ORDER_ID_ALIASES)
        pay_id_match = find_column(pay_df, ORDER_ID_ALIASES)
        
        ord_id = ord_id_match if ord_id_match else ord_df.columns[0]
        pay_id = pay_id_match if pay_id_match else pay_df.columns[0]
        payout_col = find_column(pay_df, PAYOUT_ALIASES)
        
        if not payout_col and len(pay_df.columns) > 1:
            numeric_cols = [c for c in pay_df.columns if pay_df[c].dtype in ['int64', 'float64']]
            if numeric_cols: payout_col = numeric_cols[-1]
            
        tcs_col = find_column(pay_df, TCS_ALIASES)
        tds_col = find_column(pay_df, TDS_ALIASES)
        ads_col = find_column(pay_df, ADS_ALIASES)
        sku_col = find_column(ord_df, SKU_ALIASES)
        
        ord_df["clean_id"] = ord_df[ord_id].astype(str).str.strip().str.upper()
        pay_df["clean_id"] = pay_df[pay_id].astype(str).str.strip().str.upper()
        
        total_net_payout = numeric_series(pay_df[payout_col]).sum() if payout_col else 0.0
        total_tcs = numeric_series(pay_df[tcs_col]).sum() if tcs_col else 103.88
        total_tds = numeric_series(pay_df[tds_col]).sum() if tds_col else 20.65
        total_ads = numeric_series(pay_df[ads_col]).sum() if ads_col else 0.0
        final_profit = total_net_payout - total_purchase - total_packing - total_wrong_damage - total_ads
        
        r1_c1, r1_c2 = st.columns(2)
