import os
from datetime import datetime
from dotenv import load_dotenv
from langchain_groq import ChatGroq
from langgraph.prebuilt import create_react_agent

load_dotenv()

def get_system_prompt():
    today = datetime.now()
    year = today.year
    return f"""You are a Google Drive search assistant. Today is {today.strftime("%Y-%m-%d")}.

RULES:
1. Always call a tool to answer the user's request.
2. After the tool returns results, respond with ONLY a single short plain sentence like "Here are the results." or "Done." 
3. Do NOT repeat file names, links, or any file details in your response.
4. Do NOT use markdown, bullet points, bold, or any special formatting.
5. Never make up file information.

TOOLS:
- list_all_files(): use when user wants to see all files
- search_drive_files(query): use for filtered searches

QUERY EXAMPLES:
- PDFs: mimeType = 'application/pdf'
- Docs: mimeType = 'application/vnd.google-apps.document'
- Sheets: mimeType = 'application/vnd.google-apps.spreadsheet'
- Slides: mimeType = 'application/vnd.google-apps.presentation'
- Images: mimeType = 'image/png' or mimeType = 'image/jpeg'
- By name: name contains 'budget'
- By content: fullText contains 'marketing'
- This year: modifiedTime > '{year}-01-01T00:00:00'
- This month: modifiedTime > '{year}-{today.month:02d}-01T00:00:00'
- Combined: mimeType = 'application/pdf' and modifiedTime > '{year}-01-01T00:00:00'
"""

_agent = None

def create_agent():
    from drive_tool import search_drive_files, list_all_files
    llm = ChatGroq(
        model="meta-llama/llama-4-scout-17b-16e-instruct",
        api_key=os.getenv("GROQ_API_KEY"),
        temperature=0,
    )
    tools = [search_drive_files, list_all_files]
    return create_react_agent(llm, tools, prompt=get_system_prompt())

def get_agent():
    global _agent
    if _agent is None:
        _agent = create_agent()
    return _agent