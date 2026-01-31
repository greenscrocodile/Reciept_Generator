import streamlit as st
import pandas as pd
from docxtpl import DocxTemplate
from num2words import num2words
import io
from datetime import date

st.set_page_config(page_title="Challan Gen", layout="wide")

# --- CUSTOM INDIAN CURRENCY FORMATTING ---
def format_indian_currency(number):
    s = f"{float(number):.2f}"
    parts = s.split('.')
    main = parts[0]
    decimal = parts[1]
    if len(main) <= 3:
        return f"{main}.{decimal}"
    last_three = main[-3:]
    remaining = main[:-3]
    # Comma every 2 digits for Indian system
    res = ""
    while len(remaining) > 2:
        res = "," + remaining[-2:] + res
        remaining = remaining[:-2]
    if remaining:
        res = remaining + res
    return f"{res},{last_three}.{decimal}"

# --- INITIALIZATION ---
if 'all_receipts' not in st.session_state:
    st.session_state.all_receipts = []
if 'locked' not in st.session_state:
    st.session_state.locked = False

# --- RIGHT SIDEBAR: CONFIG & FILES ---
with st.sidebar:
    st.header("⚙️ Configuration")
    # 4. Challan, pdate, Doc, and Xl on the right
    s_challan = st.text_input("Starting Challan No.", disabled=st.session_state.locked)
    s_pdate = st.date_input("Payment Date (pdate)", disabled=st.session_state.locked)
    
    st.divider()
    tpl_file = st.file_uploader("Upload Word Template", type=["docx"])
    data_file = st.file_uploader("Upload Master Excel", type=["xlsx", "csv"])
    
    if not st.session_state.locked:
        if st.button("Start Entry Session"):
            if s_challan and tpl_file and data_file:
                st.session_state.locked = True
                st.session_state.start_no = int(s_challan)
                st.session_state.formatted_pdate = s_pdate.strftime("%d.%m.%Y")
                st.rerun()
            else:
                st.error("Fill all settings & upload files!")
    else:
        if st.button("Reset Everything"):
            st.session_state.locked = False
            st.session_state.all_receipts = []
            st.rerun()

# --- MAIN AREA: SEARCH & ENTRY ---
st.title("📑 Receipt Generation System")

if st.session_state.locked:
    st.info(f"Session Active: Starting @ {st.session_state.start_no} | Date: {st.session_state.formatted_pdate}")
    
    df = pd.read_excel(data_file) if "xlsx" in data_file.name else pd.read_csv(data_file)
    
    # 2. Search Section
    with st.container(border=True):
        st.subheader("Search Consumer")
        c1, c2, c3 = st.columns(3)
        with c1:
            search_num = st.text_input("Consumer Number (No arrows)")
        with c2:
            month_list = ["January", "February", "March", "April", "May", "June", 
                          "July", "August", "September", "October", "November", "December"]
            search_month = st.selectbox("Month", options=month_list)
        with c3:
            search_year = st.selectbox("Year", options=[2025, 2026])
        
        # 2. Search Button
        find_btn = st.button("🔍 Search Consumer", type="secondary")

    if find_btn and search_num:
        m_idx = month_list.index(search_month) + 1
        result = df[(df['Consumer Number'].astype(str) == search_num) & 
                    (df['Month'] == m_idx) & 
                    (df['Year'] == search_year)]

        if not result.empty:
            row = result.iloc[0]
            st.session_state.current_found = row
        else:
            st.error("No record found. Check Number, Month, and Year.")
            st.session_state.current_found = None

    # Entry Section
    if 'current_found' in st.session_state and st.session_state.current_found is not None:
        row = st.session_state.current_found
        amt_val = float(row['Amount'])
        
        # 1. Indian Comma System & 2. Amount in words cleanup
        ind_amt = format_indian_currency(amt_val)
        words = num2words(amt_val, lang='en_IN').replace(",", "").replace(" And ", " and ").title().replace(" And ", " and ")
        
        st.success(f"**Target:** {row['Name']} | **Amount:** ₹{ind_amt}")
        
        with st.form("manual_entry"):
            st.subheader("Payment Details")
            f1, f2 = st.columns(2)
            with f2: p_type = st.selectbox("Payment Mode", ["Cheque", "Demand Draft"])
            with f1: p_no = st.text_input(f"{p_type} Number")
            
            f3, f4 = st.columns(2)
            with f3: p_date = st.date_input("Instrument Date")
            with f4: p_bank = st.text_input("Bank Name")
            
            # 3. All fields mandatory to add
            submit = st.form_submit_button("Add to Batch")
            
            if submit:
                if p_no and p_bank:
                    new_rec = {
                        'challan': st.session_state.start_no + len(st.session_state.all_receipts),
                        'pdate': st.session_state.formatted_pdate,
                        'name': row['Name'],
                        'num': row['Consumer Number'],
                        'month': search_month,
                        'year': row['Year'],
                        'amount': ind_amt,
                        'words': words,
                        'pay_type': p_type,
                        'pay_no': p_no,
                        'bank': p_bank,
                        'date': p_date.strftime("%d.%m.%Y")
                    }
                    st.session_state.all_receipts.append(new_rec)
                    st.session_state.current_found = None
                    st.success("Added to batch!")
                    st.rerun()
                else:
                    st.error("All fields (Number, Date, Bank) are mandatory!")

    # --- DOWNLOAD SECTION ---
    if st.session_state.all_receipts:
        st.divider()
        st.write(f"### Current Batch ({len(st.session_state.all_receipts)} items)")
        st.table(pd.DataFrame(st.session_state.all_receipts)[['challan', 'name', 'amount']])
        
        if st.button("🚀 Finalize & Download Word Doc", type="primary"):
            doc = DocxTemplate(tpl_file)
            doc.render({'receipts': st.session_state.all_receipts})
            output = io.BytesIO()
            doc.save(output)
            # 6. Specific filename
            fn = f"receipt_{date.today().strftime('%d_%m_%Y')}.docx"
            st.download_button("📥 Click here to Download", output.getvalue(), file_name=fn)
else:
    st.warning("Please configure the settings in the right sidebar to begin.")
