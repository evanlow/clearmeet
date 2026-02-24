"""
Integration tests for Flask routes.

Tests the complete workflow from HTTP request to response.
"""
import pytest
import json
from unittest.mock import Mock, patch, MagicMock
from io import BytesIO

from app import create_app


class TestHealthRoute:
    """Tests for health check endpoint."""
    
    def test_health_returns_200(self, client):
        """Test that health endpoint returns 200 status."""
        response = client.get('/health')
        assert response.status_code == 200
    
    def test_health_returns_json(self, client):
        """Test that health endpoint returns JSON with correct fields."""
        response = client.get('/health')
        data = json.loads(response.data)
        assert data['status'] == 'ok'
        assert 'timestamp' in data
        assert data['service'] == 'clearmeet'
    
    def test_health_has_valid_timestamp(self, client):
        """Test that health endpoint returns ISO format timestamp."""
        response = client.get('/health')
        data = json.loads(response.data)
        # Should be valid ISO format (no exception thrown)
        from datetime import datetime
        # Handle timezone-aware timestamp
        ts = data['timestamp']
        if ts.endswith('Z'):
            ts = ts[:-1] + '+00:00'
        datetime.fromisoformat(ts)


class TestIndexRoute:
    """Tests for index route."""
    
    def test_index_returns_200(self, client):
        """Test that index page loads successfully."""
        response = client.get('/')
        assert response.status_code == 200
    
    def test_index_contains_form(self, client):
        """Test that index page contains the transcript form."""
        response = client.get('/')
        assert b'Generate MOM' in response.data
        assert b'transcript_text' in response.data


class TestProcessRoute:
    """Tests for process route."""
    
    @patch('app.extract_mom_from_transcript')
    def test_process_with_valid_transcript(self, mock_generate, client):
        """Test processing a valid transcript."""
        # Setup mock
        mock_mom_data = {
            'title': 'Test Meeting',
            'date': '2026-02-16',
            'objective': 'Test objective',
            'attendees': ['Alice', 'Bob'],
            'decisions': [{'text': 'Decision 1'}],
            'action_items': [
                {'action': 'Task 1', 'owner': 'Alice', 'deadline': '2026-03-01'}
            ]
        }
        mock_generate.return_value = mock_mom_data
        
        # Create valid transcript (100+ words)
        transcript = ' '.join(['test word'] * 60)
        
        # Submit form
        response = client.post('/process', data={
            'transcript_text': transcript,
            'additional_context': ''
        }, follow_redirects=False)
        
        # Should redirect to edit page
        assert response.status_code == 302
        assert '/edit' in response.location
    
    def test_process_without_transcript_fails(self, client):
        """Test that submitting without transcript shows error."""
        response = client.post('/process', data={
            'additional_context': ''
        }, follow_redirects=True)
        
        assert response.status_code == 200
        assert b'Please provide either a transcript' in response.data
    
    @patch('app.TranscriptParser.validate_transcript')
    def test_process_with_invalid_transcript_fails(self, mock_validate, client):
        """Test that invalid transcript causes redirect to index."""
        mock_validate.return_value = (False, "Transcript too short")
        
        response = client.post('/process', data={
            'transcript_text': 'short text',
            'additional_context': ''
        }, follow_redirects=False)
        
        # Should redirect back to index on validation failure
        assert response.status_code == 302
        assert '/' in response.location
    
    @patch('app.extract_mom_from_transcript')
    def test_process_stores_data_in_session(self, mock_generate, client):
        """Test that processed data is stored in session."""
        mock_mom_data = {
            'title': 'Test Meeting',
            'date': '2026-02-16',
            'objective': 'Test objective',
            'attendees': ['Alice'],
            'decisions': [],
            'action_items': []
        }
        mock_generate.return_value = mock_mom_data
        
        transcript = ' '.join(['word'] * 60)
        
        with client:
            response = client.post('/process', data={
                'transcript_text': transcript
            }, follow_redirects=False)
            
            # Check session data
            from flask import session
            assert 'mom_data' in session
            assert session['mom_data'] == mock_mom_data
            assert session['mom_json'] == mock_mom_data
            assert session['transcript']

    @patch('app.extract_mom_from_transcript')
    def test_generate_route_alias_with_valid_transcript(self, mock_generate, client):
        """Test /generate alias behaves like /process."""
        mock_mom_data = {
            'title': 'Test Meeting',
            'date': '2026-02-16',
            'objective': 'Test objective that is long enough',
            'attendees': ['Alice'],
            'decisions': [{'text': 'Decision 1'}],
            'action_items': [{'action': 'Task 1', 'owner': 'Alice', 'deadline': '2026-03-01', 'status': 'Open'}]
        }
        mock_generate.return_value = mock_mom_data

        transcript = ' '.join(['test word'] * 60)
        response = client.post('/generate', data={
            'transcript_text': transcript,
            'instructions': 'Focus on action items'
        }, follow_redirects=False)

        assert response.status_code == 302
        assert '/edit' in response.location


class TestEditRoute:
    """Tests for edit route."""
    
    def test_edit_without_session_redirects(self, client):
        """Test that accessing edit without session data redirects."""
        response = client.get('/edit', follow_redirects=False)
        
        assert response.status_code == 302
        assert '/' in response.location
    
    def test_edit_with_session_data_succeeds(self, client):
        """Test that edit page loads with session data."""
        with client.session_transaction() as sess:
            sess['mom_data'] = {
                'title': 'Test Meeting',
                'date': '2026-02-16',
                'objective': 'Test objective',
                'attendees': ['Alice'],
                'decisions': [],
                'action_items': []
            }
            sess['mom_text'] = 'Test MOM text'
        
        response = client.get('/edit')
        
        assert response.status_code == 200
        assert b'Test' in response.data


class TestUpdateRoute:
    """Tests for update route."""
    
    def test_update_with_structured_data(self, client):
        """Test updating MOM with structured data."""
        with client.session_transaction() as sess:
            sess['mom_data'] = {
                'title': 'Old title',
                'date': '2026-02-01',
                'objective': 'Old objective',
                'attendees': [],
                'decisions': [],
                'action_items': []
            }
        
        with client:
            response = client.post('/update', data={
                'title': 'New title',
                'date': '2026-02-16',
                'objective': 'New objective',
                'attendees': 'Alice, Bob',
                'decision_0': 'Decision 1',
                'decision_1': 'Decision 2',
                'action_count': '1',
                'action_action_0': 'Task 1',
                'action_owner_0': 'Alice',
                'action_deadline_0': '2026-03-01',
                'action_status_0': 'Open'
            }, follow_redirects=False)
            
            assert response.status_code == 302
            assert '/validate' in response.location
            
            from flask import session
            assert session['mom_data']['objective'] == 'New objective'
            assert session['mom_data']['decisions'] == [
                {'text': 'Decision 1'},
                {'text': 'Decision 2'}
            ]
            assert session['mom_data']['action_items'][0]['action'] == 'Task 1'
            assert session['text_override'] is False
            assert session.get('validated') is False

    def test_edit_post_route_alias_with_text(self, client):
        """Test POST /edit updates structured and full text."""
        with client.session_transaction() as sess:
            sess['mom_data'] = {
                'title': 'Old title',
                'date': '2026-02-01',
                'objective': 'Old objective is long enough',
                'attendees': ['Alice'],
                'decisions': [{'text': 'Old decision'}],
                'action_items': [{'action': 'Old action', 'owner': 'Alice', 'deadline': None, 'status': 'Open'}]
            }
            sess['mom_text'] = 'Old MOM text that is definitely long enough to pass checks.'

        with client:
            response = client.post('/edit', data={
                'title': 'New title',
                'date': '2026-02-16',
                'objective': 'New objective long enough',
                'attendees': 'Alice, Bob',
                'decision_0': 'Decision 1',
                'action_count': '1',
                'action_action_0': 'Task 1',
                'action_owner_0': 'Alice',
                'action_deadline_0': '2026-03-01',
                'action_status_0': 'Open',
                'text_override': 'true',
                'mom_text': 'Updated full text override content that is sufficiently long.'
            }, follow_redirects=False)

            assert response.status_code == 302
            assert '/validate' in response.location

            from flask import session
            assert session['mom_data']['title'] == 'New title'
            assert session['mom_text'].startswith('Updated full text override')
            assert session['text_override'] is True

    def test_update_with_text_override(self, client):
        """Test updating MOM with full text override."""
        with client.session_transaction() as sess:
            sess['mom_data'] = {
                'title': 'Old title',
                'date': '2026-02-01',
                'objective': 'Old objective',
                'attendees': [],
                'decisions': [],
                'action_items': []
            }
            sess['mom_text'] = 'Old MOM text'
        
        override_text = "This is the full MOM text override content that is long enough."
        
        with client:
            response = client.post('/update', data={
                'use_text_override': 'true',
                'mom_text_override': override_text
            }, follow_redirects=False)
            
            assert response.status_code == 302
            assert '/validate' in response.location
            
            from flask import session
            assert session['mom_text'] == override_text
            assert session['text_override'] is True


class TestValidateRoute:
    """Tests for validate route."""
    
    def test_validate_without_session_redirects(self, client):
        """Test that validate requires session data."""
        response = client.get('/validate', follow_redirects=False)
        
        assert response.status_code == 302
    
    def test_validate_with_session_data_succeeds(self, client):
        """Test that validate page loads with session data."""
        with client.session_transaction() as sess:
            sess['mom_data'] = {
                'title': 'Test Meeting',
                'date': '2026-02-16',
                'objective': 'Test objective that is long enough',
                'attendees': ['Alice'],
                'decisions': [{'text': 'Decision 1'}],
                'action_items': []
            }
            sess['mom_text'] = 'Test MOM text'
        
        response = client.get('/validate')
        
        assert response.status_code == 200

    def test_validate_still_checks_structured_with_text_override(self, client):
        """Text override should not bypass structured validation checks."""
        with client.session_transaction() as sess:
            sess['mom_data'] = {
                'title': 'Test Meeting',
                'date': '2026-02-16',
                'objective': '',
                'attendees': ['Alice'],
                'decisions': [{'text': 'Decision 1'}],
                'action_items': []
            }
            sess['mom_text'] = 'This is a sufficiently long edited MOM text override for validation page.'
            sess['text_override'] = True

        response = client.get('/validate')

        assert response.status_code == 200
        assert b'Meeting objective is missing' in response.data

    def test_validate_post_sets_validated_and_redirects_export(self, client):
        """POST /validate should require checklist and set validated flag."""
        with client.session_transaction() as sess:
            sess['mom_data'] = {
                'title': 'Test Meeting',
                'date': '2026-02-16',
                'objective': 'Test objective that is long enough',
                'attendees': ['Alice'],
                'decisions': [{'text': 'Decision 1'}],
                'action_items': [{'action': 'Task 1', 'owner': 'Alice', 'deadline': '2026-03-01', 'status': 'Open'}]
            }
            sess['mom_text'] = 'Valid MOM text that is long enough for text length checks.'

        checklist_ids = [
            'decisions_captured',
            'action_items_owners',
            'action_items_deadlines',
            'no_confidential_info',
            'ready_within_24h'
        ]

        with client:
            response = client.post('/validate', data={'checklist': checklist_ids}, follow_redirects=False)
            assert response.status_code == 302
            assert '/export' in response.location

            from flask import session
            assert session.get('validated') is True


class TestExportRoute:
    """Tests for export route."""
    
    @patch('app.PDFExporter.export_to_pdf')
    def test_export_generates_pdf(self, mock_export, client):
        """Test that export generates and returns PDF."""
        # Mock PDF buffer
        mock_buffer = BytesIO(b'%PDF-1.4 fake pdf content')
        mock_export.return_value = mock_buffer
        
        with client.session_transaction() as sess:
            sess['mom_text'] = 'Test MOM text'
            sess['mom_data'] = {
                'title': 'Test Meeting',
                'date': '2026-02-16',
                'objective': 'Test objective',
                'attendees': [],
                'decisions': [],
                'action_items': []
            }
        
        response = client.get('/export_mom')
        
        assert response.status_code == 200
        assert response.content_type == 'application/pdf'
    
    def test_export_without_session_fails(self, client):
        """Test that export requires session data."""
        response = client.get('/export_mom', follow_redirects=False)
        
        assert response.status_code == 302

    def test_export_route_requires_validated(self, client):
        """GET /export should enforce validated checklist."""
        with client.session_transaction() as sess:
            sess['mom_text'] = 'Test MOM text'
            sess['mom_data'] = {
                'title': 'Test Meeting',
                'date': '2026-02-16',
                'objective': 'Test objective',
                'attendees': [],
                'decisions': [],
                'action_items': []
            }
            sess['validated'] = False

        response = client.get('/export', follow_redirects=False)
        assert response.status_code == 302
        assert '/validate' in response.location


class TestErrorHandlers:
    """Tests for error handlers."""
    
    def test_404_error_handler(self, client):
        """Test 404 error handler."""
        response = client.get('/nonexistent-page', follow_redirects=False)
        
        assert response.status_code == 302
        assert '/' in response.location


class TestAgendaWorkflow:
    """Tests for pre-meeting agenda workflow (Steps 1-2)."""
    
    @patch('app.AgendaBuilder.generate_agenda_with_ai')
    def test_save_agenda_redirects_with_flag(self, mock_generate, client):
        """Test that saving agenda redirects to index with agenda_saved flag."""
        with client.session_transaction() as sess:
            sess['meeting_objective'] = {
                'business_issue': 'Test issue',
                'objective': 'Test objective',
                'expected_output': 'Test output'
            }
        
        with client:
            response = client.post('/meeting/agenda/save',
                json={
                    'items': [
                        {'title': 'Item 1', 'duration_minutes': 15, 'description': ''},
                        {'title': 'Item 2', 'duration_minutes': 20, 'description': 'Test'}
                    ]
                },
                content_type='application/json',
                follow_redirects=False
            )
            
            data = json.loads(response.data)
            assert response.status_code == 200
            assert data['success'] is True
            assert 'agenda_saved=true' in data['redirect_url']
            
            from flask import session
            assert session['agenda_completed'] is True
            assert len(session['agenda_items']) == 2
    
    def test_index_shows_agenda_status_when_present(self, client):
        """Test that index page displays agenda status when session has agenda_items."""
        with client.session_transaction() as sess:
            sess['agenda_items'] = [
                {'title': 'Intro', 'duration_minutes': 10, 'description': ''},
                {'title': 'Review', 'duration_minutes': 20, 'description': ''}
            ]
        
        response = client.get('/')
        assert response.status_code == 200
        assert b'Meeting Plan Ready' in response.data
        assert b'2 items' in response.data or b'30 minutes' in response.data

    def test_index_shows_download_agenda_pdf_button(self, client):
        """Test that index page shows agenda PDF download CTA when agenda exists."""
        with client.session_transaction() as sess:
            sess['agenda_items'] = [
                {'title': 'Intro', 'duration_minutes': 10, 'description': ''}
            ]

        response = client.get('/')

        assert response.status_code == 200
        assert b'Download Agenda PDF' in response.data
        assert b'/meeting/agenda/export' in response.data

    def test_export_agenda_pdf_requires_saved_agenda(self, client):
        """Test agenda export redirects when no saved agenda exists in session."""
        response = client.get('/meeting/agenda/export', follow_redirects=False)

        assert response.status_code == 302
        assert '/meeting/agenda' in response.location

    def test_export_agenda_pdf_returns_attachment(self, client):
        """Test agenda export returns downloadable PDF when session has agenda."""
        with client.session_transaction() as sess:
            sess['meeting_objective'] = {
                'business_issue': 'Align teams',
                'objective': 'Finalize Q2 priorities',
                'expected_output': 'Approved plan'
            }
            sess['agenda_items'] = [
                {'title': 'Project updates', 'duration_minutes': 15, 'description': 'Team status roundtable'},
                {'title': 'Risk review', 'duration_minutes': 20, 'description': 'Top blockers and mitigations'}
            ]

        response = client.get('/meeting/agenda/export')

        assert response.status_code == 200
        assert response.mimetype == 'application/pdf'
        disposition = response.headers.get('Content-Disposition', '')
        assert 'attachment;' in disposition
        assert 'Agenda_' in disposition
