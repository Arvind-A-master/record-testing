import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
from mongo import collection

from google.cloud import storage
from datetime import timedelta
import streamlit as st
from google.cloud import storage
from google.oauth2 import service_account
import json
# --------------------------------------------------
# GCS SIGNED URL GENERATOR (NEW)
# --------------------------------------------------


@st.cache_resource
def get_gcs_client():
    if "gcp" in st.secrets:
        creds = service_account.Credentials.from_service_account_info(
            st.secrets["gcp"]
        )
        return storage.Client(credentials=creds, project=creds.project_id)
    return storage.Client()

def generate_signed_gcs_download_url(
    gcs_uri: str,
    expires_minutes: int = 15
) -> str:
    if not gcs_uri.startswith("gs://"):
        raise ValueError("Invalid GCS URI")

    _, path = gcs_uri.split("gs://", 1)
    bucket_name, blob_name = path.split("/", 1)

    client = get_gcs_client()
    bucket = client.bucket(bucket_name)
    blob = bucket.blob(blob_name)

    return blob.generate_signed_url(
        version="v4",
        expiration=timedelta(minutes=expires_minutes),
        method="GET"
    )

# --------------------------------------------------
# STREAMLIT CONFIG
# --------------------------------------------------
st.set_page_config(layout="wide")
st.title("📄 Compliance Review – Client View")

# --------------------------------------------------
# SESSION STATE
# --------------------------------------------------
if "docs" not in st.session_state:
    st.session_state.docs = []

if "record_map" not in st.session_state:
    st.session_state.record_map = {}

# --------------------------------------------------
# LAYOUT
# --------------------------------------------------
control_col, main_col = st.columns([1, 4])

# --------------------------------------------------
# LEFT SIDE CONTROLS (UNCHANGED)
# --------------------------------------------------
with control_col:
    st.subheader("Filters")

    selected_date = st.date_input(
        "Review Date",
        value=datetime.now().date()
    )

    fetch_clicked = st.button("Fetch Records")

    if fetch_clicked:
        date_str = selected_date.strftime("%Y-%m-%d")
        start_dt = datetime.combine(selected_date, datetime.min.time())
        end_dt = start_dt + timedelta(days=1)

        query = {
            "$or": [
                {
                    "created_at": {
                        "$gte": start_dt,
                        "$lt": end_dt
                    }
                },
                {
                    "created_at": {
                        "$regex": f"^{date_str}"
                    }
                }
            ]
        }

        docs = list(collection.find(query))

        st.session_state.docs = docs
        st.session_state.record_map = {
            str(doc["_id"]): doc for doc in docs
        }

# --------------------------------------------------
# RECORD SELECTION
# --------------------------------------------------
if not st.session_state.record_map:
    with main_col:
        st.info("Select a date and click **Fetch Records**")
    st.stop()

with control_col:
    selected_record_id = st.selectbox(
        "Review Record",
        st.session_state.record_map.keys()
    )

selected_doc = st.session_state.record_map[selected_record_id]

# --------------------------------------------------
# BUILD TABLE (UNCHANGED)
# --------------------------------------------------
rows = []

for artifact in selected_doc.get("recommendations", {}).values():
    for sec in artifact.get("sections", []):
        rows.append({
            "uuid": sec.get("uuid", ""),
            "section_title": sec.get("section_title", ""),
            "sentence": sec.get("sentence", ""),
            "page_number": sec.get("page_number", ""),
            "observations": sec.get("observations", ""),
            "rule_citation": sec.get("rule_citation", ""),
            "recommendations": sec.get("recommendations", ""),
            "category": sec.get("category", ""),
            "accept": sec.get("accept", False),
            "accept_with_changes": sec.get("accept_with_changes", False),
            "reject": sec.get("reject", False),
            "reject_reason": sec.get("reject_reason", ""),
        })

df = pd.DataFrame(rows)

if df.empty:
    with main_col:
        st.warning("No compliance sections found")
    st.stop()

df = df.astype(str)

# --------------------------------------------------
# DISPLAY TABLE + DOWNLOADS
# --------------------------------------------------
with main_col:
    st.subheader("Compliance Findings")

    st.dataframe(
        df,
        width="stretch",
        hide_index=True
    )

    # EXISTING CSV DOWNLOAD (UNCHANGED)
    st.download_button(
        "⬇ Download This Record (CSV)",
        df.to_csv(index=False),
        file_name=f"compliance_{selected_record_id}.csv",
        mime="text/csv"
    )

    # --------------------------------------------------
    # NEW: DOWNLOAD SOURCE PDF (FRESH SIGNED URL)
    # --------------------------------------------------
    gcs_uri = (
        selected_doc
        .get("metadata", {})
        .get("gcs_uri")
    )

    if gcs_uri:
        if st.button("⬇ Download Source PDF"):
            try:
                signed_pdf_url = generate_signed_gcs_download_url(gcs_uri)

                st.markdown(
                    f"[Click here to download PDF (valid 15 min)]({signed_pdf_url})",
                    unsafe_allow_html=True
                )
            except Exception as e:
                st.error(f"Failed to generate PDF download link: {e}")
    else:
        st.warning("GCS URI not available for this record")
