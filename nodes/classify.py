from langchain_anthropic import ChatAnthropic
from anthropic import APIError, APIConnectionError, RateLimitError, APITimeoutError
from src.models import ClassificationState, Classification
from prompts import CLASSIFIER_SYSTEM_PROMPT
from settings import CLASSIFICATION_MODEL
from src.logger import log

# Instantiate once at module level
_llm = ChatAnthropic(model=CLASSIFICATION_MODEL)
_structured_llm = _llm.with_structured_output(Classification)

# Configuration
MAX_RETRIES = 3


def classify(state: ClassificationState) -> dict:
    """
    Classify feedback using LLM with error recovery.

    Returns dict with suggested_category, suggested_priority, reasoning, and status.
    Status can be "classified" or "skipped".
    """
    retry_count = 0
    last_error = None

    while retry_count < MAX_RETRIES:
        try:
            result = _structured_llm.invoke([
                {"role": "system", "content": CLASSIFIER_SYSTEM_PROMPT},
                {"role": "user", "content": state["feedback"]["text"]}
            ])

            # Success — return classification
            return {
                "suggested_category": result.category,
                "suggested_priority": result.priority,
                "reasoning": result.reasoning,
                "status": "classified",
            }

        except (APIError, APIConnectionError, RateLimitError, APITimeoutError) as e:
            retry_count += 1
            last_error = e

            log(f"\n Classification failed (attempt {retry_count}/{MAX_RETRIES}): {type(e).__name__}")
            log(f"    Error: {str(e)[:200]}")  # Truncate long error messages
            log(f"    Feedback ID: {state['feedback']['id']}")

            if retry_count >= MAX_RETRIES:
                log(f"\n    Maximum retries ({MAX_RETRIES}) reached.")
                while True:
                    choice = input("    [s] Skip this item  [a] Abort: ").strip().lower()
                    if choice == "s":
                        return {"status": "skipped"}
                    elif choice == "a":
                        raise SystemExit("Aborted by user")
                    else:
                        log("    Invalid choice. Please enter 's' or 'a'.")
            else:
                while True:
                    choice = input("    [r] Retry  [s] Skip  [a] Abort: ").strip().lower()
                    if choice == "r":
                        break  # Continue outer loop
                    elif choice == "s":
                        return {"status": "skipped"}
                    elif choice == "a":
                        raise SystemExit("Aborted by user")
                    else:
                        log("    Invalid choice. Please enter 'r', 's', or 'a'.")

        except Exception as e:
            # Unexpected error — don't retry automatically
            log(f"\n Unexpected classification error: {type(e).__name__}")
            log(f"    Error: {str(e)[:200]}")
            log(f"    Feedback ID: {state['feedback']['id']}")

            while True:
                choice = input("    [r] Retry once  [s] Skip  [a] Abort: ").strip().lower()
                if choice == "r":
                    retry_count += 1
                    if retry_count >= MAX_RETRIES:
                        log("    Maximum retries reached after unexpected error.")
                        return {"status": "skipped"}
                    break  # Try once more
                elif choice == "s":
                    return {"status": "skipped"}
                elif choice == "a":
                    raise SystemExit("Aborted by user")
                else:
                    log("    Invalid choice. Please enter 'r', 's', or 'a'.")

    # Should never reach here, but handle gracefully
    log(f"\n Classification failed after {MAX_RETRIES} attempts")
    if last_error:
        log(f"    Last error: {last_error}")
    return {"status": "skipped"}
