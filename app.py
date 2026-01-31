import streamlit as st
import pandas as pd
from docxtpl import DocxTemplate
from num2words import num2words
import io
from datetime import date
import uuid

st.set_page_config(page_title="Challan Gen", layout="wide")

# --- INDIAN CURRENCY FORMATTING ---
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
for key in ['all_receipts', 'locked', 'show_batch', 'edit_mode', 'preview_mode']:
    if key not in st.session_state:
        st.session_state[key] = [] if 'receipts' in key else False

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
        if st.button("Reset / New Session"):
            for k in ['locked', 'show_batch', 'edit_mode', 'preview_mode']: st.session_state[k] = False
            st.session_state.all_receipts = []
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
        month_list = ["January", "February", "March", "April", "May", "June", "July", "August", "September", "October", "November", "December"]
        sel_month = st.selectbox("Select Month", options=month_list)
    with c2:
        sel_year = st.selectbox("Select Year", options=[2025, 2026])

    search_num = st.text_input("Enter Consumer Number")
    
    if search_num:
        m_idx = month_list.index(sel_month) + 1
        result = df[(df['Consumer Number'].astype(str) == search_num) & (df['Month'] == m_idx) & (df['Year'] == sel_year)]

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
                        st.session_state.all_receipts.append({
                            'id': str(uuid.uuid4()), 'challan': next_no, 'pdate': st.session_state.formatted_pdate,
                            'name': row['Name'], 'num': row['Consumer Number'], 'month': sel_month, 'year': sel_year,
                            'amount': ind_amt, 'words': words, 'pay_type': mode, 'pay_no': inst_no, 'bank': bank_name, 'date': inst_date.strftime("%d.%m.%Y")
                        })
                        st.session_state.show_batch = False
                        st.rerun()

    # --- BATCH VIEW ---
    if st.session_state.all_receipts:
        st.divider()
        if st.checkbox("👁️ View Batch Table", value=st.session_state.show_batch):
            st.session_state.show_batch = True
            # Header Row
            t1, t2, t3, t4, t5 = st.columns([0.8, 2.5, 1.5, 2.5, 2.7])
            t1.bold("No.") ; t2.bold("Consumer") ; t3.bold("Amount") ; t4.bold("Instrument/Bank") ; t5.bold("Actions")
            
            for i, rec in enumerate(st.session_state.all_receipts):
                r1, r2, r3, r4, r5 = st.columns([0.8, 2.5, 1.5, 2.5, 2.7])
                r1.write(f"#{rec['challan']}")
                r2.write(f"{rec['name']}")
                r3.write(f"₹{rec['amount']}")
                r4.write(f"{rec['pay_type']} {rec['pay_no']} - {rec['bank']}")
                
                # Action Buttons
                btn_col1, btn_col2, btn_col3 = r5.columns(3)
                if btn_col1.button("👁️", key=f"pre_{rec['id']}", help="Preview"):
                    st.session_state.preview_mode = rec
                if btn_col2.button("✏️", key=f"edt_{rec['id']}", help="Edit Amount"):
                    st.session_state.edit_mode = rec
                if btn_col3.button("🗑️", key=f"del_{rec['id']}"):
                    st.session_state.all_receipts.pop(i)
                    for j in range(i, len(st.session_state.all_receipts)): st.session_state.all_receipts[j]['challan'] -= 1
                    st.rerun()

    # --- MODALS / POPUPS ---
    if st.session_state.preview_mode:
        p = st.session_state.preview_mode
        with st.expander("🔍 Challan Preview", expanded=True):
            st.write(f"**Challan No:** {p['challan']} | **Date:** {p['pdate']}")
            st.write(f"**Name:** {p['name']} ({p['num']})")
            st.write(f"**Amount:** ₹{p['amount']} ({p['words']} Only)")
            st.write(f"**Payment:** {p['pay_type']} No. {p['pay_no']} dated {p['date']} from {p['bank']}")
            if st.button("Close Preview"): st.session_state.preview_mode = False; st.rerun()

    if st.session_state.edit_mode:
        e = st.session_state.edit_mode
        with st.expander("✏️ Edit Amount", expanded=True):
            new_amt = st.text_input("New Amount", value=str(e['amount']).replace(",",""))
            if st.button("Save Changes"):
                formatted = format_indian_currency(new_amt)
                word_upd = num2words(float(new_amt), lang='en_IN').replace(",", "").replace(" And ", " and ").title().replace(" And ", " and ")
                for item in st.session_state.all_receipts:
                    if item['id'] == e['id']:
                        item['amount'] = formatted
                        item['words'] = word_upd
                st.session_state.edit_mode = False; st.rerun()

    if st.session_state.all_receipts:
        if st.button("🚀 Finalize & Generate Word Doc", type="primary"):
            doc = DocxTemplate(tpl_file)
            doc.render({'receipts': st.session_state.all_receipts})
            output = io.BytesIO() ; doc.save(output)
            fn = f"receipt_{date.today().strftime('%d_%m_%Y')}.docx"
            st.download_button("📥 Download", output.getvalue(), file_name=fn)
