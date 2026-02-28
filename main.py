import json
from dotenv import load_dotenv

load_dotenv()

from langgraph.types import Command
from src.graph import create_graph
from src.models import CATEGORIES
from src.logger import log, log_session_start, log_session_end


def load_progress_state(progress_file: str = "progress.json", output_file: str = "output.jsonl") -> dict:
    """
    Load progress state from progress.json.

    If progress.json doesn't exist, initialize from output.jsonl (mark as "processed").

    Returns:
        dict: {feedback_id: "processed" | "skipped" | "pending"}
    """
    from pathlib import Path

    progress_path = Path(progress_file)

    # Try to load existing progress.json
    if progress_path.exists():
        try:
            with open(progress_file) as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError) as e:
            log(f" Warning: Could not load {progress_file}: {e}")
            log(f"    Initializing fresh progress state...")

    # Initialize from output.jsonl if it exists
    progress = {}
    try:
        with open(output_file) as f:
            for line in f:
                item = json.loads(line)
                progress[item["id"]] = "processed"
    except FileNotFoundError:
        pass  # No existing output, start fresh
    except (json.JSONDecodeError, IOError) as e:
        log(f" Warning: Could not read {output_file}: {e}")

    return progress


def save_progress_state(progress: dict, progress_file: str = "progress.json") -> None:
    """
    Save progress state to progress.json.

    Writes atomically using a temporary file to prevent corruption.
    """
    import tempfile
    import shutil
    from pathlib import Path

    tmp_path = None
    try:
        # Write to temporary file first
        with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.tmp') as tmp:
            json.dump(progress, tmp, indent=2)
            tmp_path = tmp.name

        # Atomic move
        shutil.move(tmp_path, progress_file)

    except (IOError, OSError) as e:
        log(f" Warning: Could not save progress state: {e}")
        # Try to clean up temp file if it was created
        if tmp_path:
            try:
                Path(tmp_path).unlink(missing_ok=True)
            except:
                pass


def filter_items_by_progress(items: list, progress: dict, review_skipped_only: bool) -> list:
    """
    Filter items based on progress state and mode.

    Args:
        items: List of feedback items
        progress: Progress state dict
        review_skipped_only: If True, show ONLY skipped items

    Returns:
        Filtered list of items
    """
    if review_skipped_only:
        # Show only skipped items
        return [item for item in items if progress.get(item["id"]) == "skipped"]
    else:
        # Show pending items (not processed or skipped)
        return [item for item in items if progress.get(item["id"]) not in ("processed", "skipped")]


def collect_human_input(interrupt_data: dict) -> dict:
    """Display the agent suggestion and collect a review decision via CLI."""
    feedback = interrupt_data["feedback"]
    text = feedback["text"]

    # Parse ID format: "interview_transcript_1_008" -> "item 8 from interview_transcript_1.txt"
    feedback_id = feedback["id"]
    parts = feedback_id.rsplit("_", 1)  # Split from the right, once
    source_file = f"{parts[0]}.txt" if len(parts) > 1 else feedback_id
    item_number = int(parts[1]) if len(parts) > 1 and parts[1].isdigit() else ""

    log(f"\n{'─' * 60}")
    log(f"Item {item_number} from {source_file}:")
    log(f'"{text}"')

    log(f"\nClassification:")
    log(f"  Category: {interrupt_data['suggested_category']}")
    log(f"  Reasoning: {interrupt_data['reasoning']}")

    # Display strategic alignment info
    if interrupt_data.get("impact_priority"):
        log(f"  Impact: {interrupt_data['impact_priority']}")

        log(f"\nStrategic Alignment:")
        log(f"  Score: {interrupt_data.get('alignment_score', 'N/A')}")
        related = interrupt_data.get("related_strategy_items", [])
        if related:
            log(f"  Related: {', '.join(related)}")
        log(f"  Reasoning: {interrupt_data.get('alignment_reasoning', 'N/A')}")

        log(f"\nFinal Priority: {interrupt_data['suggested_priority']}")
        if interrupt_data.get("priority_derivation"):
            # Capitalize for display
            derivation = interrupt_data['priority_derivation'].replace("impact:", "Impact:").replace("alignment:", "Alignment:")
            log(f"  {derivation}")
    else:
        # Mode without strategic alignment
        log(f"  Priority: {interrupt_data['suggested_priority']}")

    log(f"\nActions:")
    log(f"  [y] Approve  [s] Skip  [a] Abort")
    log("  ", end="")
    for i, cat in enumerate(CATEGORIES, 1):
        log(f"[{i}] {cat}", end="  ")
    log("")  # newline
    log(f"  [h] High  [m] Medium  [l] Low  [r] Edit reasoning")

    choice = input("\nYour choice: ").strip().lower()

    # Handle skip (takes precedence)
    if "s" in choice:
        return {"skip": True}

    # Handle abort
    if "a" in choice:
        raise SystemExit("Aborted by user")

    final_category = interrupt_data["suggested_category"]
    final_priority = interrupt_data["suggested_priority"]
    human_reasoning = None

    if choice not in ("y", ""):
        for char in choice:
            if char.isdigit() and 1 <= int(char) <= 7:
                final_category = CATEGORIES[int(char) - 1]
            elif char == "h":
                final_priority = "High"
            elif char == "m":
                final_priority = "Medium"
            elif char == "l":
                final_priority = "Low"

        # Handle reasoning edit (can be combined with other choices like "3hr")
        if "r" in choice:
            human_note = input("\nAdd your reasoning (press Enter to keep agent's): ").strip()
            if human_note:
                human_reasoning = human_note

    return {"category": final_category, "priority": final_priority, "human_reasoning": human_reasoning}


def ensure_strategy_normalized(force_disable: bool = False):
    """
    Auto-run strategy normalization if needed.

    Args:
        force_disable: If True, skip normalization and disable alignment

    Returns:
        bool: True if alignment should be enabled, False otherwise
    """
    if force_disable:
        log("\n Strategic alignment disabled (--no-alignment flag)\n")
        return False

    from pathlib import Path
    from settings import DEFAULT_STRATEGY_FILE, DEFAULT_NORMALIZED_STRATEGY_FILE

    strategy_path = Path(DEFAULT_STRATEGY_FILE)
    normalized_path = Path(DEFAULT_NORMALIZED_STRATEGY_FILE)

    # Check if strategy.md exists
    if not strategy_path.exists():
        log(f"\n No strategy file found: {DEFAULT_STRATEGY_FILE}")
        log("Strategic alignment disabled. Running classification only.\n")
        return False

    # Check if normalization needed (with error handling for file system issues)
    try:
        needs_normalization = (
            not normalized_path.exists() or
            strategy_path.stat().st_mtime > normalized_path.stat().st_mtime
        )
    except (OSError, IOError) as e:
        log(f"\n Warning: Cannot check strategy file timestamps: {e}")
        log("Strategic alignment disabled. Running classification only.\n")
        return False

    if needs_normalization:
        log(f"\n Normalizing strategy from {DEFAULT_STRATEGY_FILE}...")
        from normalize_strategy import normalize_strategy
        try:
            normalize_strategy()
            log("")

            # Verify the normalized file was actually created
            if not normalized_path.exists():
                log("\n Warning: Strategy normalization completed but output file not found")
                log("Strategic alignment disabled. Running classification only.\n")
                return False

            return True
        except SystemExit:
            # Normalization failed, disable alignment
            log("\n Strategy normalization failed. Running classification only.\n")
            return False
        except Exception as e:
            log(f"\n Unexpected error during strategy normalization: {e}")
            log("Strategic alignment disabled. Running classification only.\n")
            return False

    return True


def main():
    import argparse

    parser = argparse.ArgumentParser(
        description="Classify product feedback with optional strategic alignment",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # With strategic alignment (default)
  python main.py extracted_items.json

  # Without strategic alignment
  python main.py extracted_items.json --no-alignment

  # Review only previously skipped items
  python main.py extracted_items.json --review-skipped

  # Custom output files
  python main.py extracted_items.json output.jsonl decisions.csv
        """
    )
    parser.add_argument("input_file", help="Input JSON file with feedback items")
    parser.add_argument("output_file", nargs="?", default="output.jsonl",
                       help="Output JSONL file (default: output.jsonl)")
    parser.add_argument("decisions_file", nargs="?", default="decisions.csv",
                       help="Decisions CSV file (default: decisions.csv)")
    parser.add_argument("--no-alignment", action="store_true",
                       help="Disable strategic alignment (run basic classification only)")
    parser.add_argument("--review-skipped", action="store_true",
                       help="Show ONLY skipped items (filters out pending/processed items)")

    args = parser.parse_args()

    # Start logging session
    log_session_start()

    # Validate API key is set
    import os
    import sys
    if not os.environ.get("ANTHROPIC_API_KEY"):
        log("Error: ANTHROPIC_API_KEY environment variable not set")
        log("\nPlease set your API key:")
        log("  export ANTHROPIC_API_KEY=your_key_here")
        log("\nOr add to .env file:")
        log("  ANTHROPIC_API_KEY=your_key_here")
        sys.exit(1)

    input_path = args.input_file
    output_path = args.output_file
    decisions_path = args.decisions_file
    progress_path = "progress.json"

    # Create output.jsonl if it doesn't exist
    from pathlib import Path
    output_file = Path(output_path)
    if not output_file.exists():
        try:
            output_file.touch()
            log(f"Created output file: {output_path}")
        except (IOError, OSError) as e:
            log(f"Warning: Could not create output file: {e}")

    # Auto-run strategy normalization if needed (unless --no-alignment)
    enable_alignment = ensure_strategy_normalized(force_disable=args.no_alignment)

    # Configure output paths for graph nodes
    from nodes import save, human_review
    save.OUTPUT_FILE = output_path
    human_review.LOG_FILE = decisions_path

    # Load and validate input file
    try:
        with open(input_path) as file:
            feedback_items = json.load(file)
    except FileNotFoundError:
        log(f"Error: Input file not found: {input_path}")
        import sys
        sys.exit(1)
    except json.JSONDecodeError as e:
        log(f"Error: Invalid JSON in {input_path}: {e}")
        import sys
        sys.exit(1)

    # Validate input structure
    if not isinstance(feedback_items, list):
        log(f"Error: {input_path} must contain a JSON array of feedback items")
        import sys
        sys.exit(1)

    if not feedback_items:
        log(f"Warning: {input_path} contains no items. Nothing to process.")
        import sys
        sys.exit(0)

    # Validate required fields in each item
    required_fields = ["id", "text", "source", "timestamp"]
    for i, item in enumerate(feedback_items):
        if not isinstance(item, dict):
            log(f"Error: Item at index {i} is not a valid object")
            import sys
            sys.exit(1)

        missing_fields = [field for field in required_fields if field not in item]
        if missing_fields:
            log(f"Error: Item at index {i} (id: {item.get('id', 'unknown')}) missing required fields: {missing_fields}")
            log(f"Required fields: {required_fields}")
            import sys
            sys.exit(1)

    graph = create_graph(enable_alignment=enable_alignment)

    # Load progress state and filter items
    progress = load_progress_state(progress_path, output_path)
    filtered_items = filter_items_by_progress(feedback_items, progress, args.review_skipped)

    # Show filtering info
    if args.review_skipped:
        skipped_count = len(filtered_items)
        if skipped_count == 0:
            log(f"\nNo skipped items to review. Exiting.")
            log_session_end()
            import sys
            sys.exit(0)
        log(f"\nReviewing {skipped_count} skipped item(s)...")
    else:
        pending_count = len(filtered_items)
        processed_count = sum(1 for v in progress.values() if v == "processed")
        skipped_count = sum(1 for v in progress.values() if v == "skipped")
        log(f"\nProgress: {processed_count} processed, {skipped_count} skipped, {pending_count} pending")

    for i, item in enumerate(filtered_items, 1):
        log(f"\n Loading [{i}/{len(filtered_items)}] ...")
        log(f"  ID: {item['id']}")
    
        config = {"configurable": {"thread_id": f"feedback_{item['id']}"}}
        initial_state = {
            "feedback": item,
            "suggested_category": None,
            "suggested_priority": None,
            "reasoning": None,
            # Strategic alignment fields
            "alignment_score": None,
            "alignment_reasoning": None,
            "related_strategy_items": None,
            "impact_priority": None,
            "priority_derivation": None,
            # Human decision
            "final_category": None,
            "final_priority": None,
            "human_reasoning": None,
            "status": "pending",
        }

        # First invocation: runs classify, then either pauses at interrupt() in
        # human_review (normal) or reaches END directly (skipped due to error)
        graph.invoke(initial_state, config)

        # Check whether the graph paused for review or completed without interrupting
        snapshot = graph.get_state(config)
        if not snapshot.tasks:
            # Graph reached END — item was skipped (classification error)
            log(f"  Skipped: {item['id']}")
            progress[item["id"]] = "skipped"
            save_progress_state(progress, progress_path)
            continue

        # Retrieve the interrupt payload from the checkpointed thread state
        interrupt_data = snapshot.tasks[0].interrupts[0].value

        # Display suggestion and collect human decision via CLI
        human_response = collect_human_input(interrupt_data)

        # Check if user chose to skip
        if human_response.get("skip"):
            log(f"  Skipped: {item['id']}")
            progress[item["id"]] = "skipped"
            save_progress_state(progress, progress_path)
            continue

        # Resume the graph with the human's decision
        graph.invoke(Command(resume=human_response), config)

        # Mark as processed
        progress[item["id"]] = "processed"
        save_progress_state(progress, progress_path)

    log(f"\n{'═' * 60}")
    log(f"Done! Results saved to {output_path}")
    log(f"Review decisions logged to {decisions_path}")
    log(f"{'═' * 60}")

    log_session_end()


if __name__ == "__main__":
    main()
