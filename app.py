# app.py (Streamlit frontend)
import streamlit as st
import requests

st.set_page_config(page_title="Section 91 CrPC Generator")

st.title("🔏 Section 91 CrPC Request Generator")
st.markdown("Fill the details below to auto-generate and email a legally formatted PDF request.")

# Form inputs
with st.form("crpc_form"):
    officer_name = st.text_input("Officer Name")
    designation = st.text_input("Designation")
    police_station = st.text_input("Police Station")
    contact_info = st.text_input("Contact Info (email / phone)")
    case_number = st.text_input("Case Number / FIR Number")
    recipient = st.text_input("Nodal Officer / Organization")
    recipient_email = st.text_input("Nodal Officer's Email")  # ✅ New field
    suspect_identifier = st.text_input("Suspect Info (UPI ID, phone, etc.)")
    date_range = st.text_input("Date Range (e.g., 01-06-2025 to 15-06-2025)")
    data_requested = st.text_area("Data Requested")
    case_purpose = st.text_area("Purpose of Request")

    submitted = st.form_submit_button("Generate & Send PDF")

if submitted:
    with st.spinner("Generating and sending..."):
        data = {
            "officer_name": officer_name,
            "designation": designation,
            "police_station": police_station,
            "contact_info": contact_info,
            "case_number": case_number,
            "recipient": recipient,
            "recipient_email": recipient_email,  # ✅ Included in data sent
            "suspect_identifier": suspect_identifier,
            "date_range": date_range,
            "data_requested": data_requested,
            "case_purpose": case_purpose,
        }

        try:
            res = requests.post("http://localhost:8000/generate", json=data)
            res.raise_for_status()
            result = res.json()
            st.success("✅ PDF generated and email sent!")

            download_url = f"http://localhost:8000/download/{result['filename']}"
            st.markdown(f"[📥 Download PDF]({download_url})", unsafe_allow_html=True)
        except Exception as e:
            st.error(f"❌ Something went wrong: {e}")