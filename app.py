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
    [data-testid="stVerticalBlock"] > div { gap: 0.5rem !important; }
    div[data-testid="column"] button { margin-top: 28px !important; }
    
    /* Enforce fixed logo size */
    [data-testid="stImage"] img {
        width: 65px !important; height: 65px !important;
        object-fit: contain !important; border-radius: 5px;
        border: 1px solid #eee; display: block;
        margin-left: auto; margin-right: auto;
    }
    
    /* Table font alignment and sizing */
    .stMarkdown p {
        font-size: 14px !important;
        line-height: 1.6 !important;
        margin-bottom: 0px !important;
    }
    
    /* Ensure the dynamic instrument rows look uniform */
    .instrument-row {
        background-color: #f9f9f9;
        padding: 5px;
        border-radius: 5px;
        margin-bottom: 2px;
    }
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
if 'all_receipts' not in st.session_state: st.session_state.all_receipts = []
if 'locked' not in st.session_state: st.session_state.locked = False
if 'selected_bank' not in st.session_state: st.session_state.selected_bank = ""
if 'show_batch' not in st.session_state: st.session_state.show_batch = False
if 'is_period' not in st.session_state: st.session_state.is_period = False
if 'consumer_key' not in st.session_state: st.session_state.consumer_key = 0 
if 'temp_instruments' not in st.session_state: st.session_state.temp_instruments = []

with st.sidebar:
    st.header("⚙️ Configuration")
    s_challan = st.text_input("Starting Challan", disabled=st.session_state.locked)
    s_pdate = st.date_input("Challan Date", disabled=st.session_state.locked)
    st.divider()
    TEMPLATE_NAME = "Test.docx"
    template_bytes = None
    if os.path.exists(TEMPLATE_NAME):
        st.success("✅ Challan Template Loaded")
        with open(TEMPLATE_NAME, "rb") as f: template_bytes = f.read()
    else: st.error(f"❌ {TEMPLATE_NAME} missing!")
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

if st.session_state.locked:
    # Top Metrics
    curr_count = len(st.session_state.all_receipts)
    next_no = st.session_state.start_no + curr_count
    m1, m2, m3, m4 = st.columns(4)
    m1.metric("First Challan", st.session_state.start_no)
    m2.metric("Current No.", next_no)
    m3.metric("Date", st.session_state.formatted_pdate)
    m4.metric("Entered", curr_count)

    try:
        df = pd.read_excel(data_file, sheet_name="BILL")
    except: st.error("Sheet 'BILL' not found."); st.stop()

    st.divider()
    
    # Check if we should disable core inputs
    has_active_instruments = len(st.session_state.temp_instruments) > 0

    col_t1, col_t2 = st.columns([0.2, 0.8])
    with col_t1:
        toggle_label = "Single Month Mode" if not st.session_state.is_period else "Period Mode"
        # RESTRICTION: Disable toggle if instruments are being added
        if st.button(toggle_label, disabled=has_active_instruments):
            st.session_state.is_period = not st.session_state.is_period
            st.rerun()

    month_list = ["January", "February", "March", "April", "May", "June", "July", "August", "September", "October", "November", "December"]
    month_abbr = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
    year_options = [2026, 2025] 

    if not st.session_state.is_period:
        c1, c2 = st.columns(2)
        with c1: sel_month = st.selectbox("Select Month", options=month_list, disabled=has_active_instruments)
        with c2: sel_year = st.selectbox("Select Year", options=year_options, index=0, disabled=has_active_instruments)
        display_month_text = f"{sel_month} - {sel_year}"
        target_months = [(sel_month, sel_year)]
    else:
        c1, c2, c3, c4 = st.columns(4)
        with c1: f_month = st.selectbox("From Month", options=month_list, disabled=has_active_instruments)
        with c2: f_year = st.selectbox("From Year", options=year_options, index=0, disabled=has_active_instruments)
        with c3: t_month = st.selectbox("To Month", options=month_list, disabled=has_active_instruments)
        with c4: t_year = st.selectbox("To Year", options=year_options, index=0, disabled=has_active_instruments)
        
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

    # RESTRICTION: Disable consumer number if instruments are being added
    search_num = st.text_input("Enter Consumer Number", max_chars=3, key=f"consumer_{st.session_state.consumer_key}", disabled=has_active_instruments)

    if st.session_state.is_period and start_date > end_date:
        st.error("'From' date must be before 'To' date.")
    elif search_num and len(search_num) == 3 and re.match(r"^\d{3}$", search_num):
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
                
                # RESTRICTION: Disable Bank selection if instruments are active
                b_col1, b_col2 = st.columns([0.9, 0.1], vertical_alignment="bottom")
                with b_col1: bank_name = st.text_input("Bank Name", value=st.session_state.selected_bank, disabled=has_active_instruments)
                with b_col2: 
                    if st.button("🔍 Select", disabled=has_active_instruments): bank_selection_dialog()

                # --- INSTRUMENT ENTRY ---
                with st.expander("💳 Add Payment Details", expanded=True):
                    restricted_mode = None
                    if st.session_state.temp_instruments:
                        restricted_mode = st.session_state.temp_instruments[0]['type']

                    with st.form("instrument_form", clear_on_submit=True):
                        # ALIGNMENT: Proper spacing for Cheque details
                        f1, f2, f3 = st.columns(3)
                        with f1: 
                            if restricted_mode:
                                st.info(f"Mode: {restricted_mode}")
                                i_type = restricted_mode
                            else:
                                i_type = st.selectbox("Type", ["Cheque", "Demand Draft"])
                        with f2: i_no = st.text_input("No.", max_chars=6)
                        with f3: i_date = st.date_input("Date")
                        
                        if st.form_submit_button("➕ Add Payment"):
                            if bank_name and re.match(r"^\d{6}$", i_no):
                                st.session_state.temp_instruments.append({
                                    'bank': bank_name, 'type': i_type, 'no': i_no, 'date': i_date.strftime("%d.%m.%Y")
                                })
                                st.rerun()
                            else: st.error("Check Bank/No.")

                    # ALIGNMENT: Uniform font and line spacing for instrument list
                    for idx, inst in enumerate(st.session_state.temp_instruments):
                        cols = st.columns([2.5, 2, 2, 2, 0.5])
                        cols[0].write(f"🏦 {inst['bank']}")
                        cols[1].write(f"📄 {inst['type']}")
                        cols[2].write(f"🔢 {inst['no']}")
                        cols[3].write(f"📅 {inst['date']}")
                        if cols[4].button("🗑️", key=f"del_tmp_{idx}"): st.session_state.temp_instruments.pop(idx); st.rerun()

                if st.button("🚀 Add to Batch", type="primary"):
                    if not st.session_state.temp_instruments: st.error("Add at least One Payment Details.")
                    else:
                        st.session_state.all_receipts.append({
                            'id': str(uuid.uuid4()), 'challan': next_no, 'pdate': st.session_state.formatted_pdate,
                            'name': row['Name'], 'num': row['Consumer Number'], 'month': display_month_text, 
                            'amount': format_indian_currency(total_amt), 
                            'words': num2words(total_amt, lang='en_IN').title(),
                            'pay_type': st.session_state.temp_instruments[0]['type'],
                            'pay_no': ", ".join([i['no'] for i in st.session_state.temp_instruments]),
                            'bank': bank_name,
                            'date': ", ".join(list(set([i['date'] for i in st.session_state.temp_instruments])))
                        })
                        st.session_state.temp_instruments = []; st.session_state.selected_bank = ""; st.session_state.is_period = False; st.session_state.consumer_key += 1; st.rerun()

    if st.session_state.all_receipts:
        st.divider()
        if st.checkbox("👁️ View Batch Table", value=st.session_state.show_batch):
            st.session_state.show_batch = True
            t_head = st.columns([0.7, 2.5, 1.5, 1.2, 1.2, 1.8, 1.1])
            t_head[0].write("**No.**"); t_head[1].write("**Consumer**"); t_head[2].write("**Amount**"); t_head[3].write("**Mode**"); t_head[4].write("**No.**"); t_head[5].write("**Bank**"); t_head[6].write("**Actions**")
            for i, rec in enumerate(st.session_state.all_receipts):
                tcol = st.columns([0.7, 2.5, 1.5, 1.2, 1.2, 1.8, 1.1])
                tcol[0].write(rec['challan']); tcol[1].write(rec['name']); tcol[2].write(f"₹{rec['amount']}"); tcol[3].write(rec['pay_type']); tcol[4].write(rec['pay_no']); tcol[5].write(rec['bank'])
                with tcol[6]:
                    s1, s2 = st.columns(2)
                    if s1.button("✏️", key=f"e_{rec['id']}"): edit_amount_dialog(i)
                    if s2.button("🗑️", key=f"d_{rec['id']}"):
                        st.session_state.all_receipts.pop(i)
                        for j in range(i, len(st.session_state.all_receipts)): st.session_state.all_receipts[j]['challan'] -= 1
                        st.rerun()
        if st.button("🚀 Finalize Word File", type="primary"):
            doc = DocxTemplate(io.BytesIO(template_bytes))
            doc.render({'receipts': st.session_state.all_receipts})
            output = io.BytesIO(); doc.save(output); st.download_button("📥 Download", output.getvalue(), file_name=f"Challans_{date.today()}.docx")



