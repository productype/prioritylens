import json
from pathlib import Path
from langchain_anthropic import ChatAnthropic
from src.models import ClassificationState, AlignmentAssessment
from prompts import ALIGNMENT_SYSTEM_PROMPT
from settings import ALIGNMENT_MODEL, DEFAULT_NORMALIZED_STRATEGY_FILE
from src.logger import log

# Strategy data cache with modification time tracking
_STRATEGY_CACHE = {
    "data": None,
    "mtime": None
}

# Instantiate LLM once at module level
_llm = ChatAnthropic(model=ALIGNMENT_MODEL)
_structured_llm = _llm.with_structured_output(AlignmentAssessment)


def _load_strategy_data():
    """
    Load strategy data with caching and modification time checking.

    Implements lazy loading with cache invalidation:
    - Loads on first use
    - Reloads if file has been modified since last load
    - Handles malformed JSON gracefully
    - Returns None if file doesn't exist or is unreadable

    Returns:
        dict: Strategy data or None if unavailable
    """
    global _STRATEGY_CACHE

    strategy_path = Path(DEFAULT_NORMALIZED_STRATEGY_FILE)

    # Check if file exists
    if not strategy_path.exists():
        return None

    try:
        # Get current modification time
        current_mtime = strategy_path.stat().st_mtime

        # Return cached data if still valid
        if (_STRATEGY_CACHE["data"] is not None and
            _STRATEGY_CACHE["mtime"] == current_mtime):
            return _STRATEGY_CACHE["data"]

        # Load fresh data
        with open(strategy_path) as f:
            data = json.load(f)

        # Validate structure
        if not isinstance(data, dict) or "items" not in data:
            log(f"\n Warning: Invalid strategy file structure (missing 'items' key)")
            return None

        # Update cache
        _STRATEGY_CACHE["data"] = data
        _STRATEGY_CACHE["mtime"] = current_mtime

        return data

    except json.JSONDecodeError as e:
        log(f"\n Warning: Malformed strategy file: {e}")
        return None
    except (OSError, IOError) as e:
        log(f"\n Warning: Cannot read strategy file: {e}")
        return None


def align(state: ClassificationState) -> dict:
    """
    Assess how well the classified feedback aligns with strategic priorities.

    Returns:
        Dict with alignment_score, alignment_reasoning, related_strategy_items, impact_priority
    """
    # Load strategy data (with caching and timestamp checking)
    strategy_data = _load_strategy_data()

    if strategy_data is None:
        log("\n No normalized strategy found. Run: python normalize_strategy.py")
        log("    Or run classification without alignment: python main.py <input> --no-alignment")
        raise SystemExit("Missing strategy_normalized.json")

    # Format strategy for context
    strategy_items_text = ""
    for item in strategy_data["items"]:
        strategy_items_text += f"- {item['id']}: [{item['type']}] {item['title']} (importance: {item['importance']})\n"
        if item['description'] != item['title']:
            strategy_items_text += f"  Description: {item['description']}\n"

    strategy_context = f"""## Normalized Strategy

Vision: {strategy_data['vision']}
Time Horizon: {strategy_data['time_horizon']}

Strategic Items:
{strategy_items_text}
"""

    # Prepare feedback context
    feedback_context = f"""## Classified Feedback

Category: {state["suggested_category"]}
Impact Priority: {state["suggested_priority"]}
Classification Reasoning: {state["reasoning"]}

## Original Feedback Text

{state["feedback"]["text"]}
"""

    full_context = strategy_context + "\n" + feedback_context

    # Get alignment assessment
    while True:
        try:
            result = _structured_llm.invoke([
                {"role": "system", "content": ALIGNMENT_SYSTEM_PROMPT},
                {"role": "user", "content": full_context}
            ])
            break  # Success
        except Exception as e:
            log(f"\n Alignment assessment failed: {e}")
            log(f"    Feedback ID: {state['feedback']['id']}")
            choice = input("    [r] Retry  [s] Skip alignment  [a] Abort: ").strip().lower()
            if choice == "r":
                continue
            elif choice == "s":
                # Return default values (no alignment)
                return {
                    "alignment_score": "Low",
                    "alignment_reasoning": "Alignment assessment skipped due to error",
                    "related_strategy_items": [],
                    "impact_priority": state["suggested_priority"],  # Preserve original
                    "status": "aligned"
                }
            else:
                raise SystemExit("Aborted by user")

    return {
        "alignment_score": result.alignment_score,
        "alignment_reasoning": result.reasoning,
        "related_strategy_items": result.related_strategy_items,
        "impact_priority": state["suggested_priority"],  # Preserve original priority
        "status": "aligned"
    }
