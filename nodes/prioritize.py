from src.models import ClassificationState

# Priority matrix: (impact, alignment) = final_priority
PRIORITY_MATRIX = {
    ("High", "High"): "High",
    ("High", "Medium"): "High",
    ("High", "Low"): "Medium",
    ("High", "Anti-goal"): "Low",

    ("Medium", "High"): "Medium",
    ("Medium", "Medium"): "Medium",
    ("Medium", "Low"): "Low",
    ("Medium", "Anti-goal"): "Low",

    ("Low", "High"): "Low",
    ("Low", "Medium"): "Low",
    ("Low", "Low"): "Low",
    ("Low", "Anti-goal"): "Low",
}


def prioritize(state: ClassificationState) -> dict:
    """
    Compute final priority by combining impact and strategic alignment.

    Uses a priority matrix to map (impact_priority, alignment_score) → final_priority.

    Returns:
        Dict with suggested_priority (final), priority_derivation, status
    """
    impact = state["impact_priority"]
    alignment = state["alignment_score"]

    # Look up final priority in matrix
    final = PRIORITY_MATRIX.get((impact, alignment), "Medium")  # Default to Medium if not found

    # Create derivation string for transparency
    derivation = f"(impact: {impact}, alignment: {alignment}) = {final}"

    return {
        "suggested_priority": final,  # This becomes the suggestion for human review
        "priority_derivation": derivation,
        "status": "prioritized"
    }
