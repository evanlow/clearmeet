"""
OpenAI LLM integration for MOM generation.

Uses structured output (JSON) to generate meeting minutes.
"""
from typing import Optional, Any
import json
from openai import OpenAI
from openai import OpenAIError


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
            - objective: Meeting objective/purpose
            - decisions: List of decisions made
            - action_items: List of action items with owner and deadline
            - attendees: List of attendees (if extractable)
            - summary: Brief meeting summary
            
        Raises:
            ValueError: If transcript is empty
            OpenAIError: If API call fails
        """
        if not transcript or not transcript.strip():
            raise ValueError("Transcript cannot be empty")
        
        # Build system prompt
        system_prompt = """You are an expert at creating clear, concise Minutes of Meeting (MOM).
        
Your task is to analyze meeting transcripts and extract:
1. Meeting objective/purpose
2. Key decisions made (be specific)
3. Action items with owners and deadlines
4. List of attendees (if mentioned)
5. Brief summary of discussion

Return your response as valid JSON with this exact structure:
{
  "objective": "string",
  "decisions": ["decision1", "decision2", ...],
  "action_items": [
    {"task": "string", "owner": "string", "deadline": "string or null"},
    ...
  ],
  "attendees": ["name1", "name2", ...],
  "summary": "string"
}

Be specific and actionable. Use professional business language."""
        
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
            
            # Validate structure
            if not self._validate_mom_structure(mom_data):
                raise ValueError("Invalid MOM structure returned from API")
            
            return mom_data
            
        except json.JSONDecodeError as e:
            raise ValueError(f"Failed to parse JSON response: {e}")
        except OpenAIError as e:
            raise OpenAIError(f"OpenAI API error: {e}")
    
    @staticmethod
    def _validate_mom_structure(data: dict) -> bool:
        """
        Validate that MOM data has required structure.
        
        Args:
            data: MOM data dictionary
            
        Returns:
            True if valid structure
        """
        required_keys = {'objective', 'decisions', 'action_items', 'attendees', 'summary'}
        
        if not all(key in data for key in required_keys):
            return False
        
        # Validate types
        if not isinstance(data['objective'], str):
            return False
        if not isinstance(data['decisions'], list):
            return False
        if not isinstance(data['action_items'], list):
            return False
        if not isinstance(data['attendees'], list):
            return False
        if not isinstance(data['summary'], str):
            return False
        
        # Validate action items structure
        for item in data['action_items']:
            if not isinstance(item, dict):
                return False
            if not all(key in item for key in ['task', 'owner', 'deadline']):
                return False
        
        return True
    
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
        
        # Summary
        if mom_data.get('summary'):
            lines.append("SUMMARY:")
            lines.append(mom_data['summary'])
            lines.append("")
        
        # Decisions
        if mom_data.get('decisions'):
            lines.append("DECISIONS MADE:")
            for i, decision in enumerate(mom_data['decisions'], 1):
                lines.append(f"  {i}. {decision}")
            lines.append("")
        
        # Action Items
        if mom_data.get('action_items'):
            lines.append("ACTION ITEMS:")
            for i, item in enumerate(mom_data['action_items'], 1):
                task = item.get('task', 'N/A')
                owner = item.get('owner', 'Unassigned')
                deadline = item.get('deadline') or 'No deadline specified'
                lines.append(f"  {i}. {task}")
                lines.append(f"     Owner: {owner}")
                lines.append(f"     Deadline: {deadline}")
            lines.append("")
        
        lines.append("=" * 60)
        lines.append("End of Minutes")
        
        return "\n".join(lines)
