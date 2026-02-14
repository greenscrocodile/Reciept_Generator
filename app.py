import streamlit as st
import pandas as pd
from docxtpl import DocxTemplate
from num2words import num2words
import io
from datetime import date, datetime
import uuid
import re
import os

# --- FULL BANK DATABASE ---
ALL_BANKS = [
    "State Bank of India", "Indian Bank", "Indian Overseas Bank", 
    "Canara Bank", "Bank of Baroda", "Punjab National Bank", 
    "Union Bank of India", "HDFC Bank", "ICICI Bank", "Axis Bank", 
    "Kotak Mahindra Bank", "IDBI Bank", "IndusInd Bank", "Federal Bank",
    "UCO Bank", "Central Bank of India", "Bank of India", "South Indian Bank",
    "Karur Vysya Bank", "Karnataka Bank", "City Union Bank", "Yes Bank",
    "IDFC First Bank", "Standard Chartered", "HSBC Bank", "Bandhan Bank"
]

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

# --- INITIALIZATION ---
if 'all_receipts' not in st.session_state: st.session_state.all_receipts = []
if 'locked' not in st.session_state: st.session_state.locked = False

# --- SIDEBAR ---
with st.sidebar:
    st.header("⚙️ Configuration")
    s_challan = st.text_input("Starting Challan", disabled=st.session_state.locked)
    s_pdate = st.date_input("Challan Date", disabled=st.session_state.locked)
    st.divider()
    
    TEMPLATE_NAME = "Test.docx"
    if os.path.exists(TEMPLATE_NAME):
        st.success(f"✅ Template loaded")
        with open(TEMPLATE_NAME, "rb") as f: template_bytes = f.read()
    else:
        st.error(f"❌ {TEMPLATE_NAME} not found!"); template_bytes = None

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
    st.columns(4)[0].metric("Next Challan", next_no)
    
    try:
        df = pd.read_excel(data_file, sheet_name="BILL")
    except:
        st.error("Sheet 'BILL' not found."); st.stop()

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

    if search_num and re.match(r"^\d{3}$", search_num):
        result = df[df['Consumer Number'].astype(str) == search_num]
        if not result.empty:
            row = result.iloc[0]
            target_col = next((col for col in df.columns if str(col) == target_abbr or (isinstance(col, (datetime, pd.Timestamp)) and col.month == m_idx + 1 and col.year == sel_year)), None)
            
            if target_col is not None:
                amt_val = row[target_col]
                if not pd.isna(amt_val) and amt_val != 0:
                    st.success(f"**Found:** {row['Name']} | **Amt:** ₹{format_indian_currency(amt_val)}")

                    with st.form("entry_form", clear_on_submit=True):
                        # --- THE DYNAMIC BANK INPUT ---
                        # 1. Capture the typed value
                        typed_bank = st.text_input("Type Bank Name (e.g. 'Indi')", help="Suggestions will appear in the dropdown below as you type")
                        
                        # 2. Filter the list based on typed value
                        suggestions = [b for b in ALL_BANKS if typed_bank.lower() in b.lower()] if typed_bank else ALL_BANKS
                        
                        # 3. Use selectbox to show ONLY relevant suggestions
                        bank_name = st.selectbox("Suggestions:", options=suggestions if suggestions else [typed_bank])
                        
                        f1, f2 = st.columns(2)
                        with f1: mode = st.selectbox("Type", ["Cheque", "Demand Draft"])
                        with f2: inst_no = st.text_input("No.", max_chars=6)
                        inst_date = st.date_input("Date")

                        if st.form_submit_button("Add to Batch"):
                            # Use the selectbox choice, or the typed name if no matches found
                            final_bank = bank_name if bank_name else typed_bank
                            
                            if final_bank and re.match(r"^\d{6}$", inst_no):
                                ind_amt = format_indian_currency(amt_val)
                                words = num2words(amt_val, lang='en_IN').replace(",", "").replace(" And ", " and ").title().replace(" And ", " and ")
                                st.session_state.all_receipts.append({
                                    'id': str(uuid.uuid4()), 'challan': next_no, 'pdate': st.session_state.formatted_pdate,
                                    'name': row['Name'], 'num': row['Consumer Number'], 'month': sel_month, 'year': sel_year,
                                    'amount': ind_amt, 'words': words, 'pay_type': mode, 'pay_no': inst_no, 'bank': final_bank, 'date': inst_date.strftime("%d.%m.%Y")
                                })
                                st.rerun()
                            else: st.error("Fill Bank Name and 6-digit No.")
    
    # --- BATCH TABLE & DOWNLOAD (Existing logic preserved) ---
    if st.session_state.all_receipts:
        st.divider()
        if st.checkbox("👁️ View Batch Table"):
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
            output = io.BytesIO(); doc.save(output)
            st.download_button("📥 Download", output.getvalue(), file_name=f"Challans_{date.today()}.docx")
