import streamlit as st
import pandas as pd
from docxtpl import DocxTemplate
from num2words import num2words
import io
from datetime import date

st.set_page_config(page_title="Challan Search & Gen", layout="wide")
st.title("🔍 Individual Challan Search & Entry")

# Initialize storage for the receipts we create
if 'all_receipts' not in st.session_state:
    st.session_state.all_receipts = []
if 'locked_settings' not in st.session_state:
    st.session_state.locked_settings = None

# --- SECTION 1: ONE-TIME SETTINGS ---
st.subheader("1. Global Settings")
if st.session_state.locked_settings is None:
    col_set1, col_set2 = st.columns(2)
    with col_set1:
        s_challan = st.number_input("Starting Challan No.", min_value=1, value=100)
    with col_set2:
        s_pdate = st.date_input("Payment Date (pdate)", value=date.today())
    
    if st.button("Lock Settings & Start Entry"):
        st.session_state.locked_settings = {"challan": s_challan, "pdate": s_pdate.strftime("%d/%m/%Y")}
        st.rerun()
else:
    st.success(f"Locked: Starting Challan **{st.session_state.locked_settings['challan']}** | Date **{st.session_state.locked_settings['pdate']}**")
    if st.button("Reset Settings"):
        st.session_state.locked_settings = None
        st.session_state.all_receipts = []
        st.rerun()

# --- SECTION 2: FILE UPLOAD ---
tpl_file = st.file_uploader("Upload Word Template", type=["docx"])
data_file = st.file_uploader("Upload Master Excel", type=["xlsx", "csv"])

if tpl_file and data_file and st.session_state.locked_settings:
    df = pd.read_excel(data_file) if "xlsx" in data_file.name else pd.read_csv(data_file)
    
    st.divider()
    st.subheader("2. Search Consumer")
    
    # Search Inputs
    search_col1, search_col2, search_col3 = st.columns(3)
    with search_col1:
        search_num = st.number_input("Enter Consumer Number", step=1)
    with search_col2:
        search_month = st.selectbox("Select Month", options=list(range(1, 13)))
    with search_col3:
        search_year = st.selectbox("Select Year", options=[2025, 2026])

    # Filter the Master Data
    result = df[(df['Consumer Number'] == search_num) & (df['Month'] == search_month) & (df['Year'] == search_year)]

    if not result.empty:
        found_row = result.iloc[0]
        amt = float(found_row['Amount'])
        word_amt = num2words(amt, lang='en_IN').title()

        # Display Auto-Found Data
        st.success(f"**Found:** {found_row['Name']} | **Amount:** ₹{amt:,.2f}")
        st.text(f"In Words: {word_amt} Only")

        st.divider()
        st.subheader("3. Payment Details")
        
        # Split fields as requested: Right half dropdown, Left half number
        pay_col1, pay_col2 = st.columns(2)
        with pay_col2: # Right side
            p_type = st.selectbox("Payment Mode", ["Cheque", "Demand Draft"])
        with pay_col1: # Left side
            p_no = st.text_input(f"Enter {p_type} Number")

        # Bank and Date
        bank_col1, bank_col2 = st.columns(2)
        with bank_col1:
            p_date = st.date_input("Instrument Date")
        with bank_col2:
            p_bank = st.text_input("Bank Name")

        if st.button("Add to Batch"):
            # Calculate current serial challan
            current_serial = st.session_state.locked_settings['challan'] + len(st.session_state.all_receipts)
            
            new_receipt = {
                'challan': current_serial,
                'pdate': st.session_state.locked_settings['pdate'],
                'name': found_row['Name'],
                'num': found_row['Consumer Number'],
                'month': found_row['Month'],
                'year': found_row['Year'], # Added year tag
                'amount': f"{amt:,.2f}",
                'words': word_amt,
                'pay_type': p_type,
                'pay_no': p_no,
                'bank': p_bank,
                'date': p_date.strftime("%d/%m/%Y")
            }
            st.session_state.all_receipts.append(new_receipt)
            st.toast(f"Added receipt for {found_row['Name']}!")

    else:
        st.warning("No record found for this Consumer Number, Month, and Year.")

    # --- SECTION 3: DOWNLOAD ---
    if st.session_state.all_receipts:
        st.divider()
        st.write(f"### Current Batch ({len(st.session_state.all_receipts)} receipts added)")
        st.dataframe(pd.DataFrame(st.session_state.all_receipts)[['challan', 'name', 'num', 'amount']])
        
        if st.button("Generate & Download Word File", type="primary"):
            doc = DocxTemplate(tpl_file)
            doc.render({'receipts': st.session_state.all_receipts})
            
            output = io.BytesIO()
            doc.save(output)
            st.download_button(
                label="📥 Download Generated File",
                data=output.getvalue(),
                file_name=f"Receipts_{date.today()}.docx",
                mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document"
            )
