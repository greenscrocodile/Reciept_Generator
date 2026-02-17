import streamlit as st
import pandas as pd
from docxtpl import DocxTemplate
from num2words import num2words
import io
from datetime import date, datetime
import uuid
import re
import os

# --- APP CONFIGURATION ---
st.set_page_config(page_title="Challan Master", layout="wide")

# --- CUSTOM CSS ---
st.markdown("""
    <style>
    [data-testid="stVerticalBlock"] > div { gap: 0rem !important; }
    div[data-testid="column"] button { margin-top: 28px !important; }
    [data-testid="stImage"] img {
        width: 65px !important; height: 65px !important;
        object-fit: contain !important; border-radius: 5px;
        border: 1px solid #eee; display: block;
        margin-left: auto; margin-right: auto;
    }
    [data-testid="column"] { display: flex; flex-direction: column; align-items: center; }
    </style>
    """, unsafe_allow_html=True)

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
    {"name": "The Hongkong and Shanghai Banking Corporation", "file": "logos/HSBC.jpg"},
    {"name": "Tamilnad Mercantile Bank", "file": "logos/Tamilnad Mercantile Bank.jpg"},
    {"name": "Karnataka Bank", "file": "logos/Karnataka Bank.jpg"},
    {"name": "CSB Bank", "file": "logos/CSB Bank.jpg"},
    {"name": "Punjab National Bank", "file": "logos/Punjab National Bank.jpg"},
    {"name": "Federal Bank", "file": "logos/Federal Bank.jpg"},
]

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

@st.dialog("Select Bank", width="medium")
def bank_selection_dialog():
    st.write("### 🏦 Select Bank")
    cols = st.columns(7, gap="small")
    for i, bank in enumerate(BANKS):
        with cols[i % 7]:
            if os.path.exists(bank['file']): st.image(bank['file'])
            else: st.caption(bank['name'])
            if st.button("Select", key=f"btn_{i}"):
                st.session_state.selected_bank = bank['name']
                st.rerun()

# --- INITIALIZATION ---
if 'all_receipts' not in st.session_state: st.session_state.all_receipts = []
if 'locked' not in st.session_state: st.session_state.locked = False
if 'selected_bank' not in st.session_state: st.session_state.selected_bank = ""
if 'show_batch' not in st.session_state: st.session_state.show_batch = False
if 'is_period' not in st.session_state: st.session_state.is_period = False
if 'consumer_key' not in st.session_state: st.session_state.consumer_key = 0 
if 'temp_instruments' not in st.session_state: st.session_state.temp_instruments = [] # NEW

with st.sidebar:
    st.header("⚙️ Configuration")
    s_challan = st.text_input("Starting Challan", disabled=st.session_state.locked)
    s_pdate = st.date_input("Challan Date", disabled=st.session_state.locked)
    st.divider()
    TEMPLATE_NAME = "Test.docx"
    if os.path.exists(TEMPLATE_NAME):
        with open(TEMPLATE_NAME, "rb") as f: template_bytes = f.read()
    data_file = st.file_uploader("Upload Master Data (.xlsx)", type=["xlsx"])
    if not st.session_state.locked:
        if st.button("Confirm Setup", type="primary"):
            if s_challan and data_file:
                st.session_state.locked = True
                st.session_state.start_no = int(s_challan)
                st.session_state.formatted_pdate = s_pdate.strftime("%d.%m.%Y")
                st.rerun()
    else:
        if st.button("Reset Session"):
            st.session_state.locked = False
            st.session_state.all_receipts = []
            st.rerun()

if st.session_state.locked:
    curr_count = len(st.session_state.all_receipts)
    next_no = st.session_state.start_no + curr_count
    st.columns(4)[1].metric("Current No.", next_no)

    try:
        df = pd.read_excel(data_file, sheet_name="BILL")
    except: st.error("Sheet 'BILL' not found."); st.stop()

    st.divider()
    
    # Toggle logic remains same
    col_t1, col_t2 = st.columns([0.2, 0.8])
    with col_t1:
        toggle_label = "Switch to Single Month" if st.session_state.is_period else "Switch to Period"
        if st.button(toggle_label):
            st.session_state.is_period = not st.session_state.is_period
            st.rerun()

    month_list = ["January", "February", "March", "April", "May", "June", "July", "August", "September", "October", "November", "December"]
    month_abbr = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
    year_options = [2026, 2025] 

    if not st.session_state.is_period:
        c1, c2 = st.columns(2)
        with c1: sel_month = st.selectbox("Select Month", options=month_list)
        with c2: sel_year = st.selectbox("Select Year", options=year_options, index=0)
        display_month_text = f"{sel_month} - {sel_year}"
        target_months = [(sel_month, sel_year)]
    else:
        c1, c2, c3, c4 = st.columns(4)
        with c1: f_month = st.selectbox("From Month", options=month_list)
        with c2: f_year = st.selectbox("From Year", options=year_options, index=0)
        with c3: t_month = st.selectbox("To Month", options=month_list)
        with c4: t_year = st.selectbox("To Year", options=year_options, index=0)
        start_date = datetime(f_year, month_list.index(f_month) + 1, 1)
        end_date = datetime(t_year, month_list.index(t_month) + 1, 1)
        target_months = []
        if start_date <= end_date:
            curr = start_date
            while curr <= end_date:
                target_months.append((month_list[curr.month-1], curr.year))
                if curr.month == 12: curr = datetime(curr.year + 1, 1, 1)
                else: curr = datetime(curr.year, curr.month + 1, 1)
            years_dict = {}
            for m, y in target_months: years_dict.setdefault(y, []).append(m)
            parts = [f"{', '.join(m_list)} - {y}" for y, m_list in years_dict.items()]
            display_month_text = " and ".join(parts)
        else: display_month_text = None

    search_num = st.text_input("Enter Consumer Number", max_chars=3, key=f"consumer_{st.session_state.consumer_key}")

    if search_num and len(search_num) == 3 and re.match(r"^\d{3}$", search_num):
        result = df[df['Consumer Number'].astype(str).str.zfill(3) == search_num]
        if not result.empty:
            row = result.iloc[0]
            total_amt = 0
            for m, y in target_months:
                t_abbr = f"{month_abbr[month_list.index(m)]}-{str(y)[2:]}"
                t_col = next((col for col in df.columns if str(col).strip() == t_abbr or (isinstance(col, (datetime, pd.Timestamp)) and col.month == month_list.index(m) + 1 and col.year == y)), None)
                if t_col is not None: total_amt += row[t_col] if not pd.isna(row[t_col]) else 0

            if total_amt > 0:
                st.success(f"**Found:** {row['Name']} | **Total Amt:** ₹{format_indian_currency(total_amt)}")
                
                # --- DYNAMIC INSTRUMENT ENTRY ---
                with st.expander("💳 Add Payment Instruments (Cheques/DDs)", expanded=True):
                    ic1, ic2 = st.columns([0.8, 0.2], vertical_alignment="bottom")
                    with ic1: b_name = st.text_input("Bank Name", value=st.session_state.selected_bank)
                    with ic2: 
                        if st.button("🔍 Select"): bank_selection_dialog()

                    with st.form("instrument_form", clear_on_submit=True):
                        f1, f2, f3 = st.columns([1, 1, 1])
                        with f1: i_type = st.selectbox("Type", ["Cheque", "Demand Draft"])
                        with f2: i_no = st.text_input("No.", max_chars=6)
                        with f3: i_date = st.date_input("Date")
                        
                        if st.form_submit_button("➕ Add Instrument"):
                            if b_name and re.match(r"^\d{6}$", i_no):
                                st.session_state.temp_instruments.append({
                                    'bank': b_name, 'type': i_type, 'no': i_no, 'date': i_date.strftime("%d.%m.%Y")
                                })
                                st.rerun()
                            else: st.error("Enter valid Bank Name and 6-digit No.")

                    # Show currently added instruments for this challan
                    for idx, inst in enumerate(st.session_state.temp_instruments):
                        cols = st.columns([3, 2, 2, 2, 0.5])
                        cols[0].write(f"🏦 {inst['bank']}")
                        cols[1].write(f"📄 {inst['type']}")
                        cols[2].write(f"# {inst['no']}")
                        cols[3].write(f"📅 {inst['date']}")
                        if cols[4].button("🗑️", key=f"del_tmp_{idx}"):
                            st.session_state.temp_instruments.pop(idx); st.rerun()

                # Final Button to aggregate everything into the main batch
                if st.button("🚀 Finalize and Add to Batch", type="primary"):
                    if not st.session_state.temp_instruments:
                        st.error("Please add at least one payment instrument.")
                    else:
                        # You can customize how multiple cheques appear in the Word file here
                        # For now, we join the details into the single fields for the batch
                        pay_nos = ", ".join([i['no'] for i in st.session_state.temp_instruments])
                        pay_banks = ", ".join(list(set([i['bank'] for i in st.session_state.temp_instruments])))
                        pay_dates = ", ".join(list(set([i['date'] for i in st.session_state.temp_instruments])))

                        st.session_state.all_receipts.append({
                            'id': str(uuid.uuid4()), 'challan': next_no, 'pdate': st.session_state.formatted_pdate,
                            'name': row['Name'], 'num': row['Consumer Number'], 'month': display_month_text, 
                            'amount': format_indian_currency(total_amt), 
                            'words': num2words(total_amt, lang='en_IN').title() + " Only",
                            'pay_type': st.session_state.temp_instruments[0]['type'], # Example logic
                            'pay_no': pay_nos, 'bank': pay_banks, 'date': pay_dates
                        })
                        st.session_state.temp_instruments = [] # Clear temp
                        st.session_state.selected_bank = ""; st.session_state.is_period = False
                        st.session_state.consumer_key += 1; st.rerun()
