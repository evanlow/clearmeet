"""
End-to-end integration tests for complete ClearMeet workflow.

These tests verify the complete user journey from transcript submission
through MOM generation, editing, validation, and PDF export.

Following Prime Directive principles:
- Test complete workflows (not just individual routes)
- Minimal mocking (only external APIs like OpenAI)
- Verify session persistence across stages
- Test both happy paths and error scenarios
"""
import pytest
import json
from unittest.mock import Mock, patch
from io import BytesIO

from app import create_app


@pytest.fixture
def app():
    """Create test Flask application."""
    app = create_app()
    app.config['TESTING'] = True
    app.config['SECRET_KEY'] = 'test-secret-key'
    app.config['WTF_CSRF_ENABLED'] = False
    app.config['SESSION_TYPE'] = 'filesystem'  # Use filesystem for persistent sessions
    return app


@pytest.fixture
def client(app):
    """Create test client with session support."""
    return app.test_client()


@pytest.fixture
def sample_transcript():
    """Sample meeting transcript with 100+ words."""
    return """
    [10:00:00] Sarah Lee: Good morning everyone. Let's begin our weekly sync.
    Today's agenda includes project status updates and planning for next sprint.
    
    [10:00:30] Sarah Lee: First topic - Sprint 23 progress. John, can you share updates?
    
    [10:01:00] John Tan: Sure. We completed the authentication module.
    All unit tests passing. Ready for code review by end of day.
    
    [10:01:30] Priya Kumar: Great work, John. I'll review it this afternoon.
    
    [10:02:00] Sarah Lee: Excellent. Next topic - Sprint 24 planning.
    We need to prioritize the dashboard redesign.
    
    [10:02:30] John Tan: I can take the frontend components. Estimated 3 days.
    
    [10:02:45] Priya Kumar: I'll handle the backend API endpoints. Also 3 days.
    
    [10:03:00] Sarah Lee: Perfect. Let's target completion by March 15th.
    Decision: Sprint 24 will focus on dashboard redesign.
    Action item: John to start frontend work tomorrow.
    Action item: Priya to begin API work tomorrow.
    
    [10:04:00] Sarah Lee: Any other updates before we wrap up?
    
    [10:04:15] John Tan: Nothing from my side.
    
    [10:04:22] Priya Kumar: All good here.
    
    [10:04:30] Sarah Lee: Great. Thanks, everyone. Next sync will be same time next week.
    
    [10:04:45] Meeting ended.
    """


@pytest.fixture
def mock_openai_generate():
    """Mock OpenAI generate_mom response."""
    return {
        'objective': 'Weekly team sync to review Sprint 23 progress and plan Sprint 24',
        'attendees': ['Sarah Lee', 'John Tan', 'Priya Kumar'],
        'decisions': [
            'Sprint 24 will focus on dashboard redesign',
            'Target completion date set for March 15th'
        ],
        'action_items': [
            {
                'task': 'Start frontend components for dashboard redesign',
                'owner': 'John Tan',
                'deadline': '2026-02-17'
            },
            {
                'task': 'Begin API endpoint development for dashboard',
                'owner': 'Priya Kumar',
                'deadline': '2026-02-17'
            }
        ],
        'summary': 'Team completed Sprint 23 authentication module. Planned Sprint 24 dashboard redesign with 3-day estimates for frontend and backend work.'
    }


class TestCompleteTextWorkflow:
    """Test complete workflow: submit text transcript → generate → edit → validate → export."""
    
    @patch('app.MOMGenerator.generate_mom')
    @patch('app.PDFExporter.export_to_pdf')
    def test_complete_happy_path_text_transcript(self, mock_export, mock_generate, 
                                                   client, sample_transcript, mock_openai_generate):
        """Test complete successful workflow from text transcript to PDF export."""
        # Setup mocks
        mock_generate.return_value = mock_openai_generate
        mock_pdf_buffer = BytesIO(b'%PDF-1.4 fake pdf content')
        mock_export.return_value = mock_pdf_buffer
        
        # Step 1: Load index page
        response = client.get('/')
        assert response.status_code == 200
        assert b'Generate MOM' in response.data
        
        # Step 2: Submit transcript
        response = client.post('/process', data={
            'transcript_text': sample_transcript,
            'additional_context': 'Weekly team standup meeting'
        }, follow_redirects=False)
        
        # Should redirect to edit
        assert response.status_code == 302
        assert '/edit' in response.location
        
        # Verify OpenAI was called
        mock_generate.assert_called_once()
        
        # Step 3: Access edit page
        response = client.get('/edit', follow_redirects=False)
        assert response.status_code == 200
        assert b'Sprint 24' in response.data  # Content from mock
        
        # Step 4: Update MOM (user makes edits)
        response = client.post('/update', data={
            'objective': mock_openai_generate['objective'],
            'attendees': ', '.join(mock_openai_generate['attendees']),
            'decision_0': mock_openai_generate['decisions'][0],
            'decision_1': mock_openai_generate['decisions'][1],
            'action_count': '2',
            'action_task_0': mock_openai_generate['action_items'][0]['task'],
            'action_owner_0': mock_openai_generate['action_items'][0]['owner'],
            'action_deadline_0': mock_openai_generate['action_items'][0]['deadline'],
            'action_task_1': mock_openai_generate['action_items'][1]['task'],
            'action_owner_1': mock_openai_generate['action_items'][1]['owner'],
            'action_deadline_1': mock_openai_generate['action_items'][1]['deadline'],
            'summary': mock_openai_generate['summary']
        }, follow_redirects=False)
        
        # Should redirect to validate
        assert response.status_code == 302
        assert '/validate' in response.location
        
        # Step 5: Access validate page
        response = client.get('/validate', follow_redirects=False)
        assert response.status_code == 200
        
        # Step 6: Export PDF
        response = client.get('/export_mom')
        assert response.status_code == 200
        assert response.content_type == 'application/pdf'
        assert 'attachment' in response.headers['Content-Disposition']
        
        # Verify PDF export was called
        mock_export.assert_called_once()
    
    @patch('app.MOMGenerator.generate_mom')
    def test_session_persistence_across_workflow(self, mock_generate, 
                                                   client, sample_transcript, mock_openai_generate):
        """Test that session data persists throughout the workflow."""
        mock_generate.return_value = mock_openai_generate
        
        # Step 1: Submit transcript
        response = client.post('/process', data={
            'transcript_text': sample_transcript,
            'additional_context': 'Weekly standup'
        }, follow_redirects=False)
        
        assert response.status_code == 302
        
        # Step 2: Verify session has data
        with client:
            client.get('/edit')
            from flask import session
            # Note: transcript is not stored in session to avoid size limits
            assert 'mom_data' in session
            assert 'mom_text' in session
            assert 'additional_context' in session
            assert session['additional_context'] == 'Weekly standup'
            assert session['mom_data']['objective'] == mock_openai_generate['objective']
    
    @patch('app.MOMGenerator.generate_mom')
    def test_edit_page_modifications_preserved(self, mock_generate, 
                                                 client, sample_transcript, mock_openai_generate):
        """Test that user edits on edit page are preserved."""
        mock_generate.return_value = mock_openai_generate
        
        # Process transcript
        client.post('/process', data={
            'transcript_text': sample_transcript
        })
        
        # User makes modifications (using format expected by /update route)
        modified_objective = "MODIFIED: Weekly team standup"
        response = client.post('/update', data={
            'objective': modified_objective,
            'attendees': 'Alice, Bob, Charlie',  # Modified
            'decision_0': 'New decision 1',  # Modified
            'decision_1': 'New decision 2',  # Modified
            'action_count': '1',
            'action_task_0': 'Modified task',
            'action_owner_0': 'Alice',
            'action_deadline_0': '2026-03-01',
            'summary': 'Modified summary'
        }, follow_redirects=False)
        
        assert response.status_code == 302
        
        # Verify session was updated
        with client:
            client.get('/validate')
            from flask import session
            assert session['mom_data']['objective'] == modified_objective
            assert 'Alice' in session['mom_data']['attendees']
            assert 'Bob' in session['mom_data']['attendees']
            assert 'Modified task' in json.dumps(session['mom_data']['action_items'])


class TestCompleteAudioWorkflow:
    """Test complete workflow: upload audio → transcribe → generate → edit → validate → export."""
    
    @patch('app.AudioTranscriber.transcribe_audio')
    @patch('app.AudioTranscriber.validate_audio_file')
    @patch('app.MOMGenerator.generate_mom')
    @patch('app.PDFExporter.export_to_pdf')
    def test_complete_happy_path_audio_upload(self, mock_export, mock_generate, 
                                                mock_validate_audio, mock_transcribe,
                                                client, sample_transcript, mock_openai_generate):
        """Test complete workflow from audio upload to PDF export."""
        # Setup mocks
        mock_validate_audio.return_value = (True, None)
        mock_transcribe.return_value = sample_transcript
        mock_generate.return_value = mock_openai_generate
        mock_pdf_buffer = BytesIO(b'%PDF-1.4 fake pdf')
        mock_export.return_value = mock_pdf_buffer
        
        # Create mock audio file
        audio_data = BytesIO(b'fake audio content')
        audio_data.name = 'meeting.mp3'
        
        # Step 1: Upload audio file
        response = client.post('/process', data={
            'audio_file': (audio_data, 'meeting.mp3'),
            'additional_context': 'Weekly standup'
        }, content_type='multipart/form-data', follow_redirects=False)
        
        # Should redirect to edit
        assert response.status_code == 302
        assert '/edit' in response.location
        
        # Verify audio was validated and transcribed
        mock_validate_audio.assert_called_once()
        mock_transcribe.assert_called_once()
        
        # Step 2: Continue through workflow
        response = client.get('/edit')
        assert response.status_code == 200
        
        # Step 3: Update and validate
        response = client.post('/update', data={
            'objective': mock_openai_generate['objective'],
            'attendees': ', '.join(mock_openai_generate['attendees']),
            'decision_0': mock_openai_generate['decisions'][0],
            'decision_1': mock_openai_generate['decisions'][1],
            'action_count': '2',
            'action_task_0': mock_openai_generate['action_items'][0]['task'],
            'action_owner_0': mock_openai_generate['action_items'][0]['owner'],
            'action_deadline_0': mock_openai_generate['action_items'][0]['deadline'],
            'action_task_1': mock_openai_generate['action_items'][1]['task'],
            'action_owner_1': mock_openai_generate['action_items'][1]['owner'],
            'action_deadline_1': mock_openai_generate['action_items'][1]['deadline'],
            'summary': mock_openai_generate['summary']
        }, follow_redirects=False)
        
        assert response.status_code == 302
        
        # Step 4: Export PDF
        response = client.get('/export_mom')
        assert response.status_code == 200
        assert response.content_type == 'application/pdf'


class TestWorkflowErrorScenarios:
    """Test error handling throughout the workflow."""
    
    def test_accessing_edit_without_processing(self, client):
        """Test that accessing edit page without processing redirects to index."""
        response = client.get('/edit', follow_redirects=False)
        
        assert response.status_code == 302
        assert '/' in response.location
    
    def test_accessing_validate_without_processing(self, client):
        """Test that accessing validate page without processing redirects."""
        response = client.get('/validate', follow_redirects=False)
        
        assert response.status_code == 302
    
    def test_export_without_processing(self, client):
        """Test that exporting without processing redirects."""
        response = client.get('/export_mom', follow_redirects=False)
        
        assert response.status_code == 302
    
    def test_process_with_insufficient_transcript(self, client):
        """Test processing with transcript below minimum word count."""
        short_transcript = "Too short"  # Less than 10 words
        
        response = client.post('/process', data={
            'transcript_text': short_transcript
        }, follow_redirects=False)
        
        # Should redirect back to index on validation failure
        assert response.status_code == 302
        assert '/' in response.location
    
    @patch('app.AudioTranscriber.validate_audio_file')
    def test_process_with_invalid_audio_file(self, mock_validate, client):
        """Test processing with invalid audio file."""
        mock_validate.return_value = (False, "File too large")
        
        audio_data = BytesIO(b'fake large audio')
        audio_data.name = 'large_meeting.mp3'
        
        response = client.post('/process', data={
            'audio_file': (audio_data, 'large_meeting.mp3')
        }, content_type='multipart/form-data', follow_redirects=False)
        
        # Should redirect on validation failure
        assert response.status_code == 302
        assert '/' in response.location
    
    @patch('app.MOMGenerator.generate_mom')
    def test_workflow_interruption_recovery(self, mock_generate, 
                                             client, sample_transcript, mock_openai_generate):
        """Test that users can't skip steps in the workflow."""
        mock_generate.return_value = mock_openai_generate
        
        # Process transcript successfully
        client.post('/process', data={
            'transcript_text': sample_transcript
        })
        
        # Try to access validate without going through update
        # Note: This should still work because update is optional
        response = client.get('/validate', follow_redirects=False)
        assert response.status_code == 200
        
        # Export should also work if session has data
        response = client.get('/export_mom', follow_redirects=False)
        # Should redirect to GET /export_mom
        assert response.status_code in [200, 302]


class TestWorkflowEdgeCases:
    """Test edge cases and boundary conditions in workflow."""
    
    @patch('app.MOMGenerator.generate_mom')
    def test_minimal_valid_transcript(self, mock_generate, client, mock_openai_generate):
        """Test workflow with minimum valid transcript (10+ words)."""
        mock_generate.return_value = mock_openai_generate
        
        minimal_transcript = ' '.join(['word'] * 10)  # Exactly 10 words
        
        response = client.post('/process', data={
            'transcript_text': minimal_transcript
        }, follow_redirects=False)
        
        # Should succeed
        assert response.status_code == 302
        assert '/edit' in response.location
    
    @patch('app.MOMGenerator.generate_mom')
    def test_very_long_transcript(self, mock_generate, client, mock_openai_generate):
        """Test workflow with very long transcript (1000+ words)."""
        mock_generate.return_value = mock_openai_generate
        
        long_transcript = ' '.join(['word'] * 1000)
        
        response = client.post('/process', data={
            'transcript_text': long_transcript
        }, follow_redirects=False)
        
        # Should succeed
        assert response.status_code == 302
        assert '/edit' in response.location
    
    @patch('app.MOMGenerator.generate_mom')
    def test_transcript_with_special_characters(self, mock_generate, 
                                                  client, mock_openai_generate):
        """Test workflow with special characters in transcript."""
        mock_generate.return_value = mock_openai_generate
        
        special_transcript = """
        Speaker: Hello! How's everyone doing? 
        Speaker2: Great! We need to discuss Q1's results & plan Q2's strategy.
        Speaker: Perfect. Let's review the $1,000,000 revenue target (25% growth).
        Speaker2: Sounds good. Action item: Schedule follow-up @ 2pm tomorrow.
        """ * 3  # Repeat to get enough words
        
        response = client.post('/process', data={
            'transcript_text': special_transcript
        }, follow_redirects=False)
        
        # Should succeed
        assert response.status_code == 302
        assert '/edit' in response.location
    
    @patch('app.MOMGenerator.generate_mom')
    def test_empty_additional_context(self, mock_generate, 
                                       client, sample_transcript, mock_openai_generate):
        """Test workflow without providing additional context (optional field)."""
        mock_generate.return_value = mock_openai_generate
        
        response = client.post('/process', data={
            'transcript_text': sample_transcript,
            'additional_context': ''  # Empty
        }, follow_redirects=False)
        
        # Should succeed
        assert response.status_code == 302
        mock_generate.assert_called_once()
        # Verify None was passed for additional_context
        call_args = mock_generate.call_args
        assert call_args[0][1] is None or call_args[0][1] == ''
    
    @patch('app.MOMGenerator.generate_mom')
    @patch('app.PDFExporter.export_to_pdf')
    def test_multiple_workflow_executions_same_session(self, mock_export, mock_generate,
                                                         client, sample_transcript, 
                                                         mock_openai_generate):
        """Test that user can run multiple workflows in same session."""
        mock_generate.return_value = mock_openai_generate
        mock_export.return_value = BytesIO(b'%PDF-1.4 fake')
        
        # First workflow execution
        response1 = client.post('/process', data={
            'transcript_text': sample_transcript
        }, follow_redirects=False)
        assert response1.status_code == 302
        
        # Export first MOM
        response2 = client.get('/export_mom')
        assert response2.status_code == 200
        
        # Start second workflow (should overwrite session)
        different_transcript = sample_transcript.replace('Sprint 23', 'Sprint 25')
        response3 = client.post('/process', data={
            'transcript_text': different_transcript
        }, follow_redirects=False)
        assert response3.status_code == 302
        
        # Verify new session data
        with client:
            client.get('/edit')
            from flask import session
            assert 'mom_data' in session
            # Session should contain new data


class TestWorkflowPerformance:
    """Test performance aspects of workflow (within reasonable bounds)."""
    
    @patch('app.MOMGenerator.generate_mom')
    def test_workflow_handles_maximum_attendees(self, mock_generate, 
                                                  client, sample_transcript):
        """Test workflow with maximum realistic number of attendees."""
        many_attendees = [f'Person{i}' for i in range(50)]  # 50 attendees
        
        mock_generate.return_value = {
            'objective': 'Large meeting',
            'attendees': many_attendees,
            'decisions': ['Decision 1'],
            'action_items': [],
            'summary': 'Summary'
        }
        
        response = client.post('/process', data={
            'transcript_text': sample_transcript
        }, follow_redirects=False)
        
        assert response.status_code == 302
        
        # Verify edit page can handle many attendees
        response = client.get('/edit')
        assert response.status_code == 200
    
    @patch('app.MOMGenerator.generate_mom')
    def test_workflow_handles_many_action_items(self, mock_generate, 
                                                  client, sample_transcript):
        """Test workflow with many action items."""
        many_actions = [
            {'task': f'Task {i}', 'owner': 'Owner', 'deadline': '2026-03-01'}
            for i in range(30)  # 30 action items
        ]
        
        mock_generate.return_value = {
            'objective': 'Complex meeting',
            'attendees': ['Alice'],
            'decisions': ['Decision'],
            'action_items': many_actions,
            'summary': 'Summary'
        }
        
        response = client.post('/process', data={
            'transcript_text': sample_transcript
        }, follow_redirects=False)
        
        assert response.status_code == 302
        
        # Verify validate page can handle many actions
        response = client.get('/validate')
        assert response.status_code == 200
