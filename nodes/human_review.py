import csv
from datetime import datetime, timezone
from pathlib import Path

from langgraph.types import interrupt
from src.models import ClassificationState

LOG_FILE = "decisions.csv"

def log_descisions(state:dict) -> None:
    """Append one human review decision to decisions.csv."""
    log_entry= {
        "feedback_id": state["feedback"]["id"],
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "agent_category": state["suggested_category"],
        "agent_priority": state["suggested_priority"],
        "agent_reasoning": state["reasoning"],
        "impact_priority": state.get("impact_priority"),
        # Strategic alignment fields
        "alignment_score": state.get("alignment_score"),
        "final_priority": state["suggested_priority"],
        "human_category": state["final_category"],
        "human_priority": state["final_priority"],
        "category_match": state["suggested_category"] == state["final_category"],
        "priority_match": state["suggested_priority"] == state["final_priority"],
        "full_match": (
            state["suggested_category"] == state["final_category"] and
            state["suggested_priority"] == state["final_priority"]
        )
    }

    # Write headers if file doesn't exist or is empty
    file_path = Path(LOG_FILE)
    write_header = not file_path.exists() or file_path.stat().st_size == 0

    with open(LOG_FILE, "a", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=log_entry.keys())
        if write_header:
            writer.writeheader()
        writer.writerow(log_entry)


def human_review(state: ClassificationState) -> dict:
    # Pauses the graph, main.py retrieves this payload, collects CLI input, and resumes.
    human_input = interrupt({
        "feedback": state["feedback"],
        "suggested_category": state["suggested_category"],
        "suggested_priority": state["suggested_priority"],
        "reasoning": state["reasoning"],
        "impact_priority": state.get("impact_priority"),
        "alignment_score": state.get("alignment_score"),
        "alignment_reasoning": state.get("alignment_reasoning"),
        "related_strategy_items": state.get("related_strategy_items"),
        "priority_derivation": state.get("priority_derivation")
    })

    # When resumed in main.py via command resume=..., human_input contains the decision dict
    final_category = human_input.get("category", state["suggested_category"])
    final_priority = human_input.get("priority", state["suggested_priority"])
    human_reasoning = human_input.get("human_reasoning")

    log_descisions({**state, "final_category": final_category, "final_priority": final_priority, "status": "reviewed"})

    return {
        "final_category": final_category,
        "final_priority": final_priority,
        "human_reasoning": human_reasoning,
        "status": "reviewed"
    }
