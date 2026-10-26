"""Scenario loading and in-memory decision session orchestration."""

import json
import secrets
from dataclasses import dataclass, field
from pathlib import Path

from pydantic import ValidationError

from app.models.configuration import ScenarioConfig
from app.tree.decision_tree import DecisionNode, DecisionTree, TerminalNode, TreeConfigurationError


class ScenarioService:
    def __init__(self, scenarios: dict[str, ScenarioConfig]):
        self.scenarios = scenarios
        self.trees = {key: DecisionTree.from_config(value) for key, value in scenarios.items()}

    @classmethod
    def from_directory(cls, directory: Path) -> "ScenarioService":
        scenarios: dict[str, ScenarioConfig] = {}
        for path in sorted(directory.glob("*.json")):
            try:
                config = ScenarioConfig.model_validate_json(path.read_text(encoding="utf-8"))
                if config.id in scenarios:
                    raise TreeConfigurationError("Duplicate scenario identifiers")
                scenarios[config.id] = config
                DecisionTree.from_config(config)
            except (ValidationError, ValueError) as error:
                raise TreeConfigurationError(f"Invalid scenario configuration: {path.name}") from error
        if not scenarios:
            raise TreeConfigurationError("No scenario configurations were found")
        return cls(scenarios)


@dataclass
class DecisionSession:
    id: str
    scenario_id: str
    current_node_id: str
    path: list[str] = field(default_factory=list)
    completed: bool = False
    protocol_node_id: str | None = None


class DecisionService:
    """Evaluate answers against the configured tree and own session state."""

    def __init__(self, scenarios: ScenarioService):
        self.scenarios = scenarios
        self.sessions: dict[str, DecisionSession] = {}

    def start(self, scenario_id: str) -> DecisionSession:
        if scenario_id not in self.scenarios.scenarios:
            raise KeyError("Scenario not found")
        tree = self.scenarios.trees[scenario_id]
        session = DecisionSession(secrets.token_urlsafe(32), scenario_id, tree.root.id)
        self.sessions[session.id] = session
        return session

    def get_session(self, session_id: str) -> DecisionSession:
        if not isinstance(session_id, str) or not 20 <= len(session_id) <= 100:
            raise KeyError("Session not found")
        session = self.sessions.get(session_id)
        if session is None:
            raise KeyError("Session not found")
        return session

    def answer(self, session_id: str, answer: bool) -> DecisionSession:
        session = self.get_session(session_id)
        if session.completed:
            raise ValueError("Session is already complete")
        tree = self.scenarios.trees[session.scenario_id]
        node = tree.find_node(session.current_node_id)
        if not isinstance(node, DecisionNode):
            raise ValueError("Current node cannot accept an answer")
        next_node = tree.follow(node, answer)
        session.path.extend([node.id, next_node.id])
        session.current_node_id = next_node.id
        if isinstance(next_node, TerminalNode):
            session.completed = True
            session.protocol_node_id = next_node.id
        return session

    def reset(self, session_id: str) -> DecisionSession:
        session = self.get_session(session_id)
        root = self.scenarios.trees[session.scenario_id].root
        session.current_node_id = root.id
        session.path.clear()
        session.completed = False
        session.protocol_node_id = None
        return session

    def state(self, session: DecisionSession) -> dict:
        tree = self.scenarios.trees[session.scenario_id]
        node = tree.find_node(session.current_node_id)
        result = {"session_id": session.id, "scenario_id": session.scenario_id,
                  "current_node_id": session.current_node_id, "path": session.path.copy(),
                  "completed": session.completed}
        if isinstance(node, DecisionNode):
            result["question"] = node.question
            result["answers"] = [{"value": True, "label": "Sí"}, {"value": False, "label": "No"}]
        else:
            result["question"] = None
            result["protocol"] = self.protocol_payload(node.protocol)
        return result

    @staticmethod
    def protocol_payload(protocol):
        if protocol.approval_status != "approved":
            return {"id": protocol.id, "title": protocol.title, "scenario_id": protocol.scenario_id,
                    "instructions": ["Demostración de estructura. Este contenido no contiene instrucciones operativas aprobadas. Consulte el protocolo institucional vigente y las indicaciones del personal de emergencia designado."],
                    "version": protocol.version, "approval_status": "unapproved",
                    "approving_authority": None, "review_date": None}
        return {"id": protocol.id, "title": protocol.title, "scenario_id": protocol.scenario_id,
                "instructions": protocol.instructions, "version": protocol.version,
                "approval_status": protocol.approval_status,
                "approving_authority": protocol.approving_authority,
                "review_date": protocol.review_date}
