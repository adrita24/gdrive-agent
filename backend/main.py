import os
import time
import uuid
import traceback
from typing import List

from fastapi import FastAPI, HTTPException, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from dotenv import load_dotenv

from langchain_core.messages import HumanMessage, AIMessage, ToolMessage

from agent import get_agent
from logger import log, log_request, log_response, log_chat, log_error, log_agent_tool_call

load_dotenv()

# ---------------------------------------------------------------------------
# App
# ---------------------------------------------------------------------------

app = FastAPI(title="Google Drive AI Assistant", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ---------------------------------------------------------------------------
# Logging middleware — fires for EVERY request
# ---------------------------------------------------------------------------

@app.middleware("http")
async def logging_middleware(request: Request, call_next):
    request_id = str(uuid.uuid4())[:8]          # short 8-char id
    request.state.request_id = request_id       # make available to routes

    # read body size without consuming the stream
    body = await request.body()
    body_size = len(body)

    log_request(
        request_id=request_id,
        path=request.url.path,
        method=request.method,
        client_ip=request.headers.get("x-forwarded-for", request.client.host if request.client else "unknown"),
        user_agent=request.headers.get("user-agent", ""),
        body_size=body_size,
    )

    t0 = time.perf_counter()
    try:
        response: Response = await call_next(request)
    except Exception as exc:
        log_error(
            request_id=request_id,
            path=request.url.path,
            error_type=type(exc).__name__,
            detail=str(exc),
        )
        raise

    duration_ms = (time.perf_counter() - t0) * 1000
    log_response(
        request_id=request_id,
        path=request.url.path,
        status_code=response.status_code,
        duration_ms=duration_ms,
    )
    # attach request-id to every response header for easy tracing
    response.headers["X-Request-Id"] = request_id
    return response


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------

class Message(BaseModel):
    role: str
    content: str

class ChatRequest(BaseModel):
    message: str
    history: List[Message] = []

class ChatResponse(BaseModel):
    response: str
    status: str = "ok"
    request_id: str = ""


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

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
                size = modified = link = ""
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
    outputs = []
    for msg in messages:
        if isinstance(msg, ToolMessage) and isinstance(msg.content, str) and msg.content.strip():
            outputs.append(msg.content.strip())
    return "\n".join(outputs)


def extract_response(result: dict) -> tuple[str, bool]:
    """Returns (response_text, agent_used_tool)."""
    messages = result.get("messages", [])
    tool_output = extract_tool_outputs(messages)
    if tool_output:
        return format_tool_output(tool_output), True
    for msg in reversed(messages):
        if isinstance(msg, AIMessage):
            c = msg.content
            if isinstance(c, str) and c.strip():
                return c.strip(), False
    return "No results found.", False


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

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
async def chat(request: ChatRequest, http_request: Request):
    request_id = getattr(http_request.state, "request_id", "unknown")
    t0 = time.perf_counter()
    fallback_used = False

    try:
        agent = get_agent()
        messages = build_messages(request.history, request.message)

        try:
            result = agent.invoke({"messages": messages})
            collected_messages = result.get("messages", [])

            # log each tool call the agent made
            for msg in collected_messages:
                if isinstance(msg, AIMessage) and hasattr(msg, "tool_calls") and msg.tool_calls:
                    for tc in msg.tool_calls:
                        log_agent_tool_call(
                            request_id=request_id,
                            tool_name=tc.get("name", "unknown"),
                            query=str(tc.get("args", "")),
                        )

            response_text, agent_used_tool = extract_response({"messages": collected_messages})

        except Exception as agent_err:
            err_str = str(agent_err)
            if "tool_use_failed" in err_str or "Failed to call a function" in err_str:
                from drive_tool import list_all_files, search_drive_files
                user_msg = request.message.lower()
                fallback_used = True

                if any(w in user_msg for w in ["all files", "everything", "show me all", "list all"]):
                    raw = list_all_files.invoke({"max_results": 50})
                    log_agent_tool_call(request_id=request_id, tool_name="list_all_files(fallback)", query="max_results=50")
                elif "pdf" in user_msg:
                    raw = search_drive_files.invoke({"query": "mimeType = 'application/pdf'"})
                    log_agent_tool_call(request_id=request_id, tool_name="search_drive_files(fallback)", query="pdf")
                elif "sheet" in user_msg:
                    raw = search_drive_files.invoke({"query": "mimeType = 'application/vnd.google-apps.spreadsheet'"})
                    log_agent_tool_call(request_id=request_id, tool_name="search_drive_files(fallback)", query="sheet")
                elif "doc" in user_msg:
                    raw = search_drive_files.invoke({"query": "mimeType = 'application/vnd.google-apps.document'"})
                    log_agent_tool_call(request_id=request_id, tool_name="search_drive_files(fallback)", query="doc")
                elif "image" in user_msg or "photo" in user_msg or "png" in user_msg or "jpg" in user_msg:
                    raw = search_drive_files.invoke({"query": "mimeType = 'image/jpeg' or mimeType = 'image/png'"})
                    log_agent_tool_call(request_id=request_id, tool_name="search_drive_files(fallback)", query="image")
                elif "slide" in user_msg or "presentation" in user_msg:
                    raw = search_drive_files.invoke({"query": "mimeType = 'application/vnd.google-apps.presentation'"})
                    log_agent_tool_call(request_id=request_id, tool_name="search_drive_files(fallback)", query="slide")
                else:
                    words = [w for w in user_msg.split() if len(w) > 3 and w not in [
                        "find", "show", "files", "from", "that", "with", "the", "this",
                        "year", "month", "modified", "after",
                    ]]
                    if words:
                        keyword = words[0]
                        raw = search_drive_files.invoke({"query": f"name contains '{keyword}'"})
                        log_agent_tool_call(request_id=request_id, tool_name="search_drive_files(fallback)", query=keyword)
                    else:
                        raw = list_all_files.invoke({"max_results": 50})
                        log_agent_tool_call(request_id=request_id, tool_name="list_all_files(fallback)", query="generic")

                response_text = format_tool_output(raw)
                agent_used_tool = True
            else:
                raise

        duration_ms = (time.perf_counter() - t0) * 1000
        log_chat(
            request_id=request_id,
            user_message=request.message,
            history_len=len(request.history),
            response_preview=response_text,
            agent_used_tool=agent_used_tool,
            fallback_used=fallback_used,
            duration_ms=duration_ms,
        )

        return ChatResponse(response=response_text, request_id=request_id)

    except HTTPException:
        raise
    except Exception as e:
        traceback.print_exc()
        log_error(
            request_id=request_id,
            path="/chat",
            error_type=type(e).__name__,
            detail=str(e),
        )
        raise HTTPException(status_code=500, detail=str(e))


# ---------------------------------------------------------------------------
# Render entry-point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", 8000))     # Render injects $PORT automatically
    uvicorn.run("main:app", host="0.0.0.0", port=port, reload=False)
