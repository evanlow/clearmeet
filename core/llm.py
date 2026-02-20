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
from core.render import mom_to_text
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
    instructions: Optional[str] = None,
    planned_objective: Optional[dict] = None,
    agenda_items: Optional[list[dict]] = None
) -> dict[str, Any]:
    """
    Extract structured MOM from transcript using OpenAI.

    Args:
        transcript: Meeting transcript text
        objective: Optional objective provided by user
        instructions: Optional extraction instructions
        planned_objective: Optional pre-defined meeting objective from Step 1 (dict with business_issue, objective, expected_output)
        agenda_items: Optional agenda items from Step 2 (list of dicts with title, duration_minutes, description)

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

    user_sections = []
    
    # Add planned objective if available (Step 1 data)
    if planned_objective:
        user_sections.append(f"""Planned Meeting Objective (from pre-meeting planning):
Business Issue: {planned_objective.get('business_issue', '')}
Objective: {planned_objective.get('objective', '')}
Expected Output: {planned_objective.get('expected_output', '')}

Use the planned objective as the primary objective for this MOM.""")
    
    # Add agenda if available (Step 2 data)
    if agenda_items:
        agenda_text = "Planned Agenda (from pre-meeting planning):\n"
        total_duration = 0
        for idx, item in enumerate(agenda_items, 1):
            duration = item.get('duration_minutes', 0)
            total_duration += duration
            agenda_text += f"{idx}. {item.get('title', '')} ({duration}min)"
            if item.get('description'):
                agenda_text += f" - {item.get('description')}"
            agenda_text += "\n"
        agenda_text += f"\nTotal planned duration: {total_duration}min"
        user_sections.append(agenda_text)
    
    # Add transcript
    user_sections.append(f"Meeting Transcript:\n\n{transcript}")
    
    # Add optional user-provided objective and instructions
    if objective:
        user_sections.insert(0, f"Additional objective context: {objective}")
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


def render_mom_text(
    mom_data: Optional[dict[str, Any]],
    agenda_items: Optional[list[dict]] = None
) -> str:
    """
    Render structured MOM data into formatted text, with fallback logic.

    Args:
        mom_data: Structured MOM data
        agenda_items: Optional list of planned agenda items

    Returns:
        Formatted MOM text string
    """
    if not mom_data:
        return ""

    try:
        typed_mom = validate_mom_dict(mom_data)
    except ValueError:
        decisions = []
        for decision in mom_data.get('decisions', []):
            if isinstance(decision, dict):
                text = (decision.get('text') or '').strip()
            else:
                text = str(decision).strip()
            if text:
                decisions.append({'text': text})

        action_items = []
        for item in mom_data.get('action_items', []):
            if not isinstance(item, dict):
                continue
            action = (item.get('action') or '').strip()
            if not action:
                continue
            action_items.append({
                'action': action,
                'owner': (item.get('owner') or '').strip(),
                'deadline': item.get('deadline') or None,
                'status': (item.get('status') or 'Open').strip() or 'Open',
            })

        fallback_data = {
            'title': (mom_data.get('title') or 'Meeting Minutes').strip() or 'Meeting Minutes',
            'date': (mom_data.get('date') or 'Unknown Date').strip() or 'Unknown Date',
            'objective': (mom_data.get('objective') or '').strip() or 'Objective not provided.',
            'decisions': decisions,
            'action_items': action_items,
            'attendees': mom_data.get('attendees'),
            'parking_lot': mom_data.get('parking_lot'),
            'notes': mom_data.get('notes'),
            'confidentiality_flags': mom_data.get('confidentiality_flags'),
        }

        if len(fallback_data['objective']) < 10:
            fallback_data['objective'] = 'Objective not provided.'
        if not fallback_data['decisions']:
            fallback_data['decisions'] = [{'text': 'No decisions documented.'}]

        try:
            typed_mom = validate_mom_dict(fallback_data)
        except ValueError:
            return ""

    return mom_to_text(typed_mom, agenda_items=agenda_items)
