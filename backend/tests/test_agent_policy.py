from app.agent_models import AgentToolPolicyMode
from app.agent_tools import ToolDefinition, ToolRisk, policy_valid_for_tool
from app.permissions import Permission


def test_read_tool_accepts_only_read_or_deny() -> None:
    tool = ToolDefinition(
        name="test.read",
        risk=ToolRisk.READ,
        required_permission=Permission.RESOURCE_READ,
        replay_safe=True,
    )
    assert policy_valid_for_tool(tool, AgentToolPolicyMode.READ)
    assert policy_valid_for_tool(tool, AgentToolPolicyMode.DENY)
    assert not policy_valid_for_tool(tool, AgentToolPolicyMode.ACT)
    assert not policy_valid_for_tool(tool, AgentToolPolicyMode.ACT_WITH_APPROVAL)


def test_normal_action_supports_direct_or_approval_modes() -> None:
    tool = ToolDefinition(
        name="test.action",
        risk=ToolRisk.ACTION,
        required_permission=Permission.RESOURCE_WRITE,
        replay_safe=True,
    )
    assert policy_valid_for_tool(tool, AgentToolPolicyMode.ACT)
    assert policy_valid_for_tool(tool, AgentToolPolicyMode.ACT_WITH_APPROVAL)
    assert policy_valid_for_tool(tool, AgentToolPolicyMode.DENY)
    assert not policy_valid_for_tool(tool, AgentToolPolicyMode.READ)


def test_high_risk_action_cannot_use_direct_act() -> None:
    tool = ToolDefinition(
        name="test.high-risk",
        risk=ToolRisk.HIGH_RISK_ACTION,
        required_permission=Permission.RESOURCE_WRITE,
        replay_safe=True,
    )
    assert policy_valid_for_tool(tool, AgentToolPolicyMode.ACT_WITH_APPROVAL)
    assert policy_valid_for_tool(tool, AgentToolPolicyMode.DENY)
    assert not policy_valid_for_tool(tool, AgentToolPolicyMode.ACT)
    assert not policy_valid_for_tool(tool, AgentToolPolicyMode.READ)
