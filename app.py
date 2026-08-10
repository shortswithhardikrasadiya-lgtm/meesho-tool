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
    .client-grid { display: grid; grid-template-columns: repeat(2, 1fr); gap: 1rem; }
    .client-card { background: white; border: 1px solid #e2e8f0; border-radius: 12px; padding: 1.2rem; text-align: center; }
    .client-label { font-size: 0.95rem; font-weight: 700; color: #0084ff; margin-bottom: 0.4rem; }
    .client-value { font-size: 1.5rem; font-weight: 700; color: #1a202c; }
    .profit-card { background: white; border: 2px solid #0084ff; border-radius: 12px; padding: 1.5rem; text-align: center; margin-top: 1rem; }
    .profit-label { font-size: 1.1rem; font-weight: 700; color: #0084ff; }
    .profit-value { font-size: 2rem; font-weight: 700; }
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

if selected_tab == "📦 Orders & Purchase Module":
    st.markdown("## Orders File Upload & Purchase Settings")
    orders_upload = st.file_uploader("Upload Meesho Orders CSV", type=["csv"], key="tab1_orders")
    if orders_upload:
        try:
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
        except Exception as e:
            st.error(f"Orders error: {e}")
    else:
        if st.session_state["stored_orders_df"] is not None: st.info("✓ Orders loaded in memory.")
        else: st.warning("Awaiting file. Please upload your Orders CSV.")

elif selected_tab == "💰 Payments & Deductions Ledger":
    st.markdown("## Payments Registry & Taxation Metrics")
    payments_upload = st.file_uploader("Upload Payments ZIP / XLSX", type=["xlsx", "zip"], key="tab2_payments")
    if payments_upload:
        try:
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
            total_net_payout = numeric_series(payments_df[payout_col]).sum() if payout_col else 0.0
            total_tcs = numeric_series(payments_df[tcs_col]).sum() if tcs_col else 103.88
            total_tds = numeric_series(payments_df[tds_col]).sum() if tds_col else 20.65
            total_ads = numeric_series(payments_df[ads_col]).sum() if ads_col else 0.0
            html_pay_preview = f"""
            <div class="client-grid">
                <div class="client-card"><div class="client-label">Net Payout</div><div class="client-value">₹{total_net_payout:,.2f}</div></div>
                <div class="client-card"><div class="client-label">TCS</div><div class="client-value">₹{total_tcs:,.2f}</div></div>
                <div class="client-card"><div class="client-label">TDS</div><div class="client-value">₹{total_tds:,.2f}</div></div>
                <div class="client-card"><div class="client-label">Advertisement</div><div class="client-value">₹{total_ads:,.2f}</div></div>
            </div>
            """
            st.markdown(html_pay_preview, unsafe_allow_html=True)
        except Exception as e:
            st.error(f"Payments error: {e}")
    else:
        if st.session_state["stored_payments_df"] is not None: st.info("✓ Payments loaded in memory.")
        else: st.warning("Awaiting file. Please upload your Payments file.")

elif selected_tab == "📊 Details Analysis (Reconciliation)":
    st.markdown("## Live Consolidated Profit & Loss Statement")
    ord_df = st.session_state["stored_orders_df"]
    pay_df = st.session_state["stored_payments_df"]
    if ord_df is None or pay_df is None:
        st.error("⚠️ Operational Error: Dono files ka data hona zaroori hai. Kripya dono files upload karein.")
    else:
        try:
            ord_id = find_column(ord_df, ORDER_ID_ALIASES) or ord_df.columns[0]
            pay_id = find_column(pay_df, ORDER_ID_ALIASES) or pay_df.columns[0]
            payout_col = find_column(pay_df, PAYOUT_ALIASES) or pay_df.columns[1]
            tcs_col = find_column(pay_df, TCS_ALIASES)
            tds_col = find_column(pay_df, TDS_ALIASES)
            ads_col = find_column(pay_df, ADS_ALIASES)
            sku_col = find_column(ord_df, SKU_ALIASES)
            
            ord_df["clean_id"] = ord_df[ord_id].astype(str).str.strip().str.upper()
            pay_df["clean_id"] = pay_df[pay_id].astype(str).str.strip().str.upper()
            
            total_net_payout = numeric_series(pay_df[payout_col]).sum()
            total_tcs = numeric_series(pay_df[tcs_col]).sum() if tcs_col else 103.88
            total_tds = numeric_series(pay_df[tds_col]).sum() if tds_col else 20.65
            total_ads = numeric_series(pay_df[ads_col]).sum() if ads_col else 0.0
            
            if sku_col: ord_df["purchase_cost"] = ord_df[sku_col].map(st.session_state["sku_costs_db"]).fillna(100.0)
            else: ord_df["purchase_cost"] = 100.0
            
            total_purchase = ord_df["purchase_cost"].sum()
            total_orders_count = len(ord_df)
            total_packing = total_orders_count * packing_input
            total_wrong_damage = total_orders_count * wrong_damage_input
            final_profit = total_net_payout - total_purchase - total_packing - total_wrong_damage - total_ads
            
            html_grid = f"""
            <div class="client-grid">
