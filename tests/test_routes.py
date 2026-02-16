"""
Integration tests for Flask routes.

Tests the complete workflow from HTTP request to response.
"""
import pytest
import json
from unittest.mock import Mock, patch, MagicMock
from io import BytesIO

from app import create_app


@pytest.fixture
def app():
    """Create test Flask application."""
    app = create_app()
    app.config['TESTING'] = True
    app.config['SECRET_KEY'] = 'test-secret-key'
    app.config['WTF_CSRF_ENABLED'] = False  # Disable CSRF for testing
    app.config['SESSION_TYPE'] = 'null'  # Use simple sessions for testing
    return app


@pytest.fixture
def client(app):
    """Create test client."""
    return app.test_client()


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
    
    @patch('app.MOMGenerator.generate_mom')
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
    
    @patch('app.MOMGenerator.generate_mom')
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
    
    @patch('app.MOMGenerator.render_mom_text')
    def test_update_with_structured_data(self, mock_render, client):
        """Test updating MOM with structured data."""
        mock_render.return_value = "Rendered MOM text"
        
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


class TestErrorHandlers:
    """Tests for error handlers."""
    
    def test_404_error_handler(self, client):
        """Test 404 error handler."""
        response = client.get('/nonexistent-page', follow_redirects=False)
        
        assert response.status_code == 302
        assert '/' in response.location

