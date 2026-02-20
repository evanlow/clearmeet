"""
Pydantic models for MOM data structures.

Provides type-safe validation and serialization for meeting minutes.
"""
from pydantic import BaseModel, Field, ValidationError, field_validator
from typing import Optional


class MeetingObjective(BaseModel):
    """Structured meeting objective definition (Step 1 - Dyna Electric training)."""
    
    business_issue: str = Field(..., min_length=10, description="Business issue requiring discussion")
    objective: str = Field(..., min_length=15, description="Specific outcome-based meeting objective")
    expected_output: str = Field(..., min_length=10, description="Expected decision or output")
    
    @field_validator('business_issue')
    @classmethod
    def business_issue_not_empty(cls, v: str) -> str:
        """Ensure business issue is meaningful."""
        if not v or len(v.strip()) < 10:
            raise ValueError("Business issue must be at least 10 characters")
        return v.strip()
    
    @field_validator('objective')
    @classmethod
    def objective_not_empty(cls, v: str) -> str:
        """Ensure objective is specific and outcome-based."""
        if not v or len(v.strip()) < 15:
            raise ValueError("Objective must be at least 15 characters and outcome-based")
        return v.strip()
    
    @field_validator('expected_output')
    @classmethod
    def expected_output_not_empty(cls, v: str) -> str:
        """Ensure expected output is clear."""
        if not v or len(v.strip()) < 10:
            raise ValueError("Expected output must be at least 10 characters")
        return v.strip()
    
    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "business_issue": "Delivery delays affecting Q2 targets due to vendor coordination issues",
                    "objective": "Align interdepartmental action plan to resolve vendor coordination and recover timeline",
                    "expected_output": "Approved action plan with clear ownership and 2-week checkpoint schedule"
                }
            ]
        }
    }


class AgendaItem(BaseModel):
    """Single agenda item for structured meeting planning (Step 2 - Dyna Electric training)."""
    
    title: str = Field(..., min_length=3, description="Agenda item title")
    duration_minutes: int = Field(..., ge=1, le=180, description="Estimated duration in minutes")
    description: Optional[str] = Field(None, description="Additional context or notes")
    
    @field_validator('title')
    @classmethod
    def title_not_empty(cls, v: str) -> str:
        """Ensure title is meaningful."""
        if not v or len(v.strip()) < 3:
            raise ValueError("Agenda item title must be at least 3 characters")
        return v.strip()
    
    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "title": "Review current vendor performance metrics",
                    "duration_minutes": 15,
                    "description": "Present Q1 data from procurement dashboard"
                },
                {
                    "title": "Identify root causes and blockers",
                    "duration_minutes": 20,
                    "description": "Facilitated discussion with ops, procurement, and logistics"
                }
            ]
        }
    }


class Decision(BaseModel):
    """A decision made during the meeting."""
    text: str = Field(..., min_length=3, description="Decision text")

    @field_validator('text')
    @classmethod
    def text_not_empty(cls, v: str) -> str:
        """Ensure decision text is meaningful."""
        if not v or len(v.strip()) < 3:
            raise ValueError("Decision text must be at least 3 characters")
        return v.strip()

    model_config = {
        "json_schema_extra": {
            "examples": [
                {"text": "Approved budget increase of 15% for Q2 marketing"}
            ]
        }
    }


class ActionItem(BaseModel):
    """An action item from the meeting."""
    owner: str = Field(..., min_length=0, description="Who is responsible (empty if unknown)")
    action: str = Field(..., min_length=3, description="What needs to be done")
    deadline: Optional[str] = Field(None, description="Deadline (date string or 'ASAP')")
    status: str = Field(default="Open", description="Status: Open, In Progress, Completed")

    @field_validator('owner')
    @classmethod
    def owner_not_placeholder(cls, v: str) -> str:
        """Ensure owner is not a placeholder value."""
        if not v or not v.strip():
            return ""
        if v.strip().lower() in ['n/a', 'none', 'unassigned', 'tbd', 'to be determined']:
            raise ValueError("Action item owner must be a real name or empty when unknown")
        return v.strip()

    @field_validator('action')
    @classmethod
    def action_not_empty(cls, v: str) -> str:
        """Ensure action description is meaningful."""
        if not v or len(v.strip()) < 3:
            raise ValueError("Action item must include a clear action")
        return v.strip()

    @field_validator('status')
    @classmethod
    def status_valid(cls, v: str) -> str:
        """Ensure status is valid."""
        valid_statuses = ['open', 'in progress', 'completed', 'blocked', 'cancelled']
        if v.strip().lower() not in valid_statuses:
            return "Open"
        return v.strip()

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "action": "Schedule follow-up meeting with design team",
                    "owner": "Alice Johnson",
                    "deadline": "2026-02-20",
                    "status": "Open"
                }
            ]
        }
    }


class MeetingMOM(BaseModel):
    """Complete Minutes of Meeting structure."""

    title: str = Field(..., min_length=3, description="Meeting title")
    date: str = Field(..., min_length=4, description="Meeting date (YYYY-MM-DD or similar)")
    objective: str = Field(..., min_length=10, description="Meeting purpose and objective")
    decisions: list[Decision] = Field(..., description="Decisions made during meeting")
    action_items: list[ActionItem] = Field(..., description="Action items with owners")

    attendees: Optional[list[str]] = Field(None, description="List of attendee names")
    parking_lot: Optional[list[str]] = Field(None, description="Items deferred for future discussion")
    notes: Optional[str] = Field(None, description="Additional notes or context")
    confidentiality_flags: Optional[list[str]] = Field(None, description="Confidentiality or sensitivity markers")

    @field_validator('title')
    @classmethod
    def title_not_empty(cls, v: str) -> str:
        """Ensure title is meaningful."""
        if not v or len(v.strip()) < 3:
            raise ValueError("Title must be at least 3 characters")
        return v.strip()

    @field_validator('objective')
    @classmethod
    def objective_not_empty(cls, v: str) -> str:
        """Ensure objective is meaningful."""
        if not v or len(v.strip()) < 10:
            raise ValueError("Objective must be at least 10 characters and describe the meeting purpose")
        return v.strip()

    @classmethod
    def get_json_schema(cls) -> dict:
        """
        Get JSON schema for LLM instruction.

        Returns:
            JSON schema dictionary suitable for OpenAI structured output
        """
        return cls.model_json_schema()

    @classmethod
    def get_json_schema_for_llm(cls) -> dict:
        """
        Get simplified JSON schema optimized for LLM prompts.

        Returns:
            Simplified schema dict for including in LLM prompts
        """
        return {
            "type": "object",
            "properties": {
                "title": {
                    "type": "string",
                    "description": "Meeting title"
                },
                "date": {
                    "type": "string",
                    "description": "Meeting date (YYYY-MM-DD or similar)"
                },
                "objective": {
                    "type": "string",
                    "description": "Meeting objective/purpose (minimum 10 characters)"
                },
                "attendees": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "List of attendee names (optional)"
                },
                "decisions": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "text": {"type": "string", "description": "Decision text"}
                        },
                        "required": ["text"]
                    },
                    "description": "List of decisions made (be specific)"
                },
                "action_items": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "owner": {"type": "string", "description": "Who is responsible (empty string if unknown; never use placeholders)"},
                            "action": {"type": "string", "description": "What needs to be done"},
                            "deadline": {"type": "string", "description": "When it's due (date or '' if unknown)"},
                            "status": {"type": "string", "description": "Status (default: 'Open')"}
                        },
                        "required": ["owner", "action"]
                    }
                },
                "parking_lot": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Items deferred for future discussion (optional)"
                },
                "notes": {
                    "type": "string",
                    "description": "Additional notes or context (optional)"
                },
                "confidentiality_flags": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Confidentiality or sensitivity markers (optional)"
                }
            },
            "required": ["title", "date", "objective", "decisions", "action_items"]
        }

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "title": "Q2 Planning Meeting",
                    "date": "2026-02-16",
                    "objective": "Quarterly planning meeting to review Q1 performance and set Q2 goals",
                    "attendees": ["Alice Johnson", "Bob Smith", "Carol Williams"],
                    "decisions": [
                        {"text": "Approved 15% budget increase for Q2 marketing"},
                        {"text": "Postpone product launch to March 15"}
                    ],
                    "action_items": [
                        {
                            "action": "Create detailed Q2 marketing plan",
                            "owner": "Alice Johnson",
                            "deadline": "2026-02-25",
                            "status": "Open"
                        },
                        {
                            "action": "Update product roadmap with new launch date",
                            "owner": "Bob Smith",
                            "deadline": "2026-02-20",
                            "status": "Open"
                        }
                    ],
                    "parking_lot": ["Discuss Q3 hiring plan"],
                    "notes": "Follow up with Finance on revised budget assumptions.",
                    "confidentiality_flags": ["Internal", "Financial"]
                }
            ]
        }
    }


def validate_mom_dict(data: dict) -> MeetingMOM:
    """
    Validate MOM dictionary and return typed model.

    Args:
        data: Raw MOM data (typically from LLM response)

    Returns:
        Validated MeetingMOM instance

    Raises:
        ValueError: With clear error messages about what's invalid
    """
    try:
        return MeetingMOM(**data)
    except ValidationError as exc:
        raise ValueError(f"Invalid MOM data: {exc}")
