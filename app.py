# app.py
import streamlit as st
import os
from agents import agent_a, agent_b, generate_followups, generate_summary, embed_and_chunk_pdf
from io import BytesIO
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet

# ---- Authentication Section ----
def login():
    st.title("🔐 Secure Login")
    username = st.text_input("Username")
    password = st.text_input("Password", type="password")
    if st.button("Login"):
        if username == os.getenv("APP_USERNAME") and password == os.getenv("APP_PASSWORD"):
            st.session_state.authenticated = True
            st.success("Login successful!")
            st.rerun()
        else:
            st.error("Invalid credentials. Please try again.")

if "authenticated" not in st.session_state:
    st.session_state.authenticated = False

if not st.session_state.authenticated:
    login()
    st.stop()

# ---- Main App After Authentication ----
st.set_page_config(page_title="Agentic Chat", layout="wide")
st.title("🤖 Agentic AI: Dual-Agent Smart Conversation with RAG")

# Session state initialization
if "history" not in st.session_state:
    st.session_state.history = []
    st.session_state.turn = 0
    st.session_state.followup_options = []
    st.session_state.selected_followup = ""
    st.session_state.agent_a_persona = ""
    st.session_state.agent_b_persona = ""
    st.session_state.short_summary = ""
    st.session_state.long_summary = ""
    st.session_state.pdf_text = ""

# Upload PDF for context
st.sidebar.header("📄 Upload Context PDF")
pdf_file = st.sidebar.file_uploader("Upload a PDF to serve as conversation context", type=["pdf"])
if pdf_file:
    status = embed_and_chunk_pdf(pdf_file)
    st.sidebar.success(status)

# Layout: Left (Agent A), Center (Control), Right (Agent B)
col1, col2, col3 = st.columns([2, 3, 2])

with col2:
    st.header("Conversation Control")
    st.session_state.agent_a_persona = st.text_input("Enter Agent A Persona", st.session_state.agent_a_persona)
    st.session_state.agent_b_persona = st.text_input("Enter Agent B Persona", st.session_state.agent_b_persona)

    user_query = st.text_input("Start the conversation (Agent A)", "What are the differences between AI and human intelligence?")
    if st.button("Start Conversation"):
        st.session_state.history = []
        st.session_state.turn = 0
        persona_prefix = f"As a persona \"{st.session_state.agent_a_persona}\", I would like to ask: " if st.session_state.agent_a_persona else ""
        full_query = f"{persona_prefix}{user_query}\n\nContext:\n{st.session_state.pdf_text}" if st.session_state.pdf_text else persona_prefix + user_query
        st.session_state.history.append(("Agent A", full_query))
        st.session_state.followup_options = []
        st.session_state.selected_followup = ""
        st.session_state.short_summary = ""
        st.session_state.long_summary = ""

    max_turns = st.slider("Conversation Depth (Turns)", 1, 10, 3)

with col1:
    st.header("🧠 Agent A")
    for speaker, msg in st.session_state.history:
        if speaker == "Agent A":
            st.markdown(f"**{speaker}:** {msg}")

with col3:
    st.header("🧠 Agent B")
    for speaker, msg in st.session_state.history:
        if speaker == "Agent B":
            st.markdown(f"**{speaker}:** {msg}")

with col2:
    if st.button("Continue Conversation") and st.session_state.turn < max_turns:
        a_query = st.session_state.history[-1][1]
        context_query = f"{a_query}\n\nContext:\n{st.session_state.pdf_text}" if st.session_state.pdf_text else a_query
        b_response = agent_b.ask(context_query)
        if st.session_state.agent_b_persona:
            b_response = f"As a persona \"{st.session_state.agent_b_persona}\", I would like to respond: {b_response}"
        st.session_state.history.append(("Agent B", b_response))

        topic = st.session_state.history[0][1]
        followups = generate_followups(topic, a_query, b_response)

        followup_list = followups if isinstance(followups, list) else [q.strip("- ") for q in followups.split("\n") if q.strip().startswith("-")]

        if followup_list:
            st.session_state.followup_options = followup_list
            st.session_state.selected_followup = followup_list[0]

    if st.session_state.followup_options:
        user_followup = st.text_input("Or type your own follow-up question")
        selected = st.radio("Choose one suggested question to ask:", st.session_state.followup_options)

        if st.button("Ask Agent B"):
            persona_prefix = f"As a persona \"{st.session_state.agent_a_persona}\", I would like to ask: " if st.session_state.agent_a_persona else ""
            full_query = f"{persona_prefix}{selected}\n\nContext:\n{st.session_state.pdf_text}" if st.session_state.pdf_text else persona_prefix + selected
            st.session_state.history.append(("Agent A", full_query))
            b_response = agent_b.ask(full_query)
            if st.session_state.agent_b_persona:
                b_response = f"As a persona \"{st.session_state.agent_b_persona}\", I would like to respond: {b_response}"
            st.session_state.history.append(("Agent B", b_response))
            st.session_state.turn += 1

        if user_followup and st.button("Ask Agent B - custom q"):
            persona_prefix = f"As a persona \"{st.session_state.agent_a_persona}\", I would like to ask: " if st.session_state.agent_a_persona else ""
            full_query = f"{persona_prefix}{user_followup}\n\nContext:\n{st.session_state.pdf_text}" if st.session_state.pdf_text else persona_prefix + user_followup
            st.session_state.history.append(("Agent A", full_query))
            b_response = agent_b.ask(full_query)
            if st.session_state.agent_b_persona:
                b_response = f"As a persona \"{st.session_state.agent_b_persona}\", I would like to respond: {b_response}"
            st.session_state.history.append(("Agent B", b_response))
            st.session_state.turn += 1

    if st.button("End & Summarize Conversation"):
        short, long = generate_summary(st.session_state.history)
        st.session_state.short_summary = short
        st.session_state.long_summary = long

    if st.session_state.short_summary:
        st.subheader("📝 Short Summary")
        st.markdown(st.session_state.short_summary)

    if st.session_state.long_summary:
        st.subheader("📚 Detailed FAQ Summary")
        st.markdown(st.session_state.long_summary)

    if st.session_state.short_summary or st.session_state.long_summary:
        buffer = BytesIO()
        doc = SimpleDocTemplate(buffer, pagesize=letter)
        styles = getSampleStyleSheet()
        story = []

        story.append(Paragraph("Agentic AI Conversation Summary", styles['Title']))
        story.append(Spacer(1, 12))
        story.append(Paragraph("Short Summary:", styles['Heading2']))
        story.append(Paragraph(st.session_state.short_summary.replace("\n", "<br/>"), styles['Normal']))
        story.append(Spacer(1, 12))
        story.append(Paragraph("Detailed FAQ Summary:", styles['Heading2']))
        story.append(Paragraph(st.session_state.long_summary.replace("\n", "<br/>"), styles['Normal']))

        doc.build(story)
        buffer.seek(0)

        st.download_button(
            label="📄 Download Summary as PDF",
            data=buffer,
            file_name="AgenticAI_Summary.pdf",
            mime="application/pdf"
        )
