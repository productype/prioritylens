from langgraph.graph import StateGraph, START, END
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.types import RetryPolicy

from src.models import ClassificationState
from nodes.classify import classify
from nodes.align import align
from nodes.prioritize import prioritize
from nodes.human_review import human_review
from nodes.save import save


def create_graph(enable_alignment: bool = True):
    """
    Create the classification workflow graph.

    Args:
        enable_alignment: If True, includes strategic alignment (align + prioritize nodes).
                         If False, runs basic classification only (classify → human_review → save).
    """
    # Initialize graph with state schema
    workflow = StateGraph(ClassificationState)

    # Add nodes
    workflow.add_node("classify", classify)
    workflow.add_node("human_review", human_review)
    workflow.add_node("save", save)

    if enable_alignment:
        workflow.add_node("align", align)
        workflow.add_node("prioritize", prioritize)

    # Add edges
    workflow.add_edge(START, "classify")

    if enable_alignment:
        # Strategic alignment flow
        workflow.add_conditional_edges(
            "classify",
            lambda state: END if state["status"] == "skipped" else "align",
            {END: END, "align": "align"},
        )
        workflow.add_edge("align", "prioritize")
        workflow.add_edge("prioritize", "human_review")
    else:
        # Classification flow without strategic alignment
        workflow.add_conditional_edges(
            "classify",
            lambda state: END if state["status"] == "skipped" else "human_review",
            {END: END, "human_review": "human_review"},
        )

    workflow.add_edge("human_review", "save")
    workflow.add_edge("save", END)

    # Compile with checkpointer (required for interrupt)
    memory = InMemorySaver()
    graph = workflow.compile(checkpointer=memory)

    return graph
