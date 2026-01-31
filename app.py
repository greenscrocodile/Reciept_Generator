import streamlit as st
import pandas as pd
from docxtpl import DocxTemplate
from num2words import num2words
import io

st.set_page_config(page_title="Step-by-Step Receipt Gen", layout="centered")
st.title("📑 Step-by-Step Receipt Entry")

# Initialize session state to store manual entries
if 'manual_data' not in st.session_state:
    st.session_state.manual_data = {}
if 'current_idx' not in st.session_state:
    st.session_state.current_idx = 0

# --- SIDEBAR: Settings ---
st.sidebar.header("Global Settings")
start_challan = st.sidebar.number_input("Starting Challan No.", min_value=1, value=100)
p_date = st.sidebar.text_input("Payment Date (pdate)", value="31/01/2026")

# --- FILE UPLOAD ---
tpl_file = st.file_uploader("1. Upload Word Template", type=["docx"])
data_file = st.file_uploader("2. Upload Excel Data", type=["xlsx", "csv"])

if tpl_file and data_file:
    df = pd.read_excel(data_file) if "xlsx" in data_file.name else pd.read_csv(data_file)
    total_records = len(df)

    # Current Record Info
    idx = st.session_state.current_idx
    row = df.iloc[idx]
    
    st.divider()
    st.subheader(f"Record {idx + 1} of {total_records}")
    st.info(f"**Consumer:** {row['Name']} ({row['Consumer Number']})")

    # Manual Input Form for this specific record
    # We use the index as a key so Streamlit remembers the data
    col1, col2 = st.columns(2)
    with col1:
        pay_type = st.selectbox(f"Payment Type", ["Cheque", "DD", "Online", "Cash"], key=f"pt_{idx}")
        pay_no = st.text_input(f"Instrument/Ref No.", key=f"pn_{idx}")
    with col2:
        bank = st.text_input(f"Bank Name", key=f"bk_{idx}")
        date = st.text_input(f"Instrument Date", placeholder="DD/MM/YYYY", key=f"dt_{idx}")

    # Navigation Buttons
    nav_col1, nav_col2, nav_col3 = st.columns([1,1,1])
    
    with nav_col1:
        if st.button("⬅️ Previous") and idx > 0:
            st.session_state.current_idx -= 1
            st.rerun()

    with nav_col2:
        if st.button("Next ➡️") and idx < total_records - 1:
            st.session_state.current_idx += 1
            st.rerun()

    # --- GENERATION SECTION ---
    if idx == total_records - 1:
        st.success("All data entered! Ready to generate.")
        if st.button("🚀 Generate All Receipts", type="primary"):
            doc = DocxTemplate(tpl_file)
            receipt_list = []

            for i, r in df.iterrows():
                amt = float(r['Amount'])
                # Pulling the data we saved in the session state keys
                receipt_list.append({
                    'challan': int(start_challan + i),
                    'pdate': p_date,
                    'name': r['Name'],
                    'num': r['Consumer Number'],
                    'month': r['Month'],
                    'amount': f"{amt:,.2f}",
                    'words': num2words(amt, lang='en_IN').title(),
                    'pay_type': st.session_state[f"pt_{i}"],
                    'pay_no': st.session_state[f"pn_{i}"],
                    'bank': st.session_state[f"bk_{i}"],
                    'date': st.session_state[f"dt_{i}"]
                })

            doc.render({'receipts': receipt_list})
            output = io.BytesIO()
            doc.save(output)
            
            st.download_button(
                label="📥 Download Completed Word Doc",
                data=output.getvalue(),
                file_name="All_Receipts.docx",
                mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document"
            )
