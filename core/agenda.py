"""
Agenda planning and AI-assisted generation.

Supports structured agenda building for pre-meeting planning (Step 2).
"""
import os
import json
from typing import Optional
from openai import OpenAI

from core.schema import MeetingObjective, AgendaItem
from config import logger


class AgendaBuilder:
    """Manage agenda items and AI-assisted generation."""
    
    @staticmethod
    def generate_agenda_with_ai(meeting_objective: MeetingObjective) -> list[AgendaItem]:
        """
        Generate AI-assisted agenda suggestions based on meeting objective.
        
        Args:
            meeting_objective: Structured meeting objective
            
        Returns:
            List of suggested agenda items
            
        Raises:
            ValueError: If AI generation fails or returns invalid data
        """
        api_key = os.getenv('OPENAI_API_KEY')
        if not api_key:
            raise ValueError("OPENAI_API_KEY environment variable not set")
        
        client = OpenAI(api_key=api_key)
        
        # Construct prompt for agenda generation
        prompt = f"""You are a corporate meeting facilitator helping managers plan structured, outcome-driven meetings.

Given the following meeting objective, generate a logical, time-boxed agenda with 4-6 items.

**Business Issue:**
{meeting_objective.business_issue}

**Meeting Objective:**
{meeting_objective.objective}

**Expected Output:**
{meeting_objective.expected_output}

**Requirements:**
1. Create 4-6 agenda items that logically flow toward the expected output
2. Allocate realistic time (5-30 minutes per item)
3. Start with context-setting, end with action item assignment
4. Keep titles concise and action-oriented
5. Total meeting duration should be 60-90 minutes

Return ONLY valid JSON in this exact format:
{{
  "agenda_items": [
    {{
      "title": "Review current situation and context",
      "duration_minutes": 10,
      "description": "Brief overview of current status"
    }},
    ...
  ]
}}"""
        
        try:
            logger.info("Requesting AI agenda generation from OpenAI")
            response = client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {"role": "system", "content": "You are a corporate meeting planning assistant. Always return valid JSON."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.7,
                max_tokens=1000
            )
            
            response_text = response.choices[0].message.content.strip()
            logger.debug(f"AI agenda response (raw): {response_text[:500]}")
            
            # Parse JSON response
            try:
                data = json.loads(response_text)
            except json.JSONDecodeError:
                # Try to extract JSON from markdown code blocks
                if "```json" in response_text:
                    json_start = response_text.find("```json") + 7
                    json_end = response_text.find("```", json_start)
                    response_text = response_text[json_start:json_end].strip()
                    data = json.loads(response_text)
                elif "```" in response_text:
                    json_start = response_text.find("```") + 3
                    json_end = response_text.find("```", json_start)
                    response_text = response_text[json_start:json_end].strip()
                    data = json.loads(response_text)
                else:
                    raise ValueError("AI response is not valid JSON")
            
            # Validate structure
            if "agenda_items" not in data or not isinstance(data["agenda_items"], list):
                raise ValueError("AI response missing 'agenda_items' array")
            
            # Parse into AgendaItem models
            agenda_items = []
            for item_data in data["agenda_items"]:
                try:
                    agenda_item = AgendaItem(**item_data)
                    agenda_items.append(agenda_item)
                except Exception as e:
                    logger.warning(f"Skipping invalid agenda item: {item_data} - {e}")
                    continue
            
            if not agenda_items:
                raise ValueError("AI generated no valid agenda items")
            
            logger.info(f"Successfully generated {len(agenda_items)} agenda items")
            return agenda_items
            
        except Exception as e:
            logger.error(f"AI agenda generation failed: {e}")
            raise ValueError(f"Failed to generate agenda: {str(e)}")
    
    @staticmethod
    def calculate_total_duration(agenda_items: list[AgendaItem]) -> int:
        """
        Calculate total meeting duration from agenda items.
        
        Args:
            agenda_items: List of agenda items
            
        Returns:
            Total duration in minutes
        """
        return sum(item.duration_minutes for item in agenda_items)
    
    @staticmethod
    def validate_agenda_timing(agenda_items: list[AgendaItem], max_duration: int = 120) -> tuple[bool, Optional[str]]:
        """
        Validate agenda timing constraints.
        
        Args:
            agenda_items: List of agenda items
            max_duration: Maximum allowed meeting duration in minutes
            
        Returns:
            Tuple of (is_valid, error_message)
        """
        if not agenda_items:
            return False, "Agenda must have at least one item"
        
        total_duration = AgendaBuilder.calculate_total_duration(agenda_items)
        
        if total_duration > max_duration:
            return False, f"Total duration ({total_duration} min) exceeds maximum ({max_duration} min)"
        
        if total_duration < 15:
            return False, "Total duration should be at least 15 minutes for a meaningful meeting"
        
        return True, None
    
    @staticmethod
    def serialize_agenda(agenda_items: list[AgendaItem]) -> list[dict]:
        """
        Serialize agenda items to dictionaries for session storage.
        
        Args:
            agenda_items: List of AgendaItem objects
            
        Returns:
            List of dictionaries
        """
        return [item.model_dump() for item in agenda_items]
    
    @staticmethod
    def deserialize_agenda(agenda_data: list[dict]) -> list[AgendaItem]:
        """
        Deserialize agenda data from session storage.
        
        Args:
            agenda_data: List of agenda item dictionaries
            
        Returns:
            List of AgendaItem objects
        """
        return [AgendaItem(**item_data) for item_data in agenda_data]
