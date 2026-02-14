import streamlit as st
import pandas as pd
from docxtpl import DocxTemplate
from num2words import num2words
import io
from datetime import date, datetime
import uuid
import re
import os

# --- MASTER BANK LIST ---
INDIAN_BANKS = [
    "State Bank of India", "Indian Bank", "Indian Overseas Bank", "Canara Bank", 
    "Bank of Baroda", "Punjab National Bank", "Union Bank of India", "HDFC Bank", 
    "ICICI Bank", "Axis Bank", "Kotak Mahindra Bank", "IDBI Bank", "IndusInd Bank", 
    "Federal Bank", "UCO Bank", "Central Bank of India", "Bank of India", 
    "South Indian Bank", "Karur Vysya Bank", "Karnataka Bank", "City Union Bank", 
    "Yes Bank", "IDFC First Bank", "Standard Chartered", "HSBC Bank", "Bandhan Bank"
]

st.set_page_config(page_title="Challan Master", layout="wide")

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
    except: return "0"

if 'all_receipts' not in st.session_state: st.session_state.all_receipts = []
if 'locked' not in st.session_state: st.session_state.locked = False
if 'bank_input' not in st.session_state: st.session_state.bank_input = ""

# --- SIDEBAR ---
with st.sidebar:
    st.header("⚙️ Configuration")
    s_challan = st.text_input("Starting Challan", disabled=st.session_state.locked)
    s_pdate = st.date_input("Present Date", disabled=st.session_state.locked)
    st.divider()
    TEMPLATE_NAME = "Test.docx"
    if os.path.exists(TEMPLATE_NAME):
        with open(TEMPLATE_NAME, "rb") as f: template_bytes = f.read()
    else: template_bytes = None
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

# --- MAIN WORKFLOW ---
if st.session_state.locked:
    curr_count = len(st.session_state.all_receipts)
    next_no = st.session_state.start_no + curr_count
    st.columns(4)[0].metric("Next No.", next_no)

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

    target_str = f"{month_abbr[month_list.index(sel_month)]}-{str(sel_year)[2:]}"
    search_num = st.text_input("Enter Consumer Number (3 Digits)", max_chars=3)
    
    if search_num and re.match(r"^\d{3}$", search_num):
        result = df[df['Consumer Number'].astype(str) == search_num]
        if not result.empty:
            row = result.iloc[0]
            target_col = next((col for col in df.columns if str(col).strip() == target_str or 
                              (isinstance(col, (datetime, pd.Timestamp)) and col.month == month_list.index(sel_month)+1 and col.year == sel_year)), None)
            
            if target_col is not None:
                amt_val = row[target_col]
                if not pd.isna(amt_val) and amt_val != 0:
                    st.success(f"**Found:** {row['Name']} | **Amt:** ₹{format_indian_currency(amt_val)}")
                    
                    # --- DYNAMIC TEXT BOX WITH LIMITED SUGGESTIONS ---
                    current_bank = st.text_input("Bank Name", key="bank_field")
                    
                    if current_bank:
                        # Filter and limit to exactly 5 suggestions
                        suggestions = [b for b in INDIAN_BANKS if current_bank.lower() in b.lower()][:5]
                        if suggestions:
                            st.write("Suggestions (Click to apply):")
                            cols = st.columns(5) # Five buttons side-by-side
                            for i, s in enumerate(suggestions):
                                if cols[i].button(s, key=f"sug_{i}"):
                                    # This is a conceptual trigger; for a form we use the text_input value
                                    st.info(f"Selected: {s}. Please re-type or confirm below.")

                    with st.form("entry_form", clear_on_submit=True):
                        # Re-verify the name here for the form submission
                        final_bank = st.text_input("Confirm/Final Bank Name", value=current_bank)
                        
                        f1, f2 = st.columns(2)
                        with f1: mode = st.selectbox("Type", ["Cheque", "Demand Draft"])
                        with f2: inst_no = st.text_input("No.", max_chars=6)
                        inst_date = st.date_input("Date")
                        
                        if st.form_submit_button("Add to Batch"):
                            if final_bank and re.match(r"^\d{6}$", inst_no):
                                ind_amt = format_indian_currency(amt_val)
                                words = num2words(amt_val, lang='en_IN').replace(",", "").replace(" And ", " and ").title().replace(" And ", " and ")
                                st.session_state.all_receipts.append({
                                    'id': str(uuid.uuid4()), 'challan': next_no, 'pdate': st.session_state.formatted_pdate,
                                    'name': row['Name'], 'num': row['Consumer Number'], 'month': sel_month, 'year': sel_year,
                                    'amount': ind_amt, 'words': words, 'pay_type': mode, 'pay_no': inst_no, 'bank': final_bank, 'date': inst_date.strftime("%d.%m.%Y")
                                })
                                st.rerun()
                            else: st.error("Invalid Entry: Check Bank Name and 6-digit No.")
