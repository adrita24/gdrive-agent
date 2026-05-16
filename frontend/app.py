"""
Streamlit frontend for the Google Drive AI Assistant.
"""

import os
import requests
import streamlit as st
from dotenv import load_dotenv

load_dotenv()

BACKEND_URL = os.getenv("BACKEND_URL", "http://localhost:8000")

SUGGESTED_PROMPTS = [
    "📄 Show me all files",
    "🔍 Find all PDFs",
    "📊 Find all spreadsheets",
    "🖼️ Find all images",
    "📝 Find all Google Docs",
    "📅 Find files modified this year",
]

st.set_page_config(
    page_title="Drive Assistant",
    page_icon="🗂️",
    layout="centered",
    initial_sidebar_state="expanded",
)

st.markdown("""
<style>
  @import url('https://fonts.googleapis.com/css2?family=DM+Sans:wght@400;500;600&family=Space+Grotesk:wght@500;700&display=swap');

  html, body, [class*="css"] {
    font-family: 'DM Sans', sans-serif;
  }

  /* Header — works on both light and dark */
  .drive-header {
    display: flex;
    align-items: center;
    gap: 12px;
    padding: 1.2rem 0 0.4rem 0;
    margin-bottom: 0.2rem;
  }
  .drive-header .icon {
    font-size: 2.2rem;
  }
  .drive-header h1 {
    font-family: 'Space Grotesk', sans-serif;
    font-size: 1.6rem;
    font-weight: 700;
    margin: 0;
    color: inherit;
  }
  .drive-header p {
    margin: 0;
    font-size: 0.85rem;
    opacity: 0.6;
  }

  /* Status badges */
  .status-ok {
    display: inline-block;
    background: rgba(26, 122, 74, 0.15);
    color: #4ade80;
    border-radius: 999px;
    padding: 2px 10px;
    font-size: 0.75rem;
    font-weight: 600;
  }
  .status-err {
    display: inline-block;
    background: rgba(192, 57, 43, 0.15);
    color: #f87171;
    border-radius: 999px;
    padding: 2px 10px;
    font-size: 0.75rem;
    font-weight: 600;
  }

  /* Hide Streamlit chrome */
  #MainMenu {visibility: hidden;}
  footer {visibility: hidden;}
  header {visibility: hidden;}
</style>
""", unsafe_allow_html=True)

if "messages" not in st.session_state:
    st.session_state.messages = []

if "pending_prompt" not in st.session_state:
    st.session_state.pending_prompt = None

with st.sidebar:
    st.markdown("### 🗂️ Drive Assistant")
    st.markdown("Powered by **Gemini + LangGraph**")
    st.markdown("---")

    # Backend health check
    try:
        r = requests.get(f"{BACKEND_URL}/health", timeout=4)
        h = r.json()
        if r.status_code == 200:
            st.markdown('<span class="status-ok">● Backend online</span>', unsafe_allow_html=True)
            folder_ok = h.get("gdrive_folder_configured")
            key_ok = h.get("llm_api_key_configured")
            st.markdown(
                f"{'✅' if folder_ok else '❌'} Drive folder configured\n\n"
                f"{'✅' if key_ok else '❌'} LLM API key configured"
            )
        else:
            st.markdown('<span class="status-err">● Backend error</span>', unsafe_allow_html=True)
    except Exception:
        st.markdown('<span class="status-err">● Backend unreachable</span>', unsafe_allow_html=True)
        st.caption(f"Trying: `{BACKEND_URL}`")

    st.markdown("---")
    st.markdown("**Try asking:**")
    st.markdown("""
- Show me all files  
- Find all PDFs  
- Find spreadsheets modified this year  
- Search for files about marketing  
- Find images in the folder  
- Find the Q1 financial report  
    """)

    st.markdown("---")
    if st.button("🗑️ Clear conversation", use_container_width=True):
        st.session_state.messages = []
        st.rerun()

    st.markdown("---")
    st.caption("Backend URL")
    backend_input = st.text_input(
        "Backend URL", value=BACKEND_URL, label_visibility="collapsed"
    )
    if backend_input != BACKEND_URL:
        BACKEND_URL = backend_input

st.markdown("""
<div class="drive-header">
  <div class="icon">🗂️</div>
  <div>
    <h1>Google Drive Assistant</h1>
    <p>Ask me to find any file — by name, type, content, or date.</p>
  </div>
</div>
""", unsafe_allow_html=True)

if not st.session_state.messages:
    cols = st.columns(3)
    for i, prompt in enumerate(SUGGESTED_PROMPTS):
        with cols[i % 3]:
            if st.button(prompt, key=f"chip_{i}", use_container_width=True):
                st.session_state.pending_prompt = prompt
                st.rerun()

for msg in st.session_state.messages:
    with st.chat_message(msg["role"], avatar="🧑" if msg["role"] == "user" else "🤖"):
        st.markdown(msg["content"])

def send_message(user_input: str):
    # Append user turn
    st.session_state.messages.append({"role": "user", "content": user_input})
    with st.chat_message("user", avatar="🧑"):
        st.markdown(user_input)

    # Call backend
    with st.chat_message("assistant", avatar="🤖"):
        with st.spinner("Searching Drive…"):
            try:
                history_payload = [
                    {"role": m["role"], "content": m["content"]}
                    for m in st.session_state.messages[:-1]
                ]
                resp = requests.post(
                    f"{BACKEND_URL}/chat",
                    json={"message": user_input, "history": history_payload},
                    timeout=60,
                )
                resp.raise_for_status()
                reply = resp.json().get("response", "No response received.")
            except requests.exceptions.ConnectionError:
                reply = (
                    "❌ **Cannot reach the backend.**\n\n"
                    f"Make sure the FastAPI server is running at `{BACKEND_URL}`.\n"
                    "Update the URL in the sidebar if needed."
                )
            except requests.exceptions.Timeout:
                reply = "⏱️ The request timed out. The backend may be overloaded — please try again."
            except Exception as e:
                reply = f"❌ Error: {str(e)}"

            st.markdown(reply)

    st.session_state.messages.append({"role": "assistant", "content": reply})

if st.session_state.pending_prompt:
    prompt = st.session_state.pending_prompt
    st.session_state.pending_prompt = None
    send_message(prompt)

if user_input := st.chat_input("Ask me to find files… e.g. 'Find all PDFs modified last month'"):
    send_message(user_input)