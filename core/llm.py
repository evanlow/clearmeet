"""
OpenAI LLM integration for MOM generation and transcription.

Uses structured output (JSON) to generate meeting minutes with Pydantic validation.
"""
from typing import Optional, Any, Callable
import json
import os

from openai import OpenAI
from openai import OpenAIError

from core.audio import AudioTranscriber
from core.schema import MeetingMOM, validate_mom_dict


def _require_api_key() -> str:
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise ValueError("OPENAI_API_KEY environment variable is required")
    return api_key


def _get_llm_model() -> str:
    return os.getenv("OPENAI_MODEL", "gpt-4o-mini")


def _get_transcribe_model() -> str:
    return os.getenv("OPENAI_TRANSCRIBE_MODEL") or os.getenv("WHISPER_MODEL", "whisper-1")


def _get_temperature() -> float:
    try:
        return float(os.getenv("OPENAI_TEMPERATURE", "0.3"))
    except ValueError:
        return 0.3


def _get_client() -> OpenAI:
    return OpenAI(api_key=_require_api_key())


def _augment_missing_action_notes(mom_data: dict) -> dict:
    action_items = mom_data.get("action_items", [])
    if not action_items:
        return mom_data

    missing_owner = []
    missing_deadline = []

    for index, item in enumerate(action_items, start=1):
        owner = (item.get("owner") or "").strip()
        deadline = (item.get("deadline") or "").strip()
        if not owner:
            missing_owner.append(index)
        if not deadline:
            missing_deadline.append(index)

    if not missing_owner and not missing_deadline:
        return mom_data

    note_lines = []
    if missing_owner:
        note_lines.append(f"Missing owners for action items: {', '.join(map(str, missing_owner))}.")
    if missing_deadline:
        note_lines.append(f"Missing deadlines for action items: {', '.join(map(str, missing_deadline))}.")

    existing_notes = (mom_data.get("notes") or "").strip()
    combined_notes = " ".join([existing_notes, " ".join(note_lines)]).strip()
    mom_data["notes"] = combined_notes

    flags = mom_data.get("confidentiality_flags") or []
    if missing_owner and "missing_owner" not in flags:
        flags.append("missing_owner")
    if missing_deadline and "missing_deadline" not in flags:
        flags.append("missing_deadline")
    mom_data["confidentiality_flags"] = flags if flags else None

    return mom_data


def transcribe_audio(file_path: str, progress_callback: Optional[Callable[[dict], None]] = None) -> str:
    """
    Transcribe audio file to text using OpenAI Whisper.

    Args:
        file_path: Path to audio file
        progress_callback: Optional callback function(dict) called after each chunk
                         dict contains: {'chunk': #, 'total_chunks': #, 'duration_sec': #}

    Returns:
        Transcribed text
    """
    if not file_path:
        raise ValueError("Audio file path is required")

    api_key = _require_api_key()
    model = _get_transcribe_model()
    transcriber = AudioTranscriber(api_key=api_key, model=model)
    chunk_size_mb = int(os.getenv("CHUNK_SIZE_MB", "20"))

    print(f"[LLM] transcribe_audio called with progress_callback={progress_callback}")
    try:
        result = transcriber.transcribe_audio(file_path, chunk_size_mb=chunk_size_mb, progress_callback=progress_callback)
        print(f"[LLM] transcriber.transcribe_audio returned successfully")
        return result
    except (FileNotFoundError, ValueError):
        raise
    except OpenAIError:
        raise RuntimeError("Audio transcription failed. Please try again.")
    except Exception:
        raise RuntimeError("Unexpected error during audio transcription.")


def extract_mom_from_transcript(
    transcript: str,
    objective: Optional[str] = None,
    instructions: Optional[str] = None
) -> dict[str, Any]:
    """
    Extract structured MOM from transcript using OpenAI.

    Args:
        transcript: Meeting transcript text
        objective: Optional objective provided by user
        instructions: Optional extraction instructions

    Returns:
        Structured MOM data as dictionary
    """
    if not transcript or not transcript.strip():
        raise ValueError("Transcript cannot be empty")

    json_schema = MeetingMOM.get_json_schema_for_llm()
    system_prompt = f"""You are an expert at creating clear, concise Minutes of Meeting (MOM).

Return ONLY valid JSON (no markdown, no commentary) matching this structure:
{json_schema}

Rules:
- Do NOT invent owners or deadlines.
- If an owner or deadline is missing, set it to "".
- When any owner/deadline is missing, add a note in `notes` and add a flag in `confidentiality_flags`.
- Use professional business language and be specific.
"""

    user_sections = [f"Meeting Transcript:\n\n{transcript}"]
    if objective:
        user_sections.insert(0, f"Objective (if known): {objective}")
    if instructions:
        user_sections.insert(0, f"Additional instructions: {instructions}")
    user_prompt = "\n\n".join(user_sections)

    client = _get_client()
    model = _get_llm_model()
    temperature = _get_temperature()

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt}
    ]

    for attempt in range(2):
        try:
            response = client.chat.completions.create(
                model=model,
                messages=messages,
                temperature=temperature,
                response_format={"type": "json_object"}
            )
            content = response.choices[0].message.content
            if not content:
                raise ValueError("Empty response from API")

            mom_data = json.loads(content)
            if not isinstance(mom_data, dict):
                raise ValueError("Response JSON must be an object")

            validated_mom = validate_mom_dict(mom_data)
            normalized = validated_mom.model_dump(exclude_none=True)
            return _augment_missing_action_notes(normalized)
        except json.JSONDecodeError:
            if attempt == 0:
                messages.append({
                    "role": "system",
                    "content": "Return ONLY a valid JSON object. No markdown or extra text."
                })
                continue
            raise ValueError("Failed to parse JSON response from model.")
        except ValueError as e:
            raise ValueError(f"Invalid MOM structure returned from API: {e}")
        except OpenAIError:
            raise RuntimeError("OpenAI API request failed. Please try again.")
        except Exception:
            raise RuntimeError("Unexpected error during MOM extraction.")

    raise ValueError("Failed to parse JSON response from model.")


def render_mom_text(mom_data: dict) -> str:
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
            owner = item.get('owner') or 'Unassigned'
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
