import os
import re
from typing import List

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from dotenv import load_dotenv

from langchain_core.messages import HumanMessage, AIMessage, ToolMessage
from agent import get_agent

load_dotenv()

app = FastAPI(title="Google Drive AI Assistant", version="1.0.0")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_credentials=True, allow_methods=["*"], allow_headers=["*"])


class Message(BaseModel):
    role: str
    content: str

class ChatRequest(BaseModel):
    message: str
    history: List[Message] = []

class ChatResponse(BaseModel):
    response: str
    status: str = "ok"


def build_messages(history, new_message):
    messages = []
    for h in history:
        if h.role == "user":
            messages.append(HumanMessage(content=h.content))
        elif h.role == "assistant":
            messages.append(AIMessage(content=h.content))
    messages.append(HumanMessage(content=new_message))
    return messages


def format_tool_output(raw: str) -> str:
    """Convert pipe-separated plain text into nice markdown for the UI."""
    lines = raw.strip().split("\n")
    result = []
    for line in lines:
        if line.startswith("Found ") or line.startswith("No files") or line.startswith("Error"):
            result.append(f"**{line}**\n")
        elif line.startswith("- "):
            parts = line[2:].split(" | ")
            if len(parts) >= 4:
                name = parts[0]
                ftype = parts[1]
                # find size part
                size = ""
                modified = ""
                link = ""
                for p in parts[1:]:
                    if "KB" in p or "MB" in p:
                        size = p
                    elif p.startswith("Modified:"):
                        modified = p.replace("Modified: ", "").strip()
                    elif p.startswith("Link:"):
                        link = p.replace("Link: ", "").strip()
                size_str = f" · {size}" if size else ""
                entry = f"📄 **{name}**\n   • {ftype}{size_str} · Modified: {modified}"
                if link:
                    entry += f"\n   • [Open in Drive]({link})"
                result.append(entry)
            else:
                result.append(line)
        else:
            if line.strip():
                result.append(line)
    return "\n\n".join(result)


def extract_tool_outputs(messages) -> str:
    """Extract all tool outputs from message list."""
    outputs = []
    for msg in messages:
        if isinstance(msg, ToolMessage) and isinstance(msg.content, str) and msg.content.strip():
            outputs.append(msg.content.strip())
    return "\n".join(outputs)


def extract_response(result: dict) -> str:
    messages = result.get("messages", [])
    tool_output = extract_tool_outputs(messages)
    if tool_output:
        return format_tool_output(tool_output)
    # fallback: last AI message
    for msg in reversed(messages):
        if isinstance(msg, AIMessage):
            c = msg.content
            if isinstance(c, str) and c.strip():
                return c.strip()
    return "No results found."


@app.get("/")
def root():
    return {"message": "Google Drive AI Assistant API is running"}

@app.get("/health")
def health():
    return {
        "status": "ok",
        "gdrive_folder_configured": bool(os.getenv("GDRIVE_FOLDER_ID")),
        "llm_api_key_configured": bool(os.getenv("GROQ_API_KEY") or os.getenv("GOOGLE_API_KEY")),
    }

@app.post("/chat", response_model=ChatResponse)
async def chat(request: ChatRequest):
    try:
        agent = get_agent()
        messages = build_messages(request.history, request.message)

        collected_messages = []
        try:
            result = agent.invoke({"messages": messages})
            collected_messages = result.get("messages", [])
        except Exception as agent_err:
            err_str = str(agent_err)
            if "tool_use_failed" in err_str or "Failed to call a function" in err_str:
                import re
                from drive_tool import list_all_files, search_drive_files
                user_msg = request.message.lower()
                try:
                    if any(w in user_msg for w in ["all files", "everything", "show me all", "list all"]):
                        raw = list_all_files.invoke({"max_results": 50})
                    elif "pdf" in user_msg:
                        raw = search_drive_files.invoke({"query": "mimeType = 'application/pdf'"})
                    elif "sheet" in user_msg:
                        raw = search_drive_files.invoke({"query": "mimeType = 'application/vnd.google-apps.spreadsheet'"})
                    elif "doc" in user_msg:
                        raw = search_drive_files.invoke({"query": "mimeType = 'application/vnd.google-apps.document'"})
                    elif "image" in user_msg or "photo" in user_msg or "png" in user_msg or "jpg" in user_msg:
                        raw = search_drive_files.invoke({"query": "mimeType = 'image/jpeg' or mimeType = 'image/png'"})
                    elif "slide" in user_msg or "presentation" in user_msg:
                        raw = search_drive_files.invoke({"query": "mimeType = 'application/vnd.google-apps.presentation'"})
                    else:
                        words = [w for w in user_msg.split() if len(w) > 3 and w not in ["find","show","files","from","that","with","the","this","year","month","modified","after"]]
                        if words:
                            keyword = words[0]
                            raw = search_drive_files.invoke({"query": f"name contains '{keyword}'"})
                        else:
                            raw = list_all_files.invoke({"max_results": 50})
                    return ChatResponse(response=format_tool_output(raw))
                except Exception as fallback_err:
                    raise HTTPException(status_code=500, detail=f"Fallback also failed: {str(fallback_err)}")
            else:
                raise

        response = extract_response({"messages": collected_messages})
        return ChatResponse(response=response)

    except HTTPException:
        raise
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)