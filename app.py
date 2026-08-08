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
    page_title="Meesho Reconcile",
    page_icon="↗",
    layout="wide",
    initial_sidebar_state="expanded",
)


st.markdown(
    """
    <style>
    @import url('https://fonts.googleapis.com/css2?family=DM+Sans:wght@400;500;600;700&family=Space+Grotesk:wght@500;600;700&display=swap');

    :root {
        --ink: #17233d;
        --muted: #718096;
        --line: #e8edf5;
        --bg: #f6f8fc;
        --purple: #6753d9;
        --purple-soft: #efedff;
        --green: #1f9d67;
        --green-soft: #e8f8f0;
        --orange: #e79b34;
        --orange-soft: #fff5df;
        --red: #d45f6c;
        --red-soft: #fff0f2;
    }

    html, body, [class*="css"] { font-family: 'DM Sans', sans-serif; }
    .stApp { background: var(--bg); color: var(--ink); }
    [data-testid="stHeader"] { background: rgba(246,248,252,0.95); }
    [data-testid="stSidebar"] { background: #ffffff; border-right: 1px solid var(--line); }
    [data-testid="stSidebar"] > div:first-child { padding: 2rem 1.35rem; }
    .block-container { max-width: 1440px; padding: 2.4rem 3.25rem 4rem; }

    h1, h2, h3 { font-family: 'Space Grotesk', sans-serif; letter-spacing: -0.035em; color: var(--ink); }
    h1 { font-size: 2.55rem !important; margin: 0; }
    h2 { font-size: 1.18rem !important; }
    p { color: var(--muted); }

    .brand { display:flex; align-items:center; gap: 0.72rem; margin-bottom: 2.6rem; }
    .brand-mark { width: 40px; height: 40px; display:grid; place-items:center; border-radius: 12px;
        background: var(--purple); color: white; font-family:'Space Grotesk'; font-size: 1.45rem; font-weight:700; }
    .brand-name { font-family:'Space Grotesk'; font-weight:700; font-size:1.08rem; color:var(--ink); }
    .brand-sub { font-size:0.7rem; color:var(--muted); margin-top:1px; }
    .side-label { font-size: 0.71rem; font-weight:700; letter-spacing:.12em; text-transform:uppercase; color:#9aa5b8; margin: 1.4rem 0 .65rem; }
    .side-help { font-size:.75rem; line-height:1.5; color:var(--muted); margin-top:1.25rem; }

    [data-testid="stFileUploader"] { background:#fff; border:1px dashed #d9dff0; border-radius:14px; padding:.3rem; }
    [data-testid="stFileUploader"] section { padding: .9rem .85rem; }
    [data-testid="stFileUploader"] small { color: var(--muted); }
    .upload-card { background:#fff; border:1px solid var(--line); border-radius:18px; padding:1.3rem 1.35rem 1.4rem; height:100%; box-shadow:0 5px 20px rgba(29,45,83,.025); }
    .upload-card h3 { font-size:1rem; margin:.1rem 0 .25rem; }
    .upload-card p { font-size:.78rem; margin:0 0 .9rem; }
    .upload-icon { color:var(--purple); font-size:1.3rem; font-weight:700; margin-bottom:.65rem; }

    .eyebrow { color:var(--purple); font-size:.73rem; letter-spacing:.13em; text-transform:uppercase; font-weight:700; margin-bottom:.7rem; }
    .hero-copy { margin:.65rem 0 1.75rem; max-width:680px; font-size:.95rem; }
    .metric { background:#fff; border:1px solid var(--line); border-radius:16px; padding:1.15rem 1.2rem; min-height:130px; box-shadow:0 5px 20px rgba(29,45,83,.025); }
    .metric-label { font-size:.75rem; font-weight:600; color:var(--muted); }
    .metric-value { font-family:'Space Grotesk'; font-size:1.72rem; font-weight:700; color:var(--ink); margin:.55rem 0 .1rem; letter-spacing:-.04em; }
    .metric-note { font-size:.7rem; color:var(--muted); }
    .metric.green .metric-value { color:var(--green); }
    .metric.red .metric-value { color:var(--red); }
    .metric.purple .metric-value { color:var(--purple); }
    .section-heading { display:flex; justify-content:space-between; align-items:center; margin:2rem 0 .8rem; }
    .section-heading h2 { margin:0; }
    .status-pill { padding:.32rem .64rem; border-radius:20px; background:var(--green-soft); color:var(--green); font-size:.71rem; font-weight:700; }
    .status-pill.warning { background:var(--orange-soft); color:#b87b18; }
    .empty-panel { border:1px solid var(--line); background:#fff; border-radius:18px; padding:2.8rem 2rem; text-align:center; }
    .empty-symbol { width:52px; height:52px; display:grid; place-items:center; margin:0 auto 1rem; border-radius:16px; background:var(--purple-soft); color:var(--purple); font-size:1.5rem; font-weight:700; }
    .empty-panel h3 { font-size:1.1rem; margin:.3rem 0 .35rem; }
    .empty-panel p { font-size:.82rem; max-width:440px; margin:0 auto; }
    .insight { background:var(--purple-soft); border-radius:16px; padding:1rem 1.1rem; color:#5346ae; font-size:.82rem; line-height:1.5; }
    .insight strong { color:#392d9c; }
    .data-note { color:var(--muted); font-size:.75rem; margin-top:.45rem; }
    .stButton > button { border-radius:10px; border:1px solid var(--line); color:var(--ink); font-weight:600; }
    .stDownloadButton > button { border-radius:10px; background:var(--purple); color:white; border:0; font-weight:600; }
    div[data-testid="stMetric"] { background:white; }
    </style>
    """,
    unsafe_allow_html=True,
)


ORDER_ID_ALIASES = [
    "sub order no",
    "sub-order no",
    "sub_order_id",
    "suborder no",
    "sub-order id",
    "sub order id",
    "order id",
    "suborder id",
]
PAYOUT_ALIASES = [
    "final settlement amount", "settlement amount", "bank payout",
    "bank settlement", "amount transferred to bank", "transferred to bank",
    "payout", "payment received", "payment amount", "net amount",
    "paid amount", "amount",
]


@dataclass
class ReconciliationResult:
    orders: pd.DataFrame
    payments: pd.DataFrame
    matched: pd.DataFrame
    order_id_column: str
    payment_id_column: str
    payout_column: str
    order_count: int
    payout_total: float


class MissingColumnError(ValueError):
    def __init__(
        self,
        message: str,
        frames: dict[str, pd.DataFrame],
        expected_columns: Iterable[str],
    ):
        super().__init__(message)
        self.frames = frames
        self.expected_columns = list(expected_columns)


def clean_column(value: object) -> str:
    """Create a case-insensitive header key with spaces/separators removed."""
    if value is None:
        return ""
    try:
        if pd.isna(value):
            return ""
    except (TypeError, ValueError):
        pass
    text = str(value).strip().lower().replace("&", "and")
    return re.sub(r"[^a-z0-9]", "", text)


def find_column(frame: pd.DataFrame, aliases: Iterable[str]) -> str | None:
    columns = list(frame.columns)
    cleaned = {column: clean_column(column) for column in columns}
    alias_keys = [clean_column(alias) for alias in aliases]

    for alias in alias_keys:
        for column, normalized in cleaned.items():
            if normalized == alias:
                return column
    for alias in alias_keys:
        for column, normalized in cleaned.items():
            if alias in normalized or normalized in alias:
                return column
    return None


def normalize_id(series: pd.Series) -> pd.Series:
    return (
        series.astype("string")
        .fillna("")
        .str.strip()
        .str.replace(r"\.0$", "", regex=True)
        .str.upper()
    )


def numeric_series(series: pd.Series) -> pd.Series:
    # Handles currency symbols, commas, parentheses, and negative values.
    values = series.astype("string").fillna("")
    values = values.str.replace(",", "", regex=False).str.replace(r"[₹$€£]", "", regex=True)
    values = values.str.replace(r"^\((.*)\)$", r"-\1", regex=True)
    return pd.to_numeric(values.str.strip(), errors="coerce").fillna(0)


def read_csv_bytes(uploaded_file) -> pd.DataFrame:
    raw = uploaded_file.getvalue()
    for encoding in ("utf-8-sig", "utf-8", "cp1252", "latin-1"):
        try:
            return pd.read_csv(io.BytesIO(raw), encoding=encoding)
        except (UnicodeDecodeError, pd.errors.ParserError):
            continue
    raise ValueError("The orders file could not be read as a CSV.")


def find_header_row(raw_frame: pd.DataFrame) -> int | None:
    """Find a real table header below title/group rows in an export."""
    if raw_frame.empty:
        return None

    id_keys = {clean_column(alias) for alias in ORDER_ID_ALIASES}
    payout_keys = {clean_column(alias) for alias in PAYOUT_ALIASES}
    best_row: int | None = None
    best_score = -1
    scan_limit = min(len(raw_frame), 30)

    for row_index in range(scan_limit):
        row_keys = {clean_column(value) for value in raw_frame.iloc[row_index].tolist()}
        has_id = bool(row_keys & id_keys)
        has_payout = bool(row_keys & payout_keys)
        if not has_id:
            continue

        # A row containing both the primary ID and payout headers wins over
        # title/group rows, with earlier rows winning ties.
        score = (2 if has_id else 0) + (1 if has_payout else 0)
        if score > best_score:
            best_row = row_index
            best_score = score

    return best_row


def normalize_frame_headers(raw_frame: pd.DataFrame) -> pd.DataFrame:
    """Promote a detected header row and discard leading export metadata."""
    header_row = find_header_row(raw_frame)
    if header_row is None:
        frame = raw_frame.copy()
        frame.columns = [f"Column {index + 1}" for index in range(len(frame.columns))]
        return frame

    header_values = raw_frame.iloc[header_row].tolist()
    columns: list[str] = []
    seen: dict[str, int] = {}
    for index, value in enumerate(header_values):
        label = str(value).strip() if clean_column(value) else f"Unnamed column {index + 1}"
        count = seen.get(label, 0)
        seen[label] = count + 1
        columns.append(label if count == 0 else f"{label}.{count}")

    frame = raw_frame.iloc[header_row + 1:].copy()
    frame.columns = columns
    return frame.dropna(how="all").reset_index(drop=True)


def read_payment_table(raw: bytes, file_type: str) -> pd.DataFrame:
    """Read a payment table while locating headers below blank/group rows."""
    if file_type == "csv":
        for encoding in ("utf-8-sig", "utf-8", "cp1252", "latin-1"):
            try:
                raw_frame = pd.read_csv(io.BytesIO(raw), header=None, encoding=encoding)
                return normalize_frame_headers(raw_frame)
            except (UnicodeDecodeError, pd.errors.ParserError):
                continue
        raise ValueError("The payment CSV could not be read.")

    raw_frame = pd.read_excel(io.BytesIO(raw), header=None)
    return normalize_frame_headers(raw_frame)


def read_payment_file(uploaded_file) -> pd.DataFrame:
    filename = uploaded_file.name.lower()
    raw = uploaded_file.getvalue()
    frames: list[pd.DataFrame] = []

    if filename.endswith(".zip"):
        with zipfile.ZipFile(io.BytesIO(raw)) as archive:
            members = [name for name in archive.namelist() if not name.endswith("/") and not Path(name).name.startswith("~$")]
            if not members:
                raise ValueError("The ZIP file does not contain a readable CSV or XLSX file.")
            for member in members:
                member_bytes = archive.read(member)
                if member.lower().endswith(".csv"):
                    frames.append(read_payment_table(member_bytes, "csv"))
                elif member.lower().endswith((".xlsx", ".xls")):
                    sheets = pd.read_excel(io.BytesIO(member_bytes), sheet_name=None, header=None)
                    frames.extend(
                        normalize_frame_headers(sheet)
                        for sheet in sheets.values()
                        if not sheet.empty
                    )
    elif filename.endswith((".xlsx", ".xls")):
        sheets = pd.read_excel(io.BytesIO(raw), sheet_name=None, header=None)
        frames.extend(
            normalize_frame_headers(sheet)
            for sheet in sheets.values()
            if not sheet.empty
        )
    elif filename.endswith(".csv"):
        frames.append(read_payment_table(raw, "csv"))
    else:
        raise ValueError("Upload a ZIP, XLSX, XLS, or CSV payment file.")

    if not frames:
        raise ValueError("No rows were found in the payment file.")
    return pd.concat(frames, ignore_index=True, sort=False)


def reconcile(order_file, payment_file, product_cost: float, packaging_cost: float) -> ReconciliationResult:
    orders = read_csv_bytes(order_file)
    payments = read_payment_file(payment_file)
    order_id_column = find_column(orders, ORDER_ID_ALIASES)
    payment_id_column = find_column(payments, ORDER_ID_ALIASES)
    payout_column = find_column(payments, PAYOUT_ALIASES)

    if not order_id_column:
        raise MissingColumnError(
            "Could not find a sub-order ID column in the orders CSV.",
            {"Orders CSV": orders, "Payment file": payments},
            ORDER_ID_ALIASES,
        )
    if not payment_id_column:
        raise MissingColumnError(
            "Could not find a sub-order ID column in the payment file.",
            {"Orders CSV": orders, "Payment file": payments},
            ORDER_ID_ALIASES,
        )
    if not payout_column:
        raise MissingColumnError(
            "Could not find a payout or settlement amount column in the payment file.",
            {"Orders CSV": orders, "Payment file": payments},
            PAYOUT_ALIASES,
        )

    orders = orders.copy()
    payments = payments.copy()
    orders["_match_id"] = normalize_id(orders[order_id_column])
    payments["_match_id"] = normalize_id(payments[payment_id_column])
    payments["_payout"] = numeric_series(payments[payout_column])
    orders = orders[orders["_match_id"] != ""].copy()
    payments = payments[payments["_match_id"] != ""].copy()

    # Aggregate payment rows first: Meesho exports may split one sub-order across
    # multiple settlement lines or include separate fee/adjustment entries.
    payment_totals = payments.groupby("_match_id", as_index=False)["_payout"].sum()
    matched = orders[["_match_id"]].drop_duplicates().merge(payment_totals, on="_match_id", how="left")
    matched["_payout"] = matched["_payout"].fillna(0)
    matched["product_cost"] = product_cost
    matched["packaging_cost"] = packaging_cost
    matched["total_cost"] = product_cost + packaging_cost
    matched["profit_loss"] = matched["_payout"] - matched["total_cost"]

    return ReconciliationResult(
        orders=orders,
        payments=payments,
        matched=matched,
        order_id_column=order_id_column,
        payment_id_column=payment_id_column,
        payout_column=payout_column,
        order_count=len(matched),
        payout_total=float(matched["_payout"].sum()),
    )


def money(value: float) -> str:
    sign = "-" if value < 0 else ""
    return f"{sign}₹{abs(value):,.0f}"


def show_sidebar() -> tuple[float, float]:
    with st.sidebar:
        st.markdown(
            """
            <div class="brand">
                <div class="brand-mark">↗</div>
                <div><div class="brand-name">Meesho Reconcile</div><div class="brand-sub">PAYMENT INTELLIGENCE</div></div>
            </div>
            <div class="side-label">Cost assumptions</div>
            """,
            unsafe_allow_html=True,
        )
        product_cost = st.number_input("Average Product Cost (₹)", min_value=0.0, value=250.0, step=10.0, format="%.2f")
        packaging_cost = st.number_input("Packaging Cost (₹)", min_value=0.0, value=15.0, step=1.0, format="%.2f")
        st.markdown(
            """
            <div class="side-help">
              Your cost assumptions are applied per unique sub-order to calculate total cost and net profit/loss.
              <br><br>Need help? Make sure both files use the same sub-order ID format.
            </div>
            """,
            unsafe_allow_html=True,
        )
    return product_cost, packaging_cost


def show_file_diagnostics(error: MissingColumnError) -> None:
    st.error(str(error))
    with st.expander("Inspect uploaded file columns and sample rows", expanded=True):
        st.markdown(
            "Expected one of these matching headers: "
            + ", ".join(f"`{column}`" for column in error.expected_columns)
        )
        for file_label, frame in error.frames.items():
            st.markdown(f"**{file_label}**")
            if frame.empty:
                st.caption("The file was read successfully but contains no data rows.")
                continue

            columns = [str(column) for column in frame.columns]
            st.caption(f"Detected columns ({len(columns)}): {', '.join(columns)}")
            preview_columns = list(frame.columns[:30])
            preview = frame.loc[:, preview_columns].head(5)
            st.dataframe(preview, use_container_width=True, hide_index=True)
            if len(frame.columns) > len(preview_columns):
                st.caption(
                    f"Showing the first {len(preview_columns)} of {len(frame.columns)} columns "
                    "and the first 5 rows."
                )


def main() -> None:
    product_cost, packaging_cost = show_sidebar()

    st.markdown('<div class="eyebrow">Payment reconciliation workspace</div>', unsafe_allow_html=True)
    st.title("Know exactly where your money goes.")
    st.markdown(
        '<p class="hero-copy">Upload your Meesho order and payment exports to match sub-orders, track payouts, and see your true profit in one place.</p>',
        unsafe_allow_html=True,
    )

    col_orders, col_payments = st.columns(2, gap="large")
    with col_orders:
        st.markdown(
            '<div class="upload-card"><div class="upload-icon">▣</div><h3>Meesho Orders CSV</h3><p>Upload the order export containing your sub-order IDs.</p>',
            unsafe_allow_html=True,
        )
        order_file = st.file_uploader("Drop your orders CSV here", type=["csv"], key="orders", label_visibility="collapsed")
        st.markdown("</div>", unsafe_allow_html=True)
    with col_payments:
        st.markdown(
            '<div class="upload-card"><div class="upload-icon">↥</div><h3>Payments ZIP / XLSX</h3><p>Upload settlement files, including ZIPs with multiple exports.</p>',
            unsafe_allow_html=True,
        )
        payment_file = st.file_uploader("Drop your payments file here", type=["zip", "xlsx", "xls", "csv"], key="payments", label_visibility="collapsed")
        st.markdown("</div>", unsafe_allow_html=True)

    if not order_file or not payment_file:
        st.markdown(
            """
            <div class="empty-panel" style="margin-top:2rem">
              <div class="empty-symbol">↗</div>
              <h3>Your reconciliation dashboard is ready</h3>
              <p>Upload both files above to automatically match every sub-order ID and unlock your payout and profit summary.</p>
            </div>
            """,
            unsafe_allow_html=True,
        )
        return

    try:
        result = reconcile(order_file, payment_file, product_cost, packaging_cost)
    except MissingColumnError as error:
        show_file_diagnostics(error)
        return
    except (ValueError, KeyError, zipfile.BadZipFile, pd.errors.ParserError) as error:
        st.error(str(error))
        return

    matched_ids = set(result.payments["_match_id"])
    matched_count = int(result.matched["_match_id"].isin(matched_ids).sum())
    unmatched_count = result.order_count - matched_count
    total_cost = result.order_count * (product_cost + packaging_cost)
    net_profit = result.payout_total - total_cost
    profit_class = "green" if net_profit >= 0 else "red"
    status_class = "" if unmatched_count == 0 else "warning"

    st.markdown('<div class="section-heading"><h2>Reconciliation overview</h2><span class="status-pill ' + status_class + '">' + ("All orders matched" if unmatched_count == 0 else f"{unmatched_count} orders need attention") + "</span></div>", unsafe_allow_html=True)
    metrics = st.columns(4, gap="medium")
    metric_data = [
        ("Total Orders", f"{result.order_count:,}", "Unique sub-orders from CSV", ""),
        ("Total Bank Payout", money(result.payout_total), "Matched settlement amount", "purple"),
        ("Total Cost", money(total_cost), f"₹{product_cost + packaging_cost:,.0f} per order", ""),
        ("Net Profit / Loss", money(net_profit), "Payout less total costs", profit_class),
    ]
    for column, (label, value, note, style) in zip(metrics, metric_data):
        with column:
            st.markdown(f'<div class="metric {style}"><div class="metric-label">{label}</div><div class="metric-value">{value}</div><div class="metric-note">{note}</div></div>', unsafe_allow_html=True)

    st.markdown('<div class="section-heading"><h2>Matched order details</h2></div>', unsafe_allow_html=True)
    if unmatched_count:
        st.markdown(f'<div class="insight"><strong>Action needed:</strong> {unmatched_count} sub-order{"s" if unmatched_count != 1 else ""} from your orders export did not appear in the payment file. Their payout is currently counted as ₹0.</div>', unsafe_allow_html=True)
        st.write("")

    display = result.matched.rename(columns={"_match_id": "Sub-order ID", "_payout": "Bank Payout", "product_cost": "Product Cost", "packaging_cost": "Packaging", "total_cost": "Total Cost", "profit_loss": "Profit / Loss"})
    display["Status"] = display["Sub-order ID"].isin(matched_ids).map({True: "Matched", False: "Not found"})
    display = display[["Sub-order ID", "Status", "Bank Payout", "Product Cost", "Packaging", "Total Cost", "Profit / Loss"]]
    st.dataframe(
        display.style.format({column: "₹{:,.2f}" for column in ["Bank Payout", "Product Cost", "Packaging", "Total Cost", "Profit / Loss"]}),
        use_container_width=True,
        hide_index=True,
        height=340,
    )

    csv_export = display.to_csv(index=False).encode("utf-8")
    st.download_button("Download reconciliation CSV", data=csv_export, file_name="meesho_reconciliation.csv", mime="text/csv")
    st.markdown(f'<div class="data-note">Matched {matched_count:,} of {result.order_count:,} unique sub-orders · Orders column: <b>{result.order_id_column}</b> · Payout column: <b>{result.payout_column}</b></div>', unsafe_allow_html=True)


if __name__ == "__main__":
    main()
