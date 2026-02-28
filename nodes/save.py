import json
from datetime import datetime, timezone

from src.models import ClassificationState
from src.logger import log

OUTPUT_FILE = "output.jsonl"


def save(state: ClassificationState) -> dict:
    """
    Save classified feedback to output file with robust error handling.

    Implements fallback strategy:
    1. Try primary output file
    2. If fails, try .recovery fallback
    3. If fails, save to timestamped emergency file
    4. If all fail, abort with error
    """
    output = {
        **state["feedback"],  # id, text, source, timestamp
        "category": state["final_category"],
        "priority": state["final_priority"],
        "agent_reasoning": state["reasoning"],
        "human_reasoning": state.get("human_reasoning"),
        # Strategic alignment fields
        "impact_priority": state.get("impact_priority"),
        "alignment_score": state.get("alignment_score"),
        "alignment_reasoning": state.get("alignment_reasoning"),
        "related_strategy_items": state.get("related_strategy_items"),
        "priority_derivation": state.get("priority_derivation"),
        "classified_at": datetime.now(timezone.utc).isoformat()
    }

    # Try primary file
    try:
        with open(OUTPUT_FILE, "a") as f:
            f.write(json.dumps(output) + "\n")

        log(f"✓ Saved: {state['feedback']['id']} → {state['final_category']} ({state['final_priority']})")
        return {"status": "saved"}

    except IOError as primary_error:
        log(f"\n Primary save failed: {primary_error}")

        # Try fallback file
        fallback_file = f"{OUTPUT_FILE}.recovery.jsonl"
        try:
            with open(fallback_file, "a") as f:
                f.write(json.dumps(output) + "\n")

            log(f"    ✓ Saved to fallback: {fallback_file}")
            return {"status": "saved_to_fallback"}

        except IOError as fallback_error:
            log(f"    Fallback save also failed: {fallback_error}")

            # Try emergency timestamped file
            timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
            emergency_file = f"emergency_save_{state['feedback']['id']}_{timestamp}.json"

            try:
                with open(emergency_file, "w") as f:
                    json.dump(output, f, indent=2)

                log(f"    ✓ Saved to emergency file: {emergency_file}")
                log(f"    You MUST manually merge this file into {OUTPUT_FILE}")
                return {"status": "saved_to_emergency"}

            except IOError as emergency_error:
                # All save attempts failed
                log(f"\n CRITICAL: All save attempts failed!")
                log(f"    Primary error: {primary_error}")
                log(f"    Fallback error: {fallback_error}")
                log(f"    Emergency error: {emergency_error}")
                log(f"\n    Data to recover manually:")
                log(f"    {json.dumps(output, indent=2)}")

                while True:
                    choice = input("\n    [c] Continue (DATA WILL BE LOST!)  [a] Abort: ").strip().lower()
                    if choice == "c":
                        log("    WARNING: Continuing without saving. Data loss occurred.")
                        return {"status": "save_failed"}
                    elif choice == "a":
                        raise SystemExit("Aborted due to save failure. Check file system permissions.")
                    else:
                        log("    Invalid choice. Please enter 'c' or 'a'.")
