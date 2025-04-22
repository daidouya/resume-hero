import streamlit as st
import requests
import time
import json
import base64

# API Endpoints
UPLOAD_URL = "https://<YOUR_UPLOAD_URL_HERE>"
RESULTS_URL = "https://<YOUR_RESULTS_URL_HERE>"

def encode_file(file):
    """Encodes a file to Base64 string correctly."""
    file_bytes = file.getvalue()  # Read entire file as bytes
    return base64.b64encode(file_bytes).decode("utf-8")

def upload_pdfs(resume_file, description_file):
    """Uploads two PDF files to the backend and returns jobid."""
    # Ensure files are properly read as Base64
    resumedatastr = encode_file(resume_file)
    descriptiondatastr = encode_file(description_file)

    # Construct the request payload **ensuring correct JSON structure**
    payload = json.dumps({  
        "resumedata": resumedatastr,
        "descriptiondata": descriptiondatastr
    })

    # Send request with `json` ensuring `Content-Type: application/json`
    headers = {"Content-Type": "application/json"}
    response = requests.post(UPLOAD_URL, data=payload, headers=headers)  

    if response.status_code == 200:
        jobid = response.json()
        return jobid
    else:
        st.error(f"Upload failed: {response.text}")
        return None

def convert_json_strings(obj):
    """Recursively converts all stringified JSON values into dictionaries or lists."""
    if isinstance(obj, dict):
        return {k: convert_json_strings(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [convert_json_strings(v) for v in obj]
    elif isinstance(obj, str):  
        try:
            parsed_obj = json.loads(obj)  
            return convert_json_strings(parsed_obj)  
        except json.JSONDecodeError:
            return obj  
    else:
        return obj  # Return other types as is

def fetch_results(jobid, max_retries=10, interval=5):
    """Polls the results endpoint until data is available."""
    for attempt in range(max_retries):
        st.info(f"Checking results... (Attempt {attempt+1}/{max_retries})")
        response = requests.get(f"{RESULTS_URL}/{jobid}")

        if response.status_code == 200:
            results = response.json()
            if results.get("status") == "completed":
                return convert_json_strings(results["results"])  # Return processed data
        elif response.status_code == 202:
            time.sleep(interval)  # Wait and retry
        else:
            st.error(f"Error fetching results: {response.text}")
            return None
    st.error("Timeout: Results not ready.")
    return None

st.title("Retrieve Previous Results by Job ID")

jobid_input = st.text_input("Enter Job ID to Fetch Results", "")
if st.button("Fetch Results"):
    if jobid_input:
        results = fetch_results(jobid_input)
        if results:
            st.success("✅ Processing complete! Here are your results:")

            # Skills Analysis
            st.subheader("🔹 Skills Analysis")
            st.write(f"**Match Score: {results['skills_analysis'].get('score', 'N/A')}%**")

            col1, col2 = st.columns(2)
            with col1:
                st.markdown("**📌 Key Resume Skills:**")
                st.markdown("\n".join([f"- {skill}" for skill in results["skills_analysis"]["resume_skills"]]))

            with col2:
                st.markdown("**📌 Key Job Description Skills:**")
                st.markdown("\n".join([f"- {skill}" for skill in results["skills_analysis"]["description_skills"]]))

            # Resume Improvement Advice
            st.subheader("📌 Resume Improvement Advice")
            st.markdown("\n".join([f"- {tip}" for tip in results["resume_advice"]["advice"]]))

            # Generated Cover Letter
            # if isinstance(results["cover_letter"], str):
            #     results["cover_letter"] = json.loads(results["cover_letter"])
            st.subheader("✍️ Generated Cover Letter")
            st.markdown(results["cover_letter"]["letter"].replace("\n", "\n\n"))  
    else:
        st.warning("⚠️ Please enter a valid Job ID.")