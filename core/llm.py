"""
OpenAI LLM integration for MOM generation.

Uses structured output (JSON) to generate meeting minutes with Pydantic validation.
"""
from typing import Optional, Any
import json
from openai import OpenAI
from openai import OpenAIError
from core.schema import MeetingMOM, validate_mom_dict


class MOMGenerator:
    """Generate Minutes of Meeting using OpenAI API."""
    
    def __init__(self, api_key: str, model: str = "gpt-4o-mini", temperature: float = 0.3):
        """
        Initialize MOM generator.
        
        Args:
            api_key: OpenAI API key
            model: Model identifier
            temperature: Sampling temperature (0.0-1.0, lower is more focused)
        """
        if not api_key:
            raise ValueError("API key is required")
        
        self.client = OpenAI(api_key=api_key)
        self.model = model
        self.temperature = temperature
    
    def generate_mom(self, transcript: str, additional_context: Optional[str] = None) -> dict[str, Any]:
        """
        Generate structured MOM from transcript.
        
        Args:
            transcript: Meeting transcript text
            additional_context: Optional context (meeting purpose, attendees, etc.)
            
        Returns:
            Structured MOM data as dictionary with keys:
            - title: Meeting title
            - date: Meeting date
            - objective: Meeting objective/purpose
            - decisions: List of decisions made
            - action_items: List of action items with owner and deadline
            - attendees: List of attendees (if extractable)
            - parking_lot: List of deferred items (optional)
            - notes: Additional notes (optional)
            - confidentiality_flags: Confidentiality tags (optional)
            
        Raises:
            ValueError: If transcript is empty
            OpenAIError: If API call fails
        """
        if not transcript or not transcript.strip():
            raise ValueError("Transcript cannot be empty")
        
        # Build system prompt with Pydantic schema
        json_schema = MeetingMOM.get_json_schema_for_llm()
        system_prompt = f"""You are an expert at creating clear, concise Minutes of Meeting (MOM).
        
Your task is to analyze meeting transcripts and extract:
1. Meeting title and date
2. Meeting objective/purpose
3. Key decisions made (be specific)
4. Action items with owners and deadlines
5. List of attendees (if mentioned)
6. Parking lot items (if mentioned)
7. Notes or confidentiality flags (if relevant)

    Return your response as valid JSON with this exact structure:
{json_schema}

Be specific and actionable. Use professional business language.
CRITICAL: Ensure 'owner' fields are actual names, not placeholders like 'TBD' or 'To be assigned'."""
        
        # Build user prompt
        user_prompt = f"Meeting Transcript:\n\n{transcript}"
        if additional_context:
            user_prompt = f"Context: {additional_context}\n\n{user_prompt}"
        
        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                temperature=self.temperature,
                response_format={"type": "json_object"}
            )
            
            # Extract and parse JSON response
            content = response.choices[0].message.content
            if not content:
                raise ValueError("Empty response from API")
            
            mom_data = json.loads(content)
            
            # Validate structure using Pydantic
            try:
                validated_mom = validate_mom_dict(mom_data)
                # Return dict for backward compatibility
                return validated_mom.model_dump(exclude_none=True)
            except ValueError as e:
                raise ValueError(f"Invalid MOM structure returned from API: {e}")
            
        except json.JSONDecodeError as e:
            raise ValueError(f"Failed to parse JSON response: {e}")
        except OpenAIError as e:
            raise OpenAIError(f"OpenAI API error: {e}")
    
    def render_mom_text(self, mom_data: dict) -> str:
        """
        Render structured MOM data into formatted text.
        
        Args:
            mom_data: Structured MOM data
            
        Returns:
            Formatted MOM text
        """
        if not mom_data:
            return ""
        
        lines = []
        lines.append("MINUTES OF MEETING")
        lines.append("=" * 60)
        lines.append("")
        
        # Title and date
        if mom_data.get('title'):
            lines.append("MEETING TITLE:")
            lines.append(mom_data['title'])
            lines.append("")
        if mom_data.get('date'):
            lines.append("MEETING DATE:")
            lines.append(mom_data['date'])
            lines.append("")

        # Objective
        if mom_data.get('objective'):
            lines.append("MEETING OBJECTIVE:")
            lines.append(mom_data['objective'])
            lines.append("")
        
        # Attendees
        if mom_data.get('attendees'):
            lines.append("ATTENDEES:")
            for attendee in mom_data['attendees']:
                lines.append(f"  • {attendee}")
            lines.append("")
        
        # Decisions
        if mom_data.get('decisions'):
            lines.append("DECISIONS MADE:")
            for i, decision in enumerate(mom_data['decisions'], 1):
                text = decision.get('text') if isinstance(decision, dict) else str(decision)
                lines.append(f"  {i}. {text}")
            lines.append("")
        
        # Action Items
        if mom_data.get('action_items'):
            lines.append("ACTION ITEMS:")
            for i, item in enumerate(mom_data['action_items'], 1):
                action = item.get('action', 'N/A')
                owner = item.get('owner', 'Unassigned')
                deadline = item.get('deadline') or 'No deadline specified'
                status = item.get('status') or 'Open'
                lines.append(f"  {i}. {action}")
                lines.append(f"     Owner: {owner}")
                lines.append(f"     Deadline: {deadline}")
                lines.append(f"     Status: {status}")
            lines.append("")

        # Parking lot
        if mom_data.get('parking_lot'):
            lines.append("PARKING LOT:")
            for i, item in enumerate(mom_data['parking_lot'], 1):
                lines.append(f"  {i}. {item}")
            lines.append("")

        # Notes
        if mom_data.get('notes'):
            lines.append("NOTES:")
            lines.append(mom_data['notes'])
            lines.append("")

        # Confidentiality
        if mom_data.get('confidentiality_flags'):
            lines.append("CONFIDENTIALITY:")
            for flag in mom_data['confidentiality_flags']:
                lines.append(f"  • {flag}")
            lines.append("")
        
        lines.append("=" * 60)
        lines.append("End of Minutes")
        
        return "\n".join(lines)
