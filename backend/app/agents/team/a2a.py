"""
A2A-shaped hand-offs between the team's manager and its specialists, run in process.

This follows the data model of the Agent2Agent (A2A) protocol. MCP connects an agent to tools; A2A connects an
agent to other agents:
- Each specialist publishes an AgentCard: its name, what it does and the skills it offers. The manager reads the
  cards to decide who gets which part of a question (discovery).
- Work is handed over as a message (`message/send`). The receiving agent creates a Task that moves through the
  lifecycle submitted -> working -> completed | failed, and returns its output as artifacts.
- Messages and artifacts carry parts: {"kind": "text", "text": ...} or {"kind": "data", "data": {...}}.

The agents run in this process so network hops do not distort the latency being measured. The same cards and
tasks could be served over HTTP (JSON-RPC) without changing the agents.
"""
import time
import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Protocol

PROTOCOL_VERSION = "0.3.0"  # the A2A spec version whose field names these objects use


@dataclass
class AgentSkill:
    id: str
    name: str
    description: str
    tags: List[str] = field(default_factory=list)
    examples: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {"id": self.id, "name": self.name, "description": self.description, "tags": self.tags, "examples": self.examples}


@dataclass
class AgentCard:
    name: str
    description: str
    skills: List[AgentSkill]
    version: str = "1.0.0"
    url: str = "local://docs-team"
    default_input_modes: List[str] = field(default_factory=lambda: ["text/plain"])
    default_output_modes: List[str] = field(default_factory=lambda: ["application/json"])

    def to_dict(self) -> Dict[str, Any]:
        return {
            "protocolVersion": PROTOCOL_VERSION,
            "name": self.name,
            "description": self.description,
            "url": self.url,
            "version": self.version,
            "capabilities": {"streaming": False, "pushNotifications": False},
            "defaultInputModes": self.default_input_modes,
            "defaultOutputModes": self.default_output_modes,
            "skills": [s.to_dict() for s in self.skills],
        }


class TaskState(str, Enum):
    SUBMITTED = "submitted"
    WORKING = "working"
    INPUT_REQUIRED = "input-required"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELED = "canceled"


@dataclass
class Message:
    role: str  # "user" (the sender) or "agent" (the receiver replying)
    parts: List[Dict[str, Any]]
    message_id: str = field(default_factory=lambda: uuid.uuid4().hex)

    @classmethod
    def build(cls, role: str, text: str, data: Optional[Dict[str, Any]] = None) -> "Message":
        parts: List[Dict[str, Any]] = [{"kind": "text", "text": text}]
        if data:
            parts.append({"kind": "data", "data": data})
        return cls(role=role, parts=parts)

    @property
    def text(self) -> str:
        return "\n".join(p["text"] for p in self.parts if p.get("kind") == "text")

    @property
    def data(self) -> Dict[str, Any]:
        merged: Dict[str, Any] = {}
        for p in self.parts:
            if p.get("kind") == "data":
                merged.update(p.get("data") or {})
        return merged

    def to_dict(self) -> Dict[str, Any]:
        return {"kind": "message", "messageId": self.message_id, "role": self.role, "parts": self.parts}


@dataclass
class Task:
    context_id: str
    history: List[Message]
    id: str = field(default_factory=lambda: uuid.uuid4().hex)
    state: TaskState = TaskState.SUBMITTED
    status_message: str = ""
    artifacts: List[Dict[str, Any]] = field(default_factory=list)
    transitions: List[Dict[str, Any]] = field(default_factory=list)
    error_type: str = ""  # exception class name when the task failed

    def __post_init__(self):
        self._mark(self.state)

    def _mark(self, state: TaskState, message: str = "") -> None:
        self.state = state
        self.status_message = message
        self.transitions.append({"state": state.value, "timestamp": time.time()})

    def add_artifact(self, name: str, data: Dict[str, Any]) -> None:
        self.artifacts.append({"artifactId": uuid.uuid4().hex, "name": name, "parts": [{"kind": "data", "data": data}]})

    def artifact(self, name: str) -> Dict[str, Any]:
        for a in self.artifacts:
            if a["name"] == name:
                return a["parts"][0]["data"]
        return {}

    @property
    def duration_ms(self) -> float:
        return (self.transitions[-1]["timestamp"] - self.transitions[0]["timestamp"]) * 1000 if self.transitions else 0.0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "kind": "task",
            "id": self.id,
            "contextId": self.context_id,
            "status": {"state": self.state.value, "message": self.status_message},
            "history": [m.to_dict() for m in self.history],
            "artifacts": self.artifacts,
            "transitions": self.transitions,
        }


class A2AAgent(Protocol):
    card: AgentCard

    def handle(self, task: Task) -> None:
        """Do the work for task (its last history message is the request) and add the output as artifacts."""


def send_message(agent: A2AAgent, message: Message, context_id: str) -> Task:
    """`message/send`: hand a message to an agent and return the finished task. A failure inside the agent
    ends the task as failed (with the error as its status message) instead of raising, as a remote agent would."""
    task = Task(context_id=context_id, history=[message])
    task._mark(TaskState.WORKING)
    try:
        agent.handle(task)
    except Exception as err:
        task.error_type = type(err).__name__
        task._mark(TaskState.FAILED, f"{type(err).__name__}: {err}")
        return task
    task._mark(TaskState.COMPLETED)
    return task
