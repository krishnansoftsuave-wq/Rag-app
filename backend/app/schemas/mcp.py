from typing import Any, Dict, Optional
from pydantic import BaseModel


class AddServerRequest(BaseModel):
    name: str
    url: str
    description: Optional[str] = ""  # what the server is for; used to decide when a question needs it
    transport: Optional[str] = "sse"
    auth_type: Optional[str] = "none"
    auth_token: Optional[str] = ""


class TestConnectionRequest(BaseModel):
    url: str
    transport: Optional[str] = "sse"
    auth_type: Optional[str] = "none"
    auth_token: Optional[str] = ""


class CallToolRequest(BaseModel):
    server_id: str
    tool_name: str
    arguments: Optional[Dict[str, Any]] = {}
