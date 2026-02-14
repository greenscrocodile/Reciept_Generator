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

# --- INDIAN CURRENCY FORMATTING ---
def format_indian_currency(number):
    try:
        main = str(int(float(number))) 
        if len(main) <= 3: return main
        last_three = main[-3:]
        remaining = main[:-3]
        res = ""
        while len(remaining) > 2:
            res = "," + remaining[-2:] + res
            remaining = remaining[:-2]
        if remaining: res = remaining + res
        return f"{res},{last_three}"
    except:
        return "0"

# --- DIALOGS ---
@st.dialog("Edit Amount")
def edit_amount_dialog(index):
    rec = st.session_state.all_receipts[index]
    current_val = rec['amount'].replace(",", "")
    new_amt_str = st.text_input("Enter New Amount ", value=current_val)

    if st.button("Save Changes"):
        try:
            new_amt = int(new_amt_str)
            ind_amt = format_indian_currency(new_amt)
            new_words = num2words(new_amt, lang='en_IN').replace(",", "").replace(" And ", " and ").title().replace(" And ", " and ")
            st.session_state.all_receipts[index]['amount'] = ind_amt
            st.session_state.all_receipts[index]['words'] = new_words
            st.rerun()
        except ValueError:
            st.error("Please enter a valid whole number.")

# --- INITIALIZATION ---
if 'all_receipts' not in st.session_state:
    st.session_state.all_receipts = []
if 'locked' not in st.session_state:
    st.session_state.locked = False
if 'show_batch' not in st.session_state:
    st.session_state.show_batch = False

# --- BANK NAME SESSION STATE ---
if "bank_name_value" not in st.session_state:
    st.session_state.bank_name_value = ""

# --- SIDEBAR ---
with st.sidebar:
    st.header("⚙️ Configuration")
    s_challan = st.text_input("Starting Challan", disabled=st.session_state.locked)
    s_pdate = st.date_input("Challan Date", disabled=st.session_state.locked)
    st.divider()
    
    TEMPLATE_NAME = "Test.docx"
    if os.path.exists(TEMPLATE_NAME):
        st.success(f"✅ Template loaded from GitHub")
        with open(TEMPLATE_NAME, "rb") as f:
            template_bytes = f.read()
    else:
        st.error(f"❌ {TEMPLATE_NAME} not found!")
        template_bytes = None

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

# --- MAIN FLOW ---
if st.session_state.locked:
    curr_count = len(st.session_state.all_receipts)
    next_no = st.session_state.start_no + curr_count

    h1, h2, h3, h4 = st.columns(4)
    h1.metric("Starting No.", st.session_state.start_no)
    h2.metric("Next No.", next_no)
    h3.metric("Date", st.session_state.formatted_pdate)
    h4.metric("Entered", curr_count)

    try:
        df = pd.read_excel(data_file, sheet_name="BILL")
    except:
        st.error("Sheet 'BILL' not found.")
        st.stop()

    st.divider()

    c1, c2 = st.columns(2)
    with c1:
        month_list = ["January", "February", "March", "April", "May", "June", "July", "August", "September", "October", "November", "December"]
        month_abbr = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
        sel_month = st.selectbox("Select Month", options=month_list)
    with c2:
        sel_year = st.selectbox("Select Year", options=[2025, 2026])

    m_idx = month_list.index(sel_month)
    target_abbr = f"{month_abbr[m_idx]}-{str(sel_year)[2:]}"

    search_num = st.text_input("Enter Consumer Number", max_chars=3)

    if search_num:
        if not re.match(r"^\d{3}$", search_num):
            st.warning("⚠️ Consumer Number must be 3 digits.")
        else:
            result = df[df['Consumer Number'].astype(str) == search_num]

            if not result.empty:
                row = result.iloc[0]

                target_col = None
                for col in df.columns:
                    if str(col) == target_abbr:
                        target_col = col
                        break
                    if isinstance(col, (datetime, pd.Timestamp)):
                        if col.month == (m_idx + 1) and col.year == sel_year:
                            target_col = col
                            break
                
                if target_col is not None:
                    amt_val = row[target_col]
                    
                    if pd.isna(amt_val) or amt_val == 0:
                        st.warning(f"No payment found for {target_abbr}")
                    else:
                        st.success(f"**Found:** {row['Name']} | **Amt:** ₹{format_indian_currency(amt_val)}")

                        # ----------- DYNAMIC BANK NAME SUGGESTIONS -----------
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

                        bank_name = st.text_input(
                            "Bank Name",
                            key="bank_name_value"
                        )

                        if bank_name:
                            filtered_banks = [
                                b for b in BANK_LIST
                                if bank_name.lower() in b.lower()
                            ]
                        else:
                            filtered_banks = BANK_LIST

                        if filtered_banks:
                            cols = st.columns(min(3, len(filtered_banks[:6])))
                            for i, bank in enumerate(filtered_banks[:6]):
                                if cols[i % len(cols)].button(bank, key=f"sugg_{bank}"):
                                    st.session_state.bank_name_value = bank
                                    st.rerun()
                        # -----------------------------------------------------

                        with st.form("entry_form", clear_on_submit=True):

                            f1, f2 = st.columns(2)
                            with f1:
                                mode = st.selectbox("Type", ["Cheque", "Demand Draft"])
                            with f2:
                                inst_no = st.text_input("No.", max_chars=6)

                            inst_date = st.date_input("Date")

                            if st.form_submit_button("Add to Batch"):
                                if re.match(r"^[a-zA-Z\s]+$", st.session_state.bank_name_value) and re.match(r"^\d{6}$", inst_no):
                                    ind_amt = format_indian_currency(amt_val)
                                    words = num2words(amt_val, lang='en_IN').replace(",", "").replace(" And ", " and ").title().replace(" And ", " and ")
                                    
                                    st.session_state.all_receipts.append({
                                        'id': str(uuid.uuid4()),
                                        'challan': next_no,
                                        'pdate': st.session_state.formatted_pdate,
                                        'name': row['Name'],
                                        'num': row['Consumer Number'],
                                        'month': sel_month,
                                        'year': sel_year,
                                        'amount': ind_amt,
                                        'words': words,
                                        'pay_type': mode,
                                        'pay_no': inst_no,
                                        'bank': st.session_state.bank_name_value,
                                        'date': inst_date.strftime("%d.%m.%Y")
                                    })

                                    st.session_state.bank_name_value = ""
                                    st.rerun()
                                else:
                                    st.error("Check Bank Name and 6-digit No.")
                else:
                    st.error(f"Column for {sel_month} {sel_year} not found.")
            else:
                st.error("Consumer Number not found.")

    # --- BATCH TABLE ---
    if st.session_state.all_receipts:
        st.divider()
        if st.checkbox("👁️ View Batch Table", value=st.session_state.show_batch):
            st.session_state.show_batch = True
            t_head = st.columns([0.8, 3, 1.5, 1.5, 1.5, 2, 1.5])
            t_head[0].write("**No.**")
            t_head[1].write("**Consumer**")
            t_head[2].write("**Amount**")
            t_head[3].write("**Mode**")
            t_head[4].write("**No.**")
            t_head[5].write("**Bank**")
            t_head[6].write("**Actions**")

            for i, rec in enumerate(st.session_state.all_receipts):
                tcol = st.columns([0.8, 3, 1.5, 1.5, 1.5, 2, 1.5])
                tcol[0].write(rec['challan'])
                tcol[1].write(rec['name'])
                tcol[2].write(f"₹{rec['amount']}")
                tcol[3].write(rec['pay_type'])
                tcol[4].write(rec['pay_no'])
                tcol[5].write(rec['bank'])

                with tcol[6]:
                    s1, s2 = st.columns(2)
                    if s1.button("✏️", key=f"e_{rec['id']}"):
                        edit_amount_dialog(i)
                    if s2.button("🗑️", key=f"d_{rec['id']}"):
                        st.session_state.all_receipts.pop(i)
                        for j in range(i, len(st.session_state.all_receipts)):
                            st.session_state.all_receipts[j]['challan'] -= 1
                        st.rerun()

        if st.button("🚀 Generate Final Word File", type="primary"):
            doc = DocxTemplate(io.BytesIO(template_bytes))
            doc.render({'receipts': st.session_state.all_receipts})
            output = io.BytesIO()
            doc.save(output)
            st.download_button(
                "📥 Download Document",
                output.getvalue(),
                file_name=f"Challans_{date.today()}.docx"
            )
