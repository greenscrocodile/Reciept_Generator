import streamlit as st
import pandas as pd
from docxtpl import DocxTemplate
from num2words import num2words
import io
from datetime import date
import locale

# Attempt to set locale for Indian currency formatting
try:
    locale.setlocale(locale.LC_ALL, 'en_IN')
except:
    pass # Fallback if locale is not installed on the server

st.set_page_config(page_title="Challan Search & Gen", layout="wide")
st.title("🔍 Individual Challan Search & Entry")

# Initialize storage
if 'all_receipts' not in st.session_state:
    st.session_state.all_receipts = []
if 'locked_settings' not in st.session_state:
    st.session_state.locked_settings = None

# --- SECTION 1: ONE-TIME SETTINGS ---
st.subheader("1. Global Settings")
if st.session_state.locked_settings is None:
    col_set1, col_set2 = st.columns(2)
    with col_set1:
        # Removed default and step buttons
        s_challan = st.text_input("Starting Challan No.")
    with col_set2:
        # Date button (calendar)
        s_pdate = st.date_input("Payment Date (pdate)")
    
    if st.button("Lock Settings & Start Entry"):
        if s_challan:
            # Using "." for pdate representation
            st.session_state.locked_settings = {
                "challan": int(s_challan), 
                "pdate": s_pdate.strftime("%d.%m.%Y")
            }
            st.rerun()
        else:
            st.error("Please enter a Challan Number")
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
    
    search_col1, search_col2, search_col3 = st.columns(3)
    with search_col1:
        # Removed step buttons
        search_num = st.text_input("Enter Consumer Number")
    with search_col2:
        # Displaying month names
        month_names = ["January", "February", "March", "April", "May", "June", 
                       "July", "August", "September", "October", "November", "December"]
        search_month_name = st.selectbox("Select Month", options=month_names)
        search_month_idx = month_names.index(search_month_name) + 1
    with search_col3:
        search_year = st.selectbox("Select Year", options=[2025, 2026])

    if search_num:
        result = df[(df['Consumer Number'].astype(str) == search_num) & 
                    (df['Month'] == search_month_idx) & 
                    (df['Year'] == search_year)]

        if not result.empty:
            found_row = result.iloc[0]
            amt_val = float(found_row['Amount'])
            
            # 1. Indian Currency Formatting (1,23,456.00)
            formatted_amt = f"{amt_val:,.2f}" # Standard
            try:
                formatted_amt = locale.format_string("%1.2f", amt_val, grouping=True)
            except:
                pass

            # 2. Amount in words cleaning
            word_amt = num2words(amt_val, lang='en_IN').replace(",", "") # Remove commas
            word_amt = word_amt.replace(" And ", " and ").title() # lowercase "and", rest Title
            # Ensure specifically "and" stays small even after Title case
            word_amt = word_amt.replace(" And ", " and ") 

            st.success(f"**Found:** {found_row['Name']} | **Amount:** ₹{formatted_amt}")
            st.text(f"In Words: {word_amt} Only")

            st.divider()
            st.subheader("3. Payment Details")
            
            pay_col1, pay_col2 = st.columns(2)
            with pay_col2: 
                p_type = st.selectbox("Payment Mode", ["Cheque", "Demand Draft"])
            with pay_col1: 
                p_no = st.text_input(f"Enter {p_type} Number")

            bank_col1, bank_col2 = st.columns(2)
            with bank_col1:
                p_date = st.date_input("Instrument Date")
            with bank_col2:
                p_bank = st.text_input("Bank Name")

            if st.button("Add to Batch"):
                current_serial = st.session_state.locked_settings['challan'] + len(st.session_state.all_receipts)
                
                new_receipt = {
                    'challan': current_serial,
                    'pdate': st.session_state.locked_settings['pdate'],
                    'name': found_row['Name'],
                    'num': found_row['Consumer Number'],
                    'month': search_month_name, # 5. Name of month
                    'year': found_row['Year'],
                    'amount': formatted_amt,
                    'words': word_amt,
                    'pay_type': p_type,
                    'pay_no': p_no,
                    'bank': p_bank,
                    'date': p_date.strftime("%d.%m.%Y") # 3. Dot instead of slash
                }
                st.session_state.all_receipts.append(new_receipt)
                st.toast(f"Added receipt for {found_row['Name']}!")

        elif search_num:
            st.warning("No record found.")

    # --- SECTION 3: DOWNLOAD ---
    if st.session_state.all_receipts:
        st.divider()
        st.write(f"### Current Batch ({len(st.session_state.all_receipts)} receipts)")
        
        if st.button("🚀 Generate & Download", type="primary"):
            doc = DocxTemplate(tpl_file)
            doc.render({'receipts': st.session_state.all_receipts})
            
            output = io.BytesIO()
            doc.save(output)
            
            # 6. Filename formatting
            fn = f"receipt_{date.today().strftime('%d_%m_%Y')}.docx"
            
            st.download_button(
                label="📥 Download Now",
                data=output.getvalue(),
                file_name=fn,
                mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document"
            )
