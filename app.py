import streamlit as st
import pandas as pd
from docxtpl import DocxTemplate
from num2words import num2words
import io
from datetime import date, datetime
import uuid
import re
import os

st.set_page_config(page_title="Challan Master", layout="wide")

# ---------------- INDIAN CURRENCY FORMAT ----------------
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
    except:
        return "0"

# ---------------- BANK LIST (DATALIST SOURCE) ----------------
BANK_LIST = [
    "State Bank of India",
    "Indian Bank",
    "Indian Overseas Bank",
    "Canara Bank",
    "HDFC Bank",
    "ICICI Bank",
    "Axis Bank",
    "Punjab National Bank",
    "Union Bank of India",
    "Bank of Baroda"
]

# ---------------- DIALOG ----------------
@st.dialog("Edit Amount")
def edit_amount_dialog(index):
    rec = st.session_state.all_receipts[index]
    current_val = rec['amount'].replace(",", "")
    new_amt_str = st.text_input("Enter New Amount ", value=current_val)

    if st.button("Save Changes"):
        try:
            new_amt = int(new_amt_str)
            ind_amt = format_indian_currency(new_amt)
            new_words = num2words(new_amt, lang='en_IN').replace(",", "").replace(" And ", " and ").title()
            st.session_state.all_receipts[index]['amount'] = ind_amt
            st.session_state.all_receipts[index]['words'] = new_words
            st.rerun()
        except ValueError:
            st.error("Please enter a valid whole number.")

# ---------------- INITIALIZATION ----------------
if 'all_receipts' not in st.session_state:
    st.session_state.all_receipts = []

if 'locked' not in st.session_state:
    st.session_state.locked = False

if 'show_batch' not in st.session_state:
    st.session_state.show_batch = False

if "bank_input" not in st.session_state:
    st.session_state.bank_input = ""

# ---------------- SIDEBAR ----------------
with st.sidebar:
    st.header("⚙️ Configuration")
    s_challan = st.text_input("Starting Challan", disabled=st.session_state.locked)
    s_pdate = st.date_input("Challan Date", disabled=st.session_state.locked)

    st.divider()

    TEMPLATE_NAME = "Test.docx"
    if os.path.exists(TEMPLATE_NAME):
        with open(TEMPLATE_NAME, "rb") as f:
            template_bytes = f.read()
        st.success("✅ Template loaded")
    else:
        template_bytes = None
        st.error("Template not found")

    data_file = st.file_uploader("Upload Master Data (.xlsx)", type=["xlsx"])

    if not st.session_state.locked:
        if st.button("Confirm Setup", type="primary"):
            if s_challan and template_bytes and data_file:
                st.session_state.locked = True
                st.session_state.start_no = int(s_challan)
                st.session_state.formatted_pdate = s_pdate.strftime("%d.%m.%Y")
                st.rerun()
    else:
        if st.button("Reset Session"):
            st.session_state.locked = False
            st.session_state.all_receipts = []
            st.rerun()

# ---------------- MAIN FLOW ----------------
if st.session_state.locked:

    curr_count = len(st.session_state.all_receipts)
    next_no = st.session_state.start_no + curr_count

    try:
        df = pd.read_excel(data_file, sheet_name="BILL")
    except:
        st.error("Sheet 'BILL' not found.")
        st.stop()

    st.divider()

    search_num = st.text_input("Enter Consumer Number", max_chars=3)

    if search_num:

        result = df[df['Consumer Number'].astype(str) == search_num]

        if not result.empty:
            row = result.iloc[0]
            amt_val = 1000  # example for testing

            with st.form("entry_form", clear_on_submit=True):

                # -------- BANK NAME DATALIST --------
                bank_name = st.text_input(
                    "Bank Name",
                    value=st.session_state.bank_input,
                    key="bank_text"
                )

                # Dynamic suggestions
                if bank_name:
                    suggestions = [
                        b for b in BANK_LIST
                        if bank_name.lower() in b.lower()
                    ]
                else:
                    suggestions = BANK_LIST

                if suggestions:
                    st.caption("Suggestions:")
                    cols = st.columns(min(len(suggestions[:5]), 5))
                    for i, s in enumerate(suggestions[:5]):
                        if cols[i].button(s, key=f"bank_{s}"):
                            st.session_state.bank_input = s
                            st.rerun()

                # -------- OTHER FIELDS --------
                f1, f2 = st.columns(2)
                with f1:
                    mode = st.selectbox("Type", ["Cheque", "Demand Draft"])
                with f2:
                    inst_no = st.text_input("No.", max_chars=6)

                inst_date = st.date_input("Date")

                if st.form_submit_button("Add to Batch"):

                    if re.match(r"^[a-zA-Z\s\.]+$", bank_name) and re.match(r"^\d{6}$", inst_no):

                        ind_amt = format_indian_currency(amt_val)
                        words = num2words(amt_val, lang='en_IN').title()

                        st.session_state.all_receipts.append({
                            'id': str(uuid.uuid4()),
                            'challan': next_no,
                            'name': row['Name'],
                            'amount': ind_amt,
                            'words': words,
                            'pay_type': mode,
                            'pay_no': inst_no,
                            'bank': bank_name,
                            'date': inst_date.strftime("%d.%m.%Y")
                        })

                        st.session_state.bank_input = ""
                        st.rerun()
                    else:
                        st.error("Check Bank Name and 6-digit No.")
