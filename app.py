"""
ClearMeet Flask Application

Main Flask app with routes for MOM generation workflow.
"""
from flask import Flask, render_template, request, session, redirect, url_for, send_file, flash, g, jsonify
from flask_session import Session
from cachelib import SimpleCache
from werkzeug.utils import secure_filename
import os
import json
import logging
from io import BytesIO
from datetime import datetime, timezone
from typing import Optional
import threading
import uuid

from config import get_config, Config, logger
from core.parser import TranscriptParser
from core.llm import extract_mom_from_transcript, render_mom_text, transcribe_audio
from core.audio import AudioTranscriber
from core.render import mom_to_text, apply_user_edits
from core.schema import validate_mom_dict, MeetingMOM, MeetingObjective, AgendaItem
from core.validation import MOMValidator, ValidationItem
from core.export import PDFExporter
from core.pdf_export import export_mom_pdf
from core.agenda import AgendaBuilder

# Module-level progress tracking (shared across requests)
# Use a lock for thread-safe updates
_progress_lock = threading.Lock()
_progress_state = {}


def create_app(config_name: Optional[str] = None) -> Flask:
    """
    Application factory function.
    
    Args:
        config_name: Configuration environment name
        
    Returns:
        Configured Flask application
    """
    app = Flask(__name__)
    
    # Load configuration
    config_class = get_config(config_name)
    app.config.from_object(config_class)
    
    # Initialize cachelib for server-side sessions (prevents cookie size limits)
    app.config['SESSION_CACHELIB'] = SimpleCache()
    logger.info(f"Session backend initialized: {app.config['SESSION_TYPE']}")
    logger.info(f"Session cache instance: {type(app.config['SESSION_CACHELIB']).__name__}")
    
    # Initialize Flask-Session for server-side sessions
    Session(app)
    logger.info("Flask-Session initialized successfully")
    
    # Validate configuration
    is_valid, error_message = Config.validate_config()
    if not is_valid:
        raise ValueError(f"Configuration error: {error_message}")
    
    # Ensure upload folder exists
    os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
    
    # Initialize components
    pdf_exporter = PDFExporter()

    def _sanitize_text(value: Optional[str], max_len: int = 20000) -> str:
        if not value:
            return ''
        cleaned = value.replace('\x00', '').strip()
        return cleaned[:max_len]

    def _persist_transcript(text: str) -> tuple[str, Optional[str]]:
        """Persist transcript text safely without overflowing session cookies."""
        preview_limit = 2000
        if len(text) <= preview_limit:
            return text, None

        transcript_dir = os.path.join(app.config['UPLOAD_FOLDER'], 'transcripts')
        os.makedirs(transcript_dir, exist_ok=True)
        transcript_id = f"transcript_{uuid.uuid4().hex}.txt"
        transcript_path = os.path.join(transcript_dir, transcript_id)

        with open(transcript_path, 'w', encoding='utf-8') as handle:
            handle.write(text)

        preview = text[:preview_limit].rstrip() + "..."
        return preview, transcript_path

    def _persist_mom_text(text: str) -> tuple[str, Optional[str]]:
        """Persist MOM text if large; return text (or preview) and file path."""
        preview_limit = 5000
        if len(text) <= preview_limit:
            return text, None

        mom_dir = os.path.join(app.config['UPLOAD_FOLDER'], 'mom_text')
        os.makedirs(mom_dir, exist_ok=True)
        mom_id = f"mom_{uuid.uuid4().hex}.txt"
        mom_path = os.path.join(mom_dir, mom_id)

        with open(mom_path, 'w', encoding='utf-8') as handle:
            handle.write(text)

        preview = text[:preview_limit].rstrip() + "..."
        return preview, mom_path

    def _load_text_from_path(path: Optional[str]) -> Optional[str]:
        if not path:
            return None
        if not os.path.exists(path):
            return None
        with open(path, 'r', encoding='utf-8') as handle:
            return handle.read()
    
    # Routes
    @app.route('/')
    def index():
        """Landing page with input options."""
        # Only clear session if explicitly requested or if session is stale
        # Don't auto-clear to prevent losing data during workflow
        clear_session = request.args.get('clear', 'false').lower() == 'true'
        
        if clear_session:
            logger.info("Clearing session data (explicit clear requested)")
            pending_flashes = session.get('_flashes')
            session.clear()
            if pending_flashes:
                session['_flashes'] = pending_flashes
        else:
            # SESSION TRACKING LOG
            logger.info("="*80)
            logger.info("INDEX PAGE ACCESSED (session preserved)")
            logger.info(f"Session SID: {session.sid if hasattr(session, 'sid') else 'N/A'}")
            logger.info(f"Session keys: {list(session.keys())}")
            logger.info(f"'mom_data' in session: {'mom_data' in session}")
            logger.info("="*80)
        
        return render_template('index.html')
    
    @app.route('/health', methods=['GET'])
    def health():
        """
        Health check endpoint for monitoring and uptime checks.
        
        Returns:
            JSON response with status and timestamp
        """
        logger.info("Health check requested")
        return jsonify({
            "status": "ok",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "service": "clearmeet"
        }), 200
    
    @app.route('/debug/session', methods=['GET'])
    def debug_session():
        """Debug endpoint to inspect current session state."""
        return jsonify({
            "session_sid": session.sid if hasattr(session, 'sid') else None,
            "session_keys": list(session.keys()),
            "has_mom_data": 'mom_data' in session,
            "has_mom_text": 'mom_text' in session,
            "mom_text_length": len(session.get('mom_text', '')),
            "session_permanent": session.permanent,
            "session_modified": session.modified,
            "session_new": session.new if hasattr(session, 'new') else None
        }), 200
    
    # Pre-Meeting Routes (Steps 1-2: Objective Definition + Agenda Building)
    @app.route('/meeting/new', methods=['GET'])
    def define_objective():
        """Display structured objective definition form (Step 1)."""
        logger.info("Objective definition page accessed")
        return render_template('define_objective.html')
    
    @app.route('/meeting/clear', methods=['GET', 'POST'])
    def clear_session():
        """Clear current session and start a new meeting."""
        session.clear()
        logger.info("Session cleared, starting new meeting")
        flash('Session cleared. Ready to start a new meeting!', 'success')
        return redirect(url_for('index'))
    
    @app.route('/meeting/define', methods=['POST'])
    def save_objective():
        """Save meeting objective to session and proceed to agenda builder (Step 1 → 2)."""
        try:
            business_issue = request.form.get('business_issue', '').strip()
            objective = request.form.get('objective', '').strip()
            expected_output = request.form.get('expected_output', '').strip()
            start_time = request.form.get('start_time', '').strip()
            end_time = request.form.get('end_time', '').strip()
            venue = request.form.get('venue', '').strip() or None
            
            # Parse attendees from comma-separated string
            attendees_str = request.form.get('attendees', '').strip()
            attendees_list = None
            if attendees_str:
                attendees_list = [a.strip() for a in attendees_str.split(',') if a.strip()]
            
            # Validate using Pydantic model
            meeting_objective = MeetingObjective(
                business_issue=business_issue,
                objective=objective,
                expected_output=expected_output,
                start_time=start_time,
                end_time=end_time,
                venue=venue,
                attendees=attendees_list
            )
            
            # Store in session
            session['meeting_objective'] = meeting_objective.model_dump()
            session.modified = True
            
            logger.info("Meeting objective saved to session")
            flash('Objective defined successfully. Now build your agenda.', 'success')
            return redirect(url_for('build_agenda'))
            
        except Exception as e:
            logger.error(f"Objective validation failed: {e}")
            flash(f'Validation error: {str(e)}', 'error')
            return redirect(url_for('define_objective'))
    
    @app.route('/meeting/agenda', methods=['GET'])
    def build_agenda():
        """Display agenda builder interface (Step 2)."""
        # Require objective to be defined first
        if 'meeting_objective' not in session:
            flash('Please define the meeting objective first', 'warning')
            return redirect(url_for('define_objective'))
        
        meeting_objective_data = session['meeting_objective']
        agenda_items = session.get('agenda_items', [])
        
        logger.info(f"Agenda builder accessed, {len(agenda_items)} items in session")
        return render_template(
            'build_agenda.html',
            meeting_objective=meeting_objective_data,
            agenda_items=agenda_items
        )
    
    @app.route('/meeting/agenda/generate', methods=['POST'])
    def generate_agenda_ai():
        """Generate AI-assisted agenda suggestions (Step 2)."""
        try:
            if 'meeting_objective' not in session:
                return jsonify({"error": "No meeting objective defined"}), 400
            
            # Reconstruct MeetingObjective from session
            objective_data = session['meeting_objective']
            meeting_objective = MeetingObjective(**objective_data)
            
            # Generate agenda with AI
            agenda_items = AgendaBuilder.generate_agenda_with_ai(meeting_objective)
            
            # Store in session
            session['agenda_items'] = AgendaBuilder.serialize_agenda(agenda_items)
            session.modified = True
            
            logger.info(f"AI generated {len(agenda_items)} agenda items")
            return jsonify({
                "success": True,
                "agenda_items": AgendaBuilder.serialize_agenda(agenda_items),
                "total_duration": AgendaBuilder.calculate_total_duration(agenda_items)
            })
            
        except Exception as e:
            logger.error(f"AI agenda generation failed: {e}")
            return jsonify({"error": str(e)}), 500
    
    @app.route('/meeting/agenda/save', methods=['POST'])
    def save_agenda():
        """Save final agenda and proceed to existing transcript workflow."""
        try:
            # Get agenda items from form
            agenda_data = request.get_json()
            if not agenda_data or 'items' not in agenda_data:
                flash('No agenda items provided', 'error')
                return jsonify({"error": "No agenda items"}), 400
            
            # Validate agenda items
            agenda_items = []
            for item_data in agenda_data['items']:
                agenda_item = AgendaItem(**item_data)
                agenda_items.append(agenda_item)
            
            # Validate timing
            is_valid, error_msg = AgendaBuilder.validate_agenda_timing(agenda_items)
            if not is_valid:
                return jsonify({"error": error_msg}), 400
            
            # Store in session
            session['agenda_items'] = AgendaBuilder.serialize_agenda(agenda_items)
            session['agenda_completed'] = True
            session.modified = True
            
            logger.info(f"Agenda saved: {len(agenda_items)} items, {AgendaBuilder.calculate_total_duration(agenda_items)} min total")
            return jsonify({
                "success": True,
                "redirect_url": url_for('index', agenda_saved='true')
            })
            
        except Exception as e:
            logger.error(f"Agenda save failed: {e}")
            return jsonify({"error": str(e)}), 500

    @app.route('/meeting/agenda/export', methods=['GET'])
    def export_agenda_pdf():
        """Export current agenda (Steps 1-2) to PDF."""
        agenda_items = session.get('agenda_items', [])
        if not agenda_items:
            flash('No agenda found. Please build and save your agenda first.', 'warning')
            return redirect(url_for('build_agenda'))

        objective_data = session.get('meeting_objective', {})
        
        # Export using professional PDF formatter
        pdf_buffer = pdf_exporter.export_agenda_to_pdf(
            objective_data=objective_data,
            agenda_items=agenda_items
        )

        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        filename = f"Agenda_{timestamp}.pdf"

        return send_file(
            pdf_buffer,
            mimetype='application/pdf',
            as_attachment=True,
            download_name=filename
        )

    
    @app.route('/process', methods=['GET', 'POST'])
    @app.route('/generate', methods=['POST'])
    def process_input():
        """
        Process transcript input (text or audio file).
        
        Returns redirect to edit page with structured MOM data.
        """
        if request.method == 'GET':
            logger.warning("GET request to /process - redirecting to index")
            flash('Please use the form to submit your transcript', 'warning')
            return redirect(url_for('index'))
        
        try:
            logger.info("Processing input started")
            logger.debug(f"Request method: {request.method}")
            logger.debug(f"Form data keys: {list(request.form.keys())}")
            logger.debug(f"Files keys: {list(request.files.keys())}")
            
            # Clear any previous progress state
            global _progress_state
            _progress_state.clear()
            
            transcript = None
            
            # Check if audio file uploaded
            print("[DEBUG] Checking for audio file...")
            audio_file = request.files.get('audio_file')
            if audio_file and audio_file.filename:
                    print(f"[DEBUG] Processing audio file: {audio_file.filename}")
                    # Secure filename
                    filename = secure_filename(audio_file.filename)
                    filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
                    
                    # Save temporarily
                    audio_file.save(filepath)
                    
                    try:
                        # Validate audio file
                        is_valid, error_msg = AudioTranscriber.validate_audio_file(
                            filepath,
                            max_size_mb=app.config['MAX_CONTENT_LENGTH'] // (1024 * 1024),
                            allowed_extensions=app.config['ALLOWED_AUDIO_EXTENSIONS']
                        )
                        
                        if not is_valid:
                            flash(f"Audio file validation failed: {error_msg}", 'error')
                            return redirect(url_for('index'))
                        
                        # Create progress callback for SSE updates
                        def progress_callback(progress_data):
                            """Update progress tracking for SSE stream."""
                            global _progress_state, _progress_lock
                            
                            print(f"[CALLBACK] Received progress update: {progress_data}")
                            
                            with _progress_lock:
                                # Track chunk durations for average calculation
                                if 'progress_chunks' not in _progress_state:
                                    _progress_state['progress_chunks'] = []
                                
                                _progress_state['progress_chunks'].append(progress_data.get('duration_sec', 0))
                                
                                # Calculate average time per chunk
                                progress_data['avg_time_per_chunk'] = sum(_progress_state['progress_chunks']) / len(_progress_state['progress_chunks'])
                                _progress_state['current_progress'] = progress_data
                                
                                print(f"[CALLBACK] Updated _progress_state: {_progress_state}")
                                
                            print(f"[PROGRESS] Chunk {progress_data.get('chunk')}/{progress_data.get('total_chunks')} - {progress_data.get('avg_time_per_chunk', 0):.1f}s avg")
                        
                        # Transcribe audio in a background thread to keep Flask responsive for SSE
                        print(f"[DEBUG] Starting transcription in background thread")
                        
                        # Store transcript in a container so it can be updated from the thread
                        transcription_result = {'transcript': None}
                        transcription_error = {'error': None}
                        
                        def transcribe_in_background():
                            try:
                                print(f"[DEBUG] Background thread: calling transcribe_audio with progress_callback")
                                transcription_result['transcript'] = transcribe_audio(filepath, progress_callback=progress_callback)
                                print(f"[DEBUG] Background thread: transcribe_audio completed")
                                # Mark completion
                                with _progress_lock:
                                    if 'current_progress' in _progress_state:
                                        _progress_state['current_progress']['completed'] = True
                            except Exception as e:
                                print(f"[ERROR] Background thread transcription error: {e}")
                                transcription_error['error'] = str(e)
                        
                        transcribe_thread = threading.Thread(target=transcribe_in_background, daemon=False)
                        transcribe_thread.start()
                        
                        # Wait for transcription to complete
                        print(f"[DEBUG] Main thread: waiting for transcription")
                        transcribe_thread.join(timeout=1800)  # 30 minute timeout
                        
                        if transcribe_thread.is_alive():
                            print(f"[ERROR] Transcription thread timed out")
                            flash("Audio transcription timed out after 30 minutes", 'error')
                            return redirect(url_for('index'))
                        
                        # Check for errors during transcription
                        if transcription_error['error']:
                            flash(f"Transcription error: {transcription_error['error']}", 'error')
                            return redirect(url_for('index'))
                        
                        transcript = transcription_result['transcript']
                        

                    finally:
                        # Clean up uploaded file
                        if os.path.exists(filepath):
                            os.remove(filepath)
            
            # Check if text transcript provided
            if not transcript and 'transcript_text' in request.form:
                transcript = request.form['transcript_text']
                print(f"[DEBUG] Text transcript received, length: {len(transcript) if transcript else 0}")
                print(f"[DEBUG] Text transcript (first 100 chars): {transcript[:100] if transcript else 'EMPTY'}")
            
            # Ensure we have some input
            if not transcript:
                print("[DEBUG] ❌ ERROR: No transcript or audio file provided")
                print(f"[DEBUG] Form keys: {list(request.form.keys())}")
                print(f"[DEBUG] File keys: {list(request.files.keys())}")
                flash('Please provide either a transcript or upload an audio file', 'error')
                return redirect(url_for('index'))
            
            # Validate transcript
            print("\n[DEBUG] --- VALIDATION STAGE ---")
            print("[DEBUG] Cleaning transcript...")
            transcript = TranscriptParser.clean_transcript(transcript)
            print(f"[DEBUG] ✓ Cleaned transcript length: {len(transcript)}")
            print(f"[DEBUG] Cleaned transcript preview: {transcript[:150] if len(transcript) > 150 else transcript}")
            print("[DEBUG] Validating transcript...")
            is_valid, error_msg = TranscriptParser.validate_transcript(transcript)
            
            if not is_valid:
                print(f"[DEBUG] ❌ VALIDATION FAILED: {error_msg}")
                flash(f"Transcript validation failed: {error_msg}", 'error')
                print(f"[DEBUG] Redirecting to index due to validation failure")
                return redirect(url_for('index'))
            
            print(f"[DEBUG] ✓ Validation passed")
            
            # Generate MOM using LLM
            print("\n[DEBUG] --- AI GENERATION STAGE ---")
            print("[DEBUG] Calling OpenAI to generate MOM...")
            objective = _sanitize_text(request.form.get('objective', ''))
            instructions = _sanitize_text(request.form.get('instructions', '') or request.form.get('additional_context', ''))
            print(f"[DEBUG] Objective: '{objective[:100] if objective else 'None'}'")
            print(f"[DEBUG] Instructions: '{instructions[:100] if instructions else 'None'}'")
            
            # Phase 2 Integration: Pass pre-meeting planning data if available
            planned_objective = session.get('meeting_objective')
            agenda_items = session.get('agenda_items')
            if planned_objective:
                print(f"[DEBUG] Using planned objective from Step 1: {planned_objective.get('objective', '')[:100]}")
            if agenda_items:
                print(f"[DEBUG] Using planned agenda from Step 2: {len(agenda_items)} items")

            mom_data_raw = extract_mom_from_transcript(
                transcript,
                objective=objective or None,
                instructions=instructions or None,
                planned_objective=planned_objective,
                agenda_items=agenda_items
            )
            validated_mom = validate_mom_dict(mom_data_raw)
            mom_data = validated_mom.model_dump(exclude_none=True)
            mom_text = mom_to_text(validated_mom, agenda_items=agenda_items)
            print(f"[DEBUG] ✓ MOM generated successfully")
            print(f"[DEBUG] MOM data keys: {list(mom_data.keys()) if mom_data else None}")
            print(f"[DEBUG] MOM objective: {mom_data.get('objective', 'N/A')[:100] if mom_data else 'N/A'}")
            print(f"[DEBUG] MOM attendees count: {len(mom_data.get('attendees', [])) if mom_data else 0}")
            print(f"[DEBUG] MOM decisions count: {len(mom_data.get('decisions', [])) if mom_data else 0}")
            print(f"[DEBUG] MOM action_items count: {len(mom_data.get('action_items', [])) if mom_data else 0}")
            
            # Store in session
            print("\n[DEBUG] --- SESSION STORAGE STAGE ---")
            transcript_preview, transcript_path = _persist_transcript(transcript)
            session['mom_data'] = mom_data
            session['mom_json'] = mom_data
            mom_text_preview, mom_text_path = _persist_mom_text(mom_text)
            session['mom_text'] = mom_text_preview
            session['mom_text_path'] = mom_text_path
            session['transcript'] = transcript_preview
            session['transcript_path'] = transcript_path
            session['transcript_length'] = len(transcript)
            session['additional_context'] = instructions
            session['validated'] = False
            session['text_override'] = False
            
            # SESSION TRACKING LOG
            logger.info("="*80)
            logger.info("SESSION DATA STORED (process_input)")
            logger.info(f"Session SID: {session.sid if hasattr(session, 'sid') else 'N/A'}")
            logger.info(f"Session keys: {list(session.keys())}")
            logger.info(f"mom_text length: {len(session['mom_text'])}")
            logger.info(f"mom_data keys: {list(session['mom_data'].keys())}")
            logger.info(f"Session modified: {session.modified}")
            logger.info("="*80)
            
            print(f"[DEBUG] ✓ Session data stored")
            print(f"[DEBUG] Session keys: {list(session.keys())}")
            
            flash('MOM generated successfully! Please review and edit as needed.', 'success')
            print(f"\n[DEBUG] ✓ SUCCESS - Redirecting to /edit")
            print(f"[DEBUG] Redirect URL: {url_for('edit')}")
            print("="*80 + "\n")
            return redirect(url_for('edit'))
            
        except Exception as e:
            import traceback
            error_details = traceback.format_exc()
            print("\n" + "="*80)
            print("[ERROR] ❌❌❌ EXCEPTION OCCURRED ❌❌❌")
            print(f"[ERROR] Exception type: {type(e).__name__}")
            print(f"[ERROR] Exception message: {str(e)}")
            print(f"[ERROR] Full traceback:\n{error_details}")
            print(f"[ERROR] Request method: {request.method}")
            print(f"[ERROR] Request URL: {request.url}")
            print(f"[ERROR] Form data keys: {list(request.form.keys())}")
            print(f"[ERROR] Files keys: {list(request.files.keys())}")
            print("="*80 + "\n")
            flash(f"Error processing input: {str(e)}", 'error')
            return redirect(url_for('index'))
    
    @app.route('/progress')
    def progress():
        """
        Server-Sent Events endpoint for progress updates during audio processing.
        
        Yields progress events with format: data: {"chunk": #, "total_chunks": #, "percent": #, ...}
        """
        def generate():
            global _progress_state, _progress_lock
            last_chunk = 0
            consecutive_empty = 0
            iteration = 0
            
            print(f"[SSE] Generator started, initial _progress_state: {_progress_state}")
            
            while True:
                iteration += 1
                with _progress_lock:
                    progress_data = _progress_state.get('current_progress', {})
                    if iteration <= 5 or iteration % 20 == 0:
                        print(f"[SSE] Iteration {iteration}: progress_data = {progress_data}")
                
                if progress_data and progress_data.get('chunk', 0) > last_chunk:
                    consecutive_empty = 0
                    chunk = progress_data.get('chunk', 0)
                    total = progress_data.get('total_chunks', 1)
                    percent = int((chunk / total) * 100) if total > 0 else 0
                    avg_time = progress_data.get('avg_time_per_chunk', 0)
                    estimated_remaining = (total - chunk) * avg_time
                    
                    print(f"[SSE] Sending update: chunk={chunk}/{total} ({percent}%)")
                    yield f'data: {json.dumps({"chunk": chunk, "total_chunks": total, "percent": percent, "estimated_seconds": int(estimated_remaining)})}\n\n'
                    last_chunk = chunk
                    
                    # If completed, signal end
                    if chunk >= total:
                        print("[SSE] Progress complete, sending completion signal")
                        yield f'data: {json.dumps({"completed": True})}\n\n'
                        break
                else:
                    # Count consecutive empty reads
                    consecutive_empty += 1
                    # Timeout after 5 minutes of no updates
                    if consecutive_empty > 6000:  # 6000 * 0.05s = 300s = 5 min
                        print("[SSE] Timeout: No progress updates for 5 minutes")
                        break
                
                # Small sleep to prevent busy-waiting
                import time
                time.sleep(0.05)
        
        return generate(), {
            'Content-Type': 'text/event-stream',
            'Cache-Control': 'no-cache',
            'X-Accel-Buffering': 'no'
        }
    
    @app.route('/edit')
    def edit():
        """
        Edit page with structured editing and full text editor.
        
        Shows MOM data with ability to edit decisions, action items, objective.
        """
        # SESSION TRACKING LOG
        logger.info("="*80)
        logger.info("SESSION DATA RETRIEVAL (edit)")
        logger.info(f"Session SID: {session.sid if hasattr(session, 'sid') else 'N/A'}")
        logger.info(f"Session keys: {list(session.keys())}")
        logger.info(f"'mom_data' in session: {'mom_data' in session}")
        logger.info(f"Session modified: {session.modified}")
        logger.info("="*80)
        
        if 'mom_data' not in session:
            logger.error("SESSION DATA MISSING: mom_data not found in session (edit)")
            flash('No MOM data found. Please start from the beginning.', 'warning')
            return redirect(url_for('index'))
        
        mom_data = session.get('mom_data', {}).copy()
        mom_text = session.get('mom_text', '')
        if session.get('mom_text_path') and (not mom_text or mom_text.endswith('...')):
            loaded_text = _load_text_from_path(session.get('mom_text_path'))
            if loaded_text:
                mom_text = loaded_text
        
        # Phase 2 Integration: Pre-populate objective from planned objective if not user-edited
        planned_objective = session.get('meeting_objective')
        if planned_objective and not session.get('objective_user_edited'):
            # Only override if current objective looks auto-generated or generic
            current_obj = mom_data.get('objective', '').lower()
            if (not current_obj or 
                current_obj.startswith('meeting to discuss') or
                current_obj.startswith('objective not provided') or
                len(current_obj) < 15):
                mom_data['objective'] = planned_objective.get('objective', '')
                logger.info(f"Pre-populated objective from Step 1: {mom_data['objective'][:100]}")
        
        # Phase 2 Integration: Pre-populate date/time/venue from planned objective
        if planned_objective and not session.get('date_time_venue_user_edited'):
            # Extract date from start_time if available (ISO 8601: "2026-02-23T09:30")
            if planned_objective.get('start_time') and not mom_data.get('date'):
                start_time = planned_objective.get('start_time')
                if 'T' in start_time:
                    mom_data['date'] = start_time.split('T')[0]
                    logger.info(f"Pre-populated meeting date from Step 1 start_time: {mom_data['date']}")
            
            if planned_objective.get('start_time') and not mom_data.get('start_time'):
                mom_data['start_time'] = planned_objective.get('start_time')
                logger.info(f"Pre-populated start time from Step 1: {mom_data['start_time']}")
            
            if planned_objective.get('end_time') and not mom_data.get('end_time'):
                mom_data['end_time'] = planned_objective.get('end_time')
                logger.info(f"Pre-populated end time from Step 1: {mom_data['end_time']}")
            
            if planned_objective.get('venue') and not mom_data.get('venue'):
                mom_data['venue'] = planned_objective.get('venue')
                logger.info(f"Pre-populated venue from Step 1: {mom_data['venue']}")
            
            if planned_objective.get('attendees') and not mom_data.get('attendees'):
                mom_data['attendees'] = planned_objective.get('attendees')
                logger.info(f"Pre-populated attendees from Step 1: {len(mom_data['attendees'])} attendees")

        
        # Phase 2 Integration: Pass agenda items for display
        agenda_items = session.get('agenda_items', [])
        if agenda_items:
            total_agenda_duration = sum(item.get('duration_minutes', 0) for item in agenda_items)
        else:
            total_agenda_duration = 0
        
        return render_template(
            'edit.html', 
            mom_data=mom_data, 
            mom_text=mom_text,
            agenda_items=agenda_items,
            total_agenda_duration=total_agenda_duration
        )
    
    @app.route('/update', methods=['POST'])
    @app.route('/edit', methods=['POST'])
    def edit_submit():
        """
        Update MOM data from edit form.
        
        Handles both structured edits and full text override.
        """
        try:
            # Update structured data
            mom_data = session.get('mom_json') or session.get('mom_data', {})

            # Update title/date/objective when provided
            if 'title' in request.form:
                mom_data['title'] = _sanitize_text(request.form.get('title', ''))
            if 'date' in request.form:
                mom_data['date'] = _sanitize_text(request.form.get('date', ''))
            if 'start_time' in request.form:
                start_time = _sanitize_text(request.form.get('start_time', ''))
                mom_data['start_time'] = start_time if start_time else None
            if 'end_time' in request.form:
                end_time = _sanitize_text(request.form.get('end_time', ''))
                mom_data['end_time'] = end_time if end_time else None
            if 'venue' in request.form:
                venue = _sanitize_text(request.form.get('venue', ''))
                mom_data['venue'] = venue if venue else None
            if 'objective' in request.form:
                mom_data['objective'] = _sanitize_text(request.form.get('objective', ''))

            # Update attendees
            if 'attendees' in request.form:
                attendees_str = _sanitize_text(request.form.get('attendees', ''))
                attendees_list = [a.strip() for a in attendees_str.split(',') if a.strip()]
                mom_data['attendees'] = attendees_list if attendees_list else None

            # Update decisions
            if any(key.startswith('decision_') for key in request.form.keys()):
                decisions = []
                for key in request.form.keys():
                    if key.startswith('decision_'):
                        decision = _sanitize_text(request.form.get(key, ''))
                        if decision:
                            decisions.append({'text': decision})
                mom_data['decisions'] = decisions

            # Update action items
            if 'action_count' in request.form:
                action_items = []
                action_count = int(request.form.get('action_count', 0))
                for i in range(action_count):
                    action = _sanitize_text(request.form.get(f'action_action_{i}', ''))
                    owner = _sanitize_text(request.form.get(f'action_owner_{i}', ''))
                    deadline = _sanitize_text(request.form.get(f'action_deadline_{i}', '')) or None
                    status = _sanitize_text(request.form.get(f'action_status_{i}', '')) or 'Open'

                    if action:
                        action_items.append({
                            'action': action,
                            'owner': owner or '',
                            'deadline': deadline,
                            'status': status
                        })
                mom_data['action_items'] = action_items

            # Update parking lot
            if 'parking_lot' in request.form:
                parking_lot_str = _sanitize_text(request.form.get('parking_lot', ''))
                if parking_lot_str.strip():
                    mom_data['parking_lot'] = [p.strip() for p in parking_lot_str.split(',') if p.strip()]
                else:
                    mom_data['parking_lot'] = None

            # Update notes
            if 'notes' in request.form:
                notes = _sanitize_text(request.form.get('notes', ''), max_len=50000)
                mom_data['notes'] = notes if notes else None

            # Update confidentiality flags
            if 'confidentiality_flags' in request.form:
                flags_str = _sanitize_text(request.form.get('confidentiality_flags', ''))
                if flags_str.strip():
                    mom_data['confidentiality_flags'] = [f.strip() for f in flags_str.split(',') if f.strip()]
                else:
                    mom_data['confidentiality_flags'] = None

            # Validate structured model if possible (MVP keeps structure unchanged on text edits)
            typed_mom = validate_mom_dict(mom_data)

            # Update text editor override only when explicitly requested
            text_override = request.form.get('text_override', 'false').lower() == 'true'
            use_text_override = request.form.get('use_text_override', 'false').lower() == 'true'
            edited_text = _sanitize_text(request.form.get('mom_text_override', ''), max_len=100000)
            if not edited_text:
                edited_text = _sanitize_text(request.form.get('mom_text', ''), max_len=100000)

            if (text_override or use_text_override or bool(request.form.get('mom_text_override', '').strip())) and edited_text:
                typed_mom = apply_user_edits(typed_mom, edited_text)
                mom_text_preview, mom_text_path = _persist_mom_text(edited_text)
                session['mom_text'] = mom_text_preview
                session['mom_text_path'] = mom_text_path
                session['text_override'] = True
            else:
                # Phase 2 Integration: Include agenda when rendering MOM text
                agenda_items_for_render = session.get('agenda_items', [])
                rendered_text = mom_to_text(typed_mom, agenda_items=agenda_items_for_render)
                mom_text_preview, mom_text_path = _persist_mom_text(rendered_text)
                session['mom_text'] = mom_text_preview
                session['mom_text_path'] = mom_text_path
                session['text_override'] = False

            # Store updated structured data
            normalized = typed_mom.model_dump(exclude_none=True)
            session['mom_data'] = normalized
            session['mom_json'] = normalized
            session['validated'] = False
            
            # SESSION TRACKING LOG
            logger.info("="*80)
            logger.info("SESSION DATA UPDATED (edit_submit)")
            logger.info(f"Session SID: {session.sid if hasattr(session, 'sid') else 'N/A'}")
            logger.info(f"Session keys: {list(session.keys())}")
            logger.info(f"mom_text length: {len(session.get('mom_text', ''))}")
            logger.info(f"Session modified: {session.modified}")
            logger.info("="*80)
            
            flash('MOM updated successfully!', 'success')
            return redirect(url_for('validate_page'))
            
        except Exception as e:
            flash(f"Error updating MOM: {str(e)}", 'error')
            return redirect(url_for('edit'))
    
    @app.route('/validate')
    def validate_page():
        """
        Validation checklist page.
        
        Enforces validation before allowing export.
        """
        # SESSION TRACKING LOG
        logger.info("="*80)
        logger.info("SESSION DATA RETRIEVAL (validate_page)")
        logger.info(f"Session SID: {session.sid if hasattr(session, 'sid') else 'N/A'}")
        logger.info(f"Session keys: {list(session.keys())}")
        logger.info(f"'mom_text' in session: {'mom_text' in session}")
        logger.info(f"Session modified: {session.modified}")
        logger.info("="*80)
        
        if 'mom_text' not in session:
            logger.error("SESSION DATA MISSING: mom_text not found in session (validate_page)")
            flash('No MOM data found. Please start from the beginning.', 'warning')
            return redirect(url_for('index'))
        
        # Get validation checklist
        checklist = MOMValidator.get_validation_checklist()
        
        # Compute content issues using structured data and text
        mom_data = session.get('mom_data', {})
        safe_mom_data = {
            'title': mom_data.get('title', ''),
            'date': mom_data.get('date', ''),
            'objective': mom_data.get('objective', ''),
            'decisions': mom_data.get('decisions', []),
            'action_items': mom_data.get('action_items', []),
            'attendees': mom_data.get('attendees'),
            'parking_lot': mom_data.get('parking_lot'),
            'notes': mom_data.get('notes'),
            'confidentiality_flags': mom_data.get('confidentiality_flags'),
        }
        mom_obj = MeetingMOM.model_construct(**safe_mom_data)
        
        # Validate text length
        mom_text = session.get('mom_text', '')
        if session.get('mom_text_path') and (not mom_text or mom_text.endswith('...')):
            loaded_text = _load_text_from_path(session.get('mom_text_path'))
            if loaded_text:
                mom_text = loaded_text
        transcript_text = session.get('transcript', '')
        if session.get('transcript_path') and (not transcript_text or transcript_text.endswith('...')):
            loaded_transcript = _load_text_from_path(session.get('transcript_path'))
            if loaded_transcript:
                transcript_text = loaded_transcript

        combined_text = f"{mom_text}\n{transcript_text}".strip()
        content_issues = MOMValidator.compute_validation_issues(mom_obj, combined_text)

        text_valid, text_message = MOMValidator.validate_text_length(mom_text)
        if not text_valid:
            content_issues.append(text_message)
        
        return render_template(
            'validate.html',
            checklist=checklist,
            content_issues=content_issues,
            mom_text=mom_text
        )

    @app.route('/validate', methods=['POST'])
    def validate_submit():
        """Validate checklist submission and mark session validated."""
        # SESSION TRACKING LOG
        logger.info("="*80)
        logger.info("SESSION DATA RETRIEVAL (validate_submit)")
        logger.info(f"Session SID: {session.sid if hasattr(session, 'sid') else 'N/A'}")
        logger.info(f"Session keys: {list(session.keys())}")
        logger.info(f"'mom_text' in session: {'mom_text' in session}")
        logger.info(f"Session modified: {session.modified}")
        logger.info("="*80)
        
        if 'mom_text' not in session:
            logger.error("SESSION DATA MISSING: mom_text not found in session (validate_submit)")
            flash('No MOM data found. Please start from the beginning.', 'warning')
            return redirect(url_for('index'))

        checklist_data = request.form.getlist('checklist')
        full_checklist = MOMValidator.get_validation_checklist()

        for item in full_checklist:
            item.checked = item.id in checklist_data

        all_checked, unchecked = MOMValidator.validate_checklist(full_checklist)
        if not all_checked:
            flash(f"Please check all required items: {', '.join(unchecked)}", 'error')
            return redirect(url_for('validate_page'))

        session['validated'] = True
        
        # SESSION TRACKING LOG
        logger.info("="*80)
        logger.info("SESSION VALIDATED (validate_submit)")
        logger.info(f"Session SID: {session.sid if hasattr(session, 'sid') else 'N/A'}")
        logger.info(f"Session keys: {list(session.keys())}")
        logger.info(f"Session modified: {session.modified}")
        logger.info(f"Redirecting to export_mom")
        logger.info("="*80)
        
        flash('Validation checklist completed. Ready to export.', 'success')
        return redirect(url_for('export_mom'))
    
    @app.route('/export', methods=['GET'])
    @app.route('/export_mom', methods=['GET', 'POST'])
    def export_mom():
        """
        Export MOM to PDF.
        
        Validates checklist before allowing export (POST requests only).
        GET requests export directly (for testing/direct download).
        """
        try:
            # SESSION TRACKING LOG
            logger.info("="*80)
            logger.info("SESSION DATA RETRIEVAL (export_mom)")
            logger.info(f"Session SID: {session.sid if hasattr(session, 'sid') else 'N/A'}")
            logger.info(f"Session keys: {list(session.keys())}")
            logger.info(f"'mom_text' in session: {'mom_text' in session}")
            logger.info(f"Request method: {request.method}")
            logger.info(f"Request path: {request.path}")
            logger.info(f"Session modified: {session.modified}")
            
            # Check if session data exists (required for both GET and POST)
            mom_text = session.get('mom_text', '')
            logger.info(f"mom_text retrieved: {len(mom_text)} characters")
            logger.info("="*80)
            
            if not mom_text:
                logger.error("SESSION DATA MISSING: mom_text not found or empty in session (export_mom)")
                logger.error(f"All session data: {dict(session)}")
                flash('No MOM data found. Please generate a MOM first.', 'error')
                return redirect(url_for('index'))

            if request.path == '/export' and not session.get('validated', False):
                flash('Please complete the validation checklist before export.', 'error')
                return redirect(url_for('validate_page'))
            
            # Validate checklist only for POST requests (from validation form)
            if request.method == 'POST':
                checklist_data = request.form.getlist('checklist')
                
                # Get full checklist
                full_checklist = MOMValidator.get_validation_checklist()
                
                # Mark checked items
                for item in full_checklist:
                    item.checked = item.id in checklist_data
                
                # Validate all required items checked
                all_checked, unchecked = MOMValidator.validate_checklist(full_checklist)
                
                if not all_checked:
                    flash(f"Please check all required items: {', '.join(unchecked)}", 'error')
                    return redirect(url_for('validate_page'))
                session['validated'] = True
            
            # Prepare metadata
            mom_data = session.get('mom_data', {})
            
            # Extract meeting date from mom_data or planned_objective
            meeting_date = None
            if mom_data.get('date'):
                meeting_date = mom_data['date']
            elif mom_data.get('start_time') and 'T' in mom_data['start_time']:
                meeting_date = mom_data['start_time'].split('T')[0]
            else:
                # Fallback to today's date
                meeting_date = datetime.now().strftime('%Y-%m-%d')
            
            metadata = {
                'meeting_date': meeting_date,
                'meeting_title': 'Meeting Minutes'
            }
            
            # Extract title/objective for PDF header
            if not session.get('text_override', False):
                if mom_data.get('title'):
                    metadata['meeting_title'] = mom_data['title'][:50]
                elif mom_data.get('objective'):
                    metadata['meeting_title'] = mom_data['objective'][:50]  # Truncate if too long
            
            # Export to PDF
            pdf_buffer = pdf_exporter.export_to_pdf(mom_text, metadata=metadata)
            
            # Generate filename
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            filename = f"MOM_{timestamp}.pdf"
            
            return send_file(
                pdf_buffer,
                mimetype='application/pdf',
                as_attachment=True,
                download_name=filename
            )
            
        except Exception as e:
            flash(f"Error exporting PDF: {str(e)}", 'error')
            return redirect(url_for('validate_page'))
    
    @app.route('/preview')
    def preview():
        """Preview page showing final MOM before export."""
        if 'mom_text' not in session:
            flash('No MOM data found. Please start from the beginning.', 'warning')
            return redirect(url_for('index'))
        
        mom_text = session.get('mom_text', '')
        return render_template('preview.html', mom_text=mom_text)
    
    # Error handlers
    @app.errorhandler(404)
    def not_found(error):
        """Handle 404 errors by redirecting to index."""
        flash('Page not found. Redirecting to home.', 'warning')
        return redirect(url_for('index'))
    
    @app.errorhandler(500)
    def internal_error(error):
        """Handle 500 errors."""
        flash('An internal error occurred. Please try again.', 'error')
        return redirect(url_for('index'))
    
    return app


# Create app instance
app = create_app()


if __name__ == '__main__':
    app.run(debug=True)
