import json
import sys
from pathlib import Path
from dotenv import load_dotenv
from langchain_anthropic import ChatAnthropic
from src.models import StrategyItem, NormalizedStrategy
from settings import NORMALIZATION_MODEL, DEFAULT_STRATEGY_FILE, DEFAULT_NORMALIZED_STRATEGY_FILE

load_dotenv()

NORMALIZATION_SYSTEM_PROMPT = """You are a strategic analyst who normalizes product strategy documents into a structured format.

Your task is to extract strategic elements from various document formats (OKRs, goals, themes, metrics, personas, etc.) and convert them into a flat, universal structure.

**Extract these types of strategic elements:**
- **objective**: High-level goals or objectives (e.g., "O1: Expand into enterprise segment")
- **metric**: Measurable targets, KPIs, or key results (e.g., "Land 10 enterprise customers", "Increase retention from 40% to 55%")
- **theme**: Strategic themes or focus areas (e.g., "Enterprise readiness", "Integration ecosystem")
- **persona**: Target user segments or personas (e.g., "Engineering teams at mid-size companies")
- **anti-goal**: Explicitly stated non-targets or things NOT to pursue (e.g., "NOT targeting: Individual freelancers")
- **initiative**: Specific projects or initiatives (e.g., "Ship admin dashboard with SSO")

**Assign IDs:**
- Use simple sequential IDs: "S1", "S2", "S3", etc.
- IDs are global across all types (don't restart numbering per type)

**Determine importance level** based on:
1. **Language cues**: "must", "critical", "essential", "required" → critical; "improve", "enhance", "increase" → high; "explore", "consider", "nice to have" → medium
2. **Quantified targets**: Ambitious numbers suggest higher importance (e.g., "10x growth" vs "5% improvement")
3. **Document position**: Items mentioned first or emphasized are likely more important
4. **Explicit markers**: If document includes [P0], [P1], [critical] tags, use those

**Granularity for OKRs:**
- Extract each Objective as a separate item (type: objective)
- Extract each Key Result as a separate item (type: metric)
- Keep structure flat (no nesting)

**Vision and time horizon:**
- Extract any mission/vision statement if present
- Infer time horizon from context (e.g., "Q1 2025", "2025", "Next 6 months")

**Example transformations:**

Input (OKR format):
```
Vision: Become the leading collaboration tool for remote-first teams

Q1 2025 OKRs:
O1: Expand into enterprise segment
  KR1: Land 10 enterprise customers (500+ seats)
  KR2: Achieve SOC2 compliance

Strategic Themes:
- Enterprise readiness (security, compliance, admin controls)
- Onboarding simplification

NOT targeting:
- Individual freelancers
```

Output:
```json
{
  "vision": "Become the leading collaboration tool for remote-first teams",
  "time_horizon": "Q1 2025",
  "items": [
    {
      "id": "S1",
      "type": "objective",
      "title": "Expand into enterprise segment",
      "description": "O1: Expand into enterprise segment",
      "importance": "critical"
    },
    {
      "id": "S2",
      "type": "metric",
      "title": "Land 10 enterprise customers",
      "description": "KR1: Land 10 enterprise customers (500+ seats)",
      "importance": "critical"
    },
    {
      "id": "S3",
      "type": "metric",
      "title": "Achieve SOC2 compliance",
      "description": "KR2: Achieve SOC2 compliance",
      "importance": "critical"
    },
    {
      "id": "S4",
      "type": "theme",
      "title": "Enterprise readiness",
      "description": "Enterprise readiness (security, compliance, admin controls)",
      "importance": "critical"
    },
    {
      "id": "S5",
      "type": "theme",
      "title": "Onboarding simplification",
      "description": "Onboarding simplification",
      "importance": "high"
    },
    {
      "id": "S6",
      "type": "anti-goal",
      "title": "Individual freelancers",
      "description": "NOT targeting: Individual freelancers",
      "importance": "high"
    }
  ]
}
```

Extract all strategic elements from the document. Prefer:
- More granular extraction over bundling (each KR separate, each theme separate)
- Explicit importance assignment based on evidence in the document
- Self-contained descriptions that preserve context
"""


def normalize_strategy(
    strategy_path: str = DEFAULT_STRATEGY_FILE,
    output_path: str = DEFAULT_NORMALIZED_STRATEGY_FILE
) -> NormalizedStrategy:
    """
    Normalize a strategy document into structured format.

    Args:
        strategy_path: Path to strategy.md file
        output_path: Where to save normalized strategy JSON

    Returns:
        NormalizedStrategy object
    """
    # Read strategy document
    strategy_file = Path(strategy_path)
    if not strategy_file.exists():
        print(f"\n Strategy file not found: {strategy_path}")
        print("\nCreate a strategy.md file with your product strategy, or run without alignment:")
        print("  python main.py extracted_items.json --no-alignment")
        sys.exit(1)

    with open(strategy_path) as f:
        strategy_content = f.read()

    if not strategy_content.strip():
        print(f"\n Strategy file is empty: {strategy_path}")
        print("\nAdd content to your strategy.md file, or run without alignment:")
        print("  python main.py extracted_items.json --no-alignment")
        sys.exit(1)

    # Use a good reasoning model for normalization - requires judgment to infer importance
    llm = ChatAnthropic(model=NORMALIZATION_MODEL)
    structured_llm = llm.with_structured_output(NormalizedStrategy)

    print(f"Normalizing strategy from {strategy_path}...")
    print(f"  Strategy length: {len(strategy_content)} characters\n")

    # Extract and normalize
    result = structured_llm.invoke([
        {"role": "system", "content": NORMALIZATION_SYSTEM_PROMPT},
        {"role": "user", "content": f"Normalize this strategy document:\n\n{strategy_content}"}
    ])

    # Validate: must have at least one strategic item
    if not result.items:
        print("\n Failed to extract any strategic items from strategy.md\n")
        print("Possible causes:")
        print("- Content is too vague (add specific goals, metrics, or initiatives)")
        print("- Format is not parseable\n")
        print("Fix the strategy document or run without alignment:")
        print("  python main.py extracted_items.json --no-alignment")
        sys.exit(1)

    # Save to file
    with open(output_path, "w") as f:
        json.dump(result.model_dump(), f, indent=2)

    # Print summary
    importance_counts = {"critical": 0, "high": 0, "medium": 0}
    for item in result.items:
        importance_counts[item.importance] += 1

    print(f"✓ Extracted {len(result.items)} strategic items:")
    print(f"  {importance_counts['critical']} critical, {importance_counts['high']} high, {importance_counts['medium']} medium")
    print(f"\nBreakdown by type:")

    type_counts = {}
    for item in result.items:
        type_counts[item.type] = type_counts.get(item.type, 0) + 1

    for item_type, count in sorted(type_counts.items()):
        print(f"  {count} {item_type}")

    print(f"\nVision: {result.vision}")
    print(f"Time horizon: {result.time_horizon}")
    print(f"\nSaved to: {output_path}")
    print(f"Review the normalized strategy before running classification.")

    return result


def main():
    if len(sys.argv) < 2:
        # Default behavior: normalize default strategy file
        normalize_strategy()
    else:
        # Custom paths
        strategy_path = sys.argv[1]
        output_path = sys.argv[2] if len(sys.argv) > 2 else DEFAULT_NORMALIZED_STRATEGY_FILE
        normalize_strategy(strategy_path, output_path)


if __name__ == "__main__":
    main()
