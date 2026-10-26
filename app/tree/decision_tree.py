"""Reference-based binary decision tree and configuration validation."""

from dataclasses import dataclass
from typing import Iterator

from app.models.configuration import ScenarioConfig


class TreeConfigurationError(ValueError):
    """Raised when a configured tree is malformed or unsafe to load."""


@dataclass
class TerminalProtocol:
    id: str
    title: str
    scenario_id: str
    instructions: list[str]
    version: str
    approval_status: str
    approving_authority: str | None
    review_date: str | None


@dataclass
class DecisionNode:
    id: str
    question: str
    yes_child: "TreeNode | None" = None
    no_child: "TreeNode | None" = None


@dataclass
class TerminalNode:
    id: str
    protocol: TerminalProtocol


TreeNode = DecisionNode | TerminalNode


class DecisionTree:
    """A binary tree whose node links represent configured decisions."""

    def __init__(self, root: TreeNode, nodes: dict[str, TreeNode]):
        self.root = root
        self._nodes = nodes

    @classmethod
    def from_config(cls, config: ScenarioConfig) -> "DecisionTree":
        node_configs = {item.id: item for item in config.nodes}
        if len(node_configs) != len(config.nodes):
            raise TreeConfigurationError("Duplicate node identifiers")
        protocols = {item.id: item for item in config.protocols}
        if len(protocols) != len(config.protocols):
            raise TreeConfigurationError("Duplicate protocol identifiers")
        for protocol in config.protocols:
            if protocol.scenario_id != config.id:
                raise TreeConfigurationError("Protocol scenario reference does not match")
        if config.root_id not in node_configs:
            raise TreeConfigurationError("Root node reference is invalid")
        for node in config.nodes:
            if node.type == "decision":
                for target in (node.yes, node.no):
                    if target not in node_configs:
                        raise TreeConfigurationError("Decision node contains an invalid branch reference")
            elif node.protocol_id not in protocols:
                raise TreeConfigurationError("Terminal node contains an invalid protocol reference")

        built: dict[str, TreeNode] = {}
        for item in config.nodes:
            if item.type == "decision":
                built[item.id] = DecisionNode(item.id, item.question or "")
            else:
                protocol = protocols[item.protocol_id]
                built[item.id] = TerminalNode(item.id, TerminalProtocol(
                    id=protocol.id, title=protocol.title, scenario_id=protocol.scenario_id,
                    instructions=protocol.instructions.copy(), version=protocol.version,
                    approval_status=protocol.approval_status,
                    approving_authority=protocol.approving_authority,
                    review_date=protocol.review_date.isoformat() if protocol.review_date else None,
                ))
        for item in config.nodes:
            if item.type == "decision":
                node = built[item.id]
                assert isinstance(node, DecisionNode)
                node.yes_child = built[item.yes]
                node.no_child = built[item.no]
        root = built[config.root_id]
        cls._validate_graph(root, built)
        return cls(root, built)

    @staticmethod
    def _validate_graph(root: TreeNode, nodes: dict[str, TreeNode]) -> None:
        colors: dict[str, int] = {}
        reached: set[str] = set()
        stack: list[tuple[TreeNode, bool]] = [(root, False)]
        while stack:
            node, leaving = stack.pop()
            if leaving:
                colors[node.id] = 2
                continue
            color = colors.get(node.id, 0)
            if color == 1:
                raise TreeConfigurationError("Cycle detected in decision tree")
            if color == 2:
                continue
            colors[node.id] = 1
            reached.add(node.id)
            if isinstance(node, DecisionNode):
                if node.yes_child is None or node.no_child is None:
                    raise TreeConfigurationError("Decision node has a missing branch")
            stack.append((node, True))
            if isinstance(node, DecisionNode):
                stack.append((node.no_child, False))
                stack.append((node.yes_child, False))
        if reached != set(nodes):
            raise TreeConfigurationError("Configuration contains nodes unreachable from the root")
        parent_counts = {node_id: 0 for node_id in nodes}
        for node in nodes.values():
            if isinstance(node, DecisionNode):
                parent_counts[node.yes_child.id] += 1
                parent_counts[node.no_child.id] += 1
        if parent_counts[root.id] != 0 or any(
            count != 1 for node_id, count in parent_counts.items() if node_id != root.id
        ):
            raise TreeConfigurationError("Configuration does not form a binary tree")

    def find_node(self, node_id: str) -> TreeNode | None:
        """Find a configured node by identifier in O(1) expected time."""
        return self._nodes.get(node_id)

    def preorder(self) -> Iterator[TreeNode]:
        """Yield nodes in preorder, visiting shared references once."""
        seen: set[str] = set()
        stack = [self.root]
        while stack:
            node = stack.pop()
            if node.id in seen:
                continue
            seen.add(node.id)
            yield node
            if isinstance(node, DecisionNode):
                if node.no_child is not None:
                    stack.append(node.no_child)
                if node.yes_child is not None:
                    stack.append(node.yes_child)

    def follow(self, node: DecisionNode, answer: bool) -> TreeNode:
        """Follow a yes/no reference and reject incomplete branches."""
        if type(answer) is not bool:
            raise ValueError("Answer must be a boolean")
        child = node.yes_child if answer else node.no_child
        if child is None:
            raise TreeConfigurationError("Decision node has a missing branch")
        return child

    def evaluate(self, answers: list[bool]) -> TerminalProtocol:
        """Evaluate answers from the root and return the reached protocol."""
        node = self.root
        for answer in answers:
            if isinstance(node, TerminalNode):
                raise ValueError("Answers continue beyond a terminal node")
            node = self.follow(node, answer)
        if not isinstance(node, TerminalNode):
            raise ValueError("Decision path did not reach a terminal node")
        return node.protocol
