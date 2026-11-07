import tempfile
from pathlib import Path

import pandas as pd
import streamlit as st
from docling.document_converter import DocumentConverter

from docling_test.table_rows import document_to_row_chunks, search_rows

st.set_page_config(
    page_title="Docling - Row-Level Table Chunks for RAG",
    page_icon="📊",
    layout="wide",
)

# Fond dégradé (dégradé violet/bleu) pour une page plus visuelle
st.markdown(
    """
    <style>
        .stApp {
            background: linear-gradient(135deg, #fff176 0%, #ffca28 45%, #ff9800 100%);
        }
        [data-testid="stSidebar"] {
            background: linear-gradient(180deg, #fff9c4 0%, #ffd54f 100%);
        }
        .stApp, .stApp * { color: #3a2e00; }
        /* La couleur sombre n'est pas appliquée aux boutons, qui gardent le style Streamlit */
        button, [data-testid*="Button"], [data-testid*="button"] {
            color: revert !important;
        }
        button * {
            color: revert !important;
        }
        [data-testid="stSidebar"] [data-testid="stCaptionContainer"] {
            color: #3a2e00 !important;
        }
        .stMetric { background: rgba(255,255,255,0.55); border-radius: 12px; padding: 12px; color: #3a2e00; }
        h1, h2, h3 { color: #4a3300 !important; text-shadow: 0 2px 6px rgba(255,255,255,0.45); }
        .stDataFrame { background: rgba(255,255,255,0.35); border-radius: 10px; color: #3a2e00; }
    </style>
    """,
    unsafe_allow_html=True,
)

st.title("📊 Row-Level Table Chunks for RAG")
st.sidebar.markdown("🟢 **Status: Live**")
st.markdown(
    "Convert PDFs with **Docling** and extract **one retrievable chunk per table body row**. "
    "Column headers stay with the values so each row reads like a self-contained sentence."
)

# Sidebar - Settings & File Upload
st.sidebar.header("Source PDF")
upload_option = st.sidebar.radio(
    "Choose input source:",
    ("Use sample PDF (IPCC SPM)", "Upload your own PDF"),
)

sample_pdf = Path("data/raw/IPCC_AR6_WGI_SPM-25-29.pdf")
pdf_path = None

if upload_option == "Use sample PDF (IPCC SPM)":
    if sample_pdf.exists():
        pdf_path = sample_pdf
        st.sidebar.success(f"Using {sample_pdf.name}")
    else:
        st.sidebar.error("Sample PDF not found.")
else:
    uploaded_file = st.sidebar.file_uploader("Upload a PDF file", type=["pdf"])
    if uploaded_file is not None:
        temp_dir = tempfile.mkdtemp()
        pdf_path = Path(temp_dir) / uploaded_file.name
        pdf_path.write_bytes(uploaded_file.read())

if pdf_path is not None and pdf_path.exists():
    pdf_bytes = pdf_path.read_bytes()
    st.sidebar.markdown(
        f'<span style="color:#3a2e00; font-weight:600;">Fichier source : {pdf_path.name}</span>',
        unsafe_allow_html=True,
    )
    st.sidebar.download_button(
        label="📥 Télécharger le PDF",
        data=pdf_bytes,
        file_name=pdf_path.name,
        mime="application/pdf",
        use_container_width=True,
    )

include_caption = st.sidebar.checkbox("Include table captions", value=True)

if pdf_path:
    st.subheader("Processing")
    with st.spinner("Extracting table row chunks with Docling..."):
        try:
            converter = DocumentConverter()
            result = converter.convert(str(pdf_path))
            rows_df = document_to_row_chunks(result.document, include_caption=include_caption)
        except Exception as e:
            st.error(f"Error processing PDF: {e}")
            rows_df = pd.DataFrame()

    if not rows_df.empty:
        # Metrics
        col1, col2, col3 = st.columns(3)
        n_tables = rows_df["table_id"].nunique()
        n_rows = len(rows_df)
        n_pages = rows_df["page_num"].nunique()

        col1.metric("Tables Extracted", n_tables)
        col2.metric("Total Row Chunks", n_rows)
        col3.metric("Pages with Tables", n_pages)

        st.markdown("---")

        # Search filter
        query = st.text_input("🔍 Search within row chunks (row_serialized):", "")
        if query:
            filtered_df = search_rows(rows_df, query)
            st.caption(f"Showing {len(filtered_df)} hit(s) for query: **{query}**")
        else:
            filtered_df = rows_df

        # Display Options
        st.subheader("Row Chunks Table")
        selected_columns = st.multiselect(
            "Select columns to display:",
            options=rows_df.columns.tolist(),
            default=["table_id", "page_num", "row_index", "row_serialized"],
        )

        st.dataframe(
            filtered_df[selected_columns],
            use_container_width=True,
            hide_index=True,
        )

        # Downloads
        st.subheader("Export Options")
        dl_container = st.container(horizontal=True, gap="small")

        jsonl_data = rows_df.to_json(orient="records", lines=True, force_ascii=False)
        with dl_container:
            st.download_button(
                label="📥 Download JSONL",
                data=jsonl_data,
                file_name=f"{pdf_path.stem}_rows.jsonl",
                mime="application/jsonlines",
            )

            csv_data = rows_df.to_csv(index=False)
            st.download_button(
                label="📥 Download CSV",
                data=csv_data,
                file_name=f"{pdf_path.stem}_rows.csv",
                mime="text/csv",
            )
    else:
        st.warning("No tables were detected in the PDF.")
