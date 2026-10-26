"""Decision tree construction, traversal, and validation tests."""

import pytest

from app.models.configuration import NodeConfig, ScenarioConfig
from app.tree.decision_tree import DecisionNode, DecisionTree, TerminalNode, TreeConfigurationError


def scenario(nodes=None, root_id="root"):
    return ScenarioConfig.model_validate({
        "id": "sample", "title": "Sample", "description": "Test data", "root_id": root_id,
        "nodes": nodes or [
            {"id": "root", "type": "decision", "question": "Continue?", "yes": "yes", "no": "no"},
            {"id": "yes", "type": "terminal", "protocol_id": "p1"},
            {"id": "no", "type": "terminal", "protocol_id": "p2"},
        ],
        "protocols": [
            {"id": "p1", "title": "One", "scenario_id": "sample", "instructions": ["Demo"], "version": "1", "approval_status": "unapproved", "approving_authority": None, "review_date": None},
            {"id": "p2", "title": "Two", "scenario_id": "sample", "instructions": ["Demo"], "version": "1", "approval_status": "unapproved", "approving_authority": None, "review_date": None},
        ],
    })


def test_tree_construction_preorder_and_search():
    tree = DecisionTree.from_config(scenario())
    assert isinstance(tree.root, DecisionNode)
    assert tree.root.yes_child is tree.find_node("yes")
    assert tree.root.no_child is tree.find_node("no")
    assert [node.id for node in tree.preorder()] == ["root", "yes", "no"]
    assert tree.find_node("yes").protocol.id == "p1"
    assert tree.find_node("missing") is None


@pytest.mark.parametrize(("answer", "protocol_id"), [(True, "p1"), (False, "p2")])
def test_evaluate_valid_path(answer, protocol_id):
    assert DecisionTree.from_config(scenario()).evaluate([answer]).id == protocol_id


def test_evaluate_requires_terminal_path_and_rejects_extra_answers():
    tree = DecisionTree.from_config(scenario())
    with pytest.raises(ValueError, match="did not reach"):
        tree.evaluate([])
    with pytest.raises(ValueError, match="beyond a terminal"):
        tree.evaluate([True, False])


@pytest.mark.parametrize("answer", ["yes", 1, None])
def test_invalid_answer_is_rejected_by_tree(answer):
    tree = DecisionTree.from_config(scenario())
    with pytest.raises(ValueError, match="must be a boolean"):
        tree.follow(tree.root, answer)
    with pytest.raises(ValueError, match="must be a boolean"):
        tree.evaluate([answer])


def test_missing_branch_detected_when_traversed():
    tree = DecisionTree.from_config(scenario())
    tree.root.yes_child = None
    with pytest.raises(TreeConfigurationError, match="missing branch"):
        tree.follow(tree.root, True)


def test_missing_branch_rejected_in_configuration():
    with pytest.raises(ValueError, match="Decision nodes require"):
        NodeConfig.model_validate({"id": "root", "type": "decision", "question": "Q", "yes": "leaf"})


def test_duplicate_node_identifiers_rejected():
    nodes = [
        {"id": "root", "type": "decision", "question": "Q", "yes": "leaf", "no": "leaf"},
        {"id": "leaf", "type": "terminal", "protocol_id": "p1"},
        {"id": "leaf", "type": "terminal", "protocol_id": "p2"},
    ]
    with pytest.raises(TreeConfigurationError, match="Duplicate node"):
        DecisionTree.from_config(scenario(nodes))


def test_duplicate_protocol_identifiers_rejected():
    config = scenario()
    config.protocols[1].id = config.protocols[0].id
    with pytest.raises(TreeConfigurationError, match="Duplicate protocol"):
        DecisionTree.from_config(config)


def test_invalid_node_or_protocol_reference_rejected():
    nodes = [{"id": "root", "type": "decision", "question": "Q", "yes": "absent", "no": "leaf"},
             {"id": "leaf", "type": "terminal", "protocol_id": "p1"}]
    with pytest.raises(TreeConfigurationError, match="invalid branch"):
        DecisionTree.from_config(scenario(nodes))
    nodes = [{"id": "root", "type": "terminal", "protocol_id": "absent"}]
    with pytest.raises(TreeConfigurationError, match="invalid protocol"):
        DecisionTree.from_config(scenario(nodes))


def test_cycle_rejected():
    nodes = [{"id": "root", "type": "decision", "question": "Q", "yes": "root", "no": "leaf"},
             {"id": "leaf", "type": "terminal", "protocol_id": "p1"}]
    with pytest.raises(TreeConfigurationError, match="Cycle"):
        DecisionTree.from_config(scenario(nodes))


def test_shared_child_rejected_because_configuration_must_be_a_tree():
    nodes = [
        {"id": "root", "type": "decision", "question": "Q", "yes": "left", "no": "right"},
        {"id": "left", "type": "decision", "question": "L?", "yes": "leaf", "no": "leaf"},
        {"id": "right", "type": "terminal", "protocol_id": "p2"},
        {"id": "leaf", "type": "terminal", "protocol_id": "p1"},
    ]
    with pytest.raises(TreeConfigurationError, match="binary tree"):
        DecisionTree.from_config(scenario(nodes))


def test_terminal_protocol_metadata_and_unapproved_status():
    protocol = DecisionTree.from_config(scenario()).evaluate([True])
    assert protocol.id == "p1"
    assert protocol.approval_status == "unapproved"
    assert protocol.approving_authority is None
