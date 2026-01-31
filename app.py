import streamlit as st
import pandas as pd
from docxtpl import DocxTemplate
from num2words import num2words
import io
from datetime import date
import uuid
import re  # Added for validation

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

# --- DIALOGS ---
@st.dialog("Challan Preview (Template View)")
def preview_dialog(index):
    rec = st.session_state.all_receipts[index]
    
    st.write(f"### Previewing Challan: {rec['challan']}")
    st.info("This will generate a single Word document for this record so you can check the formatting.")
    
    # 1. Create a temporary document for just this one record
    try:
        # We need to reload the template from the uploaded file
        # We seek(0) to ensure we read from the start of the file buffer
        tpl_file.seek(0)
        temp_doc = DocxTemplate(tpl_file)
        
        # 2. Render only this specific record
        # Note: We wrap it in a list because your template uses {% for r in receipts %}
        temp_doc.render({'receipts': [rec]})
        
        # 3. Save to a byte buffer
        preview_buf = io.BytesIO()
        temp_doc.save(preview_buf)
        preview_buf.seek(0)
        
        # 4. Provide a specific download button for this preview
        st.download_button(
            label="📄 Open Word Preview",
            data=preview_buf,
            file_name=f"PREVIEW_{rec['num']}_{rec['month']}.docx",
            mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            use_container_width=True
        )
        
        # Display the data summary below the button for quick reference
        st.divider()
        st.write("**Data injected into template:**")
        st.json(rec)
        
    except Exception as e:
        st.error(f"Could not generate preview: {e}")

@st.dialog("Challan Preview")
def preview_dialog(index):
    rec = st.session_state.all_receipts[index]
    st.markdown(f"### Challan No: {rec['challan']}")
    st.write(f"**Consumer:** {rec['name']} ({rec['num']})")
    st.write(f"**Amount:** ₹{rec['amount']}")
    st.write(f"**Words:** {rec['words']} Only")
    st.write(f"**Payment:** {rec['pay_type']} - {rec['pay_no']}")
    st.write(f"**Bank:** {rec['bank']} ({rec['date']})")
    st.write(f"**Period:** {rec['month']} {rec['year']}")

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
    s_challan = st.text_input("Starting Challan No", disabled=st.session_state.locked)
    s_pdate = st.date_input("Present Date", disabled=st.session_state.locked)
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

    # 1. LIMITATION: Consumer Number (3 digits only)
    search_num = st.text_input("Enter Consumer Number", max_chars=3, help="Must be exactly 3 digits")
    
    if search_num:
        # Check if it is exactly 3 digits
        if not re.match(r"^\d{3}$", search_num):
            st.warning("⚠️ Consumer Number must be exactly 3 digits.")
            result = pd.DataFrame() # Empty result to stop flow
        else:
            m_idx = month_list.index(sel_month) + 1
            result = df[(df['Consumer Number'].astype(str) == search_num) & (df['Month'] == m_idx) & (df['Year'] == sel_year)]

        if not result.empty:
            row = result.iloc[0]
            amt_val = float(row['Amount'])
            st.success(f"**Found:** {row['Name']} | **Amt:** ₹{format_indian_currency(amt_val)}")

            with st.form("entry_form", clear_on_submit=True):
                # 3. LIMITATION: Bank Name (String with gaps, no symbols/numbers)
                bank_name = st.text_input("Bank Name", help="Only letters and spaces allowed")
                
                f1, f2 = st.columns(2)
                with f1: mode = st.selectbox("Type", ["Cheque", "Demand Draft"])
                with f2: 
                    # 2. LIMITATION: DD/Cheque Number (6 digits, allows leading zeros)
                    inst_no = st.text_input("DD/Cheque No", max_chars=6, help="Must be exactly 6 digits (e.g., 001234)")
                
                inst_date = st.date_input("DD/Cheque Date")
                
                if st.form_submit_button("Add to Batch"):
                    # Validation Checks
                    is_valid = True
                    
                    # Validate Bank Name
                    if not re.match(r"^[a-zA-Z\s]+$", bank_name):
                        st.error("❌ Bank Name must contain only letters and spaces (no numbers or symbols).")
                        is_valid = False
                    
                    # Validate Instrument Number
                    if not re.match(r"^\d{6}$", inst_no):
                        st.error("❌ Instrument Number must be exactly 6 digits.")
                        is_valid = False
                        
                    if is_valid:
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
        elif search_num and re.match(r"^\d{3}$", search_num): 
            st.error("No record found in the master data for this selection.")

    # --- BATCH TABLE ---
    if st.session_state.all_receipts:
        st.divider()
        if st.checkbox("👁️ View Batch Table", value=st.session_state.show_batch):
            st.session_state.show_batch = True
            t_head = st.columns([0.8, 2, 1.5, 1.5, 1.5, 2, 2])
            t_head[0].write("**No.**")
            t_head[1].write("**Consumer**")
            t_head[2].write("**Amount**")
            t_head[3].write("**Mode**")
            t_head[4].write("**Inst. No.**")
            t_head[5].write("**Bank**")
            t_head[6].write("**Actions**")
            
            for i, rec in enumerate(st.session_state.all_receipts):
                tcol = st.columns([0.8, 2, 1.5, 1.5, 1.5, 2, 2])
                tcol[0].write(rec['challan'])
                tcol[1].write(rec['name'])
                tcol[2].write(f"₹{rec['amount']}")
                tcol[3].write(rec['pay_type'])
                tcol[4].write(rec['pay_no'])
                tcol[5].write(rec['bank'])
                
                with tcol[6]:
                    sub1, sub2, sub3 = st.columns(3)
                    if sub1.button("👁️", key=f"p_{rec['id']}", help="Preview"): preview_dialog(i)
                    if sub2.button("✏️", key=f"e_{rec['id']}", help="Edit"): edit_amount_dialog(i)
                    if sub3.button("🗑️", key=f"d_{rec['id']}", help="Delete"):
                        st.session_state.all_receipts.pop(i)
                        for j in range(i, len(st.session_state.all_receipts)):
                            st.session_state.all_receipts[j]['challan'] -= 1
                        st.rerun()

        if st.button("🚀 Generate Final Word File", type="primary"):
            doc = DocxTemplate(tpl_file)
            doc.render({'receipts': st.session_state.all_receipts})
            output = io.BytesIO()
            doc.save(output)
            fn = f"receipt_{date.today().strftime('%d_%m_%Y')}.docx"
            st.download_button("📥 Download Now", output.getvalue(), file_name=fn)







