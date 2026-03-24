import queue
import threading
import time

import streamlit as st

from src.workflow import run_workflow

st.set_page_config(page_title="QAC Automation", layout="wide")
st.image("static/studiesweekly.webp", width=200)
st.title("Quality Assurance Check")

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
if "intro_chars_shown" not in st.session_state:
    st.session_state.intro_chars_shown = 0

_INTRO_TEXT = (
    "Hey! I'll get started on this right away. "
    "I'll begin by getting all the info I need from Studies Weekly Online. "
    "After that I'll analyze any provided PDFs and run a full QA analysis of everything. "
    "Any issues I find I'll write directly into your QAC spreadsheet.\n\n"
    "While I'm working, here are the QA checks I can't perform that you should handle (if applicable):"
)

# ---- Layout ----
col1, col2, col3 = st.columns([1, 1, 1])

# ---- Column 1: Inputs ----
with col1:
    st.subheader("Inputs")
    st.info(
        "**How to use:**\n\n"
        "1. Share your QAC Google Sheet with editor access to this email: "
        "`qac-automation@tonal-history-489219-j7.iam.gserviceaccount.com`\n"
        "2. Paste the Google Sheet URL below\n"
        "3. Upload any of the following PDFs you have available: "
        "SE, TE, Printables, Walkthrough Slides\n"
        "4. Click **Start Quality Assurance** — the workflow will scrape the online portal, "
        "analyze your PDFs, and write QA findings directly to the checklist"
    )
    st.markdown("**QAC Checklist (Google Sheet URL)**")
    sheet_url = st.text_input(
        "QAC Checklist (Google Sheet URL)",
        placeholder="https://docs.google.com/spreadsheets/d/...",
        disabled=st.session_state.workflow_running,
        label_visibility="collapsed",
    )
    st.markdown("**Classroom Card Override** *(optional)*")
    st.caption("Only needed if the classroom card is mislabeled (e.g. NY3 content is inside a card named NY5). Leave blank to auto-detect.")
    classroom_override = st.text_input(
        "Classroom Card Override",
        placeholder="e.g. NY5",
        disabled=st.session_state.workflow_running,
        label_visibility="collapsed",
    )

    st.markdown("**Student Edition PDF**")
    se_pdf = st.file_uploader(
        "Student Edition PDF", type="pdf", disabled=st.session_state.workflow_running, label_visibility="collapsed"
    )
    st.markdown("**Teacher Edition PDF**")
    te_pdf = st.file_uploader(
        "Teacher Edition PDF", type="pdf", disabled=st.session_state.workflow_running, label_visibility="collapsed"
    )
    st.markdown("**Printables PDF**")
    printables_pdf = st.file_uploader(
        "Printables PDF", type="pdf", disabled=st.session_state.workflow_running, label_visibility="collapsed"
    )
    st.markdown("**Walkthrough Slides PDF**")
    st.markdown(
        "<small style='color:gray'>"
        "• Please use the Answer Key Slides from Teacher Resources if available<br>"
        "• Download as Full Width<br>"
        "• Before uploading you must compress the file:<br>"
        "&nbsp;&nbsp;1. Open in Preview<br>"
        "&nbsp;&nbsp;2. Go to File > Export<br>"
        "&nbsp;&nbsp;3. Set Quartz Filter to Reduce File Size<br>"
        "&nbsp;&nbsp;4. Click Save and upload the compressed file"
        "</small>",
        unsafe_allow_html=True,
    )
    walkthrough_pdf = st.file_uploader(
        "Walkthrough Slides PDF", type="pdf", disabled=st.session_state.workflow_running, label_visibility="collapsed"
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
        st.session_state.intro_chars_shown = 0
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
                classroom_override.strip() or None,
            ),
            daemon=True,
        )
        thread.start()
        st.rerun()

# ---- Column 2: Live Status ----
with col2:
    st.subheader("Status")
    intro_container = st.empty()
    manual_checks_container = st.empty()
    status_spacer = st.empty()
    status_label = st.empty()
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

    # Typewriter intro — runs independently of live status
    if st.session_state.workflow_running or st.session_state.intro_chars_shown > 0:
        shown = st.session_state.intro_chars_shown
        if shown < len(_INTRO_TEXT):
            text_html = _INTRO_TEXT[:shown].replace("\n\n", "<br><br>")
            intro_container.markdown(f"<div style='display:flex; gap:1rem; align-items:flex-start'><span style='font-size:2.5rem'>🤖</span><div style='font-size:1.2rem; line-height:1.7'>{text_html}▌</div></div>", unsafe_allow_html=True)
            st.session_state.intro_chars_shown = min(shown + 5, len(_INTRO_TEXT))
            time.sleep(0.03)
            st.rerun()
        else:
            text_html = _INTRO_TEXT.replace("\n\n", "<br><br>")
            intro_container.markdown(f"<div style='display:flex; gap:1rem; align-items:flex-start'><span style='font-size:2.5rem'>🤖</span><div style='font-size:1.2rem; line-height:1.7'>{text_html}</div></div>", unsafe_allow_html=True)

    # Manual checks reference — shown while workflow is running
    if st.session_state.workflow_running or st.session_state.status_messages:
        checks_html = """
<div style="height:260px; overflow-y:auto; padding:0.75rem 1rem; border:1px solid #e0e0e0; border-radius:8px; background:#fafafa; font-size:0.95rem; line-height:1.7">
<b>🗂️ Table of Contents - TOC (online)</b><br>
&bull; Check PDF attachments/icons in the TOC<br><br>
<b>📚 Student View - SV (online)</b><br><br>
<b>🔤 🖥🎞 Walkthrough - WT</b><br>
&bull; Answer key slides are teacher-facing only<br>
&bull; Walkthrough slides function correctly online (videos, all slides present, etc.)<br><br>
<b>🔤 Vocabulary</b><br>
&bull; Vocabulary bolding/unbolding consistency across sources<br><br>
<b>📖🔈 Article/activity text and audio</b><br>
&bull; Article and question audio narration and text highlighting<br>
&bull; Activities are interactive and correct answers on submission page make sense<br>
&bull; Podcast functionality<br><br>
<b>🖼🎬🎶 Explore More / Related Media - RM</b><br>
&bull; Video and audio clips free of errors<br>
&bull; Videos have closed captions and CCs are free of errors<br>
&bull; Images have no questions and videos have 0–3 questions<br>
&bull; Media questions can be answered by media<br><br>
<b>🧩 Crossword</b><br>
&bull; Crossword has 3–10 terms and is functional<br><br>
<b>🎮 Misspilled</b><br>
&bull; Any issues related to Misspilled<br><br>
<b>💰 Coins</b><br>
&bull; Coins can be collected throughout<br><br>
<b>⚠️ Other</b><br>
&bull; Broken links, images, wrong content attached, etc.
</div>
"""
        manual_checks_container.markdown(checks_html, unsafe_allow_html=True)

    # Render live status
    if st.session_state.status_messages:
        status_spacer.markdown("<hr>", unsafe_allow_html=True)
        status_label.markdown("**What I'm currently working on:**")
        last_msg = st.session_state.status_messages[-1]
        current_activity.info(f"{last_msg}")
        logs_html = "<div style='height:200px; overflow-y:auto; padding:0.75rem; border:1px solid #e0e0e0; border-radius:8px; background:#fafafa; font-size:0.8rem; font-family:monospace; line-height:1.6'>" + "<br>".join(st.session_state.status_messages[-60:]) + "</div>"
        log_container.markdown(logs_html, unsafe_allow_html=True)

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
