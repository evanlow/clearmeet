"""
Pydantic models for MOM data structures.

Provides type-safe validation and serialization for meeting minutes.
"""
from pydantic import BaseModel, Field, field_validator
from typing import Optional
from datetime import datetime


class Decision(BaseModel):
    """A decision made during the meeting."""
    text: str = Field(..., min_length=5, description="Decision text")
    
    model_config = {
        "json_schema_extra": {
            "examples": [
                {"text": "Approved budget increase of 15% for Q2 marketing"}
            ]
        }
    }


class ActionItem(BaseModel):
    """An action item from the meeting."""
    task: str = Field(..., min_length=5, description="What needs to be done")
    owner: str = Field(..., min_length=1, description="Who is responsible")
    deadline: Optional[str] = Field(None, description="Deadline (date string or 'ASAP')")
    status: str = Field(default="Open", description="Status: Open, In Progress, Completed")
    
    @field_validator('owner')
    @classmethod
    def owner_not_placeholder(cls, v: str) -> str:
        """Ensure owner is not a placeholder value."""
        if v.strip().lower() in ['n/a', 'none', 'unassigned', '', 'tbd', 'to be determined']:
            raise ValueError("Action item must have a real owner assigned (not 'N/A', 'None', or 'Unassigned')")
        return v.strip()
    
    @field_validator('status')
    @classmethod
    def status_valid(cls, v: str) -> str:
        """Ensure status is valid."""
        valid_statuses = ['open', 'in progress', 'completed', 'blocked', 'cancelled']
        if v.strip().lower() not in valid_statuses:
            # Default to Open if invalid
            return "Open"
        return v.strip()
    
    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "task": "Schedule follow-up meeting with design team",
                    "owner": "Alice Johnson",
                    "deadline": "2026-02-20",
                    "status": "Open"
                }
            ]
        }
    }


class MeetingMOM(BaseModel):
    """Complete Minutes of Meeting structure."""
    
    # Core required fields
    objective: str = Field(..., min_length=10, description="Meeting purpose and objective")
    attendees: list[str] = Field(default_factory=list, description="List of attendee names")
    decisions: list[str] = Field(default_factory=list, description="Decisions made during meeting")
    action_items: list[ActionItem] = Field(default_factory=list, description="Action items with owners")
    summary: str = Field(..., min_length=10, description="Brief meeting summary")
    
    # Optional fields
    title: Optional[str] = Field(None, description="Meeting title")
    date: Optional[datetime] = Field(None, description="Meeting date")
    parking_lot: Optional[list[str]] = Field(None, description="Items deferred for future discussion")
    notes: Optional[str] = Field(None, description="Additional notes or context")
    confidentiality_flags: Optional[list[str]] = Field(None, description="Confidentiality or sensitivity markers")
    
    @field_validator('objective')
    @classmethod
    def objective_not_empty(cls, v: str) -> str:
        """Ensure objective is meaningful."""
        if not v or len(v.strip()) < 10:
            raise ValueError("Objective must be at least 10 characters and describe the meeting purpose")
        return v.strip()
    
    @field_validator('summary')
    @classmethod
    def summary_not_empty(cls, v: str) -> str:
        """Ensure summary is meaningful."""
        if not v or len(v.strip()) < 10:
            raise ValueError("Summary must be at least 10 characters")
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
                "objective": {
                    "type": "string",
                    "description": "Meeting objective/purpose (minimum 10 characters)"
                },
                "attendees": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "List of attendee names"
                },
                "decisions": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "List of decisions made (be specific)"
                },
                "action_items": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "task": {"type": "string", "description": "What needs to be done"},
                            "owner": {"type": "string", "description": "Who is responsible (must be a real name, not 'TBD')"},
                            "deadline": {"type": "string", "description": "When it's due (date or 'ASAP' or null)"},
                            "status": {"type": "string", "description": "Status (default: 'Open')"}
                        },
                        "required": ["task", "owner"]
                    }
                },
                "summary": {
                    "type": "string",
                    "description": "Brief summary of the meeting (minimum 10 characters)"
                }
            },
            "required": ["objective", "attendees", "decisions", "action_items", "summary"]
        }
    
    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "objective": "Quarterly planning meeting to review Q1 performance and set Q2 goals",
                    "attendees": ["Alice Johnson", "Bob Smith", "Carol Williams"],
                    "decisions": [
                        "Approved 15% budget increase for Q2 marketing",
                        "Decided to postpone product launch to March 15"
                    ],
                    "action_items": [
                        {
                            "task": "Create detailed Q2 marketing plan",
                            "owner": "Alice Johnson",
                            "deadline": "2026-02-25",
                            "status": "Open"
                        },
                        {
                            "task": "Update product roadmap with new launch date",
                            "owner": "Bob Smith",
                            "deadline": "2026-02-20",
                            "status": "Open"
                        }
                    ],
                    "summary": "Team reviewed Q1 performance metrics, discussed budget allocation for Q2, and adjusted product launch timeline based on development progress."
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
        ValidationError: With clear error messages about what's invalid
        
    Example:
        >>> data = {
        ...     "objective": "Plan Q2 strategy",
        ...     "attendees": ["Alice", "Bob"],
        ...     "decisions": ["Hire 2 engineers"],
        ...     "action_items": [{"task": "Post job", "owner": "Alice"}],
        ...     "summary": "Discussed hiring needs for Q2 expansion"
        ... }
        >>> mom = validate_mom_dict(data)
        >>> print(mom.objective)
        Plan Q2 strategy
    """
    return MeetingMOM(**data)
