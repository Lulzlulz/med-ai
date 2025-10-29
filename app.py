import streamlit as st
from groq import Groq
from dotenv import load_dotenv
import os
import sqlite3
import pyttsx3
import speech_recognition as sr
import PyPDF2
from io import BytesIO

# -----------------------------
# INITIAL SETUP
# -----------------------------
load_dotenv()
GROQ_KEY = os.getenv("GROQ_API_KEY")
client = Groq(api_key=GROQ_KEY)

# -----------------------------
# DATABASE SETUP
# -----------------------------
DB_PATH = "chat_history.db"

def init_db():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS chat_history
                 (id INTEGER PRIMARY KEY AUTOINCREMENT,
                  role TEXT,
                  content TEXT)''')
    conn.commit()
    conn.close()

def save_message(role, content):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("INSERT INTO chat_history (role, content) VALUES (?, ?)", (role, content))
    conn.commit()
    conn.close()

def load_messages():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT role, content FROM chat_history")
    messages = c.fetchall()
    conn.close()
    return [{"role": r, "content": c} for r, c in messages]

# -----------------------------
# SPEECH SETUP
# -----------------------------
def speak_text(text):
    engine = pyttsx3.init()
    engine.say(text)
    engine.runAndWait()

def recognize_voice():
    r = sr.Recognizer()
    with sr.Microphone() as source:
        st.info("🎙️ Listening... Speak now!")
        audio = r.listen(source)
    try:
        text = r.recognize_google(audio)
        st.success(f"🗣️ You said: {text}")
        return text
    except sr.UnknownValueError:
        st.error("❌ Sorry, I didn’t understand that.")
        return ""
    except sr.RequestError:
        st.error("⚠️ Speech service not available.")
        return ""

# -----------------------------
# FILE READER
# -----------------------------
def extract_text_from_pdf(uploaded_file):
    reader = PyPDF2.PdfReader(uploaded_file)
    text = ""
    for page in reader.pages:
        text += page.extract_text()
    return text

# -----------------------------
# STREAMLIT UI
# -----------------------------
st.set_page_config(page_title="Groq Ultimate AI Assistant", page_icon="🤖", layout="centered")
st.title("🤖 Groq Ultimate AI Assistant")
st.caption("Built with Streamlit + Groq API + Voice & Memory Support")

# Sidebar
st.sidebar.header("⚙️ Settings")
model_choice = st.sidebar.selectbox(
    "Choose model:",
    ["llama-3.3-70b-versatile", "llama-3.1-8b-instant", "gemma2-9b-it"]
)
voice_mode = st.sidebar.checkbox("🔊 Enable Voice Replies", value=False)
st.sidebar.info(f"API Key Loaded: {'✅ Yes' if GROQ_KEY else '❌ No'}")

# Initialize DB and messages
init_db()
if "messages" not in st.session_state:
    st.session_state.messages = load_messages()
if not st.session_state.messages:
    st.session_state.messages = [{"role": "assistant", "content": "Hello! How can I help you today?"}]

# Display messages
for msg in st.session_state.messages:
    if msg["role"] == "user":
        st.markdown(f"🧑 **You:** {msg['content']}")
    else:
        st.markdown(f"🤖 **Assistant:** {msg['content']}")

# -----------------------------
# INPUT AREA
# -----------------------------
col1, col2, col3 = st.columns([3, 1, 1])
with col1:
    user_input = st.text_input("💬 Type your message:")
with col2:
    if st.button("🎙️ Speak"):
        spoken_text = recognize_voice()
        if spoken_text:
            user_input = spoken_text
with col3:
    uploaded_file = st.file_uploader("📄 Upload", type=["pdf", "txt"])

# -----------------------------
# HANDLE INPUT
# -----------------------------
if uploaded_file:
    if uploaded_file.type == "application/pdf":
        file_text = extract_text_from_pdf(uploaded_file)
    else:
        file_text = uploaded_file.read().decode("utf-8")
    st.info("📘 File content uploaded, summarizing...")
    user_input = f"Summarize this text:\n{file_text[:4000]}"

if st.button("Send"):
    if not user_input.strip():
        st.warning("Please enter or speak something first!")
    else:
        st.session_state.messages.append({"role": "user", "content": user_input})
        save_message("user", user_input)

        with st.spinner("Thinking..."):
            try:
                response = client.chat.completions.create(
                    model=model_choice,
                    messages=[
                        {"role": "system", "content": "You are a helpful and friendly assistant."},
                        *st.session_state.messages
                    ]
                )
                reply = response.choices[0].message.content
                st.session_state.messages.append({"role": "assistant", "content": reply})
                save_message("assistant", reply)
                if voice_mode:
                    speak_text(reply)
                st.rerun()
            except Exception as e:
                st.error(f"⚠️ Error: {e}")

# -----------------------------
# UTILITIES
# -----------------------------
if st.sidebar.button("🗑️ Clear Chat"):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("DELETE FROM chat_history")
    conn.commit()
    conn.close()
    st.session_state.messages = [{"role": "assistant", "content": "Chat cleared! How can I help now?"}]
    st.rerun()

if st.sidebar.button("💾 Export Chat"):
    chat_text = "\n\n".join([f"{m['role'].upper()}: {m['content']}" for m in st.session_state.messages])
    st.download_button("Download Chat", chat_text, file_name="chat_history.txt")
