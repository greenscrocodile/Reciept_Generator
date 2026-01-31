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
    except:
        return number

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
                st.error("Please complete all fields.")
    else:
        if st.button("Reset Session"):
            st.session_state.locked = False
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
        month_list = ["January", "February", "March", "April", "May", "June", 
                      "July", "August", "September", "October", "November", "December"]
        sel_month = st.selectbox("Select Month", options=month_list)
    with c2:
        sel_year = st.selectbox("Select Year", options=[2025, 2026])

    search_num = st.text_input("Enter Consumer Number")
    
    if search_num:
        m_idx = month_list.index(sel_month) + 1
        result = df[(df['Consumer Number'].astype(str) == search_num) & 
                    (df['Month'] == m_idx) & 
                    (df['Year'] == sel_year)]

        if not result.empty:
            row = result.iloc[0]
            amt_val = float(row['Amount'])
            ind_amt = format_indian_currency(amt_val)
            
            st.success(f"**Name:** {row['Name']} | **Amount:** ₹{ind_amt}")

            with st.form("instrument_details", clear_on_submit=True):
                bank_name = st.text_input("Bank Name")
                f1, f2 = st.columns(2)
                with f1: mode = st.selectbox("Type", ["Cheque", "Demand Draft"])
                with f2: inst_no = st.text_input(f"{mode} Number", max_chars=6)
                inst_date = st.date_input(f"{mode} Date")
                
                if st.form_submit_button("Add to Batch"):
                    if bank_name and inst_no and len(inst_no) == 6:
                        words = num2words(amt_val, lang='en_IN').replace(",", "").replace(" And ", " and ").title().replace(" And ", " and ")
                        new_rec = {
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
                        # 2. Automatically turn off View Batch table when new record added
                        st.session_state.show_batch = False
                        st.rerun()
                    else:
                        st.error("Fill all fields correctly.")
        else:
            st.error("No record found.")

    # --- BATCH VIEW (EDIT/DELETE) & DOWNLOAD ---
    if st.session_state.all_receipts:
        st.divider()
        st.session_state.show_batch = st.checkbox("👁️ View/Edit Batch Table", value=st.session_state.show_batch)
        
        if st.session_state.show_batch:
            st.info("💡 **Blue Edit:** Change values directly in the table. | **Delete:** Select a row and press 'Delete' on your keyboard.")
            
            # Convert batch to DataFrame for editing
            batch_df = pd.DataFrame(st.session_state.all_receipts)
            
            # 1. No need to mention Word representation in table (Words column hidden)
            # 3 & 4. Editable table with Delete support
            edited_df = st.data_editor(
                batch_df,
                column_order=("challan", "name", "num", "month", "year", "amount", "pay_type", "pay_no", "bank", "date"),
                column_config={
                    "amount": st.column_config.TextColumn("Amount (Editable)"),
                    "month": st.column_config.SelectboxColumn("Month", options=month_list),
                    "year": st.column_config.SelectboxColumn("Year", options=[2025, 2026]),
                    "pay_type": st.column_config.SelectboxColumn("Type", options=["Cheque", "Demand Draft"]),
                },
                num_rows="dynamic", # Enables deletion
                use_container_width=True,
                key="batch_editor"
            )
            
            # Sync edits back to session state and update 'words' if amount changed
            if st.button("💾 Save Changes to Batch"):
                updated_list = edited_df.to_dict('records')
                for rec in updated_list:
                    # Recalculate words in case amount was edited
                    clean_amt = str(rec['amount']).replace(',', '')
                    rec['words'] = num2words(float(clean_amt), lang='en_IN').replace(",", "").replace(" And ", " and ").title().replace(" And ", " and ")
                st.session_state.all_receipts = updated_list
                st.success("Batch updated!")
                st.rerun()

        if st.button("🚀 Finalize & Generate Word Doc", type="primary"):
            doc = DocxTemplate(tpl_file)
            doc.render({'receipts': st.session_state.all_receipts})
            output = io.BytesIO()
            doc.save(output)
            fn = f"receipt_{date.today().strftime('%d_%m_%Y')}.docx"
            st.download_button("📥 Click to Download File", output.getvalue(), file_name=fn)
