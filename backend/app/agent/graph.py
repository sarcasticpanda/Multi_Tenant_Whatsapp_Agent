from langgraph.graph import StateGraph, END
from app.agent.state import AgentState
from app.agent.nodes import (
    acknowledge_node,
    context_retriever_node,
    llm_reasoning_node,
    dispatcher_node,
)


def build_graph():
    graph = StateGraph(AgentState)

    graph.add_node("acknowledge", acknowledge_node)
    graph.add_node("retrieve_context", context_retriever_node)
    graph.add_node("llm_reason", llm_reasoning_node)
    graph.add_node("dispatch", dispatcher_node)

    graph.set_entry_point("acknowledge")
    graph.add_edge("acknowledge", "retrieve_context")
    graph.add_edge("retrieve_context", "llm_reason")
    graph.add_edge("llm_reason", "dispatch")
    graph.add_edge("dispatch", END)

    return graph.compile()


# Single compiled instance — reused for every webhook
agent_graph = build_graph()
