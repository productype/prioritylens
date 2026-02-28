# PriorityLens

**Strategic feedback classification and prioritization**

An AI-powered feedback classification system with strategic alignment. Combines LLM-based classification with human-in-the-loop review to categorize and prioritize product feedback intelligently.

## Overview

PriorityLens processes user feedback (pain points, feature requests, bugs) through an automated workflow that:
1. **Classifies** feedback into 7 categories with impact-based priority
2. **Aligns** feedback against documented product strategy
3. **Prioritizes** using a matrix that combines impact × strategic alignment
4. **Reviews** with mandatory human oversight before saving results

**Key capabilities:**
- **Strategic alignment** - Evaluates how feedback aligns with your product strategy
- **Progress tracking** - Skip items, resume sessions, review skipped items later
- **Human-in-the-loop** - Mandatory review before saving results
- **Analytics** - Track agent vs. human agreement rates

**Workflow:**
```
# With strategic alignment
classify → align → prioritize → human review → save

# Without strategic alignment
classify → human review → save
```

## Features

### Core Classification
- **7 categories**: Opportunity, Pain, Bug, Usability, Performance, Feature Request, Pricing
- **3 priorities**: High, Medium, Low (based on impact and urgency)

### Strategic Alignment
- Normalize any strategy format (OKRs, goals, priorities) into a flat structure
- Assess alignment score: High, Medium, Low, Anti-goal
- Priority matrix combines impact × alignment → final priority

**Priority Matrix:**

| Impact \ Alignment | High | Medium | Low | Anti-goal |
|-------------------|------|--------|-----|-----------|
| **High**          | High | High   | Med | Low       |
| **Medium**        | Med  | Med    | Low | Low       |
| **Low**           | Low  | Low    | Low | Low       |

### Human-in-the-Loop
- Approve, override category/priority, skip, abort, or edit reasoning
- All decisions are logged to `decisions.csv` for agreement metrics between LLM and human
- Agreement rate analysis with `analyze.py` for alignment debugging

### Progress Management
- **Skip functionality** - Skip items during review
- **Session resume** - Resume later without re-processing
- **Review skipped** - `--review-skipped` flag to revisit skipped items
- **Progress tracking** - `progress.json` tracks processed/skipped/pending states

## Quick Start

### Installation

```bash
# Clone the repository
git clone <your-repo-url>
cd prioritylens

# Create virtual environment (Python 3.10+ recommended)
python3 -m venv .venv
source .venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Set API key
export ANTHROPIC_API_KEY=your_key_here
# Or create .env file with: ANTHROPIC_API_KEY=your_key_here

# Test the installation with example data
python main.py input.json
```

### Basic Usage

```bash
# Try with example data
python main.py input.json

# Or extract your own feedback from transcripts and process the extracted items
python extract.py interviews/transcript.txt feedback.json
python main.py feedback.json

# Analyze agreement metrics
python analyze.py
# Or analyze agreement metrics from a specific decision file
python analyze.py decisions_1.csv
```

### Common Workflows

**Skip items and review later:**
```bash
# During classification, press [s] to skip items
python main.py input.json
# Progress: 10 processed, 3 skipped, 0 pending

# Later, review only skipped items
python main.py input.json --review-skipped
```

**Resume after interruption:**
```bash
# Press Ctrl+C or [a] during classification to interrupt processing
python main.py input.json
# Progress: 5 processed, 0 skipped, 4 pending

# Resume later - continues from item 6
python main.py input.json
```

**Classification without strategic alignment:**
```bash
python main.py input.json --no-alignment
```

## Project Structure

```
.
├── main.py                  # Classification workflow
├── extract.py               # Extract feedback from transcripts
├── normalize_strategy.py    # Normalize strategy documents
├── analyze.py               # Analyze classification metrics
├── settings.py              # Model and path configuration
├── nodes/                   # Workflow nodes (classify, align, prioritize, review, save)
├── prompts/                 # LLM prompt templates
├── src/                     # Core library (models, graph, logger)
└── tests/                   # Test suite (25 tests)
```

## Testing

```bash
./run_tests.sh  # Runs 25 tests
```

## Output Files

- **`output.jsonl`** - Complete classification results
- **`decisions.csv`** - Human review decisions for analysis
- **`progress.json`** - Progress state (auto-managed)
- **`classifier.log`** - Session logs

## Configuration

### Command-line Options

**main.py** - Classification workflow:
```bash
python main.py INPUT_FILE [OUTPUT_FILE] [DECISIONS_FILE] [OPTIONS]

Options:
  --no-alignment     Disable strategic alignment (basic classification only)
  --review-skipped   Show ONLY skipped items (for reviewing later)
  -h, --help         Show help message
```

**analyze.py** - Agreement metrics analysis:
```bash
python analyze.py [CSV_FILE]

Arguments:
  CSV_FILE           CSV file to analyze (default: decisions.csv)

Options:
  -h, --help         Show help message
```

### Environment Variables

```bash
ANTHROPIC_API_KEY=your_key_here  # Required
```

### Model Configuration

Edit `settings.py` to change models:
```python
# Fast and cheap
CLASSIFICATION_MODEL = "claude-haiku-4-5-20251001"
ALIGNMENT_MODEL = "claude-haiku-4-5-20251001"
# Complex reasoning
EXTRACTION_MODEL = "claude-sonnet-4-6"             
NORMALIZATION_MODEL = "claude-sonnet-4-6"
```

## Cost Analysis
Estimates based on February 2026 Anthropic pricing

**Extraction costs for transcripts from user interviews:**
- 30-60 minute interview transcript: <$0.10

**Per-item costs (with strategic alignment):**
- Classification: ~$0.003
- Alignment: ~$0.005
- **Total:** <$0.01 per item

**Total estimates:**
- 100 items: <$1

## Classification Taxonomy

### Categories (7)

1. **Opportunity** - New market, use case, or growth area
2. **Pain** - Frustration or difficulty with current experience
3. **Bug** - Something broken or not working as expected
4. **Usability** - UI/UX struggles, navigation, discoverability
5. **Performance** - Slowness, resource problems
6. **New Feature Request** - Explicit ask for new functionality
7. **Pricing Concern** - Comments on cost, value, or pricing model

### Priorities (3)

**Based on impact:**

- **High** - Blocks core workflows, broad impact, revenue or churn risk
- **Medium** - Degrades experience, has workarounds, subset of users
- **Low** - Cosmetic issues, edge cases, nice-to-have improvements

### Alignment Scores (4)

- **High** - Directly supports current objective/metric/priority
- **Medium** - Tangentially related, indirect strategic value
- **Low** - Not related to strategy but not contradictory
- **Anti-goal** - Contradicts strategy or targets excluded persona

## Design Decisions

**Human-in-the-loop** - Mandatory human review before finalizing classifications

**Append-only outputs** - `output.jsonl` and `decisions.csv` support idempotent re-runs

**Progress tracking** - Enables skip, resume, and review workflows

**Error recovery** - 3 retries on API failures with user intervention options

**File safety** - 3-tier fallback (primary → recovery → emergency) for robust saving

**Session logging** - All output logged to `classifier.log` with timestamps

## Built With

- **[LangChain](https://github.com/langchain-ai/langchain)** - LLM orchestration framework
- **[LangGraph](https://github.com/langchain-ai/langgraph)** - Workflow orchestration framework
- **[Anthropic Claude API](https://www.anthropic.com/api)** - LLM provider
- **[Pydantic](https://github.com/pydantic/pydantic)** - Data validation

## License

MIT License

---

**Author:** Bettina Heinlein
**Created:** 2026
