import json
from datetime import datetime, timezone
from dotenv import load_dotenv
from pathlib import Path
from langchain_anthropic import ChatAnthropic
from src.models import ExtractedItem, ExtractionResult
from prompts import EXTRACTION_SYSTEM_PROMPT
from settings import EXTRACTION_MODEL

load_dotenv()


def extract_feedback_from_transcript(
    transcript_path: str,
    output_path: str = "extracted_items.json",
    source_name: str = "interview"
) -> list[dict]:
    """
    Extract individual feedback items from a long-form transcript.

    Args:
        transcript_path: Path to .txt file containing interview transcript
        output_path: Where to save extracted items (input.json format)
        source_name: Label for the source (e.g., "interview", "support_ticket")

    Returns:
        List of extracted feedback items in input.json format
    """
    # Read transcript
    with open(transcript_path) as f:
        transcript = f.read()

    llm = ChatAnthropic(model=EXTRACTION_MODEL)
    structured_llm = llm.with_structured_output(ExtractionResult)

    print(f"Extracting feedback from {transcript_path}...")
    print(f"  Transcript length: {len(transcript)} characters\n")

    # Extract items
    result = structured_llm.invoke([
        {"role": "system", "content": EXTRACTION_SYSTEM_PROMPT},
        {"role": "user", "content": f"Extract feedback items from this transcript:\n\n{transcript}"}
    ])

    # Generate unique IDs based on transcript filename and timestamp
    transcript_id = Path(transcript_path).stem  # e.g., "sample_interview"
    timestamp = datetime.now(timezone.utc).isoformat()

    # Convert to input.json format
    feedback_items = []
    for i, item in enumerate(result.items, 1):
        feedback_items.append({
            "id": f"{transcript_id}_{i:03d}",
            "text": item.text,
            "source": source_name,
            "timestamp": timestamp,
            "source_quote": item.source_quote,
            "extracted_type": item.item_type,  # Hint for human reviewer
        })

    # Save to file
    with open(output_path, "w") as f:
        json.dump(feedback_items, f, indent=2)

    # Print summary
    print(f"✓ Extracted {len(feedback_items)} items:")
    for item in feedback_items:
        print(f"  [{item['extracted_type']}] {item['text'][:80]}...")
    print(f"\n  Saved to: {output_path}")
    print(f"  Next step: Review extracted items, then run: python main.py")

    return feedback_items


def main():
    import sys

    if len(sys.argv) < 2:
        print("Usage: python extract.py <transcript_file.txt> [output_file.json]")
        print("\nExample: python extract.py interviews/interview_transcript_1.txt")
        sys.exit(1)

    transcript_path = sys.argv[1]
    output_path = sys.argv[2] if len(sys.argv) > 2 else "extracted_items.json"

    extract_feedback_from_transcript(transcript_path, output_path)


if __name__ == "__main__":
    main()
