import streamlit as st
import pandas as pd
from docxtpl import DocxTemplate
from num2words import num2words
import io
from datetime import date

st.set_page_config(page_title="Challan Gen Pro", layout="wide")

# --- INDIAN CURRENCY FORMATTING (NO DECIMALS) ---
def format_indian_currency(number):
    try:
        main = str(int(float(str(number).replace(',', ''))))
        if len(main) <= 3: return main
        last_three = main[-3:]
        remaining = main[:-3]
        res = ""
        while len(remaining) > 2:
            res = "," + remaining[-2:] + res
            remaining = remaining[:-2]
        if remaining: res = remaining + res
        return f"{res},{last_three}"
    except: return str(number)

# --- INITIALIZATION ---
if 'all_receipts' not in st.session_state:
    st.session_state.all_receipts = []
if 'locked' not in st.session_state:
    st.session_state.locked = False
if 'show_batch' not in st.session_state:
    st.session_state.show_batch = False

# --- EDIT DIALOG (POP-UP) ---
@st.dialog("Edit Record")
def edit_record_popup(index):
    rec = st.session_state.all_receipts[index]
    
    st.write(f"Editing Challan: **{rec['challan']}** ({rec['name']})")
    
    # Editable fields with limitations
    new_amt = st.text_input("Amount", value=rec['amount'].replace(',', ''))
    new_month = st.selectbox("Month", ["January", "February", "March", "April", "May", "June", 
                                       "July", "August", "September", "October", "November", "December"],
                             index=["January", "February", "March", "April", "May", "June", 
                                    "July", "August", "September", "October", "November", "December"].index(rec['month']))
    new_year = st.selectbox("Year", [2025, 2026], index=[2025, 2026].index(rec['year']))
    new_bank = st.text_input("Bank Name", value=rec['bank'])
    new_type = st.selectbox("Type", ["Cheque", "Demand Draft"], index=0 if rec['pay_type'] == "Cheque" else 1)
    new_no = st.text_input("Number", value=rec['pay_no'], max_chars=6)
    
    # Date needs conversion for the widget
    d_parts = rec['date'].split('.')
    current_date = date(int(d_parts[2]), int(d_parts[1]), int(d_parts[0]))
    new_date = st.date_input("Instrument Date", value=current_date)

    if st.button("Save Changes"):
        # Update record
        st.session_state.all_receipts[index].update({
            'amount': format_indian_currency(new_amt),
            'words': num2words(float(new_amt), lang='en_IN').replace(",", "").replace(" And ", " and ").title().replace(" And ", " and "),
            'month': new_month,
            'year': new_year,
            'bank': new_bank,
            'pay_type': new_type,
            'pay_no': new_no,
            'date': new_date.strftime("%d.%m.%Y")
        })
        st.rerun()

# --- SIDEBAR ---
with st.sidebar:
    st.header("⚙️ Configuration")
    s_challan = st.text_input("Starting Challan No.", disabled=st.session_state.locked)
    s_pdate = st.date_input("Payment Date (pdate)", disabled=st.session_state.locked)
    st.divider()
    tpl_file = st.file_uploader("Template (.docx)", type=["docx"])
    data_file = st.file_uploader("Master Excel", type=["xlsx", "csv"])
    
    if not st.session_state.locked:
        if st.button("Confirm Setup"):
            if s_challan and tpl_file and data_file:
                st.session_state.locked = True
                st.session_state.start_no = int(s_challan)
                st.session_state.formatted_pdate = s_pdate.strftime("%d.%m.%Y")
                st.rerun()
    else:
        if st.button("Reset Session"):
            st.session_state.locked = False
            st.session_state.all_receipts = []
            st.rerun()

# --- MAIN AREA ---
st.title("📑 Receipt Workflow")

if st.session_state.locked:
    # Header Metrics
    curr_count = len(st.session_state.all_receipts)
    next_no = st.session_state.start_no + curr_count
    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Start No.", st.session_state.start_no)
    m2.metric("Next No.", next_no)
    m3.metric("Date", st.session_state.formatted_pdate)
    m4.metric("Batch Count", curr_count)

    df = pd.read_excel(data_file) if "xlsx" in data_file.name else pd.read_csv(data_file)
    st.divider()
    
    # Workflow
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
        res = df[(df['Consumer Number'].astype(str) == search_num) & (df['Month'] == m_idx) & (df['Year'] == sel_year)]

        if not res.empty:
            row = res.iloc[0]
            st.success(f"**Name:** {row['Name']} | **Amount:** ₹{format_indian_currency(row['Amount'])}")

            with st.form("entry_form", clear_on_submit=True):
                bank = st.text_input("Bank Name")
                f1, f2 = st.columns(2)
                with f1: mode = st.selectbox("Type", ["Cheque", "Demand Draft"])
                with f2: p_no = st.text_input(f"{mode} Number", max_chars=6)
                p_date = st.date_input(f"{mode} Date")
                
                if st.form_submit_button("Add to Batch"):
                    if bank and p_no and len(p_no) == 6:
                        st.session_state.all_receipts.append({
                            'challan': next_no, 'pdate': st.session_state.formatted_pdate,
                            'name': row['Name'], 'num': row['Consumer Number'],
                            'month': sel_month, 'year': sel_year,
                            'amount': format_indian_currency(row['Amount']),
                            'words': num2words(float(row['Amount']), lang='en_IN').replace(",", "").replace(" And ", " and ").title().replace(" And ", " and "),
                            'pay_type': mode, 'pay_no': p_no, 'bank': bank, 'date': p_date.strftime("%d.%m.%Y")
                        })
                        # 2. View batch table button should off when record added
                        st.session_state.show_batch = False
                        st.rerun()

    # --- BATCH VIEW & DOWNLOAD ---
    if st.session_state.all_receipts:
        st.divider()
        st.session_state.show_batch = st.checkbox("👁️ View Batch Table", value=st.session_state.show_batch)
        
        if st.session_state.show_batch:
            # Custom Table with Edit/Delete
            # 1. No Word representation in table
            cols = st.columns([1, 2, 1, 1, 1, 1, 1, 1])
            fields = ["Challan", "Name", "Number", "Amount", "Mode", "Inst No", "Edit", "Delete"]
            for col, field in zip(cols, fields): col.write(f"**{field}**")
            
            for i, r in enumerate(st.session_state.all_receipts):
                c = st.columns([1, 2, 1, 1, 1, 1, 1, 1])
                c[0].write(r['challan'])
                c[1].write(r['name'])
                c[2].write(r['num'])
                c[3].write(r['amount'])
                c[4].write(r['pay_type'])
                c[5].write(r['pay_no'])
                # 3. Edit Button (Blue)
                if c[6].button("Edit", key=f"ed_{i}", type="primary"):
                    edit_record_popup(i)
                # 4. Delete Button
                if c[7].button("Delete", key=f"del_{i}"):
                    st.session_state.all_receipts.pop(i)
                    # Adjust subsequent challan numbers if needed? 
                    # Usually, challans are serial, so deleting might need logic update
                    st.rerun()
        
        if st.button("🚀 Finalize & Download Word Doc"):
            doc = DocxTemplate(tpl_file)
            doc.render({'receipts': st.session_state.all_receipts})
            output = io.BytesIO()
            doc.save(output)
            st.download_button("📥 Download", output.getvalue(), file_name=f"receipt_{date.today().strftime('%d_%m_%Y')}.docx")
