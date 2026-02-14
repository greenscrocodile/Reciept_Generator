import streamlit as st
import pandas as pd
from docxtpl import DocxTemplate
from num2words import num2words
import io
from datetime import date, datetime
import uuid
import re
import os

# --- 1. CONFIGURATION ---
st.set_page_config(page_title="Challan Master", layout="wide")

INDIAN_BANKS = [
    "State Bank of India", "Indian Bank", "Indian Overseas Bank", "Canara Bank", 
    "Bank of Baroda", "Punjab National Bank", "Union Bank of India", "HDFC Bank", 
    "ICICI Bank", "Axis Bank", "Kotak Mahindra Bank", "IDBI Bank", "IndusInd Bank", 
    "Federal Bank", "UCO Bank", "Central Bank of India", "Bank of India", 
    "South Indian Bank", "Karur Vysya Bank", "Karnataka Bank", "City Union Bank", 
    "Yes Bank", "IDFC First Bank", "Standard Chartered", "HSBC Bank", "Bandhan Bank"
]

# --- 2. UTILITY FUNCTIONS ---
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

# --- 3. SESSION INITIALIZATION ---
if 'all_receipts' not in st.session_state:
    st.session_state.all_receipts = []
if 'locked' not in st.session_state:
    st.session_state.locked = False

# --- 4. SIDEBAR: TEMPLATE LOADING & SETUP ---
with st.sidebar:
    st.header("⚙️ Configuration")
    s_challan = st.text_input("First Challan No.", disabled=st.session_state.locked)
    s_pdate = st.date_input("Present Date", disabled=st.session_state.locked)
    st.divider()
    
    TEMPLATE_NAME = "Test.docx"
    template_bytes = None
    if os.path.exists(TEMPLATE_NAME):
        st.success(f"✅ Template Loaded")
        with open(TEMPLATE_NAME, "rb") as f:
            template_bytes = f.read()
    else:
        st.error(f"❌ {TEMPLATE_NAME} not found!")

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

# --- 5. MAIN APPLICATION FLOW ---
if st.session_state.locked:
    # --- METRICS BAR ---
    curr_count = len(st.session_state.all_receipts)
    next_no = st.session_state.start_no + curr_count
    
    m1, m2, m3, m4 = st.columns(4)
    m1.metric("First Challan No.", st.session_state.start_no)
    m2.metric("Current Challan No.", next_no)
    m3.metric("Challan Date", st.session_state.formatted_pdate)
    m4.metric("Entered Challans", curr_count)

    try:
        df = pd.read_excel(data_file, sheet_name="BILL")
    except:
        st.error("Sheet 'BILL' not found."); st.stop()

    st.divider()
    
    # Period Selection
    c1, c2 = st.columns(2)
    with c1:
        month_list = ["January", "February", "March", "April", "May", "June", "July", "August", "September", "October", "November", "December"]
        month_abbr = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
        sel_month = st.selectbox("Select Month", options=month_list)
    with c2:
        sel_year = st.selectbox("Select Year", options=[2025, 2026])

    target_str = f"{month_abbr[month_list.index(sel_month)]}-{str(sel_year)[2:]}"

    # Consumer Search
    search_num = st.text_input("Enter Consumer Number (3 Digits)", max_chars=3)
    
    if search_num and re.match(r"^\d{3}$", search_num):
        result = df[df['Consumer Number'].astype(str).str.zfill(3) == search_num]
        
        if not result.empty:
            row = result.iloc[0]
            target_col = next((col for col in df.columns if str(col).strip() == target_str or 
                              (isinstance(col, (datetime, pd.Timestamp)) and col.month == month_list.index(sel_month)+1 and col.year == sel_year)), None)
            
            if target_col is not None:
                amt_val = row[target_col]
                if pd.isna(amt_val) or amt_val == 0:
                    st.warning(f"No payment data for {target_str}")
                else:
                    st.success(f"**Found:** {row['Name']} | **Amt:** ₹{format_indian_currency(amt_val)}")
                    
                    with st.form("entry_form", clear_on_submit=True):
                        # --- DYNAMIC BANK LOGIC ---
                        # To make it truly dynamic, we use a selectbox that accepts typing.
                        # This combines the 'type-to-filter' with the 'take any value' logic.
                        bank_name = st.selectbox(
                            "Bank Name (Select or type custom name below)", 
                            options=sorted(INDIAN_BANKS) + ["OTHER / NOT IN LIST"],
                            index=None,
                            placeholder="Search Banks..."
                        )
                        custom_bank = st.text_input("Manual Bank Name (Use if bank not in list above)")
                        
                        f1, f2 = st.columns(2)
                        with f1: mode = st.selectbox("Mode", ["Cheque", "Demand Draft"])
                        with f2: inst_no = st.text_input("No.", max_chars=6)
                        inst_date = st.date_input("Date")
                        
                        if st.form_submit_button("Add to Batch"):
                            # Logic: If custom bank is filled, use it. Otherwise use the selectbox.
                            final_bank = custom_bank if custom_bank else bank_name

                            if final_bank and re.match(r"^\d{6}$", inst_no):
                                ind_amt = format_indian_currency(amt_val)
                                words = num2words(amt_val, lang='en_IN').replace(",", "").replace(" And ", " and ").title().replace(" And ", " and ")
                                
                                st.session_state.all_receipts.append({
                                    'id': str(uuid.uuid4()), 'challan': next_no, 'pdate': st.session_state.formatted_pdate,
                                    'name': row['Name'], 'num': row['Consumer Number'], 'month': sel_month, 'year': sel_year,
                                    'amount': ind_amt, 'words': words, 'pay_type': mode, 'pay_no': inst_no, 'bank': final_bank, 'date': inst_date.strftime("%d.%m.%Y")
                                })
                                st.rerun()
                            else: st.error("Invalid Entry: Ensure Bank Name and 6-digit No. are correct.")

    # --- 6. BATCH TABLE ---
    if st.session_state.all_receipts:
        st.divider()
        if st.checkbox("👁️ View Batch Table"):
            for i, rec in enumerate(st.session_state.all_receipts):
                tcol = st.columns([0.8, 3, 1.5, 1.5, 1.5, 2, 0.5])
                tcol[0].write(rec['challan']); tcol[1].write(rec['name']); tcol[2].write(f"₹{rec['amount']}")
                tcol[3].write(rec['pay_type']); tcol[4].write(rec['pay_no']); tcol[5].write(rec['bank'])
                if tcol[6].button("🗑️", key=f"d_{rec['id']}"):
                    st.session_state.all_receipts.pop(i)
                    for j in range(i, len(st.session_state.all_receipts)): st.session_state.all_receipts[j]['challan'] -= 1
                    st.rerun()

        if st.button("🚀 Generate Final Document", type="primary"):
            doc = DocxTemplate(io.BytesIO(template_bytes))
            doc.render({'receipts': st.session_state.all_receipts})
            output = io.BytesIO(); doc.save(output)
            st.download_button("📥 Download", output.getvalue(), file_name=f"Challans_{date.today()}.docx")
