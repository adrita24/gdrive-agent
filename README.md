# 🗂️ Google Drive AI Assistant

A conversational AI agent that helps you search and discover files in Google Drive using natural language — powered by **Groq (LLaMA 4)**, **LangGraph**, **FastAPI**, and **Streamlit**.

![Python](https://img.shields.io/badge/Python-3.11-blue)
![FastAPI](https://img.shields.io/badge/FastAPI-0.111-green)
![Streamlit](https://img.shields.io/badge/Streamlit-Latest-red)
![LangGraph](https://img.shields.io/badge/LangGraph-ReAct-orange)

---

## 🔗 Live Demo

| | URL |
|---|---|
| 🎨 **Streamlit App** | https://gdrive-agent.streamlit.app |
| ⚙️ **Backend API** | https://gdrive-agent-backend.onrender.com |
| 💻 **GitHub** | https://github.com/adrita24/gdrive-agent |

> **Note:** Backend is on Render's free tier — first request after 15min idle may take ~30s to wake up.

---

## 🧠 How It Works

```
User (Streamlit UI)
      ↓
FastAPI /chat endpoint
      ↓
LangGraph ReAct Agent
      ↓  ↑
   Groq LLM  ←→  Drive Search Tool
                        ↓
              Google Drive API v3
              (Service Account)
```

1. User types a natural language query like *"find all PDFs modified this year"*
2. FastAPI passes it to the LangGraph ReAct agent
3. The LLM translates it into a Drive API `q` string: `mimeType = 'application/pdf' and modifiedTime > '2026-01-01T00:00:00'`
4. The Drive tool executes the query and returns matching files
5. Results are formatted and displayed in the Streamlit UI with clickable links

---

## ✨ Features

- 🔍 **Search by name** — exact or partial match
- 📁 **Filter by file type** — PDFs, Docs, Sheets, Slides, Images
- 📝 **Search by content** — fullText search inside documents
- 📅 **Filter by date** — this year, this month, after a specific date
- 🔗 **Combined queries** — e.g. "PDFs modified this year with budget in the name"
- 💬 **Conversational** — follow-up queries with memory
- 🔗 **Clickable links** — direct "Open in Drive" links for every result

---

## 🏗️ Project Structure

```
gdrive-agent/
├── backend/
│   ├── main.py          # FastAPI app — /chat and /health endpoints
│   ├── agent.py         # LangGraph ReAct agent with Groq LLM
│   ├── drive_tool.py    # Google Drive search tools (@tool decorated)
│   ├── requirements.txt
│   └── runtime.txt      # Python 3.11 for Render
├── frontend/
│   ├── app.py           # Streamlit chat UI
│   ├── requirements.txt
│   └── .streamlit/
│       └── config.toml  # Light theme config
└── README.md
```

---

## 🛠️ Tech Stack

| Layer | Technology |
|---|---|
| LLM | Groq — `meta-llama/llama-4-scout-17b-16e-instruct` |
| Agent Framework | LangGraph (ReAct) |
| Drive Integration | Google Drive API v3 (Service Account) |
| Backend | FastAPI + Uvicorn |
| Frontend | Streamlit |
| Backend Hosting | Render |
| Frontend Hosting | Streamlit Cloud |

---

## 🚀 Local Setup

### 1. Clone the repo

```bash
git clone https://github.com/adrita24/gdrive-agent.git
cd gdrive-agent
```

### 2. Google Cloud Setup

1. Create a project at [console.cloud.google.com](https://console.cloud.google.com)
2. Enable **Google Drive API**
3. Create a **Service Account** → download the JSON key
4. Save as `backend/credentials/service_account.json`
5. Share the Drive folder with the service account email (Viewer access)

### 3. Get API Keys

- **Groq API Key:** [console.groq.com](https://console.groq.com)

### 4. Configure Environment

Create `backend/.env`:
```env
GROQ_API_KEY=your_groq_api_key
GDRIVE_FOLDER_ID=1qkx58doSeYrcLjHPDysJyVJ36PsSqqlt
SERVICE_ACCOUNT_FILE=credentials/service_account.json
```

### 5. Run Backend

```bash
cd backend
python -m venv venv
venv\Scripts\activate        # Windows
pip install -r requirements.txt
uvicorn main:app --reload --port 8000
```

### 6. Run Frontend

```bash
cd frontend
pip install -r requirements.txt
streamlit run app.py
```

Open http://localhost:8501

---

## 📡 API Reference

### `POST /chat`

```json
{
  "message": "find all PDFs modified this year",
  "history": []
}
```

**Response:**
```json
{
  "response": "Found 4 file(s):\n...",
  "status": "ok"
}
```

### `GET /health`

```json
{
  "status": "ok",
  "gdrive_folder_configured": true,
  "llm_api_key_configured": true
}
```

---

## 🔍 Drive Query Examples

| User says | Agent queries |
|---|---|
| "show me all files" | `list_all_files()` |
| "find all PDFs" | `mimeType = 'application/pdf'` |
| "find files named budget" | `name contains 'budget'` |
| "find files about marketing" | `fullText contains 'marketing'` |
| "files modified this year" | `modifiedTime > '2026-01-01T00:00:00'` |
| "PDFs from this month" | `mimeType = 'application/pdf' and modifiedTime > '2026-05-01T00:00:00'` |

---

## ☁️ Deployment

### Backend → Render

1. Connect GitHub repo on [render.com](https://render.com)
2. Root directory: `backend`
3. Start command: `uvicorn main:app --host 0.0.0.0 --port $PORT`
4. Environment variables:
   - `GROQ_API_KEY`
   - `GDRIVE_FOLDER_ID`
   - `SERVICE_ACCOUNT_JSON` ← paste full contents of service_account.json

### Frontend → Streamlit Cloud

1. Connect GitHub repo on [share.streamlit.io](https://share.streamlit.io)
2. Main file: `frontend/app.py`
3. Secrets:
```toml
BACKEND_URL = "https://your-backend.onrender.com"
```

---

## 📄 License

MIT
