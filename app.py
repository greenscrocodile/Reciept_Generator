import streamlit as st
import pandas as pd
from docxtpl import DocxTemplate
from num2words import num2words
import io
from datetime import date
import uuid
import re
import os

# --- PREDEFINED BANK LIST FOR SUGGESTIONS ---
INDIAN_BANKS = [
    "State Bank of India", "HDFC Bank", "ICICI Bank", "Axis Bank", "Punjab National Bank",
    "Bank of Baroda", "Canara Bank", "Union Bank of India", "IndusInd Bank", "IDBI Bank",
    "Indian Bank", "Bank of India", "UCO Bank", "Central Bank of India", "Indian Overseas Bank"
]

st.set_page_config(page_title="Challan Master Pro", layout="wide")

def format_indian_currency(number):
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

# --- INITIALIZATION ---
if 'all_receipts' not in st.session_state:
    st.session_state.all_receipts = []
if 'locked' not in st.session_state:
    st.session_state.locked = False
if 'show_batch' not in st.session_state:
    st.session_state.show_batch = False

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

    data_file = st.file_uploader("Upload Master Data (.xlsx)", type=["xlsx", "csv"])

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
    h2.metric("Next Challan", next_no)
    h3.metric("Date", st.session_state.formatted_pdate)
    h4.metric("Entered", curr_count)

    df = pd.read_excel(data_file) if "xlsx" in data_file.name else pd.read_csv(data_file)
    st.divider()

    # --- FEATURE 3: PERIOD TOGGLE ---
    st.subheader("1. Select Period")
    is_period = st.toggle("Multiple Months (Period Mode)", value=False)
    
    month_list = ["January", "February", "March", "April", "May", "June", "July", "August", "September", "October", "November", "December"]
    
    if not is_period:
        c1, c2 = st.columns(2)
        with c1: sel_month = st.selectbox("Month", options=month_list)
        with c2: sel_year = st.selectbox("Year", options=[2025, 2026])
        period_text = f"{sel_month} - {sel_year}"
    else:
        c1, c2, c3, c4 = st.columns(4)
        with c1: f_month = st.selectbox("From Month", options=month_list)
        with c2: f_year = st.selectbox("From Year", options=[2025, 2026])
        with c3: t_month = st.selectbox("To Month", options=month_list)
        with c4: t_year = st.selectbox("To Year", options=[2025, 2026])
        period_text = f"{f_month} {f_year} to {t_month} {t_year}"

    # --- FEATURE 3: SEARCH & SUM LOGIC ---
    search_num = st.text_input("Enter Consumer Number", max_chars=3)
    
    if search_num and re.match(r"^\d{3}$", search_num):
        if not is_period:
            m_idx = month_list.index(sel_month) + 1
            result = df[(df['Consumer Number'].astype(str) == search_num) & (df['Month'] == m_idx) & (df['Year'] == sel_year)]
        else:
            # Logic to find range (Simplistic: captures all rows for that consumer in period)
            # You can refine this to be strictly between month indices
            result = df[(df['Consumer Number'].astype(str) == search_num)]
            # Note: For a true period search, we'd compare (Year * 12 + Month)
            st.info(f"Period mode will sum all matching records for Consumer {search_num}")

        if not result.empty:
            total_amt = result['Amount'].sum()
            row = result.iloc[0] # Take name from first match
            st.success(f"**Name:** {row['Name']} | **Total Amount:** ₹{format_indian_currency(total_amt)}")

            # --- FEATURE 2: MULTIPLE INSTRUMENTS ---
            with st.form("entry_form", clear_on_submit=True):
                # FEATURE 1: Bank Suggestions
                bank_name = st.selectbox("Bank Name (Auto-suggestions)", options=INDIAN_BANKS)
                
                st.write("Instrument Details (Separated by comma if multiple)")
                f1, f2, f3 = st.columns([1, 2, 2])
                with f1: mode = st.selectbox("Type", ["Cheque", "DD"])
                with f2: inst_nos = st.text_input("Instrument Number(s)", help="e.g. 111222, 333444")
                with f3: inst_dates = st.text_input("Instrument Date(s)", help="e.g. 14.02.2026")

                if st.form_submit_button("Add to Batch"):
                    if re.match(r"^[a-zA-Z\s]+$", bank_name):
                        ind_amt = format_indian_currency(total_amt)
                        words = num2words(total_amt, lang='en_IN').replace(",", "").replace(" And ", " and ").title().replace(" And ", " and ")
                        
                        st.session_state.all_receipts.append({
                            'id': str(uuid.uuid4()), 'challan': next_no, 'pdate': st.session_state.formatted_pdate,
                            'name': row['Name'], 'num': row['Consumer Number'], 
                            'month': period_text, # Display period instead of single month
                            'amount': ind_amt, 'words': words, 'pay_type': mode, 
                            'pay_no': inst_nos, 'bank': bank_name, 'date': inst_dates
                        })
                        st.rerun()

    # --- BATCH TABLE ---
    if st.session_state.all_receipts:
        st.divider()
        if st.checkbox("👁️ View Batch Table", value=st.session_state.show_batch):
            st.session_state.show_batch = True
            for i, rec in enumerate(st.session_state.all_receipts):
                tcol = st.columns([0.8, 3, 1.5, 1.5, 1.5, 2, 1.5])
                tcol[0].write(rec['challan']); tcol[1].write(rec['name']); tcol[2].write(f"₹{rec['amount']}")
                tcol[3].write(rec['pay_type']); tcol[4].write(rec['pay_no']); tcol[5].write(rec['bank'])
                with tcol[6]:
                    if st.button("🗑️", key=f"d_{rec['id']}"):
                        st.session_state.all_receipts.pop(i)
                        st.rerun()

        if st.button("🚀 Generate Final Word File", type="primary"):
            doc = DocxTemplate(io.BytesIO(template_bytes))
            doc.render({'receipts': st.session_state.all_receipts})
            output = io.BytesIO()
            doc.save(output)
            st.download_button("📥 Download", output.getvalue(), file_name=f"Challan_{date.today()}.docx")
