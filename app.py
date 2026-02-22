import io
import os
import re
import uuid
from datetime import date, datetime

import pandas as pd
import streamlit as st
from docxtpl import DocxTemplate
from num2words import num2words

# --- APP CONFIGURATION ---
st.set_page_config(page_title="Challan Master", layout="wide")

# --- CUSTOM CSS ---
CSS_BLOCK = r"""
<style>
[data-testid="stVerticalBlock"] > div { gap: 0.5rem !important; }
div[data-testid="column"] button { margin-top: 28px !important; }

[data-testid="stImage"] img {
    width: 65px !important; height: 65px !important;
    object-fit: contain !important; border-radius: 5px;
    border: 1px solid #eee; display: block;
    margin-left: auto; margin-right: auto;
}

.stMarkdown p {
    font-size: 14px !important;
    line-height: 1.6 !important;
    margin-bottom: 0px !important;
}

.instrument-row {
    background-color: #f9f9f9;
    padding: 5px;
    border-radius: 5px;
    margin-bottom: 2px;
}
</style>
"""
st.markdown(CSS_BLOCK, unsafe_allow_html=True)

# --- BANK LOGOS CONFIGURATION ---
BANKS = [
    {"name": "State Bank of India", "file": "logos/SBI.jpg"},
    {"name": "HDFC Bank", "file": "logos/HDFC.jpg"},
    {"name": "ICICI Bank", "file": "logos/ICICI Bank.jpg"},
    {"name": "Axis Bank", "file": "logos/Axis Bank.jpg"},
    {"name": "Indian Bank", "file": "logos/Indian Bank.jpg"},
    {"name": "Canara Bank", "file": "logos/Canara.jpg"},
    {"name": "Bank of Baroda", "file": "logos/Bank of Baroda.jpg"},
    {"name": "Union Bank of India", "file": "logos/Union Bank of India.jpg"},
    {"name": "Karur Vysya Bank", "file": "logos/KVB.jpg"},
    {"name": "Yes Bank", "file": "logos/Yes Bank.jpg"},
    {"name": "IDFC First Bank", "file": "logos/IDFC First Bank.jpg"},
    {"name": "Bandhan Bank", "file": "logos/Bandhan Bank.jpg"},
    {"name": "Kotak Mahindra Bank", "file": "logos/KMB.jpg"},
    {"name": "South Indian Bank", "file": "logos/South Indian Bank.jpg"},
    {"name": "Central Bank of India", "file": "logos/Central Bank of India.jpg"},
    {"name": "Indian Overseas Bank", "file": "logos/Indian Overseas Bank.jpg"},
    {"name": "Bank of India", "file": "logos/Bank of India.jpg"},
    {"name": "UCO Bank", "file": "logos/UCO Bank.jpg"},
    {"name": "City Union Bank", "file": "logos/City Union Bank.jpg"},
    {"name": "Deutsche Bank", "file": "logos/Deutsche Bank.jpg"},
    {"name": "Equitas Bank", "file": "logos/Equitas Bank.jpg"},
    {"name": "IDBI Bank", "file": "logos/IDBI Bank.jpg"},
    {
        "name": "The Hongkong and Shanghai Banking Corporation",
        "file": "logos/HSBC.jpg",
    },
    {
        "name": "Tamilnad Mercantile Bank",
        "file": "logos/Tamilnad Mercantile Bank.jpg",
    },
    {"name": "Karnataka Bank", "file": "logos/Karnataka Bank.jpg"},
    {"name": "CSB Bank", "file": "logos/CSB Bank.jpg"},
    {"name": "Punjab National Bank", "file": "logos/Punjab National Bank.jpg"},
    {"name": "Federal Bank", "file": "logos/Federal Bank.jpg"},
]

CC_ADVANCE_TEMPLATE = "CCTemplate.docx"
SD_TEMPLATE = "SDTemplate.docx"

OTHER_PURPOSES = [
    "Advance Payment",
    "Advance Security Deposit (ASD)",
    "Security Deposit and Meter Security Deposit (SD and MSD)",
    "Processing Fee",
]

MONTH_LIST = [
    "January",
    "February",
    "March",
    "April",
    "May",
    "June",
    "July",
    "August",
    "September",
    "October",
    "November",
    "December",
]
MONTH_ABBR = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
YEAR_OPTIONS = [2026, 2025]


def format_indian_currency(number):
    try:
        main = str(int(float(number)))
        if len(main) <= 3:
            return main
        last_three = main[-3:]
        remaining = main[:-3]
        res = ""
        while len(remaining) > 2:
            res = "," + remaining[-2:] + res
            remaining = remaining[:-2]
        if remaining:
            res = remaining + res
        return f"{res},{last_three}"
    except Exception:
        return "0"


def amount_words(number):
    return (
        num2words(int(number), lang="en_IN")
        .replace(",", "")
        .replace(" And ", " and ")
        .title()
        .replace(" And ", " and ")
    )


def format_period_month_text(target_months):
    year_to_months = {}
    for month_name, year in target_months:
        year_to_months.setdefault(year, []).append(month_name)

    parts = []
    for year, months in year_to_months.items():
        parts.append(f"{', '.join(months)} - {year}")

    return " and ".join(parts)


class SafeReceipt(dict):
    def __getattr__(self, key):
        return self.get(key, "")


@st.dialog("Select Bank", width="medium")
def bank_selection_dialog():
    st.write("### 🏦 Select Bank")
    cols = st.columns(7, gap="small")
    for i, bank in enumerate(BANKS):
        with cols[i % 7]:
            if os.path.exists(bank["file"]):
                st.image(bank["file"])
            else:
                st.caption(bank["name"])
            if st.button("Select", key=f"btn_{i}"):
                st.session_state.selected_bank = bank["name"]
                st.rerun()


@st.dialog("Edit Amount")
def edit_amount_dialog(index):
    rec = st.session_state.all_receipts[index]
    current_val = rec["amount"].replace(",", "")
    new_amt_str = st.text_input("Enter New Amount", value=current_val)

    if st.button("Save Changes"):
        try:
            new_amt = int(new_amt_str)
            st.session_state.all_receipts[index]["amount"] = format_indian_currency(new_amt)
            st.session_state.all_receipts[index]["words"] = amount_words(new_amt)
            st.rerun()
        except ValueError:
            st.error("Please enter a valid whole number.")


if "all_receipts" not in st.session_state:
    st.session_state.all_receipts = []
if "locked" not in st.session_state:
    st.session_state.locked = False
if "selected_bank" not in st.session_state:
    st.session_state.selected_bank = ""
if "show_batch" not in st.session_state:
    st.session_state.show_batch = False
if "is_period" not in st.session_state:
    st.session_state.is_period = False
if "consumer_key" not in st.session_state:
    st.session_state.consumer_key = 0
if "temp_instruments" not in st.session_state:
    st.session_state.temp_instruments = []
if "challan_type" not in st.session_state:
    st.session_state.challan_type = "C. C"
if "other_form_key" not in st.session_state:
    st.session_state.other_form_key = 0
if "batch_purpose" not in st.session_state:
    st.session_state.batch_purpose = ""

with st.sidebar:
    st.header("⚙️ Configuration")
    challan_type = st.radio(
        "Challan Type",
        ["C. C", "OTHER"],
        index=0 if st.session_state.challan_type == "C. C" else 1,
        disabled=st.session_state.locked,
    )

    s_challan = st.text_input("Starting Challan", disabled=st.session_state.locked)
    s_pdate = st.date_input("Challan Date", disabled=st.session_state.locked)

    if s_challan and not s_challan.isdigit():
        st.error("Challan Number must contain Numbers only.")

    st.divider()

    template_bytes = None

    if challan_type == "C. C":
        if os.path.exists(CC_ADVANCE_TEMPLATE):
            st.success("✅ C.C Template Loaded")
            with open(CC_ADVANCE_TEMPLATE, "rb") as f:
                template_bytes = f.read()
        else:
            st.error(f"❌ {CC_ADVANCE_TEMPLATE} Missing!")
    else:
        cc_ok = os.path.exists(CC_ADVANCE_TEMPLATE)
        sd_ok = os.path.exists(SD_TEMPLATE)

        if cc_ok:
            st.success("✅ CCTemplate Loaded (for Advance Payment)")
        else:
            st.error(f"❌ {CC_ADVANCE_TEMPLATE} Missing!")

        if sd_ok:
            st.success("✅ SDTemplate Loaded (for ASD / SD & MSD / Processing Fee)")
        else:
            st.error(f"❌ {SD_TEMPLATE} Missing!")

    data_file = st.file_uploader("Upload Master Data (.xlsx)", type=["xlsx"])

    if not st.session_state.locked:
        if st.button("Confirm Setup", type="primary"):
            if not s_challan or not s_challan.isdigit():
                st.error("Enter a valid Numeric Challan Number.")
            elif challan_type == "C. C" and not template_bytes:
                st.error("C.C template not loaded.")
            elif challan_type == "OTHER" and (not os.path.exists(CC_ADVANCE_TEMPLATE) or not os.path.exists(SD_TEMPLATE)):
                st.error("Load both CCTemplate.docx and SDTemplate.docx.")
            elif not data_file:
                st.error("Upload Master Data.")
            else:
                st.session_state.locked = True
                st.session_state.challan_type = challan_type
                st.session_state.start_no = int(s_challan)
                st.session_state.formatted_pdate = s_pdate.strftime("%d.%m.%Y")
                st.rerun()
    else:
        if st.button("Reset Session"):
            st.session_state.locked = False
            st.session_state.all_receipts = []
            st.session_state.temp_instruments = []
            st.session_state.selected_bank = ""
            st.session_state.other_form_key = 0
            st.session_state.batch_purpose = ""
            st.rerun()

if st.session_state.locked:
    curr_count = len(st.session_state.all_receipts)
    next_no = st.session_state.start_no + curr_count

    if st.session_state.challan_type == "C. C":
        m1, m2, m3, m4 = st.columns(4)
        m1.metric("First Challan", st.session_state.start_no)
        m2.metric("Current No.", next_no)
        m3.metric("Date", st.session_state.formatted_pdate)
        m4.metric("Entered", curr_count)
    else:
        m1, m2 = st.columns(2)
        m1.metric("Current No.", next_no)
        m2.metric("Date", st.session_state.formatted_pdate)

    try:
        df = pd.read_excel(data_file, sheet_name="BILL")
    except Exception:
        st.error("Sheet 'BILL' not found.")
        st.stop()

    st.divider()

    has_active_instruments = len(st.session_state.temp_instruments) > 0
    row = None
    total_amt = None
    display_month_text = ""
    purpose_value = ""
    description_value = ""
    breakdown_value = ""

    if st.session_state.challan_type == "C. C":
        col_t1, _ = st.columns([0.2, 0.8])
        with col_t1:
            toggle_label = "Single Month Mode" if not st.session_state.is_period else "Period Mode"
            if st.button(toggle_label, disabled=has_active_instruments):
                st.session_state.is_period = not st.session_state.is_period
                st.rerun()

        if not st.session_state.is_period:
            c1, c2 = st.columns(2)
            with c1:
                sel_month = st.selectbox(
                    "Select Month", options=MONTH_LIST, disabled=has_active_instruments
                )
            with c2:
                sel_year = st.selectbox(
                    "Select Year", options=YEAR_OPTIONS, index=0, disabled=has_active_instruments
                )

            display_month_text = f"{sel_month} - {sel_year}"
            target_months = [(sel_month, sel_year)]
        else:
            c1, c2, c3, c4 = st.columns(4)
            with c1:
                f_month = st.selectbox("From Month", options=MONTH_LIST, disabled=has_active_instruments)
            with c2:
                f_year = st.selectbox(
                    "From Year", options=YEAR_OPTIONS, index=0, disabled=has_active_instruments
                )
            with c3:
                t_month = st.selectbox("To Month", options=MONTH_LIST, disabled=has_active_instruments)
            with c4:
                t_year = st.selectbox(
                    "To Year", options=YEAR_OPTIONS, index=0, disabled=has_active_instruments
                )

            start_date = datetime(f_year, MONTH_LIST.index(f_month) + 1, 1)
            end_date = datetime(t_year, MONTH_LIST.index(t_month) + 1, 1)

            target_months = []

            if start_date <= end_date:
                curr = start_date
                while curr <= end_date:
                    target_months.append((MONTH_LIST[curr.month - 1], curr.year))
                    curr = (
                        datetime(curr.year + 1, 1, 1)
                        if curr.month == 12
                        else datetime(curr.year, curr.month + 1, 1)
                    )
                display_month_text = format_period_month_text(target_months)
            else:
                st.error("'From' date must be before 'To' date.")

            if not target_months:
                st.warning("Selected Month-Year range is empty.")

        search_num = st.text_input(
            "Enter Consumer Number",
            max_chars=3,
            key=f"consumer_{st.session_state.consumer_key}",
            disabled=has_active_instruments,
        )

        if search_num and not re.match(r"^\d*$", search_num):
            st.error("Consumer Number must contain numbers only.")
        elif search_num and len(search_num) == 3 and re.match(r"^\d{3}$", search_num):
            result = df[df["Consumer Number"].astype(str).str.zfill(3) == search_num]

            if result.empty:
                st.error("Consumer not found in Master Data.")
            else:
                row = result.iloc[0]
                total_amt = 0
                month_found = False

                for m, y in target_months:
                    t_abbr = f"{MONTH_ABBR[MONTH_LIST.index(m)]}-{str(y)[2:]}"
                    t_col = next(
                        (
                            col
                            for col in df.columns
                            if str(col).strip() == t_abbr
                            or (
                                isinstance(col, (datetime, pd.Timestamp))
                                and col.month == MONTH_LIST.index(m) + 1
                                and col.year == y
                            )
                        ),
                        None,
                    )

                    if t_col is not None:
                        month_found = True
                        total_amt += row[t_col] if not pd.isna(row[t_col]) else 0

                if not month_found:
                    st.error("Selected Month-Year column not found in Master Data.")
                elif total_amt <= 0:
                    st.warning("Amount is zero for selected Month-Year.")
                else:
                    purpose_value = "C. C. Charges"
                    description_value = display_month_text
                    st.success(
                        f"**Found:** {row['Name']} | **Total Amt:** ₹{format_indian_currency(total_amt)}"
                    )

    else:
        purpose_locked = bool(st.session_state.batch_purpose)
        if purpose_locked:
            selected_other_purpose = st.selectbox(
                "Purpose",
                [st.session_state.batch_purpose],
                index=0,
                disabled=True,
                key=f"other_purpose_locked_{st.session_state.other_form_key}",
            )
        else:
            selected_other_purpose = st.selectbox(
                "Purpose",
                OTHER_PURPOSES,
                disabled=has_active_instruments,
                key=f"other_purpose_{st.session_state.other_form_key}",
            )
        purpose_value = selected_other_purpose
        description_value = ""
        desc_value_4d = ""
        breakdown_value = ""
        require_kva_value = False
        is_new_consumer = False
        new_consumer_name = ""
        tag_value = ""
        account_value = ""

        if selected_other_purpose == "Advance Payment":
            c1, c2 = st.columns(2)
            with c1:
                adv_month = st.selectbox("Month", MONTH_LIST, disabled=has_active_instruments, key=f"adv_month_{st.session_state.other_form_key}")
            with c2:
                adv_year = st.selectbox(
                    "Year", YEAR_OPTIONS, index=0, disabled=has_active_instruments, key=f"adv_year_{st.session_state.other_form_key}"
                )
            purpose_value = "Advance Payment"
            description_value = f"{adv_month} - {adv_year}"
            other_amount = st.text_input("Amount", value="", disabled=has_active_instruments, key=f"adv_amt_{st.session_state.other_form_key}")
            if other_amount and re.match(r"^\d+$", other_amount):
                total_amt = int(other_amount)
            elif other_amount:
                total_amt = None
                st.error("Amount must be a valid whole number.")
            else:
                total_amt = None

        elif selected_other_purpose == "Advance Security Deposit (ASD)":
            asd_desc_options = [
                "Review of ASD for April - 2023 to March - 2024",
                "Review of ASD for April - 2024 to March - 2025",
                "Review of ASD for April - 2025 to March - 2026",
            ]
            description_value = st.selectbox(
                "Description",
                asd_desc_options,
                index=1,
                key=f"asd_desc_{st.session_state.other_form_key}",
            )
            purpose_value = description_value
            other_amount = st.text_input("Amount", value="", disabled=has_active_instruments, key=f"asd_amt_{st.session_state.other_form_key}")
            if other_amount and re.match(r"^\d+$", other_amount):
                total_amt = int(other_amount)
            elif other_amount:
                total_amt = None
                st.error("Amount must be a valid whole number.")
            else:
                total_amt = None
            tag_value = "SD"
            account_value = "8336 – CIVIL DEPOSITS – 101 – SECURITY DEPOSITS"

        elif selected_other_purpose == "Security Deposit and Meter Security Deposit (SD and MSD)":
            sd_desc_options = [
                "SD and MSD - Extension of HT power supply service for CMD of",
                "Custom...",
            ]
            c1, c2 = st.columns([0.75, 0.25])
            with c1:
                sd_desc_choice = st.selectbox("Description", sd_desc_options, key=f"sd_desc_choice_{st.session_state.other_form_key}")
            with c2:
                desc_value_4d = st.text_input("Value (max 4 digits)", max_chars=4, key=f"sd_value_{st.session_state.other_form_key}")

            if sd_desc_choice == "Custom...":
                base_desc = st.text_input(
                    "Custom Description",
                    placeholder="Enter SD and MSD description",
                    key=f"sd_custom_desc_{st.session_state.other_form_key}",
                )
                description_value = base_desc.strip()
            else:
                require_kva_value = True
                if desc_value_4d and not re.match(r"^\d{1,4}$", desc_value_4d):
                    st.error("Value must be numeric and maximum 4 digits.")
                description_value = f"{sd_desc_choice} {desc_value_4d} KVA".strip()

            purpose_value = description_value
            tag_value = "SD"
            account_value = "8336 – CIVIL DEPOSITS – 101 – SECURITY DEPOSITS"

            s1, s2 = st.columns(2)
            with s1:
                sd_amount_str = st.text_input("SD Amount", value="", key=f"sd_amt_{st.session_state.other_form_key}")
            with s2:
                msd_amount_str = st.text_input("MSD Amount", value="", key=f"msd_amt_{st.session_state.other_form_key}")

            if sd_amount_str and msd_amount_str and re.match(r"^\d+$", sd_amount_str) and re.match(r"^\d+$", msd_amount_str):
                sd_amount = int(sd_amount_str)
                msd_amount = int(msd_amount_str)
                total_amt = sd_amount + msd_amount
                breakdown_value = (
                    f"[S.D     : {format_indian_currency(sd_amount)}]\n"
                    f"[M.S.D : {format_indian_currency(msd_amount)}]"
                )
            else:
                total_amt = None
                if sd_amount_str or msd_amount_str:
                    st.error("Enter valid whole numbers for SD Amount and MSD Amount.")

        else:
            proc_desc_options = [
                "registration cum-processing fees for the extension of HT power supply of CMD of",
                "Custom...",
            ]
            c1, c2 = st.columns([0.75, 0.25])
            with c1:
                proc_desc_choice = st.selectbox("Description", proc_desc_options, key=f"proc_desc_choice_{st.session_state.other_form_key}")
            with c2:
                desc_value_4d = st.text_input("Value (max 4 digits)", max_chars=4, key=f"proc_value_{st.session_state.other_form_key}")

            if proc_desc_choice == "Custom...":
                description_value = st.text_input(
                    "Custom Description",
                    placeholder="Enter processing fee description",
                    key=f"proc_custom_desc_{st.session_state.other_form_key}",
                ).strip()
            else:
                require_kva_value = True
                if desc_value_4d and not re.match(r"^\d{1,4}$", desc_value_4d):
                    st.error("Value must be numeric and maximum 4 digits.")
                description_value = f"{proc_desc_choice} {desc_value_4d} KVA".strip()

            purpose_value = description_value
            tag_value = "CCC/PF"
            account_value = "0801 – Power 05 – Transmission and Distribution (101) Sale of Power"
            total_amt = 20000
            st.info("Processing Fee amount is fixed at ₹20,000")

        if selected_other_purpose in [
            "Security Deposit and Meter Security Deposit (SD and MSD)",
            "Processing Fee",
        ]:
            is_new_consumer = st.checkbox("New Consumer", value=True, key=f"new_consumer_{st.session_state.other_form_key}")

        if is_new_consumer:
            new_consumer_name = st.text_input(
                "Consumer Name",
                placeholder="Enter new consumer name",
                key=f"new_consumer_name_{st.session_state.other_form_key}",
            )
            st.text_input(
                "Enter Consumer Number",
                value="NEW",
                disabled=True,
                key=f"consumer_new_{st.session_state.consumer_key}",
            )
            row = {
                "Name": new_consumer_name.strip() if new_consumer_name.strip() else "NEW CONSUMER",
                "Consumer Number": "NEW",
            }
        else:
            search_num = st.text_input(
                "Enter Consumer Number",
                max_chars=3,
                key=f"consumer_{st.session_state.consumer_key}",
            )
            if search_num and not re.match(r"^\d*$", search_num):
                st.error("Consumer Number must contain numbers only.")
            elif search_num and len(search_num) == 3 and re.match(r"^\d{3}$", search_num):
                result = df[df["Consumer Number"].astype(str).str.zfill(3) == search_num]
                if result.empty:
                    st.error("Consumer not found in Master Data.")
                else:
                    row = result.iloc[0]

        if row is not None:
            if is_new_consumer:
                st.success(f"**Name:** {row['Name']} | **Purpose:** {purpose_value}")
            else:
                st.success(f"**Found:** {row['Name']} | **Purpose:** {purpose_value}")

    if row is not None and total_amt is not None:
        b_col1, b_col2 = st.columns([0.9, 0.1], vertical_alignment="bottom")
        with b_col1:
            bank_name = st.text_input(
                "Bank Name", value=st.session_state.selected_bank, disabled=has_active_instruments
            )
        with b_col2:
            if st.button("🔍 Select", disabled=has_active_instruments):
                bank_selection_dialog()

        with st.expander("💳 Add Payment Details", expanded=True):
            restricted_mode = None
            if st.session_state.temp_instruments:
                restricted_mode = st.session_state.temp_instruments[0]["type"]

            with st.form("instrument_form", clear_on_submit=True):
                f1, f2, f3 = st.columns(3)
                with f1:
                    if restricted_mode:
                        st.markdown("🔒 Locked")
                        st.info(f"Mode: {restricted_mode}")
                        i_type = restricted_mode
                    else:
                        i_type = st.selectbox("Type", ["Cheque", "Demand Draft"])
                with f2:
                    i_no = st.text_input("No.", max_chars=6)
                with f3:
                    i_date = st.date_input("Date")

                if st.form_submit_button("➕ Add Payment"):
                    if bank_name and re.match(r"^\d{6}$", i_no):
                        st.session_state.temp_instruments.append(
                            {
                                "bank": bank_name,
                                "type": i_type,
                                "no": i_no,
                                "date": i_date.strftime("%d.%m.%Y"),
                            }
                        )
                        st.rerun()
                    else:
                        st.error("Check Bank Name and Cheque/DD No.")

            for idx, inst in enumerate(st.session_state.temp_instruments):
                cols = st.columns([2.5, 2, 2, 2, 0.5])
                cols[0].write(f"🏦 {inst['bank']}")
                cols[1].write(f"📄 {inst['type']}")
                cols[2].write(f"🔢 {inst['no']}")
                cols[3].write(f"📅 {inst['date']}")
                if cols[4].button("🗑️", key=f"del_tmp_{idx}"):
                    st.session_state.temp_instruments.pop(idx)
                    st.rerun()

        if st.button("🚀 Add to Batch", type="primary"):
            if not st.session_state.temp_instruments:
                st.error("Add at least One Payment Details.")
            elif not bank_name:
                st.error("Bank Name is required.")
            elif st.session_state.challan_type == "OTHER" and not description_value.strip() and selected_other_purpose != "Advance Payment":
                st.error("Description is required for selected purpose.")
            elif st.session_state.challan_type == "OTHER" and require_kva_value and not re.match(r"^\d{1,4}$", desc_value_4d):
                st.error("Please enter a valid 1 to 4 digit value.")
            elif st.session_state.challan_type == "OTHER" and is_new_consumer and not new_consumer_name.strip():
                st.error("Please enter Consumer Name for New Consumer.")
            elif st.session_state.challan_type == "OTHER" and selected_other_purpose not in [
                "Processing Fee",
                "Security Deposit and Meter Security Deposit (SD and MSD)",
            ] and total_amt is None:
                st.error("Please enter a valid Amount.")
            elif st.session_state.challan_type == "OTHER" and selected_other_purpose == "Security Deposit and Meter Security Deposit (SD and MSD)" and total_amt is None:
                st.error("Please enter valid SD Amount and MSD Amount.")
            else:
                receipt = {
                    "id": str(uuid.uuid4()),
                    "challan": next_no,
                    "pdate": st.session_state.formatted_pdate,
                    "name": row["Name"],
                    "num": row["Consumer Number"],
                    "purpose": purpose_value,
                    "selected_purpose": selected_other_purpose if st.session_state.challan_type == "OTHER" else "C. C",
                    "description": description_value,
                    "tag": tag_value,
                    "account": account_value,
                    "breakdown": breakdown_value,
                    "amount": format_indian_currency(total_amt),
                    "words": amount_words(total_amt),
                    "pay_type": st.session_state.temp_instruments[0]["type"],
                    "pay_no": ", ".join([i["no"] for i in st.session_state.temp_instruments]),
                    "bank": bank_name,
                    "date": ", ".join(list(set([i["date"] for i in st.session_state.temp_instruments]))),
                }
                if st.session_state.challan_type == "C. C":
                    receipt["month"] = display_month_text
                else:
                    receipt["month"] = description_value
                st.session_state.all_receipts.append(receipt)
                st.session_state.temp_instruments = []
                st.session_state.selected_bank = ""
                st.session_state.is_period = False
                if st.session_state.challan_type == "OTHER" and not st.session_state.batch_purpose:
                    st.session_state.batch_purpose = selected_other_purpose
                if st.session_state.challan_type == "OTHER":
                    st.session_state.other_form_key += 1
                st.session_state.consumer_key += 1
                st.rerun()

    if st.session_state.all_receipts:
        st.divider()
        if st.checkbox("👁️ View Batch Table", value=st.session_state.show_batch):
            st.session_state.show_batch = True
            t_head = st.columns([0.7, 2.2, 1.7, 1.2, 1.2, 2, 1.1])
            t_head[0].write("**No.**")
            t_head[1].write("**Consumer**")
            t_head[2].write("**Amount**")
            t_head[3].write("**Mode**")
            t_head[4].write("**No.**")
            t_head[5].write("**Purpose**")
            t_head[6].write("**Actions**")
            for i, rec in enumerate(st.session_state.all_receipts):
                tcol = st.columns([0.7, 2.2, 1.7, 1.2, 1.2, 2, 1.1])
                tcol[0].write(rec["challan"])
                tcol[1].write(rec["name"])
                tcol[2].write(f"₹{rec['amount']}")
                tcol[3].write(rec["pay_type"])
                tcol[4].write(rec["pay_no"])
                tcol[5].write(rec.get("purpose", "C. C"))
                with tcol[6]:
                    s1, s2 = st.columns(2)
                    if s1.button("✏️", key=f"e_{rec['id']}"):
                        edit_amount_dialog(i)
                    if s2.button("🗑️", key=f"d_{rec['id']}"):
                        st.session_state.all_receipts.pop(i)
                        for j in range(i, len(st.session_state.all_receipts)):
                            st.session_state.all_receipts[j]["challan"] -= 1
                        if not st.session_state.all_receipts:
                            st.session_state.batch_purpose = ""
                            st.session_state.other_form_key += 1
                        st.rerun()

        if st.button("🚀 Finalize Word File", type="primary"):
            if st.session_state.challan_type == "C. C":
                with open(CC_ADVANCE_TEMPLATE, "rb") as f:
                    doc = DocxTemplate(io.BytesIO(f.read()))
            else:
                first_selected_purpose = st.session_state.all_receipts[0].get("selected_purpose", "")
                tpl = CC_ADVANCE_TEMPLATE if first_selected_purpose == "Advance Payment" else SD_TEMPLATE
                if not os.path.exists(tpl):
                    st.error(f"Template missing: {tpl}")
                    st.stop()
                with open(tpl, "rb") as f:
                    doc = DocxTemplate(io.BytesIO(f.read()))

            safe_receipts = [SafeReceipt(r) for r in st.session_state.all_receipts]
            doc.render({"receipts": safe_receipts})
            output = io.BytesIO()
            doc.save(output)
            output.seek(0)
            st.download_button(
                "📥 Download",
                output.getvalue(),
                file_name=f"Challans_{date.today()}.docx",
            )
