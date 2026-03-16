import streamlit as st
import pandas as pd
import requests
import json
import time
import io

# --- CONFIGURATION (Streamlit Secrets) ---
# Instead of userdata.get, we use st.secrets
SERPER_API_KEY = st.secrets["SERPER_API_KEY"]
GROQ_API_KEY = st.secrets["GROQ_API_KEY"]

# --- HELPER FUNCTIONS ---
def get_search_context(name, role, org, state):
    url = "https://google.serper.dev/search"
    query = f"{name} {role} {org} {state} current designation 2026"
    payload = json.dumps({"q": query, "num": 4})
    headers = {'X-API-KEY': SERPER_API_KEY, 'Content-Type': 'application/json'}
    try:
        response = requests.post(url, headers=headers, data=payload, timeout=30)
        response.raise_for_status()
        snippets = [res.get('snippet', '') for res in response.json().get('organic', [])]
        return " ".join(snippets)
    except Exception as e:
        return ""

def verify_with_groq(row, context):
    url = "https://api.groq.com/openai/v1/chat/completions"
    headers = {"Content-Type": "application/json", "Authorization": f"Bearer {GROQ_API_KEY}"}
    json_response_format = '{"status": "verified/outdated", "updated_role": "...", "updated_city": "...", "updated_organisation": "..."}'
    prompt_text = f"Verify if {row['Name']} is still {row['Current Designation / Role']} at {row['Organisation']} in {row['Base City']} based on these search results: {context}. Return ONLY a JSON: {json_response_format}"

    payload = {
        "model": "llama-3.1-8b-instant",
        "messages": [{"role": "user", "content": prompt_text}],
        "response_format": {"type": "json_object"}
    }
    try:
        res = requests.post(url, headers=headers, data=json.dumps(payload), timeout=60)
        res.raise_for_status()
        return json.loads(res.json()['choices'][0]['message']['content'])
    except Exception:
        return {"status": "error", "updated_role": "N/A", "updated_city": "N/A", "updated_organisation": "N/A"}

# --- STREAMLIT UI ---
st.title("Dignitary Verification Portal")
st.write("Upload your list to verify current designations using AI.")

# File Uploader
uploaded_file = st.file_uploader("Upload your list for verification", type=["csv", "xlsx"])

if uploaded_file is not None:
    if uploaded_file.name.endswith('.csv'):
        df = pd.read_csv(uploaded_file)
    else:
        df = pd.read_excel(uploaded_file)
    
    st.write(f"Loaded {len(df)} records.")
    
    if st.button("Start Verification"):
        results = []
        progress_bar = st.progress(0)
        status_text = st.empty()

        for i, row in df.iterrows():
            status_text.text(f"Verifying {i+1}/{len(df)}: {row['Name']}")
            context = get_search_context(row['Name'], row['Current Designation / Role'], row['Organisation'], row['State'])
            verification = verify_with_groq(row, context)
            
            processed_verification = {
                "status": verification.get("status", "error"),
                "updated_role": verification.get("updated_role", "N/A"),
                "updated_city": verification.get("updated_city", "N/A"),
                "updated_organisation": verification.get("updated_organisation", "N/A")
            }
            
            new_row = {**row.to_dict(), **processed_verification}
            results.append(new_row)
            progress_bar.progress((i + 1) / len(df))

        # Final DataFrame
        final_df = pd.DataFrame(results)
        st.success("Processing complete!")
        st.dataframe(final_df)

        # Download Button
        csv = final_df.to_csv(index=False).encode('utf-8')
        st.download_button(
            label="Download Verified Results",
            data=csv,
            file_name="verified_results_2026.csv",
            mime="text/csv",
        )
