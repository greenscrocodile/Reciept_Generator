import streamlit as st
import pandas as pd
from docxtpl import DocxTemplate
from num2words import num2words
import io
from datetime import date

st.set_page_config(page_title="Challan Gen Pro", layout="wide")

# --- INDIAN CURRENCY FORMATTING (NO DECIMALS) ---
def format_indian_currency(number):
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

# --- INITIALIZATION ---
if 'all_receipts' not in st.session_state:
    st.session_state.all_receipts = []
if 'locked' not in st.session_state:
    st.session_state.locked = False
if 'view_table' not in st.session_state:
    st.session_state.view_table = False

# --- RIGHT SIDEBAR: CONFIG ---
with st.sidebar:
    st.header("⚙️ Setup")
    s_challan = st.text_input("Starting Challan No.", disabled=st.session_state.locked)
    s_pdate = st.date_input("Payment Date", disabled=st.session_state.locked)
    tpl_file = st.file_uploader("Upload Word Template", type=["docx"])
    data_file = st.file_uploader("Upload Master Excel", type=["xlsx", "csv"])
    
    if not st.session_state.locked:
        if st.button("Confirm Setup", type="primary"):
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
    
    # 1. Sequential Entry
    month_list = ["January", "February", "March", "April", "May", "June", 
                  "July", "August", "September", "October", "November", "December"]
    c1, c2 = st.columns(2)
    with c1: sel_month = st.selectbox("Select Month", options=month_list)
    with c2: sel_year = st.selectbox("Select Year", options=[2025, 2026])

    search_num = st.text_input("Enter Consumer Number")
    
    if search_num:
        m_idx = month_list.index(sel_month) + 1
        result = df[(df['Consumer Number'].astype(str) == search_num) & (df['Month'] == m_idx) & (df['Year'] == sel_year)]

        if not result.empty:
            row = result.iloc[0]
            amt_val = float(row['Amount'])
            ind_amt = format_indian_currency(amt_val)
            
            st.success(f"**Name:** {row['Name']} | **Amount:** ₹{ind_amt}")

            with st.form("entry_form", clear_on_submit=True):
                bank_name = st.text_input("Bank Name")
                f1, f2 = st.columns(2)
                with f1: mode = st.selectbox("Type", ["Cheque", "Demand Draft"])
                with f2: inst_no = st.text_input(f"{mode} Number", max_chars=6)
                inst_date = st.date_input(f"{mode} Date")
                
                if st.form_submit_button("Add to Batch"):
                    if bank_name and inst_no and len(inst_no) == 6:
                        # Logic to calculate words on the fly
                        words = num2words(amt_val, lang='en_IN').replace(",", "").replace(" And ", " and ").title().replace(" And ", " and ")
                        
                        new_rec = {
                            'challan': next_no, 'pdate': st.session_state.formatted_pdate,
                            'name': row['Name'], 'num': row['Consumer Number'],
                            'month': sel_month, 'year': sel_year, 'amount': ind_amt,
                            'words': words, 'pay_type': mode, 'pay_no': inst_no,
                            'bank': bank_name, 'date': inst_date.strftime("%d.%m.%Y")
                        }
                        st.session_state.all_receipts.append(new_rec)
                        st.session_state.view_table = False # 2. Turn off view batch on add
                        st.rerun()

    # --- BATCH MANAGEMENT ---
    if st.session_state.all_receipts:
        st.divider()
        if st.button("👁️ View/Manage Batch"):
            st.session_state.view_table = not st.session_state.view_table

        if st.session_state.view_table:
            st.subheader("Current Batch Records")
            # 1. Word representation removed from display table
            for i, rec in enumerate(st.session_state.all_receipts):
                with st.container(border=True):
                    cols = st.columns([1, 2, 2, 2, 1, 1])
                    cols[0].write(f"#{rec['challan']}")
                    cols[1].write(f"**{rec['name']}**")
                    cols[2].write(f"₹{rec['amount']}")
                    cols[3].write(f"{rec['pay_type']} ({rec['pay_no']})")
                    
                    # 3. EDIT BUTTON (Blue)
                    if cols[4].button("📝 Edit", key=f"edit_{i}", type="secondary"):
                        @st.dialog(f"Edit Receipt #{rec['challan']}")
                        def edit_modal(index):
                            curr = st.session_state.all_receipts[index]
                            e_amt = st.text_input("Amount", value=curr['amount'])
                            e_bank = st.text_input("Bank Name", value=curr['bank'])
                            e_type = st.selectbox("Mode", ["Cheque", "Demand Draft"], index=0 if curr['pay_type']=="Cheque" else 1)
                            e_no = st.text_input("Number", value=curr['pay_no'], max_chars=6)
                            e_date = st.date_input("Instrument Date")
                            e_month = st.selectbox("Month", options=month_list, index=month_list.index(curr['month']))
                            e_year = st.selectbox("Year", options=[2025, 2026], index=0 if curr['year']==2025 else 1)
                            
                            if st.button("Save Changes"):
                                # Re-calculate words if amount changed
                                clean_amt = float(e_amt.replace(',', ''))
                                new_words = num2words(clean_amt, lang='en_IN').replace(",", "").replace(" And ", " and ").title().replace(" And ", " and ")
                                
                                st.session_state.all_receipts[index].update({
                                    'amount': format_indian_currency(clean_amt),
                                    'words': new_words, 'bank': e_bank, 'pay_type': e_type,
                                    'pay_no': e_no, 'date': e_date.strftime("%d.%m.%Y"),
                                    'month': e_month, 'year': e_year
                                })
                                st.rerun()
                        edit_modal(i)

                    # 4. DELETE BUTTON (Red)
                    if cols[5].button("🗑️ Delete", key=f"del_{i}"):
                        st.session_state.all_receipts.pop(i)
                        # Re-calculate serial numbers for remaining items
                        for j in range(len(st.session_state.all_receipts)):
                            st.session_state.all_receipts[j]['challan'] = st.session_state.start_no + j
                        st.rerun()

        # --- DOWNLOAD ---
        st.divider()
        if st.button("🚀 Finalize & Generate Word Doc", type="primary"):
            doc = DocxTemplate(tpl_file)
            doc.render({'receipts': st.session_state.all_receipts})
            output = io.BytesIO()
            doc.save(output)
            fn = f"receipt_{date.today().strftime('%d_%m_%Y')}.docx"
            st.download_button("📥 Click to Download File", output.getvalue(), file_name=fn)
else:
    st.warning("👈 Please complete the Setup Configuration in the sidebar to start.")
