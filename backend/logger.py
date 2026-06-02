import json
import logging
import sys
import time
import uuid
from datetime import datetime, timezone

# ---------------------------------------------------------------------------
# JSON formatter — every log line is a valid JSON object
# ---------------------------------------------------------------------------

class JSONFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        base = {
            "ts": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "msg": record.getMessage(),
        }
        # merge any extra dict payload attached with logger.info("...", extra={"data": {...}})
        if hasattr(record, "data") and isinstance(record.data, dict):
            base.update(record.data)
        if record.exc_info:
            base["exc"] = self.formatException(record.exc_info)
        return json.dumps(base, default=str)


def get_logger(name: str = "gdrive_assistant") -> logging.Logger:
    logger = logging.getLogger(name)
    if logger.handlers:          # avoid duplicate handlers on reload
        return logger
    logger.setLevel(logging.DEBUG)
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(JSONFormatter())
    logger.addHandler(handler)
    logger.propagate = False
    return logger


# Singleton used throughout the app
log = get_logger()


# ---------------------------------------------------------------------------
# Activity helpers — call these from your route/agent code
# ---------------------------------------------------------------------------

def log_request(
    *,
    request_id: str,
    path: str,
    method: str,
    client_ip: str,
    user_agent: str,
    body_size: int,
) -> None:
    log.info("http_request", extra={"data": {
        "event": "http_request",
        "request_id": request_id,
        "path": path,
        "method": method,
        "client_ip": client_ip,
        "user_agent": user_agent,
        "body_size_bytes": body_size,
    }})


def log_response(
    *,
    request_id: str,
    path: str,
    status_code: int,
    duration_ms: float,
) -> None:
    level = logging.WARNING if status_code >= 400 else logging.INFO
    log.log(level, "http_response", extra={"data": {
        "event": "http_response",
        "request_id": request_id,
        "path": path,
        "status_code": status_code,
        "duration_ms": round(duration_ms, 2),
    }})


def log_chat(
    *,
    request_id: str,
    user_message: str,
    history_len: int,
    response_preview: str,
    agent_used_tool: bool,
    fallback_used: bool,
    duration_ms: float,
) -> None:
    log.info("chat_turn", extra={"data": {
        "event": "chat_turn",
        "request_id": request_id,
        "user_message_preview": user_message[:120],
        "history_turns": history_len,
        "response_preview": response_preview[:120],
        "agent_used_tool": agent_used_tool,
        "fallback_used": fallback_used,
        "duration_ms": round(duration_ms, 2),
    }})


def log_agent_tool_call(
    *,
    request_id: str,
    tool_name: str,
    query: str,
) -> None:
    log.info("agent_tool_call", extra={"data": {
        "event": "agent_tool_call",
        "request_id": request_id,
        "tool_name": tool_name,
        "query_preview": query[:120],
    }})


def log_error(
    *,
    request_id: str,
    path: str,
    error_type: str,
    detail: str,
) -> None:
    log.error("request_error", extra={"data": {
        "event": "request_error",
        "request_id": request_id,
        "path": path,
        "error_type": error_type,
        "detail": detail[:300],
    }})
