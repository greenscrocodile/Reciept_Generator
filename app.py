import streamlit as st
import pandas as pd
from docxtpl import DocxTemplate
from num2words import num2words
import io
from datetime import date
import uuid

st.set_page_config(page_title="Challan Gen", layout="wide")

# --- INDIAN CURRENCY FORMATTING (NO DECIMALS) ---
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

# --- RIGHT SIDEBAR: CONFIG & FILES ---
with st.sidebar:
    st.header("⚙️ Setup Configuration")
    s_challan = st.text_input("Starting Challan No.", disabled=st.session_state.locked)
    s_pdate = st.date_input("Payment Date (pdate)", disabled=st.session_state.locked)
    
    st.divider()
    tpl_file = st.file_uploader("Upload Word Template (.docx)", type=["docx"])
    data_file = st.file_uploader("Upload Master Excel", type=["xlsx", "csv"])
    
    if not st.session_state.locked:
        if st.button("Confirm Setup", type="primary"):
            if s_challan and tpl_file and data_file:
                st.session_state.locked = True
                st.session_state.start_no = int(s_challan)
                st.session_state.formatted_pdate = s_pdate.strftime("%d.%m.%Y")
                st.rerun()
            else:
                st.error("Please complete all fields and uploads.")
    else:
        if st.button("Reset / New Session"):
            st.session_state.locked = False
            st.session_state.all_receipts = []
            st.session_state.show_batch = False
            st.rerun()

# --- MAIN AREA ---
st.title("📑 Receipt Generation Workflow")

if st.session_state.locked:
    curr_count = len(st.session_state.all_receipts)
    next_no = st.session_state.start_no + curr_count
    
    h1, h2, h3, h4 = st.columns(4)
    h1.metric("Starting No.", st.session_state.start_no)
    h2.metric("Next Challan No.", next_no)
    h3.metric("Payment Date", st.session_state.formatted_pdate)
    h4.metric("Batch Count", curr_count)

    df = pd.read_excel(data_file) if "xlsx" in data_file.name else pd.read_csv(data_file)
    st.divider()
    
    # 1. Sequential Workflow
    c1, c2 = st.columns(2)
    with c1:
        month_list = ["January", "February", "March", "April", "May", "June", 
                      "July", "August", "September", "October", "November", "December"]
        sel_month = st.selectbox("Select Month", options=month_list)
    with c2:
        sel_year = st.selectbox("Select Year", options=[2025, 2026])

    search_num = st.text_input("Enter Consumer Number")
    
    if search_num:
        m_idx = month_list.index(sel_month) + 1
        result = df[(df['Consumer Number'].astype(str) == search_num) & 
                    (df['Month'] == m_idx) & (df['Year'] == sel_year)]

        if not result.empty:
            row = result.iloc[0]
            amt_val = float(row['Amount'])
            ind_amt = format_indian_currency(amt_val)
            words = num2words(amt_val, lang='en_IN').replace(",", "").replace(" And ", " and ").title().replace(" And ", " and ")
            
            st.success(f"**Name:** {row['Name']} | **Amount:** ₹{ind_amt}")

            with st.form("instrument_details", clear_on_submit=True):
                bank_name = st.text_input("Bank Name")
                f1, f2 = st.columns(2)
                with f1: mode = st.selectbox("Type", ["Cheque", "Demand Draft"])
                with f2: inst_no = st.text_input(f"{mode} Number", max_chars=6)
                inst_date = st.date_input(f"{mode} Date")
                
                if st.form_submit_button("Add to Batch"):
                    if bank_name and inst_no and len(inst_no) == 6:
                        new_rec = {
                            'id': str(uuid.uuid4()), # Unique ID for deleting
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
                            'bank': bank_name,
                            'date': inst_date.strftime("%d.%m.%Y")
                        }
                        st.session_state.all_receipts.append(new_rec)
                        # 2. Reset the eye/table button to OFF when added
                        st.session_state.show_batch = False
                        st.success(f"Added Challan {next_no} to batch!")
                        st.rerun()
                    else:
                        st.error("Check mandatory fields and ensure 6-digit instrument number.")
        else:
            st.error("No record found.")

    # --- BATCH VIEW & DOWNLOAD ---
    if st.session_state.all_receipts:
        st.divider()
        # Toggle with session state persistence
        if st.checkbox("👁️ View Batch Table", value=st.session_state.show_batch):
            st.session_state.show_batch = True
            
            # 4. Table with Delete Button Logic
            for i, rec in enumerate(st.session_state.all_receipts):
                tcol1, tcol2, tcol3, tcol4 = st.columns([1, 4, 2, 1])
                # 1. No amount in words in this display
                tcol1.write(f"#{rec['challan']}")
                tcol2.write(f"{rec['name']} ({rec['num']})")
                tcol3.write(f"₹{rec['amount']}")
                
                # 4. Red Delete Button
                if tcol4.button("🗑️ Delete", key=f"del_{rec['id']}", help="Remove from batch"):
                    st.session_state.all_receipts.pop(i)
                    # Recalculate subsequent challan numbers to keep them serial
                    for j in range(i, len(st.session_state.all_receipts)):
                        st.session_state.all_receipts[j]['challan'] -= 1
                    st.rerun()
        else:
            st.session_state.show_batch = False
        
        if st.button("🚀 Finalize & Generate Word Doc", type="primary"):
            doc = DocxTemplate(tpl_file)
            doc.render({'receipts': st.session_state.all_receipts})
            output = io.BytesIO()
            doc.save(output)
            fn = f"receipt_{date.today().strftime('%d_%m_%Y')}.docx"
            st.download_button("📥 Click to Download File", output.getvalue(), file_name=fn)
