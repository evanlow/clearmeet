"""
ClearMeet Flask Application

Main Flask app with routes for MOM generation workflow.
"""
from flask import Flask, render_template, request, session, redirect, url_for, send_file, flash, g, jsonify
from werkzeug.utils import secure_filename
import os
import json
import logging
from datetime import datetime, timezone
from typing import Optional
import threading
import uuid

from config import get_config, Config, logger
from core.parser import TranscriptParser
from core.llm import extract_mom_from_transcript, render_mom_text, transcribe_audio
from core.audio import AudioTranscriber
from core.render import mom_to_text, apply_user_edits
from core.schema import validate_mom_dict, MeetingMOM
from core.validation import MOMValidator, ValidationItem
from core.export import PDFExporter

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
        # Clear any existing session data for fresh start
        pending_flashes = session.get('_flashes')
        session.clear()
        if pending_flashes:
            session['_flashes'] = pending_flashes
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

            mom_data_raw = extract_mom_from_transcript(
                transcript,
                objective=objective or None,
                instructions=instructions or None
            )
            validated_mom = validate_mom_dict(mom_data_raw)
            mom_data = validated_mom.model_dump(exclude_none=True)
            mom_text = mom_to_text(validated_mom)
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
        if 'mom_data' not in session:
            flash('No MOM data found. Please start from the beginning.', 'warning')
            return redirect(url_for('index'))
        
        mom_data = session.get('mom_data', {})
        mom_text = session.get('mom_text', '')
        if session.get('mom_text_path') and (not mom_text or mom_text.endswith('...')):
            loaded_text = _load_text_from_path(session.get('mom_text_path'))
            if loaded_text:
                mom_text = loaded_text
        
        return render_template('edit.html', mom_data=mom_data, mom_text=mom_text)
    
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

            # Update text editor override if provided, otherwise render from structure
            edited_text = _sanitize_text(request.form.get('mom_text_override', ''), max_len=100000)
            if not edited_text:
                edited_text = _sanitize_text(request.form.get('mom_text', ''), max_len=100000)

            if edited_text:
                typed_mom = apply_user_edits(typed_mom, edited_text)
                mom_text_preview, mom_text_path = _persist_mom_text(edited_text)
                session['mom_text'] = mom_text_preview
                session['mom_text_path'] = mom_text_path
                session['text_override'] = True
            else:
                rendered_text = mom_to_text(typed_mom)
                mom_text_preview, mom_text_path = _persist_mom_text(rendered_text)
                session['mom_text'] = mom_text_preview
                session['mom_text_path'] = mom_text_path
                session['text_override'] = False

            # Store updated structured data
            normalized = typed_mom.model_dump(exclude_none=True)
            session['mom_data'] = normalized
            session['mom_json'] = normalized
            session['validated'] = False
            
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
        if 'mom_text' not in session:
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
        if 'mom_text' not in session:
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
            # Check if session data exists (required for both GET and POST)
            mom_text = session.get('mom_text', '')
            if not mom_text:
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
            metadata = {
                'meeting_date': datetime.now().strftime('%Y-%m-%d'),
                'meeting_title': 'Meeting Minutes'
            }
            
            # Extract title/objective for PDF header
            if not session.get('text_override', False):
                mom_data = session.get('mom_data', {})
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
