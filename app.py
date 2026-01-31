import streamlit as st
import pandas as pd
from docxtpl import DocxTemplate
from num2words import num2words
import io
from datetime import date

st.set_page_config(page_title="Challan Search & Gen", layout="wide")
st.title("🔍 Individual Challan Search & Entry")

# Custom Indian Formatting Function
def format_indian_currency(number):
    s = str(int(number))
    if len(s) <= 3:
        return s
    last_three = s[-3:]
    remaining = s[:-3]
    remaining_with_commas = ""
    # Add commas every two digits for Indian system
    while len(remaining) > 2:
        remaining_with_commas = "," + remaining[-2:] + remaining_with_commas
        remaining = remaining[:-2]
    return remaining + remaining_with_commas + "," + last_three + ".00"

# Initialize storage
if 'all_receipts' not in st.session_state:
    st.session_state.all_receipts = []
if 'locked_settings' not in st.session_state:
    st.session_state.locked_settings = None

# --- SECTION 1: GLOBAL SETTINGS ---
st.subheader("1. Global Settings")
if st.session_state.locked_settings is None:
    col_set1, col_set2 = st.columns(2)
    with col_set1:
        s_challan = st.text_input("Starting Challan No.", value="", help="Mandatory")
    with col_set2:
        # No default date selection shown initially if possible (Streamlit defaults to today)
        s_pdate = st.date_input("Payment Date (pdate)", value=None)
    
    if st.button("Lock Settings & Start Entry"):
        if s_challan and s_pdate:
            st.session_state.locked_settings = {
                "challan": int(s_challan), 
                "pdate": s_pdate.strftime("%d.%m.%Y")
            }
            st.rerun()
        else:
            st.error("All Global Settings are mandatory.")
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
        search_num = st.text_input("Enter Consumer Number", value="")
    with search_col2:
        month_names = ["January", "February", "March", "April", "May", "June", 
                       "July", "August", "September", "October", "November", "December"]
        search_month_name = st.selectbox("Select Month", options=[""] + month_names)
    with search_col3:
        search_year = st.selectbox("Select Year", options=["", 2025, 2026])

    # Search Logic
    if st.button("🔍 Search Consumer"):
        if search_num and search_month_name and search_year:
            m_idx = month_names.index(search_month_name) + 1
            res = df[(df['Consumer Number'].astype(str) == search_num) & 
                     (df['Month'] == m_idx) & 
                     (df['Year'] == search_year)]
            
            if not res.empty:
                st.session_state.found_item = res.iloc[0]
                st.session_state.search_month_text = search_month_name
            else:
                st.session_state.found_item = None
                st.error("No record found.")
        else:
            st.error("All search fields (Number, Month, Year) are mandatory.")

    # Display Result and Form
    if 'found_item' in st.session_state and st.session_state.found_item is not None:
        item = st.session_state.found_item
        amt_val = float(item['Amount'])
        
        # Indian Numbering (1,23,456.00)
        formatted_amt = format_indian_currency(amt_val)
        
        # Word formatting
        word_amt = num2words(amt_val, lang='en_IN').replace(",", "")
        word_amt = word_amt.replace(" And ", " and ").title().replace(" And ", " and ")

        st.info(f"**Name:** {item['Name']} | **Amount:** ₹{formatted_amt}")
        
        st.divider()
        st.subheader("3. Payment Details")
        
        pay_col1, pay_col2 = st.columns(2)
        with pay_col2: 
            p_type = st.selectbox("Payment Mode", options=["", "Cheque", "Demand Draft"])
        with pay_col1: 
            p_no = st.text_input(f"Enter Number")

        bank_col1, bank_col2 = st.columns(2)
        with bank_col1:
            # UI display is DD/MM/YYYY by default in the widget
            p_date = st.date_input("Instrument Date", value=None)
        with bank_col2:
            p_bank = st.text_input("Bank Name")

        if st.button("➕ Add to Batch"):
            if p_type and p_no and p_date and p_bank:
                current_serial = st.session_state.locked_settings['challan'] + len(st.session_state.all_receipts)
                
                st.session_state.all_receipts.append({
                    'challan': current_serial,
                    'pdate': st.session_state.locked_settings['pdate'],
                    'name': item['Name'],
                    'num': item['Consumer Number'],
                    'month': st.session_state.search_month_text,
                    'year': item['Year'],
                    'amount': formatted_amt,
                    'words': word_amt,
                    'pay_type': p_type,
                    'pay_no': p_no,
                    'bank': p_bank,
                    'date': p_date.strftime("%d.%m.%Y") # Doc format
                })
                st.success(f"Added {item['Name']} to batch!")
            else:
                st.error("All payment details are mandatory.")

    # --- SECTION 4: DOWNLOAD ---
    if st.session_state.all_receipts:
        st.divider()
        st.write(f"### Current Batch: {len(st.session_state.all_receipts)} Receipts")
        
        if st.button("🚀 Generate & Download", type="primary"):
            doc = DocxTemplate(tpl_file)
            doc.render({'receipts': st.session_state.all_receipts})
            output = io.BytesIO()
            doc.save(output)
            
            fn = f"receipt_{date.today().strftime('%d_%m_%Y')}.docx"
            st.download_button("📥 Click to Download", output.getvalue(), file_name=fn)
