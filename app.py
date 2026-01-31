import streamlit as st
import pandas as pd
from docxtpl import DocxTemplate
from num2words import num2words
import io

st.set_page_config(page_title="Receipt Generator", layout="wide")
st.title("⚡ Automatic Challan Generator")

# --- SIDEBAR INPUTS ---
st.sidebar.header("One-Time Settings")
start_challan = st.sidebar.number_input("Starting Challan No.", min_value=1, value=100)
p_date = st.sidebar.text_input("Payment Date (pdate)", value="31/01/2026")

# --- FILE UPLOADS ---
col1, col2 = st.columns(2)
with col1:
    tpl_file = st.file_uploader("Upload Word Template (Test.docx)", type=["docx"])
with col2:
    data_file = st.file_uploader("Upload Excel Data (Book.xlsx)", type=["xlsx", "csv"])

if tpl_file and data_file:
    df = pd.read_excel(data_file) if "xlsx" in data_file.name else pd.read_csv(data_file)
    
    st.subheader("Manual Data Entry")
    st.info("Enter details for each consumer below:")
    
    # Add empty columns for the manual fields if they don't exist
    for col in ['pay_type', 'pay_no', 'bank', 'date']:
        if col not in df.columns:
            df[col] = ""

    # Let the user edit the data in a table
    edited_df = st.data_editor(df, num_rows="fixed")

    if st.button("Generate Receipts"):
        doc = DocxTemplate(tpl_file)
        receipt_list = []

        for index, row in edited_df.iterrows():
            # Auto-calculation logic
            amt = float(row['Amount'])
            word_amt = num2words(amt, lang='en_IN').title()
            
            # Map the data to your {{r.variable}} format
            receipt_list.append({
                'challan': int(start_challan + index),
                'pdate': p_date,
                'name': row['Name'],
                'num': row['Consumer Number'],
                'month': row['Month'],
                'amount': f"{amt:,.2f}",
                'words': word_amt,
                'pay_type': row['pay_type'],
                'pay_no': row['pay_no'],
                'bank': row['bank'],
                'date': row['date']
            })

        # Render and Save
        doc.render({'receipts': receipt_list})
        output = io.BytesIO()
        doc.save(output)
        
        st.success("✅ Receipts Generated!")
        st.download_button(
            label="Download Completed Word Doc",
            data=output.getvalue(),
            file_name="Generated_Receipts.docx",
            mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document"
        )