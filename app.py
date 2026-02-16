"""
ClearMeet Flask Application

Main Flask app with routes for MOM generation workflow.
"""
from flask import Flask, render_template, request, session, redirect, url_for, send_file, flash, g
from werkzeug.utils import secure_filename
import os
import json
from datetime import datetime
from typing import Optional
import threading

from config import get_config, Config
from core.parser import TranscriptParser
from core.llm import extract_mom_from_transcript, render_mom_text, transcribe_audio
from core.audio import AudioTranscriber
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
    
    # Routes
    @app.route('/')
    def index():
        """Landing page with input options."""
        # Clear any existing session data for fresh start
        session.clear()
        return render_template('index.html')
    
    @app.route('/process', methods=['GET', 'POST'])
    def process_input():
        """
        Process transcript input (text or audio file).
        
        Returns redirect to edit page with structured MOM data.
        """
        if request.method == 'GET':
            print("[DEBUG] ⚠️ WARNING: GET request to /process - redirecting to index")
            flash('Please use the form to submit your transcript', 'warning')
            return redirect(url_for('index'))
        
        try:
            print("\n" + "="*80)
            print("[DEBUG] ===== PROCESS INPUT STARTED =====")
            print(f"[DEBUG] Request method: {request.method}")
            print(f"[DEBUG] Request URL: {request.url}")
            print(f"[DEBUG] Form data keys: {list(request.form.keys())}")
            print(f"[DEBUG] Files keys: {list(request.files.keys())}")
            print(f"[DEBUG] Content-Type: {request.content_type}")
            print(f"[DEBUG] transcript_text in form: {'transcript_text' in request.form}")
            if 'transcript_text' in request.form:
                transcript_preview = request.form['transcript_text'][:200] if len(request.form['transcript_text']) > 200 else request.form['transcript_text']
                print(f"[DEBUG] transcript_text value (first 200 chars): '{transcript_preview}'")
                print(f"[DEBUG] transcript_text length: {len(request.form['transcript_text'])}")
            print("="*80 + "\n")
            
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
                            
                            with _progress_lock:
                                # Track chunk durations for average calculation
                                if 'progress_chunks' not in _progress_state:
                                    _progress_state['progress_chunks'] = []
                                
                                _progress_state['progress_chunks'].append(progress_data.get('duration_sec', 0))
                                
                                # Calculate average time per chunk
                                progress_data['avg_time_per_chunk'] = sum(_progress_state['progress_chunks']) / len(_progress_state['progress_chunks'])
                                _progress_state['current_progress'] = progress_data
                                
                            print(f"[PROGRESS] Chunk {progress_data.get('chunk')}/{progress_data.get('total_chunks')} - {progress_data.get('avg_time_per_chunk', 0):.1f}s avg")
                        
                        # Transcribe audio (with automatic chunking for large files)
                        transcript = transcribe_audio(filepath, progress_callback=progress_callback)
                        
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
            additional_context = request.form.get('additional_context', '')
            print(f"[DEBUG] Additional context: '{additional_context[:100] if additional_context else 'None'}'")
            
            mom_data = extract_mom_from_transcript(
                transcript,
                objective=None,
                instructions=additional_context or None
            )
            print(f"[DEBUG] ✓ MOM generated successfully")
            print(f"[DEBUG] MOM data keys: {list(mom_data.keys()) if mom_data else None}")
            print(f"[DEBUG] MOM objective: {mom_data.get('objective', 'N/A')[:100] if mom_data else 'N/A'}")
            print(f"[DEBUG] MOM attendees count: {len(mom_data.get('attendees', [])) if mom_data else 0}")
            print(f"[DEBUG] MOM decisions count: {len(mom_data.get('decisions', [])) if mom_data else 0}")
            print(f"[DEBUG] MOM action_items count: {len(mom_data.get('action_items', [])) if mom_data else 0}")
            
            # Store in session (exclude transcript to avoid session size limits)
            print("\n[DEBUG] --- SESSION STORAGE STAGE ---")
            session['mom_data'] = mom_data
            session['mom_text'] = render_mom_text(mom_data)
            session['additional_context'] = additional_context
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
            
            while True:
                with _progress_lock:
                    progress_data = _progress_state.get('current_progress', {})
                
                if progress_data and progress_data.get('chunk', 0) > last_chunk:
                    consecutive_empty = 0
                    chunk = progress_data.get('chunk', 0)
                    total = progress_data.get('total_chunks', 1)
                    percent = int((chunk / total) * 100) if total > 0 else 0
                    avg_time = progress_data.get('avg_time_per_chunk', 0)
                    estimated_remaining = (total - chunk) * avg_time
                    
                    yield f'data: {json.dumps({"chunk": chunk, "total_chunks": total, "percent": percent, "estimated_seconds": int(estimated_remaining)})}\n\n'
                    last_chunk = chunk
                    print(f"[SSE] Sent progress: Chunk {chunk}/{total} ({percent}%)")
                    
                    # If completed, signal end
                    if chunk >= total:
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
        
        return render_template('edit.html', mom_data=mom_data, mom_text=mom_text)
    
    @app.route('/update', methods=['POST'])
    def update_mom():
        """
        Update MOM data from edit form.
        
        Handles both structured edits and full text override.
        """
        try:
            # Check if full text override is being used
            if request.form.get('use_text_override') == 'true':
                # User chose to override with full text
                mom_text = request.form.get('mom_text_override', '')
                
                if not mom_text or len(mom_text.strip()) < 50:
                    flash('MOM text is too short or empty', 'error')
                    return redirect(url_for('edit'))
                
                session['mom_text'] = mom_text
                session['text_override'] = True
                
            else:
                # Update structured data
                mom_data = session.get('mom_data', {})
                
                # Update title and date
                mom_data['title'] = request.form.get('title', '')
                mom_data['date'] = request.form.get('date', '')

                # Update objective
                mom_data['objective'] = request.form.get('objective', '')
                
                # Update attendees
                attendees_str = request.form.get('attendees', '')
                attendees_list = [a.strip() for a in attendees_str.split(',') if a.strip()]
                mom_data['attendees'] = attendees_list if attendees_list else None
                
                # Update decisions
                decisions = []
                for key in request.form.keys():
                    if key.startswith('decision_'):
                        decision = request.form.get(key, '').strip()
                        if decision:
                            decisions.append({'text': decision})
                mom_data['decisions'] = decisions
                
                # Update action items
                action_items = []
                action_count = int(request.form.get('action_count', 0))
                for i in range(action_count):
                    action = request.form.get(f'action_action_{i}', '').strip()
                    owner = request.form.get(f'action_owner_{i}', '').strip()
                    deadline = request.form.get(f'action_deadline_{i}', '').strip() or None
                    status = request.form.get(f'action_status_{i}', '').strip() or 'Open'

                    if action:  # Only add if action is not empty
                        action_items.append({
                            'action': action,
                            'owner': owner or '',
                            'deadline': deadline,
                            'status': status
                        })
                mom_data['action_items'] = action_items

                # Update parking lot
                parking_lot_str = request.form.get('parking_lot', '')
                if parking_lot_str.strip():
                    mom_data['parking_lot'] = [p.strip() for p in parking_lot_str.split(',') if p.strip()]
                else:
                    mom_data['parking_lot'] = None

                # Update notes
                notes = request.form.get('notes', '').strip()
                mom_data['notes'] = notes if notes else None

                # Update confidentiality flags
                flags_str = request.form.get('confidentiality_flags', '')
                if flags_str.strip():
                    mom_data['confidentiality_flags'] = [f.strip() for f in flags_str.split(',') if f.strip()]
                else:
                    mom_data['confidentiality_flags'] = None
                
                # Store updated data
                session['mom_data'] = mom_data
                session['mom_text'] = render_mom_text(mom_data)
                session['text_override'] = False
            
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
        
        # Validate MOM content if not using text override
        content_issues = []
        if not session.get('text_override', False):
            mom_data = session.get('mom_data', {})
            is_valid, content_issues = MOMValidator.validate_mom_content(mom_data)
        
        # Validate text length
        mom_text = session.get('mom_text', '')
        text_valid, text_message = MOMValidator.validate_text_length(mom_text)
        if not text_valid:
            content_issues.append(text_message)
        
        return render_template(
            'validate.html',
            checklist=checklist,
            content_issues=content_issues,
            mom_text=mom_text
        )
    
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
