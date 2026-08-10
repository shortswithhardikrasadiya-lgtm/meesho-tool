
import io
import re
import zipfile
from datetime import datetime

import pandas as pd
import streamlit as st

# ---------------------------------------------------------
# PAGE
# ---------------------------------------------------------
st.set_page_config(
    page_title="Sunix Insights - Meesho Profit & Loss",
    page_icon="☀️",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# ---------------------------------------------------------
# CSS - Sunix Insights style UI
# ---------------------------------------------------------
st.markdown(
    """
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');

    html, body, [class*="css"] {
        font-family: 'Inter', sans-serif;
    }

    .stApp {
        background: #eaf3f7;
        color: #18212b;
    }

    [data-testid="stHeader"] {
        background: rgba(255,255,255,0);
    }

    .block-container {
        max-width: 1240px;
        padding-top: 1.2rem;
        padding-bottom: 4.5rem;
    }

    .topbar {
        background: #ffffff;
        border-bottom: 1px solid #cbdde4;
        box-shadow: 0 4px 14px rgba(20, 55, 70, .10);
        margin: -1.2rem -2rem 1.5rem -2rem;
        padding: .72rem 2.2rem;
        display: flex;
        align-items: center;
        justify-content: space-between;
        min-height: 64px;
    }

    .brand {
        display: flex;
        align-items: center;
        gap: .55rem;
        font-size: 1.15rem;
        font-weight: 700;
        color: #121820;
    }

    .brand-icon {
        color: #0099a6;
        font-size: 1.55rem;
        line-height: 1;
    }

    .page-card {
        background: #ffffff;
        border: 1px solid #bfd5dd;
        border-radius: 9px;
        box-shadow: 0 8px 18px rgba(30, 65, 80, .08);
        padding: 1rem;
        margin-bottom: 1rem;
    }

    .section-title {
        font-size: 1.05rem;
        font-weight: 700;
        margin-bottom: .25rem;
        color: #151c24;
    }

    .muted {
        color: #607487;
        font-size: .86rem;
    }

    .metric-grid {
        display: grid;
        grid-template-columns: repeat(4, 1fr);
        gap: 12px;
        margin: 12px 0;
    }

    .metric {
        background: #ffffff;
        border: 1px solid #c7dbe2;
        border-radius: 9px;
        padding: 14px 16px;
        min-height: 88px;
    }

    .metric-label {
        color: #607487;
        font-size: .76rem;
        font-weight: 600;
        text-transform: uppercase;
        letter-spacing: .04em;
    }

    .metric-value {
        color: #17202a;
        font-size: 1.38rem;
        font-weight: 700;
        margin-top: 5px;
    }

    .profit-card {
        background: #ffffff;
        border: 1px solid #c7dbe2;
        border-left: 5px solid #0099a6;
        border-radius: 9px;
        padding: 17px;
        margin: 12px 0;
    }

    .profit-value {
        font-size: 2rem;
        font-weight: 700;
    }

    .upload-box {
        background: #f9fbfc;
        border: 2px dashed #b7d2da;
        border-radius: 9px;
        padding: 16px;
    }

    .empty {
        text-align: center;
        color: #607487;
        padding: 80px 20px;
        font-size: 1rem;
    }

    .small-note {
        font-size: .78rem;
        color: #607487;
    }

    footer {
        visibility: hidden;
    }

    @media (max-width: 900px) {
        .metric-grid { grid-template-columns: repeat(2, 1fr); }
    }

    @media (max-width: 600px) {
        .metric-grid { grid-template-columns: 1fr; }
    }
    </style>
    """,
    unsafe_allow_html=True,
)

# ---------------------------------------------------------
# ALIASES
# ---------------------------------------------------------
ORDER_ID_ALIASES = [
    "sub order no", "sub-order no", "sub_order_id", "suborder no",
    "sub-order id", "sub order id", "order id", "suborder id",
    "order_id", "sub_order_no"
]

PAYOUT_ALIASES = [
    "final settlement amount", "settlement amount", "bank payout",
    "bank settlement", "amount transferred to bank", "payout",
    "net amount", "amount", "total payout", "payout amount",
    "net payout", "settlementamt"
]

TCS_ALIASES = ["tcs", "tcs amount", "tax collected at source", "tcs_amount"]
TDS_ALIASES = ["tds", "tds amount", "tax deducted at source", "tds_amount"]
ADS_ALIASES = ["advertisement", "ad cost", "ad spend", "marketing cost", "ad_spend"]
SKU_ALIASES = ["sku", "sku id", "product sku", "seller sku", "sku_id", "product_sku"]
STATUS_ALIASES = ["order status", "status", "order_status"]
PAYMENT_STATUS_ALIASES = ["payment status", "payment_status", "settlement status"]
PAYMENT_DATE_ALIASES = ["payment date", "payment_date", "settlement date", "settlement_date"]

# ---------------------------------------------------------
# HELPERS
# ---------------------------------------------------------
def clean_column(value) -> str:
    if value is None:
        return ""
    return re.sub(r"[^a-z0-9]", "", str(value).strip().lower())


def find_column(frame: pd.DataFrame, aliases) -> str | None:
    if frame is None or frame.empty:
        return None

    cleaned = {col: clean_column(col) for col in frame.columns}

    # Exact normalized match
    for alias in aliases:
        target = clean_column(alias)
        for col, value in cleaned.items():
            if value == target:
                return col

    # Partial normalized match
    for alias in aliases:
        target = clean_column(alias)
        if not target:
            continue
        for col, value in cleaned.items():
            if target in value or value in target:
                return col

    return None


def numeric_series(series) -> pd.Series:
    if series is None:
        return pd.Series(dtype="float64")
    values = (
        series.astype("string")
        .fillna("0")
        .str.replace(",", "", regex=False)
        .str.replace(r"[₹$]", "", regex=True)
        .str.replace(r"\((.*?)\)", r"-\1", regex=True)
    )
    return pd.to_numeric(values.str.strip(), errors="coerce").fillna(0.0)


def money(value) -> str:
    try:
        return f"₹{float(value):,.2f}"
    except Exception:
        return "₹0.00"


def safe_df(value):
    if value is None:
        return None
    return pd.DataFrame(value)


def detect_file_type(name: str) -> str:
    lower = name.lower()
    if lower.endswith(".csv"):
        return "csv"
    if lower.endswith(".xlsx") or lower.endswith(".xls"):
        return "excel"
    return "unknown"


def read_tabular_bytes(data: bytes, name: str):
    kind = detect_file_type(name)

    try:
        if kind == "csv":
            try:
                return pd.read_csv(io.BytesIO(data), encoding="utf-8-sig")
            except UnicodeDecodeError:
                return pd.read_csv(io.BytesIO(data), encoding="latin1")

        if kind == "excel":
            return pd.read_excel(io.BytesIO(data))

    except Exception as exc:
        st.warning(f"Could not read {name}: {exc}")

    return None


def extract_payment_zip(uploaded_file):
    """Read CSV/XLSX files found inside one or more payment ZIP files."""
    frames = []

    try:
        with zipfile.ZipFile(io.BytesIO(uploaded_file.getvalue())) as z:
            for member in z.namelist():
                if member.endswith("/") or member.startswith("__MACOSX/"):
                    continue

                name = member.split("/")[-1]
                kind = detect_file_type(name)
                if kind == "unknown":
                    continue

                try:
                    raw = z.read(member)
                    df = read_tabular_bytes(raw, name)
                    if df is not None and not df.empty:
                        df.columns = [str(c).strip() for c in df.columns]
                        df["_source_file"] = name
                        frames.append(df)
                except Exception:
                    continue
    except zipfile.BadZipFile:
        st.error(f"{uploaded_file.name} is not a valid ZIP file.")
    except Exception as exc:
        st.error(f"Could not process {uploaded_file.name}: {exc}")

    if not frames:
        return None

    return pd.concat(frames, ignore_index=True, sort=False)


def process_payment_files(files):
    frames = []

    for uploaded in files or []:
        if uploaded.name.lower().endswith(".zip"):
            df = extract_payment_zip(uploaded)
        else:
            df = read_tabular_bytes(uploaded.getvalue(), uploaded.name)

        if df is not None and not df.empty:
            frames.append(df)

    if not frames:
        return None

    return pd.concat(frames, ignore_index=True, sort=False)


def serialize_df(df):
    return df.to_dict(orient="list") if df is not None else None


def export_csv(df):
    return df.to_csv(index=False).encode("utf-8-sig")


def build_financial_detail(orders, payments):
    if orders is None:
        return pd.DataFrame()

    result = orders.copy()

    if payments is None or payments.empty:
        result["Payment Payout"] = 0.0
        result["TCS"] = 0.0
        result["TDS"] = 0.0
        result["Ad Spend"] = 0.0
        return result

    order_id_orders = find_column(result, ORDER_ID_ALIASES)
    order_id_payments = find_column(payments, ORDER_ID_ALIASES)
    payout_col = find_column(payments, PAYOUT_ALIASES)
    tcs_col = find_column(payments, TCS_ALIASES)
    tds_col = find_column(payments, TDS_ALIASES)
    ads_col = find_column(payments, ADS_ALIASES)

    if not order_id_orders or not order_id_payments:
        result["Payment Payout"] = 0.0
        result["TCS"] = numeric_series(payments[tcs_col]).sum() if tcs_col else 0.0
        result["TDS"] = numeric_series(payments[tds_col]).sum() if tds_col else 0.0
        result["Ad Spend"] = numeric_series(payments[ads_col]).sum() if ads_col else 0.0
        return result

    p = payments.copy()
    p["_join_order_id"] = p[order_id_payments].astype("string").fillna("").str.strip()
    result["_join_order_id"] = result[order_id_orders].astype("string").fillna("").str.strip()

    aggregations = {}
    if payout_col:
        p["_payout_num"] = numeric_series(p[payout_col])
        aggregations["_payout_num"] = "sum"
    if tcs_col:
        p["_tcs_num"] = numeric_series(p[tcs_col])
        aggregations["_tcs_num"] = "sum"
    if tds_col:
        p["_tds_num"] = numeric_series(p[tds_col])
        aggregations["_tds_num"] = "sum"
    if ads_col:
        p["_ads_num"] = numeric_series(p[ads_col])
        aggregations["_ads_num"] = "sum"

    if aggregations:
        grouped = p.groupby("_join_order_id", dropna=False).agg(aggregations).reset_index()
        result = result.merge(grouped, on="_join_order_id", how="left")

    rename = {
        "_payout_num": "Payment Payout",
        "_tcs_num": "TCS",
        "_tds_num": "TDS",
        "_ads_num": "Ad Spend",
    }
    for old, new in rename.items():
        if old in result.columns:
            result[new] = pd.to_numeric(result[old], errors="coerce").fillna(0)
            result.drop(columns=[old], inplace=True)
        elif new not in result.columns:
            result[new] = 0.0

    result.drop(columns=["_join_order_id"], inplace=True, errors="ignore")
    return result


# ---------------------------------------------------------
# SESSION STATE
# ---------------------------------------------------------
defaults = {
    "stored_orders": None,
    "stored_payments": None,
    "sku_costs_db": {},
    "sku_packaging_db": {},
    "sku_gst_db": {},
    "last_processed": None,
}

for key, default in defaults.items():
    if key not in st.session_state:
        st.session_state[key] = default

# ---------------------------------------------------------
# HEADER
# ---------------------------------------------------------
st.markdown(
    """
    <div class="topbar">
        <div class="brand">
            <span class="brand-icon">☀</span>
            <span>Sunix Insights</span>
        </div>
    </div>
    """,
    unsafe_allow_html=True,
)

# ---------------------------------------------------------
# NAVIGATION
# ---------------------------------------------------------
nav_items = ["Dashboard", "Products", "Orders", "File Upload"]
selected = st.radio(
    "Navigation",
    nav_items,
    horizontal=True,
    label_visibility="collapsed",
    key="main_navigation",
)

orders = safe_df(st.session_state["stored_orders"])
payments = safe_df(st.session_state["stored_payments"])

# ---------------------------------------------------------
# DASHBOARD
# ---------------------------------------------------------
if selected == "Dashboard":
    st.markdown('<div class="page-card">', unsafe_allow_html=True)

    if orders is None or payments is None:
        st.markdown(
            '<div class="empty">Please upload files in the "File Upload" tab to see dashboard data.</div>',
            unsafe_allow_html=True,
        )
    else:
        payout_col = find_column(payments, PAYOUT_ALIASES)
        tcs_col = find_column(payments, TCS_ALIASES)
        tds_col = find_column(payments, TDS_ALIASES)
        ads_col = find_column(payments, ADS_ALIASES)

        total_net_payout = numeric_series(payments[payout_col]).sum() if payout_col else 0.0
        total_tcs = numeric_series(payments[tcs_col]).sum() if tcs_col else 0.0
        total_tds = numeric_series(payments[tds_col]).sum() if tds_col else 0.0
        total_ads = numeric_series(payments[ads_col]).sum() if ads_col else 0.0

        sku_col = find_column(orders, SKU_ALIASES)
        if sku_col:
            purchase_cost = orders[sku_col].map(st.session_state["sku_costs_db"]).fillna(0.0)
            packaging_cost = orders[sku_col].map(st.session_state["sku_packaging_db"]).fillna(0.0)
        else:
            purchase_cost = pd.Series(0.0, index=orders.index)
            packaging_cost = pd.Series(0.0, index=orders.index)

        total_purchase = purchase_cost.sum()
        total_packaging = packaging_cost.sum()
        total_orders = len(orders)

        status_col = find_column(orders, STATUS_ALIASES)
        status_values = orders[status_col].astype("string").str.lower() if status_col else pd.Series("", index=orders.index)

        delivered = int(status_values.str.contains("deliver", na=False).sum())
        returned = int(status_values.str.contains("return|rto", regex=True, na=False).sum())
        cancelled = int(status_values.str.contains("cancel", na=False).sum())

        # Keep the same basic profit model as the user's original app,
        # but make the configurable product costs default to zero.
        final_profit = total_net_payout - total_purchase - total_packaging - total_ads
        margin = (final_profit / total_net_payout * 100) if total_net_payout else 0.0

        st.markdown(
            '<div class="section-title">Dashboard</div>'
            '<div class="muted">Meesho order, payment and profit overview.</div>',
            unsafe_allow_html=True,
        )

        st.markdown(
            f"""
            <div class="metric-grid">
                <div class="metric"><div class="metric-label">Net Payout</div><div class="metric-value">{money(total_net_payout)}</div></div>
                <div class="metric"><div class="metric-label">Total Orders</div><div class="metric-value">{total_orders:,}</div></div>
                <div class="metric"><div class="metric-label">TCS Amount</div><div class="metric-value">{money(total_tcs)}</div></div>
                <div class="metric"><div class="metric-label">TDS Amount</div><div class="metric-value">{money(total_tds)}</div></div>
                <div class="metric"><div class="metric-label">Ad Spends</div><div class="metric-value">{money(total_ads)}</div></div>
                <div class="metric"><div class="metric-label">Product Purchase</div><div class="metric-value">{money(total_purchase)}</div></div>
                <div class="metric"><div class="metric-label">Packaging</div><div class="metric-value">{money(total_packaging)}</div></div>
                <div class="metric"><div class="metric-label">Delivered / Returned</div><div class="metric-value">{delivered:,} / {returned:,}</div></div>
            </div>

            <div class="profit-card">
                <div class="metric-label">Estimated Net Profit</div>
                <div class="profit-value" style="color:{'#0f9d78' if final_profit >= 0 else '#dc3545'}">
                    {money(final_profit)}
                </div>
                <div class="muted">Estimated margin: {margin:.2f}% &nbsp; • &nbsp; Cancelled: {cancelled:,}</div>
            </div>
            """,
            unsafe_allow_html=True,
        )

        st.markdown("#### Order Status Summary")
        if status_col:
            counts = (
                orders[status_col]
                .astype("string")
                .fillna("Unknown")
                .value_counts()
                .rename_axis("Order Status")
                .reset_index(name="Orders")
            )
            st.bar_chart(counts.set_index("Order Status"))
        else:
            st.info("Order status column was not detected in the uploaded file.")

    st.markdown("</div>", unsafe_allow_html=True)


# ---------------------------------------------------------
# PRODUCTS
# ---------------------------------------------------------
elif selected == "Products":
    st.markdown('<div class="page-card">', unsafe_allow_html=True)

    st.markdown(
        '<div class="section-title">Products Management</div>'
        '<div class="muted">Enter Cost & Packaging. GST can be stored per SKU. Use Update All to refresh calculations.</div>',
        unsafe_allow_html=True,
    )

    if orders is None:
        st.markdown(
            '<div class="empty">Please upload an Order CSV first to create the unique product list.</div>',
            unsafe_allow_html=True,
        )
    else:
        sku_col = find_column(orders, SKU_ALIASES)

        if not sku_col:
            st.warning("SKU column was not detected in the Order CSV.")
        else:
            skus = (
                orders[sku_col]
                .dropna()
                .astype(str)
                .str.strip()
            )
            skus = skus[skus != ""].drop_duplicates().tolist()

            if not skus:
                st.info("No SKU values were found.")
            else:
                c1, c2 = st.columns([1, 1])
                with c1:
                    bulk_packaging = st.number_input(
                        "Bulk Set Packaging Cost (₹)",
                        min_value=0.0,
                        value=0.0,
                        step=0.50,
                        key="bulk_packaging_input",
                    )
                with c2:
                    st.write("")
                    st.write("")
                    if st.button("Apply to All Products", use_container_width=True):
                        for sku in skus:
                            st.session_state["sku_packaging_db"][sku] = float(bulk_packaging)
                        st.success("Packaging cost applied to all products.")

                rows = []
                for sku in skus:
                    cost = float(st.session_state["sku_costs_db"].get(sku, 0.0))
                    packaging = float(st.session_state["sku_packaging_db"].get(sku, 0.0))
                    gst = float(st.session_state["sku_gst_db"].get(sku, 3.0))
                    final_price = (cost + packaging) * (1 + gst / 100)

                    rows.append(
                        {
                            "S.NO": len(rows) + 1,
                            "SKU": sku,
                            "COST (₹)": cost,
                            "PACKAGING (₹)": packaging,
                            "GST (%)": gst,
                            "FINAL PRICE": final_price,
                        }
                    )

                product_df = pd.DataFrame(rows)

                edited = st.data_editor(
                    product_df,
                    use_container_width=True,
                    hide_index=True,
                    num_rows="fixed",
                    column_config={
                        "S.NO": st.column_config.NumberColumn(disabled=True),
                        "SKU": st.column_config.TextColumn(disabled=True),
                        "COST (₹)": st.column_config.NumberColumn(min_value=0.0, step=0.50),
                        "PACKAGING (₹)": st.column_config.NumberColumn(min_value=0.0, step=0.50),
                        "GST (%)": st.column_config.NumberColumn(min_value=0.0, max_value=100.0, step=0.5),
                        "FINAL PRICE": st.column_config.NumberColumn(disabled=True, format="₹%.2f"),
                    },
                    key="product_editor",
                )

                if st.button("Update All Product Costs & Packaging in Dashboard", type="primary"):
                    for _, row in edited.iterrows():
                        sku = str(row["SKU"])
                        st.session_state["sku_costs_db"][sku] = float(row["COST (₹)"] or 0)
                        st.session_state["sku_packaging_db"][sku] = float(row["PACKAGING (₹)"] or 0)
                        st.session_state["sku_gst_db"][sku] = float(row["GST (%)"] or 0)

                    st.success("✓ Product costs, packaging and GST updated.")
                    st.rerun()

    st.markdown("</div>", unsafe_allow_html=True)


# ---------------------------------------------------------
# ORDERS
# ---------------------------------------------------------
elif selected == "Orders":
    st.markdown('<div class="page-card">', unsafe_allow_html=True)

    st.markdown(
        '<div class="section-title">Orders Details</div>'
        '<div class="muted">Data from Order CSVs, enriched by Payment files.</div>',
        unsafe_allow_html=True,
    )

    if orders is None:
        st.markdown(
            '<div class="empty">No orders match the current filters, or no orders have been processed yet.</div>',
            unsafe_allow_html=True,
        )
    else:
        working = orders.copy()

        # Add financial columns
        financial = build_financial_detail(orders, payments)
        for col in ["Payment Payout", "TCS", "TDS", "Ad Spend"]:
            if col in financial.columns:
                working[col] = financial[col].values

        order_id_col = find_column(working, ORDER_ID_ALIASES)
        status_col = find_column(working, STATUS_ALIASES)
        payment_status_col = find_column(working, PAYMENT_STATUS_ALIASES)
        payment_date_col = find_column(working, PAYMENT_DATE_ALIASES)

        f1, f2, f3, f4, f5 = st.columns([1.35, 1, 1, 1, 1])

        with f1:
            order_search = st.text_input("Filter by Sub Order ID", placeholder="Enter Sub Order ID...")

        with f2:
            statuses = ["All Order Statuses"]
            if status_col:
                statuses += sorted(working[status_col].dropna().astype(str).unique().tolist())
            selected_status = st.selectbox("Order Status", statuses)

        with f3:
            payment_statuses = ["All Payment Statuses"]
            if payment_status_col:
                payment_statuses += sorted(working[payment_status_col].dropna().astype(str).unique().tolist())
            selected_payment_status = st.selectbox("Payment Status (Excel)", payment_statuses)

        with f4:
            date_options = ["All Payment Dates"]
            if payment_date_col:
                date_series = pd.to_datetime(working[payment_date_col], errors="coerce").dropna()
                date_options += [str(x.date()) for x in sorted(date_series.unique())]
            selected_date = st.selectbox("Payment Date", date_options)

        with f5:
            duplicate_option = st.selectbox(
                "Duplicate Handling",
                ["Show All Orders", "Keep First Order ID", "Remove Duplicate Order IDs"],
            )

        if order_search and order_id_col:
            mask = working[order_id_col].astype(str).str.contains(order_search, case=False, na=False)
            working = working[mask]

        if selected_status != "All Order Statuses" and status_col:
            working = working[working[status_col].astype(str) == selected_status]

        if selected_payment_status != "All Payment Statuses" and payment_status_col:
            working = working[working[payment_status_col].astype(str) == selected_payment_status]

        if selected_date != "All Payment Dates" and payment_date_col:
            d = pd.to_datetime(working[payment_date_col], errors="coerce")
            working = working[d.dt.strftime("%Y-%m-%d") == selected_date]

        if order_id_col and duplicate_option == "Keep First Order ID":
            working = working.drop_duplicates(subset=[order_id_col], keep="first")
        elif order_id_col and duplicate_option == "Remove Duplicate Order IDs":
            dup_mask = working.duplicated(subset=[order_id_col], keep=False)
            working = working[~dup_mask]

        e1, e2, _ = st.columns([1, 1, 2])
        with e1:
            st.download_button(
                "⬇ Export Standard CSV",
                export_csv(working),
                file_name="meesho_orders_standard.csv",
                mime="text/csv",
                use_container_width=True,
            )
        with e2:
            financial_export = build_financial_detail(working, payments)
            st.download_button(
                "⬇ Export Financial Detail CSV",
                export_csv(financial_export),
                file_name="meesho_orders_financial_detail.csv",
                mime="text/csv",
                use_container_width=True,
            )

        st.markdown(f"**Showing {len(working):,} order rows**")

        if working.empty:
            st.markdown(
                '<div class="empty">No orders match the current filters.</div>',
                unsafe_allow_html=True,
            )
        else:
            st.dataframe(
                working,
                use_container_width=True,
                height=500,
                hide_index=True,
            )

    st.markdown("</div>", unsafe_allow_html=True)


# ---------------------------------------------------------
# FILE UPLOAD
# ---------------------------------------------------------
elif selected == "File Upload":
    st.markdown('<div class="page-card">', unsafe_allow_html=True)

    st.markdown(
        '<div class="section-title">Upload Files</div>',
        unsafe_allow_html=True,
    )

    c1, c2 = st.columns(2)

    with c1:
        st.markdown(
            """
            <div class="upload-box">
                <b>Payment Files (ZIP)</b>
                <p class="small-note">
                Select one or more Payment ZIP files. ZIP files may contain
                Order Payments, Ads Cost, Referral Payments and related CSV/XLSX files.
                </p>
            </div>
            """,
            unsafe_allow_html=True,
        )
        payment_uploads = st.file_uploader(
            "Payment Files",
            type=["zip", "xlsx", "xls", "csv"],
            accept_multiple_files=True,
            key="payment_files_upload",
            label_visibility="collapsed",
        )

    with c2:
        st.markdown(
            """
            <div class="upload-box">
                <b>Order File (CSV)</b>
                <p class="small-note">
                Select a single Meesho Order data CSV.
                </p>
            </div>
            """,
            unsafe_allow_html=True,
        )
        order_upload = st.file_uploader(
            "Order File",
            type=["csv"],
            accept_multiple_files=False,
            key="order_file_upload",
            label_visibility="collapsed",
        )

    st.write("")

    if st.button("☁ Process Files", type="primary", use_container_width=False):
        if not order_upload:
            st.error("Please upload an Order CSV.")
        elif not payment_uploads:
            st.error("Please upload at least one Payment ZIP/CSV/XLSX file.")
        else:
            with st.spinner("Processing Meesho files..."):
                order_df = read_tabular_bytes(
                    order_upload.getvalue(),
                    order_upload.name,
                )
                payment_df = process_payment_files(payment_uploads)

                if order_df is not None and not order_df.empty:
                    order_df.columns = [str(c).strip() for c in order_df.columns]
                    st.session_state["stored_orders"] = serialize_df(order_df)

                if payment_df is not None and not payment_df.empty:
                    payment_df.columns = [str(c).strip() for c in payment_df.columns]
                    st.session_state["stored_payments"] = serialize_df(payment_df)

                st.session_state["last_processed"] = datetime.now().strftime(
                    "%d-%m-%Y %I:%M %p"
                )

            if st.session_state["stored_orders"] is not None and st.session_state["stored_payments"] is not None:
                st.success(
                    f"✓ Files processed successfully. Last processed: {st.session_state['last_processed']}"
                )
                st.rerun()
            else:
                st.warning(
                    "Some files could not be read. Check the uploaded formats and column structure."
                )

    if st.session_state.get("last_processed"):
        st.caption(f"Last processed: {st.session_state['last_processed']}")

    st.markdown("</div>", unsafe_allow_html=True)

# ---------------------------------------------------------
# FOOTER
# ---------------------------------------------------------
st.markdown(
    """
    <div style="
        text-align:center;
        color:#607487;
        border-top:1px solid #bfd5dd;
        margin-top:2rem;
        padding:18px;
        font-size:.8rem;
    ">
        © 2026 Sunix Insights. All rights reserved.
    </div>
    """,
    unsafe_allow_html=True,
