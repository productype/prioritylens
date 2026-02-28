from typing import TypedDict, Optional, Literal
from pydantic import BaseModel, Field


# Shared constant — imported by nodes/human_review.py and main.py
CATEGORIES = [
    "Opportunity", "Pain", "Bug", "Usability",
    "Performance", "New Feature Request", "Pricing Concern"
]


class FeedbackItem(TypedDict):
    id: str
    text: str
    source: str
    timestamp: str


class ClassificationState(TypedDict):
    # Input
    feedback: FeedbackItem

    # Classification (from classify node)
    suggested_category: Optional[str]      # Agent's category suggestion
    suggested_priority: Optional[str]      # Agent's priority suggestion (becomes impact_priority)
    reasoning: Optional[str]               # Agent's classification reasoning

    # Strategic alignment (from align node)
    alignment_score: Optional[str]         # "High" | "Medium" | "Low" | "Anti-goal"
    alignment_reasoning: Optional[str]     # Why this alignment score
    related_strategy_items: Optional[list[str]]  # e.g., ["S1", "S3", "S5"]

    # Priority (from prioritize node)
    impact_priority: Optional[str]         # Original impact-based priority (preserved)
    priority_derivation: Optional[str]     # "(impact: Medium, alignment: High) → High"

    # Human decision (from human_review node)
    final_category: Optional[str]          # After human approval/override
    final_priority: Optional[str]          # After impact × alignment matrix
    human_reasoning: Optional[str]         # Human's additional notes (if any)

    # Workflow status
    status: str  # "pending" | "classified" | "aligned" | "prioritized" | "reviewed" | "saved"


class Classification(BaseModel):
    """Structured output schema for the classify node."""
    category: Literal[
        "Opportunity", "Pain", "Bug", "Usability",
        "Performance", "New Feature Request", "Pricing Concern"
    ] = Field(description="The category that best fits this feedback")

    priority: Literal["High", "Medium", "Low"] = Field(
        description="Priority based on impact and urgency"
    )

    reasoning: str = Field(
        description="Brief explanation of why this category and priority were chosen"
    )


class DecisionLog(TypedDict):
    """Schema for one row in decisions.csv."""
    feedback_id: str
    timestamp: str

    # Agent suggestions
    agent_category: str
    agent_priority: str
    agent_reasoning: str

    # Strategic alignment
    impact_priority: Optional[str]
    alignment_score: Optional[str]
    final_priority: Optional[str]

    # Human decisions
    human_category: str
    human_priority: str

    # Computed
    category_match: bool
    priority_match: bool
    full_match: bool


# --- Interview Transcript Extraction (optional extension) ---

class ExtractedItem(BaseModel):
    """One distinct feedback point extracted from a longer source."""
    text: str = Field(
        description="Self-contained description (3-4 sentences max) with problem statement, quantified impact, and observable consequences"
    )
    source_quote: str = Field(
        description="Direct quote from the source material supporting this item"
    )
    item_type: Literal[
        "Pain", "Bug", "Opportunity", "Feature Request",
        "Pricing", "Performance", "Usability", "Other"
    ] = Field(
        description="Preliminary classification hint (not binding for final classification)"
    )


class ExtractionResult(BaseModel):
    """Collection of items extracted from a single source."""
    items: list[ExtractedItem]


# --- Strategic Alignment ---

class StrategyItem(BaseModel):
    """Universal structure that can represent any strategy format."""
    id: str = Field(
        description="Simple sequential ID like 'S1', 'S2', 'S3'"
    )
    type: Literal["objective", "metric", "theme", "persona", "anti-goal", "initiative"] = Field(
        description="Type of strategic element"
    )
    title: str = Field(
        description="Short summary of this strategic item"
    )
    description: str = Field(
        description="Full context and details"
    )
    importance: Literal["critical", "high", "medium"] = Field(
        description="Importance level inferred from language cues and quantified targets"
    )


class NormalizedStrategy(BaseModel):
    """Complete normalized strategy document."""
    vision: str = Field(
        description="Overall mission/vision statement (if present in source)"
    )
    time_horizon: str = Field(
        description="Time period for this strategy, e.g. 'Q1 2025', '2025', 'Next 6 months'"
    )
    items: list[StrategyItem] = Field(
        description="List of strategic elements extracted from the source document"
    )


class AlignmentAssessment(BaseModel):
    """Structured output for the align node."""
    alignment_score: Literal["High", "Medium", "Low", "Anti-goal"] = Field(
        description="How well this request aligns with current strategy"
    )
    related_strategy_items: list[str] = Field(
        description="List of strategy item IDs this relates to, e.g. ['S1', 'S2']"
    )
    reasoning: str = Field(
        description="Explain the strategic relevance or why it's an anti-goal"
    )
