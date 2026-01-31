import streamlit as st
import pandas as pd
from docxtpl import DocxTemplate
from num2words import num2words
import io
from datetime import date
import uuid
import re
import streamlit.components.v1 as components

st.set_page_config(page_title="Challan Master", layout="wide")

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

# --- PRINT LOGIC ---
def trigger_print(rec):
    # This HTML mimics your Word template structure for the print window
    receipt_html = f"""
    <div id="print-area" style="font-family: Arial, sans-serif; padding: 20px; color: black; line-height: 1.5;">
        <div style="text-align: center; font-weight: bold; text-decoration: underline;">G.A.R. 7 [See rule 26(1)] - ORIGINAL</div>
        <div style="display: flex; justify-content: space-between; margin-top: 20px;">
            <span><b>Chalan No. :</b> {rec['challan']}/CC/HT/2025-26</span>
            <span><b>Date:</b> {rec['pdate']}</span>
        </div>
        <p><b>Bank:</b> STATE BANK OF INDIA, MAIN Branch</p>
        <hr>
        <p>Collected from: <b>M/s {rec['name']} (C.C.No. {rec['num']})</b></p>
        <p>Vide {rec['pay_type']} No. {rec['pay_no']}, Dated {rec['date']} of {rec['bank']}</p>
        <p>For the month of: {rec['month']} - {rec['year']}</p>
        <div style="display: flex; justify-content: space-between; font-weight: bold; border-top: 1px solid black; padding-top: 10px;">
            <span>Amount:</span>
            <span>Rs. {rec['amount']}</span>
        </div>
        <p><i>In Words: Rupees {rec['words']} Only</i></p>
        <div style="margin-top: 50px; text-align: right;">
            <p>__________________________</p>
            <p>Authorized Signatory</p>
        </div>
    </div>
    <script>
        window.print();
    </script>
    """
    # Use components to inject the print script
    components.html(receipt_html, height=0, width=0)

# --- DIALOGS ---
@st.dialog("Edit Amount")
def edit_amount_dialog(index):
    rec = st.session_state.all_receipts[index]
    current_val = rec['amount'].replace(",", "")
    new_amt_str = st.text_input("New Amount", value=current_val)
    if st.button("Save Changes"):
        try:
            new_amt = int(new_amt_str)
            st.session_state.all_receipts[index]['amount'] = format_indian_currency(new_amt)
            st.session_state.all_receipts[index]['words'] = num2words(new_amt, lang='en_IN').replace(",", "").replace(" And ", " and ").title().replace(" And ", " and ")
            st.rerun()
        except: st.error("Enter valid number")

# --- INITIALIZATION ---
if 'all_receipts' not in st.session_state: st.session_state.all_receipts = []
if 'locked' not in st.session_state: st.session_state.locked = False
if 'show_batch' not in st.session_state: st.session_state.show_batch = False

# --- SIDEBAR ---
with st.sidebar:
    st.header("⚙️ Configuration")
    s_challan = st.text_input("Starting No.", disabled=st.session_state.locked)
    s_pdate = st.date_input("Payment Date", disabled=st.session_state.locked)
    st.divider()
    tpl_file = st.file_uploader("Template (.docx)", type=["docx"])
    data_file = st.file_uploader("Master Data (.xlsx)", type=["xlsx", "csv"])
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

# --- MAIN FLOW ---
if st.session_state.locked:
    curr_count = len(st.session_state.all_receipts)
    next_no = st.session_state.start_no + curr_count
    
    h1, h2, h3, h4 = st.columns(4)
    h1.metric("Starting No.", st.session_state.start_no)
    h2.metric("Next No.", next_no)
    h3.metric("Date", st.session_state.formatted_pdate)
    h4.metric("Batch", curr_count)

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
        if re.match(r"^\d{3}$", search_num):
            m_idx = month_list.index(sel_month) + 1
            result = df[(df['Consumer Number'].astype(str) == search_num) & (df['Month'] == m_idx) & (df['Year'] == sel_year)]

            if not result.empty:
                row = result.iloc[0]
                st.success(f"**Found:** {row['Name']} | **Amt:** ₹{format_indian_currency(row['Amount'])}")
                with st.form("entry_form", clear_on_submit=True):
                    bank_name = st.text_input("Bank Name")
                    f1, f2 = st.columns(2)
                    with f1: mode = st.selectbox("Type", ["Cheque", "Demand Draft"])
                    with f2: inst_no = st.text_input(f"{mode} No.", max_chars=6)
                    inst_date = st.date_input("Instrument Date")
                    if st.form_submit_button("Add to Batch"):
                        if re.match(r"^[a-zA-Z\s]+$", bank_name) and re.match(r"^\d{6}$", inst_no):
                            amt_val = float(row['Amount'])
                            st.session_state.all_receipts.append({
                                'id': str(uuid.uuid4()), 'challan': next_no, 'pdate': st.session_state.formatted_pdate,
                                'name': row['Name'], 'num': row['Consumer Number'], 'month': sel_month, 'year': sel_year,
                                'amount': format_indian_currency(amt_val), 'words': num2words(amt_val, lang='en_IN').replace(",", "").replace(" And ", " and ").title().replace(" And ", " and "),
                                'pay_type': mode, 'pay_no': inst_no, 'bank': bank_name, 'date': inst_date.strftime("%d.%m.%Y")
                            })
                            st.rerun()

    # --- BATCH TABLE ---
    if st.session_state.all_receipts:
        st.divider()
        if st.checkbox("👁️ View Batch Table", value=st.session_state.show_batch):
            st.session_state.show_batch = True
            for i, rec in enumerate(st.session_state.all_receipts):
                tcol = st.columns([0.8, 3, 1.5, 1.5, 1.5, 2, 1.5])
                tcol[0].write(rec['challan']); tcol[1].write(rec['name']); tcol[2].write(f"₹{rec['amount']}")
                tcol[3].write(rec['pay_type']); tcol[4].write(rec['pay_no']); tcol[5].write(rec['bank'])
                with tcol[6]:
                    s1, s2, s3 = st.columns(3)
                    # 1. PRINT BUTTON (Replaces Preview)
                    if s1.button("🖨️", key=f"p_{rec['id']}"): trigger_print(rec)
                    if s2.button("✏️", key=f"e_{rec['id']}"): edit_amount_dialog(i)
                    if s3.button("🗑️", key=f"d_{rec['id']}"):
                        st.session_state.all_receipts.pop(i)
                        for j in range(i, len(st.session_state.all_receipts)): st.session_state.all_receipts[j]['challan'] -= 1
                        st.rerun()

        if st.button("🚀 Generate Final Word File", type="primary"):
            doc = DocxTemplate(tpl_file)
            doc.render({'receipts': st.session_state.all_receipts})
            output = io.BytesIO(); doc.save(output)
            st.download_button("📥 Download Final Document", output.getvalue(), file_name=f"receipt_{date.today()}.docx")
