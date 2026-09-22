"""
SERA 2.0 — Stateful Graph Runtime Package.
"""

from __future__ import annotations

from typing import Any, Dict, Optional

from app.core.events import EventBus
from app.core.graph.control import ErrorCategory, GraphDecision, NodeResult
from app.core.graph.engine import StatefulGraphRuntime
from app.core.graph.node import GraphNode
from app.core.graph.nodes.context import ContextNode
from app.core.graph.nodes.decide import DecideNode
from app.core.graph.nodes.execute import ExecuteNode
from app.core.graph.nodes.normalize import NormalizeNode
from app.core.graph.nodes.observe import ObserveNode
from app.core.graph.nodes.perceive import PerceiveNode
from app.core.graph.nodes.plan import PlanNode
from app.core.graph.nodes.recover import RecoverNode
from app.core.graph.nodes.respond import RespondNode
from app.core.graph.nodes.route import RouteNode
from app.core.graph.nodes.verify import VerifyNode
from app.core.graph.state import (
    GraphExecutionStatus,
    GraphObservation,
    GraphPlanStep,
    GraphState,
    GraphVerification,
)
from app.core.router import ModelRouter
from app.core.verification import EvidenceVerificationFabric
from app.tools.registry import ToolRegistry


def create_default_graph_runtime(
    tools: ToolRegistry,
    router: Optional[ModelRouter] = None,
    event_bus: Optional[EventBus] = None,
    fabric: Optional[EvidenceVerificationFabric] = None,
    context_provider: Optional[Dict[str, Any]] = None,
    max_loop_iterations: int = 50,
    max_retries_per_step: int = 2,
) -> StatefulGraphRuntime:
    """Constructs and returns the canonical SERA Stateful Graph Runtime."""
    engine = StatefulGraphRuntime(
        event_bus=event_bus,
        max_loop_iterations=max_loop_iterations,
        max_retries_per_step=max_retries_per_step,
    )

    # 1. Register Core Nodes
    engine.register_node(PerceiveNode())
    engine.register_node(NormalizeNode())
    engine.register_node(ContextNode(context_provider=context_provider))
    engine.register_node(RouteNode())
    engine.register_node(PlanNode(router=router, tools=tools))
    engine.register_node(ExecuteNode(tools=tools))
    engine.register_node(ObserveNode())
    engine.register_node(VerifyNode(fabric=fabric))
    engine.register_node(DecideNode())
    engine.register_node(RecoverNode())
    engine.register_node(RespondNode())

    # 2. Directed Edges
    engine.add_edge("PERCEIVE", "NORMALIZE")
    engine.add_edge("NORMALIZE", "CONTEXT")
    engine.add_edge("CONTEXT", "ROUTE")
    engine.add_edge("PLAN", "EXECUTE")
    engine.add_edge("EXECUTE", "OBSERVE")
    engine.add_edge("OBSERVE", "VERIFY")
    engine.add_edge("VERIFY", "DECIDE")
    engine.add_edge("RECOVER", "EXECUTE")

    # 3. Entry point
    engine.set_start_node("PERCEIVE")

    return engine


__all__ = [
    "StatefulGraphRuntime",
    "GraphState",
    "GraphPlanStep",
    "GraphObservation",
    "GraphVerification",
    "GraphExecutionStatus",
    "GraphDecision",
    "ErrorCategory",
    "NodeResult",
    "GraphNode",
    "create_default_graph_runtime",
]
