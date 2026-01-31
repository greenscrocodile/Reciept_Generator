import streamlit as st
import pandas as pd
from docxtpl import DocxTemplate
from num2words import num2words
import io
from datetime import date
import uuid
import re

st.set_page_config(page_title="Challan Master", layout="wide")

# --- INDIAN CURRENCY FORMATTING (NO DECIMALS) ---
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

# --- HIGH-FIDELITY DOC PREVIEW ---
@st.dialog("Document Preview", width="large")
def preview_dialog(index):
    r = st.session_state.all_receipts[index]
    
    st.markdown("""
        <style>
        .doc-page {
            background-color: white; padding: 40px; border: 1px solid #000;
            color: black; font-family: 'Arial', sans-serif; line-height: 1.2; font-size: 13px;
        }
        .section-box { border: 2px solid black; padding: 10px; margin-bottom: 10px; position: relative; }
        .header-text { text-align: center; font-weight: bold; }
        .chalan-info { display: flex; justify-content: space-between; margin: 10px 0; }
        .table-sim { width: 100%; border-collapse: collapse; margin-top: 10px; }
        .table-sim td, .table-sim th { border: 1px solid black; padding: 5px; vertical-align: top; }
        .footer-line { border-top: 2px dashed black; margin: 20px 0; }
        </style>
    """, unsafe_allow_html=True)

    # Mimicking the Test.docx layout [cite: 2, 4, 6, 9, 14, 16, 18, 21]
    def render_challan_html(label):
        return f"""
        <div class="section-box">
            <div class="header-text">G.A.R. 7 [See rule 26(1)]</div>
            <div class="header-text" style="font-size: 16px;">{label}</div>
            <div class="chalan-info">
                <span><b>Chalan No. :</b> {r['challan']}/CC/HT/2025-26</span>
                <span><b>Date:</b> {r['pdate']}</span>
            </div>
            <p>Chalan of money paid into <b>STATE BANK OF INDIA</b> (Bank) <b>MAIN</b> (Branch)</p>
            <table class="table-sim">
                <tr>
                    <th width="30%">To be filled-in by Remitter</th>
                    <th width="70%">To be filled-in by Dept. Officer</th>
                </tr>
                <tr>
                    <td>Senior Accounts Officer, Circle-I Electricity Dept, Puducherry</td>
                    <td>Towards Remittance of C.C.Charges collected from <b>M/s {r['name']} ({r['num']})</b> 
                        vide {r['pay_type']} No. <b>{r['pay_no']}</b>, Dated {r['date']} of {r['bank']} 
                        for month of {r['month']} - {r['year']}
                    </td>
                </tr>
                <tr>
                    <td style="text-align:right;"><b>Total Amount:</b></td>
                    <td><b>₹ {r['amount']}</b></td>
                </tr>
            </table>
            <p style="margin-top:10px;">*(in words) Rupees <b>{r['words']} Only</b></p>
        </div>
        """

    st.markdown(f"""
    <div class="doc-page">
        {render_challan_html("ORIGINAL")}
        <div class="footer-line"></div>
        {render_challan_html("DUPLICATE")}
    </div>
    """, unsafe_allow_html=True)

# --- DIALOGS ---
@st.dialog("Edit Amount")
def edit_amount_dialog(index):
    rec = st.session_state.all_receipts[index]
    current_val = rec['amount'].replace(",", "")
    new_amt_str = st.text_input("New Amount (Numbers only)", value=current_val)
    if st.button("Save Changes"):
        try:
            new_amt = int(new_amt_str)
            ind_amt = format_indian_currency(new_amt)
            new_words = num2words(new_amt, lang='en_IN').replace(",", "").replace(" And ", " and ").title().replace(" And ", " and ")
            st.session_state.all_receipts[index]['amount'] = ind_amt
            st.session_state.all_receipts[index]['words'] = new_words
            st.rerun()
        except ValueError: st.error("Enter a valid whole number.")

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
    with c2: sel_year = st.selectbox("Select Year", options=[2025, 2026])

    search_num = st.text_input("Enter Consumer Number", max_chars=3)
    if search_num:
        if not re.match(r"^\d{3}$", search_num): st.warning("⚠️ Must be 3 digits.")
        else:
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
                            new_rec = {
                                'id': str(uuid.uuid4()), 'challan': next_no, 'pdate': st.session_state.formatted_pdate,
                                'name': row['Name'], 'num': row['Consumer Number'], 'month': sel_month, 'year': sel_year,
                                'amount': format_indian_currency(amt_val),
                                'words': num2words(amt_val, lang='en_IN').replace(",", "").replace(" And ", " and ").title().replace(" And ", " and "),
                                'pay_type': mode, 'pay_no': inst_no, 'bank': bank_name, 'date': inst_date.strftime("%d.%m.%Y")
                            }
                            st.session_state.all_receipts.append(new_rec)
                            st.session_state.show_batch = False
                            st.rerun()
                        else: st.error("❌ Invalid Bank Name (letters only) or Instrument No (6 digits).")
            else: st.error("No record found.")

    if st.session_state.all_receipts:
        st.divider()
        if st.checkbox("👁️ View Batch Table", value=st.session_state.show_batch):
            st.session_state.show_batch = True
            t_head = st.columns([0.8, 3, 1.5, 1.5, 1.5, 2, 1.5])
            for idx, title in enumerate(["No.", "Consumer", "Amount", "Mode", "Inst No.", "Bank", "Actions"]): t_head[idx].write(f"**{title}**")
            for i, rec in enumerate(st.session_state.all_receipts):
                tcol = st.columns([0.8, 3, 1.5, 1.5, 1.5, 2, 1.5])
                tcol[0].write(rec['challan']); tcol[1].write(rec['name']); tcol[2].write(f"₹{rec['amount']}")
                tcol[3].write(rec['pay_type']); tcol[4].write(rec['pay_no']); tcol[5].write(rec['bank'])
                with tcol[6]:
                    s1, s2, s3 = st.columns(3)
                    if s1.button("👁️", key=f"p_{rec['id']}"): preview_dialog(i)
                    if s2.button("✏️", key=f"e_{rec['id']}"): edit_amount_dialog(i)
                    if s3.button("🗑️", key=f"d_{rec['id']}"):
                        st.session_state.all_receipts.pop(i)
                        for j in range(i, len(st.session_state.all_receipts)): st.session_state.all_receipts[j]['challan'] -= 1
                        st.rerun()

        if st.button("🚀 Generate Word File", type="primary"):
            doc = DocxTemplate(tpl_file)
            doc.render({'receipts': st.session_state.all_receipts})
            output = io.BytesIO(); doc.save(output)
            st.download_button("📥 Download Now", output.getvalue(), file_name=f"receipt_{date.today().strftime('%d_%m_%Y')}.docx")
