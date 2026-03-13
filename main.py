import queue
import threading
import time

import streamlit as st

from src.workflow import run_workflow

st.set_page_config(page_title="QAC Automation", layout="wide")
st.title("QAC — Quality Assurance Check Automation")

# ---- Session state initialization ----
if "log_queue" not in st.session_state:
    st.session_state.log_queue = queue.Queue()
if "result_queue" not in st.session_state:
    st.session_state.result_queue = queue.Queue()
if "status_messages" not in st.session_state:
    st.session_state.status_messages = []
if "workflow_running" not in st.session_state:
    st.session_state.workflow_running = False
if "workflow_result" not in st.session_state:
    st.session_state.workflow_result = None

# ---- Layout ----
col1, col2, col3 = st.columns([1, 1, 1])

# ---- Column 1: Inputs ----
with col1:
    st.subheader("Inputs")
    sheet_url = st.text_input(
        "QAC Checklist (Google Sheet URL)",
        placeholder="https://docs.google.com/spreadsheets/d/...",
        disabled=st.session_state.workflow_running,
    )
    se_pdf = st.file_uploader(
        "Student Edition PDF", type="pdf", disabled=st.session_state.workflow_running
    )
    te_pdf = st.file_uploader(
        "Teacher Edition PDF", type="pdf", disabled=st.session_state.workflow_running
    )
    printables_pdf = st.file_uploader(
        "Printables PDF", type="pdf", disabled=st.session_state.workflow_running
    )
    walkthrough_pdf = st.file_uploader(
        "Walkthrough Slides PDF", type="pdf", disabled=st.session_state.workflow_running
    )

    start_clicked = st.button(
        "Start Quality Assurance",
        disabled=st.session_state.workflow_running or not sheet_url,
        type="primary",
        use_container_width=True,
    )

    if start_clicked and sheet_url:
        st.session_state.workflow_running = True
        st.session_state.status_messages = []
        st.session_state.workflow_result = None
        # Reset queues
        st.session_state.log_queue = queue.Queue()
        st.session_state.result_queue = queue.Queue()

        pdf_files = {
            "SE": se_pdf,
            "TE": te_pdf,
            "Printables": printables_pdf,
            "Walkthrough": walkthrough_pdf,
        }

        thread = threading.Thread(
            target=run_workflow,
            args=(
                sheet_url,
                pdf_files,
                st.session_state.log_queue,
                st.session_state.result_queue,
            ),
            daemon=True,
        )
        thread.start()
        st.rerun()

# ---- Column 2: Live Status ----
with col2:
    st.subheader("Status")
    current_activity = st.empty()
    log_container = st.empty()

    if st.session_state.workflow_running:
        # Drain log queue into session state
        while not st.session_state.log_queue.empty():
            try:
                msg = st.session_state.log_queue.get_nowait()
                st.session_state.status_messages.append(msg)
            except queue.Empty:
                break

        # Check if workflow finished
        if not st.session_state.result_queue.empty():
            try:
                result = st.session_state.result_queue.get_nowait()
                st.session_state.workflow_result = result
                st.session_state.workflow_running = False
            except queue.Empty:
                pass

    # Render current state BEFORE triggering any rerun
    if st.session_state.status_messages:
        last_msg = st.session_state.status_messages[-1]
        current_activity.info(f"**Now:** {last_msg}")
        log_container.text("\n".join(st.session_state.status_messages[-60:]))
    elif st.session_state.workflow_running:
        current_activity.info("**Now:** Starting workflow...")

    # Schedule next poll cycle only after rendering
    if st.session_state.workflow_running:
        time.sleep(0.3)
        st.rerun()

# ---- Column 3: Result ----
with col3:
    st.subheader("Result")
    result = st.session_state.workflow_result

    if result:
        if result["status"] == "done":
            st.success("All done!")
            st.markdown(f"[Open QA Checklist ↗]({result['sheet_url']})")
        elif result["status"] == "error":
            st.error(f"Workflow failed: {result.get('message', 'Unknown error')}")
