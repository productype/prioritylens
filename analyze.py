import argparse
import csv
from collections import Counter
from pathlib import Path


def analyze_decisions(csv_file="decisions.csv"):
    decisions_file = Path(csv_file)

    # Check if file exists
    if not decisions_file.exists():
        print(f"Error: {csv_file} not found. Check the spelling.")
        print("\nRun the classifier first to generate decisions:")
        print("  python main.py extracted_items.json")
        return

    # Check if file is empty
    if decisions_file.stat().st_size == 0:
        print(f"Error: {csv_file} is empty.")
        print("\nRun the classifier to generate decisions:")
        print("  python main.py extracted_items.json")
        return

    # Read decisions with error handling
    try:
        with open(decisions_file) as f:
            reader = csv.DictReader(f)
            decisions = list(reader)
    except csv.Error as e:
        print(f"Error: Malformed CSV file: {e}")
        return
    except Exception as e:
        print(f"Error reading {csv_file}: {e}")
        return

    total = len(decisions)
    if total == 0:
        print("No decisions logged yet.")
        print("\nThe CSV file exists but contains no decision records.")
        return

    # Validate required fields exist
    required_fields = [
        "category_match", "priority_match", "full_match",
        "agent_category", "human_category", "agent_priority", "human_priority"
    ]
    if decisions and not all(field in decisions[0] for field in required_fields):
        missing = [f for f in required_fields if f not in decisions[0]]
        print(f"Error: CSV file is missing required fields: {', '.join(missing)}")
        print("\nThe file may be corrupted or from an older version.")
        print(f"Run the classifier again to regenerate {csv_file}:")
        print("  python main.py extracted_items.json")
        return

    # Agreement rates
    cat_match = sum(1 for d in decisions if d["category_match"] == "True")
    pri_match = sum(1 for d in decisions if d["priority_match"] == "True")
    full_match = sum(1 for d in decisions if d["full_match"] == "True")

    print(f"\n{'═' * 50}")
    print(f"EVALUATION METRICS - {csv_file}")
    print(f"({total} decisions)")
    print(f"{'═' * 50}")
    print(f"Category agreement:  {cat_match}/{total} ({100*cat_match/total:.1f}%)")
    print(f"Priority agreement:  {pri_match}/{total} ({100*pri_match/total:.1f}%)")
    print(f"Full agreement:      {full_match}/{total} ({100*full_match/total:.1f}%)")

    # Override patterns
    print(f"\n{'─' * 50}")
    print("CATEGORY OVERRIDES (where human disagreed)")
    print(f"{'─' * 50}")

    overrides = [(d["agent_category"], d["human_category"])
                 for d in decisions if d["category_match"] == "False"]

    if overrides:
        for (agent, human), count in Counter(overrides).most_common(5):
            print(f"  {agent} → {human}: {count}x")
    else:
        print("  None! Perfect category agreement.")

    # Priority overrides
    print(f"\n{'─' * 50}")
    print("PRIORITY OVERRIDES")
    print(f"{'─' * 50}")

    pri_overrides = [(d["agent_priority"], d["human_priority"])
                     for d in decisions if d["priority_match"] == "False"]

    if pri_overrides:
        for (agent, human), count in Counter(pri_overrides).most_common(5):
            print(f"  {agent} → {human}: {count}x")
    else:
        print("  None! Perfect priority agreement.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Analyze classification decisions and compute agreement metrics.",
        epilog="""
Examples:
  python analyze.py                    # Analyzes decisions.csv (default)
  python analyze.py decisions_1.csv    # Analyzes decisions_1.csv
        """,
        formatter_class=argparse.RawDescriptionHelpFormatter
    )

    parser.add_argument(
        'csv_file',
        nargs='?',
        default='decisions.csv',
        help='CSV file containing classification decisions (default: decisions.csv)'
    )

    args = parser.parse_args()
    analyze_decisions(args.csv_file)
