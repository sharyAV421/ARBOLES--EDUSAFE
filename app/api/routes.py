"""REST endpoints for scenarios and decision sessions."""

from fastapi import APIRouter, HTTPException, Request
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, StrictBool

from app.services.decision_service import DecisionService
from app.tree.decision_tree import DecisionNode, TerminalNode

router = APIRouter(prefix="/api")


class StrictRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")


class StartRequest(StrictRequest):
    scenario_id: str = Field(min_length=1, max_length=100)


class AnswerRequest(StrictRequest):
    answer: StrictBool


class ScenarioResponse(BaseModel):
    id: str
    title: str
    description: str


class ScenarioListResponse(BaseModel):
    scenarios: list[ScenarioResponse]


class TreeNodeResponse(BaseModel):
    id: str
    type: Literal["decision", "terminal"]
    label: str
    yes: str | None = None
    no: str | None = None


class TreeResponse(BaseModel):
    scenario_id: str
    root_id: str
    nodes: list[TreeNodeResponse]


class ProtocolResponse(BaseModel):
    id: str
    title: str
    scenario_id: str
    instructions: list[str]
    version: str
    approval_status: Literal["approved", "unapproved"]
    approving_authority: str | None
    review_date: str | None


class AnswerOptionResponse(BaseModel):
    value: bool
    label: str


class SessionResponse(BaseModel):
    session_id: str
    scenario_id: str
    current_node_id: str
    path: list[str]
    completed: bool
    question: str | None = None
    answers: list[AnswerOptionResponse] | None = None
    protocol: ProtocolResponse | None = None


def service(request: Request) -> DecisionService:
    return request.app.state.decision_service


@router.get("/scenarios", response_model=ScenarioListResponse)
def list_scenarios(request: Request):
    configured = service(request).scenarios
    return {"scenarios": [{"id": item.id, "title": item.title, "description": item.description}
                           for item in configured.scenarios.values()]}


@router.get("/scenarios/{scenario_id}/tree", response_model=TreeResponse)
def get_tree(scenario_id: str, request: Request):
    configured = service(request).scenarios
    if scenario_id not in configured.scenarios:
        raise HTTPException(404, "Escenario no encontrado.")
    tree = configured.trees[scenario_id]
    nodes = []
    for node in tree.preorder():
        if isinstance(node, DecisionNode):
            nodes.append({"id": node.id, "type": "decision", "label": node.question,
                          "yes": node.yes_child.id if node.yes_child else None,
                          "no": node.no_child.id if node.no_child else None})
        else:
            nodes.append({"id": node.id, "type": "terminal", "label": node.protocol.title})
    return {"scenario_id": scenario_id, "root_id": tree.root.id, "nodes": nodes}


@router.post("/sessions", status_code=201, response_model=SessionResponse)
def start_session(body: StartRequest, request: Request):
    try:
        session = service(request).start(body.scenario_id)
    except KeyError:
        raise HTTPException(404, "Escenario no encontrado.") from None
    return service(request).state(session)


@router.get("/sessions/{session_id}", response_model=SessionResponse)
def get_session(session_id: str, request: Request):
    try:
        session = service(request).get_session(session_id)
    except KeyError:
        raise HTTPException(404, "Sesión no encontrada.") from None
    return service(request).state(session)


@router.post("/sessions/{session_id}/answers", response_model=SessionResponse)
def submit_answer(session_id: str, body: AnswerRequest, request: Request):
    try:
        session = service(request).answer(session_id, body.answer)
    except KeyError:
        raise HTTPException(404, "Sesión no encontrada.") from None
    except ValueError as error:
        raise HTTPException(409, "La sesión ya está completa.") from error
    return service(request).state(session)


@router.post("/sessions/{session_id}/reset", response_model=SessionResponse)
def reset_session(session_id: str, request: Request):
    try:
        session = service(request).reset(session_id)
    except KeyError:
        raise HTTPException(404, "Sesión no encontrada.") from None
    return service(request).state(session)
