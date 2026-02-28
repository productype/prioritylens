"""
Configuration for the PriorityLens project.
"""

# Model configuration
EXTRACTION_MODEL = "claude-sonnet-4-6"  # Use a model with good reasoning capabilities for extracting feedback from transcripts, since extraction requires judgment and a good reasoning model is also better at preserving context and writing self-contained descriptions
CLASSIFICATION_MODEL = "claude-haiku-4-5-20251001"  # Use a simpler model for classifying individual items, since classification is simpler
NORMALIZATION_MODEL = "claude-sonnet-4-6"  # Use Sonnet for strategy normalization (requires judgment to infer importance)
ALIGNMENT_MODEL = "claude-haiku-4-5-20251001"  # Use Haiku for alignment assessment (straightforward matching task)

# File paths (defaults, can be overridden via CLI)
DEFAULT_OUTPUT_FILE = "output.jsonl"
DEFAULT_DECISIONS_FILE = "decisions.csv"
DEFAULT_EXTRACTION_OUTPUT = "extracted_items.json"
DEFAULT_STRATEGY_FILE = "./business_docs/strategy.md"
DEFAULT_NORMALIZED_STRATEGY_FILE = "strategy_normalized.json"
