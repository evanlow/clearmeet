"""
Tests for session persistence across redirects and routes.

This test suite specifically tests that session data survives across
the complete workflow: process_input -> edit -> validate -> export_mom
"""
import pytest
from unittest.mock import patch, MagicMock
from app import create_app


@pytest.fixture
def app():
    """Create and configure a test app instance."""
    app = create_app('testing')
    app.config['TESTING'] = True
    app.config['WTF_CSRF_ENABLED'] = False
    yield app


@pytest.fixture
def client(app):
    """Create a test client."""
    return app.test_client()


@pytest.fixture
def mock_llm_response():
    """Mock LLM response for testing."""
    return {
        'title': 'Test Meeting',
        'date': '2024-01-15',
        'objective': 'Test Objective',
        'attendees': ['Alice', 'Bob'],
        'decisions': [{'text': 'Decision 1'}],
        'action_items': [
            {
                'action': 'Test action',
                'owner': 'Alice',
                'deadline': '2024-02-01',
                'status': 'Open'
            }
        ]
    }


class TestSessionPersistence:
    """Test session data persistence across the workflow."""
    
    def test_session_data_survives_process_to_edit(self, client, mock_llm_response):
        """Test that session data persists from /process to /edit."""
        with patch('core.llm.extract_mom_from_transcript') as mock_extract:
            mock_extract.return_value = mock_llm_response
            
            # Step 1: Submit transcript (must be 10+ words)
            response = client.post('/process', data={
                'transcript_text': 'This is a test transcript for the meeting with enough words to pass validation requirements.'
            }, follow_redirects=False)
            
            assert response.status_code == 302  # Redirect
            assert '/edit' in response.location
            
            # Step 2: Access edit page (should have session data)
            with client.session_transaction() as sess:
                print(f"Session keys after /process: {list(sess.keys())}")
                print(f"'mom_data' in session: {'mom_data' in sess}")
                assert 'mom_data' in sess, "Session should contain mom_data after /process"
                assert 'mom_text' in sess, "Session should contain mom_text after /process"
                
            response = client.get('/edit')
            assert response.status_code == 200, "Edit page should load successfully"
            assert b'No MOM data found' not in response.data
    
    def test_session_data_survives_edit_to_validate(self, client, mock_llm_response):
        """Test that session data persists from /edit to /validate."""
        with patch('core.llm.extract_mom_from_transcript') as mock_extract:
            mock_extract.return_value = mock_llm_response
            
            # Step 1: Submit transcript (must be 10+ words)
            client.post('/process', data={
                'transcript_text': 'This is a test transcript for the meeting with enough words to pass validation.'
            })
            
            # Step 2: Submit edits
            response = client.post('/edit', data={
                'title': 'Updated Title',
                'objective': 'Updated Objective'
            }, follow_redirects=False)
            
            assert response.status_code == 302
            assert '/validate' in response.location
            
            # Step 3: Check session persists to validate page
            with client.session_transaction() as sess:
                print(f"Session keys after /edit: {list(sess.keys())}")
                assert 'mom_data' in sess, "Session should contain mom_data after /edit"
                assert 'mom_text' in sess, "Session should contain mom_text after /edit"
            
            response = client.get('/validate')
            assert response.status_code == 200
            assert b'No MOM data found' not in response.data
    
    def test_session_data_survives_validate_to_export(self, client, mock_llm_response):
        """Test that session data persists from /validate to /export_mom."""
        with patch('core.llm.extract_mom_from_transcript') as mock_extract:
            mock_extract.return_value = mock_llm_response
            
            # Step 1: Submit transcript (must be 10+ words)
            client.post('/process', data={
                'transcript_text': 'This is a test transcript for the meeting with enough words to pass validation.'
            })
            
            # Step 2: Submit edits
            client.post('/edit', data={
                'title': 'Test Title'
            })
            
            # Step 3: Access validate page
            response = client.get('/validate')
            assert response.status_code == 200
            
            # Step 4: Check session before export
            with client.session_transaction() as sess:
                print(f"Session keys before export: {list(sess.keys())}")
                print(f"'mom_text' in session: {'mom_text' in sess}")
                print(f"mom_text length: {len(sess.get('mom_text', ''))}")
                assert 'mom_text' in sess, "Session should contain mom_text before export"
                assert len(sess.get('mom_text', '')) > 0, "mom_text should not be empty"
            
            # Step 5: Submit validation (this redirects to export_mom)
            response = client.post('/validate', data={
                'checklist': [
                    'decisions_captured',
                    'action_items_owners',
                    'action_items_deadlines',
                    'no_confidential_info',
                    'ready_within_24h'
                ]
            }, follow_redirects=False)
            
            assert response.status_code == 302
            assert '/export' in response.location
            
            # Step 6: Check session persists to export
            with client.session_transaction() as sess:
                print(f"Session keys after validate submit: {list(sess.keys())}")
                print(f"'mom_text' in session: {'mom_text' in sess}")
                print(f"mom_text length: {len(sess.get('mom_text', ''))}")
                assert 'mom_text' in sess, "Session should contain mom_text after validate"
                assert len(sess.get('mom_text', '')) > 0, "mom_text should not be empty after validate"
    
    def test_full_workflow_session_persistence(self, client, mock_llm_response):
        """Test complete workflow from input to export maintains session."""
        with patch('core.llm.extract_mom_from_transcript') as mock_extract:
            mock_extract.return_value = mock_llm_response
            
            # Step 1: Submit transcript
            print("\n=== STEP 1: Submit transcript ===")
            response = client.post('/process', data={
                'transcript_text': 'This is a test transcript with enough content to be valid.'
            }, follow_redirects=True)
            assert response.status_code == 200
            
            with client.session_transaction() as sess:
                print(f"After /process - Session keys: {list(sess.keys())}")
                assert 'mom_data' in sess
                assert 'mom_text' in sess
            
            # Step 2: Submit edits
            print("\n=== STEP 2: Submit edits ===")
            response = client.post('/edit', data={
                'title': 'Test Meeting',
                'objective': 'Test Objective'
            }, follow_redirects=True)
            assert response.status_code == 200
            
            with client.session_transaction() as sess:
                print(f"After /edit - Session keys: {list(sess.keys())}")
                assert 'mom_data' in sess
                assert 'mom_text' in sess
            
            # Step 3: View validate page
            print("\n=== STEP 3: View validate page ===")
            response = client.get('/validate')
            assert response.status_code == 200
            assert b'No MOM data found' not in response.data
            
            with client.session_transaction() as sess:
                print(f"After /validate GET - Session keys: {list(sess.keys())}")
                assert 'mom_text' in sess
                mom_text_len = len(sess.get('mom_text', ''))
                print(f"mom_text length: {mom_text_len}")
                assert mom_text_len > 0
            
            # Step 4: Submit validation
            print("\n=== STEP 4: Submit validation ===")
            response = client.post('/validate', data={
                'checklist': [
                    'decisions_captured',
                    'action_items_owners',
                    'action_items_deadlines',
                    'no_confidential_info',
                    'ready_within_24h'
                ]
            }, follow_redirects=False)
            
            print(f"Validation response status: {response.status_code}")
            print(f"Validation response location: {response.location}")
            
            with client.session_transaction() as sess:
                print(f"After /validate POST - Session keys: {list(sess.keys())}")
                print(f"'mom_text' in session: {'mom_text' in sess}")
                if 'mom_text' in sess:
                    print(f"mom_text length: {len(sess['mom_text'])}")
                else:
                    print("ERROR: mom_text NOT IN SESSION")
            
            # Step 5: Try to export (this is where the error occurs)
            print("\n=== STEP 5: Export PDF ===")
            response = client.get('/export_mom', follow_redirects=False)
            
            print(f"Export response status: {response.status_code}")
            
            # This should NOT redirect back to index with "No MOM data found"
            if response.status_code == 302:
                print(f"Export redirected to: {response.location}")
                assert '/index' not in response.location and '/' != response.location, \
                    "Export should not redirect to index - session data was lost!"
            else:
                # Should be 200 with PDF download
                assert response.status_code == 200
                assert response.mimetype == 'application/pdf'
    
    def test_session_cookie_set_after_process(self, client, mock_llm_response):
        """Test that session cookie is properly set after /process."""
        with patch('core.llm.extract_mom_from_transcript') as mock_extract:
            mock_extract.return_value = mock_llm_response
            
            response = client.post('/process', data={
                'transcript_text': 'Test transcript content with enough words to meet the minimum validation requirements for processing.'
            })
            
            # Check for session cookie
            cookies = response.headers.getlist('Set-Cookie')
            print(f"Cookies set: {cookies}")
            
            session_cookie_found = any('session' in cookie.lower() for cookie in cookies)
            assert session_cookie_found, "Session cookie should be set after /process"
    
    def test_session_backend_type(self, app):
        """Test that session backend is correctly configured."""
        with app.app_context():
            print(f"Session type: {app.config.get('SESSION_TYPE')}")
            print(f"Session permanent: {app.config.get('SESSION_PERMANENT')}")
            print(f"Session cache: {type(app.config.get('SESSION_CACHELIB'))}")
            
            assert app.config.get('SESSION_TYPE') == 'cachelib', \
                "Session type should be 'cachelib' for server-side storage"
            
            assert app.config.get('SESSION_CACHELIB') is not None, \
                "Session cache backend should be initialized"


class TestSessionDataIntegrity:
    """Test that session data maintains integrity."""
    
    def test_large_mom_text_storage(self, client, mock_llm_response):
        """Test that large MOM text data can be stored and retrieved."""
        # Create a large MOM response
        large_mom = mock_llm_response.copy()
        large_mom['notes'] = 'X' * 10000  # 10KB of text
        
        with patch('core.llm.extract_mom_from_transcript') as mock_extract:
            mock_extract.return_value = large_mom
            
            # Submit transcript (must be 10+ words)
            client.post('/process', data={
                'transcript_text': 'Test transcript with sufficient content to meet minimum validation word count requirements.'
            })
            
            # Check session contains data
            with client.session_transaction() as sess:
                assert 'mom_data' in sess
                print(f"Session data size estimate: {len(str(sess))} bytes")
            
            # Access edit page (should work)
            response = client.get('/edit')
            assert response.status_code == 200
            assert b'No MOM data found' not in response.data
