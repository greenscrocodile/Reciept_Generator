import streamlit as st
import pandas as pd
from docxtpl import DocxTemplate
from num2words import num2words
import io
from datetime import date
import uuid
import re
import os # Added to check for the file in your GitHub folder

st.set_page_config(page_title="Challan Master", layout="wide")

# --- INDIAN CURRENCY FORMATTING (STRICT NO DECIMALS) ---
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

# --- DIALOGS ---
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
if 'all_receipts' not in st.session_state:
    st.session_state.all_receipts = []
if 'locked' not in st.session_state:
    st.session_state.locked = False
if 'show_batch' not in st.session_state:
    st.session_state.show_batch = False

# --- SIDEBAR ---
with st.sidebar:
    st.header("⚙️ Configuration")
    s_challan = st.text_input("Starting Challan", disabled=st.session_state.locked)
    s_pdate = st.date_input("Present Date", disabled=st.session_state.locked)
    st.divider()
    
    # AUTO-LOAD TEMPLATE FROM GITHUB
    TEMPLATE_NAME = "Test.docx"
    if os.path.exists(TEMPLATE_NAME):
        st.success(f"✅ Template '{TEMPLATE_NAME}' loaded from GitHub")
        # Read the file from the project folder
        with open(TEMPLATE_NAME, "rb") as f:
            template_bytes = f.read()
    else:
        st.error(f"❌ {TEMPLATE_NAME} not found in GitHub folder!")
        template_bytes = None

    data_file = st.file_uploader("Upload Master Data (.xlsx)", type=["xlsx", "csv"])

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

# --- MAIN FLOW ---
if st.session_state.locked:
    curr_count = len(st.session_state.all_receipts)
    next_no = st.session_state.start_no + curr_count

    h1, h2, h3, h4 = st.columns(4)
    h1.metric("Starting Challan", st.session_state.start_no)
    h2.metric("Current Challan", next_no)
    h3.metric("Date", st.session_state.formatted_pdate)
    h4.metric("Challans Entered", curr_count)

    df = pd.read_excel(data_file) if "xlsx" in data_file.name else pd.read_csv(data_file)
    st.divider()

    c1, c2 = st.columns(2)
    with c1:
        month_list = ["January", "February", "March", "April", "May", "June", "July", "August", "September", "October", "November", "December"]
        sel_month = st.selectbox("Select Month", options=month_list)
    with c2:
        sel_year = st.selectbox("Select Year", options=[2025, 2026])

    search_num = st.text_input("Enter Consumer Number", max_chars=3)

    if search_num:
        if not re.match(r"^\d{3}$", search_num):
            st.warning("⚠️ Consumer Number must be exactly 3 digits.")
            result = pd.DataFrame()
        else:
            m_idx = month_list.index(sel_month) + 1
            result = df[(df['Consumer Number'].astype(str) == search_num) & (df['Month'] == m_idx) & (df['Year'] == sel_year)]

        if not result.empty:
            row = result.iloc[0]
            amt_val = float(row['Amount'])
            st.success(f"**Found:** {row['Name']} | **Amt:** ₹{format_indian_currency(amt_val)}")

            with st.form("entry_form", clear_on_submit=True):
                bank_name = st.text_input("Bank Name")
                f1, f2 = st.columns(2)
                with f1: mode = st.selectbox("Type", ["Cheque", "Demand Draft"])
                with f2: inst_no = st.text_input("DD/Cheque No", max_chars=6)
                inst_date = st.date_input("DD/Cheque Date")

                if st.form_submit_button("Add to Batch"):
                    if re.match(r"^[a-zA-Z\s]+$", bank_name) and re.match(r"^\d{6}$", inst_no):
                        ind_amt = format_indian_currency(amt_val)
                        words = num2words(amt_val, lang='en_IN').replace(",", "").replace(" And ", " and ").title().replace(" And ", " and ")
                        new_rec = {
                            'id': str(uuid.uuid4()), 'challan': next_no, 'pdate': st.session_state.formatted_pdate,
                            'name': row['Name'], 'num': row['Consumer Number'], 'month': sel_month, 'year': sel_year,
                            'amount': ind_amt, 'words': words, 'pay_type': mode, 'pay_no': inst_no, 'bank': bank_name, 'date': inst_date.strftime("%d.%m.%Y")
                        }
                        st.session_state.all_receipts.append(new_rec)
                        st.session_state.show_batch = False
                        st.rerun()
                    else:
                        st.error("Invalid Entry: Check Bank Name and Instrument Number.")

    # --- BATCH TABLE ---
    if st.session_state.all_receipts:
        st.divider()
        if st.checkbox("👁️ View Batch Table", value=st.session_state.show_batch):
            st.session_state.show_batch = True
            t_head = st.columns([0.8, 3, 1.5, 1.5, 1.5, 2, 1.5])
            t_head[0].write("**No.**"); t_head[1].write("**Consumer**"); t_head[2].write("**Amount**")
            t_head[3].write("**Mode**"); t_head[4].write("**Inst. No.**"); t_head[5].write("**Bank**"); t_head[6].write("**Actions**")

            for i, rec in enumerate(st.session_state.all_receipts):
                tcol = st.columns([0.8, 3, 1.5, 1.5, 1.5, 2, 1.5])
                tcol[0].write(rec['challan']); tcol[1].write(rec['name']); tcol[2].write(f"₹{rec['amount']}")
                tcol[3].write(rec['pay_type']); tcol[4].write(rec['pay_no']); tcol[5].write(rec['bank'])

                with tcol[6]:
                    s1, s2 = st.columns(2)
                    if s1.button("✏️", key=f"e_{rec['id']}", help="Edit Amount"): edit_amount_dialog(i)
                    if s2.button("🗑️", key=f"d_{rec['id']}", help="Delete"):
                        st.session_state.all_receipts.pop(i)
                        for j in range(i, len(st.session_state.all_receipts)): st.session_state.all_receipts[j]['challan'] -= 1
                        st.rerun()

        if st.button("🚀 Generate Final Word File", type="primary"):
            # Use the bytes loaded from GitHub
            doc = DocxTemplate(io.BytesIO(template_bytes))
            doc.render({'receipts': st.session_state.all_receipts})
            output = io.BytesIO()
            doc.save(output)
            fn = f"receipt_{date.today().strftime('%d_%m_%Y')}.docx"
            st.download_button("📥 Download Final Document", output.getvalue(), file_name=fn)
