# ClearMeet - Minutes of Meeting Generator

**ClearMeet** is an internal corporate tool that helps managers generate structured Minutes of Meeting (MOM) from meeting transcripts or audio recordings. It uses OpenAI's GPT and Whisper APIs to automatically extract key information and create professional MOM documents.

Aligned with Dyna Electric's 6-step meeting management training framework, ClearMeet supports proactive meeting planning and post-meeting documentation.

---

## 🚀 Quick Start

### For First-Time Users

1. **Choose your workflow:**
   - **Plan a Meeting** → Define objective → Build agenda with AI → Generate MOM after meeting
   - **Generate MOM Directly** → Upload audio/transcript → Get structured MOM immediately

2. **Plan a Meeting (Recommended):**
   - Click "Plan Meeting" on home page
   - Define your meeting objective with business context
   - Use AI to generate agenda (or build manually)
   - After meeting: upload audio/transcript to generate MOM with full context

3. **Direct MOM Generation:**
   - Click "Generate MOM" on home page
   - Upload audio file (MP3, WAV, M4A, etc.) OR paste transcript
   - Review AI-generated MOM
   - Edit, validate, and export to PDF

### Quick Setup (5 Minutes)

```powershell
# 1. Verify virtual environment
python -c "import sys; print(sys.executable)"
# Should show: ...\clearmeet\Scripts\python.exe

# 2. Install dependencies
pip install -r requirements.txt

# 3. Set OpenAI API key
# Create .env file and add: OPENAI_API_KEY=sk-your-key-here

# 4. Run application
python app.py

# 5. Open browser to http://localhost:5000
```

---

## Features

✅ **Pre-Meeting Planning** (Steps 1-2 of Dyna Electric Framework)
- **Define Objective**: Structured objective with business issue, goal, and expected output
- **AI Agenda Builder**: GPT-4o-mini generates meeting agenda from objective
- **Manual Agenda**: Build agenda with durations and descriptions
- **Smart Context**: Pre-meeting data flows into MOM generation automatically

✅ **Multiple Input Methods**
- Paste meeting transcript (text, minimum 50 words)
- Upload audio recording (auto-transcribed using Whisper)
- Combine with pre-meeting planning for enhanced context

✅ **AI-Powered Generation**
- Structured JSON output from GPT-4o-mini (title, date, objective, decisions, action items, attendees)
- Automatic extraction of key meeting information
- **Context-aware**: Uses planned objective and agenda for better MOM quality
- Intelligent prompting with pre-meeting planning data

✅ **Flexible Editing**
- **Pre-populated objective** from pre-meeting planning
- **Agenda reference panel** shows planned agenda during editing
- Edit structured components (decisions, action items, objective)
- Full text editor override for complete control
- Dynamic add/remove for decisions and action items

✅ **Quality Validation**
- Built-in validation checklist
- Content quality checks
- Manager approval workflow

✅ **Professional Export**
- PDF export with professional formatting
- **Includes planned agenda section** in MOM text
- Metadata support (meeting date, title)

✅ **Secure Audio Upload**
- Supported formats: `.mp3, .wav, .m4a, .ogg, .webm, .mp4, .mpeg, .mpga`
- Maximum file size: 200MB (with automatic chunking for large files)
- Secure filename handling (prevents path traversal attacks)
- Automatic temporary file cleanup after transcription
- Validation: Both transcript and audio cannot be empty

## Tech Stack

- **Backend**: Flask 3.0
- **LLM**: OpenAI GPT-4o-mini (structured JSON output)
- **Transcription**: OpenAI Whisper API
- **PDF Generation**: ReportLab
- **Session Storage**: Flask server-side sessions (no database for MVP)
- **Deployment**: Heroku Eco compatible

## Project Structure

```
clearmeet/
├── app.py                      # Main Flask application (19 routes)
├── config.py                   # Configuration management
├── requirements.txt            # Python dependencies
├── Procfile                    # Heroku deployment
├── runtime.txt                 # Python version
├── .env.example                # Environment variables template
├── core/                       # Core business logic
│   ├── __init__.py
│   ├── parser.py               # Text parsing utilities
│   ├── llm.py                  # OpenAI LLM integration (GPT + Whisper)
│   ├── agenda.py               # AI agenda generation & validation (NEW)
│   ├── schema.py               # Pydantic models (MeetingMOM, MeetingObjective, AgendaItem)
│   ├── validation.py           # MOM validation logic
│   ├── render.py               # MOM text rendering with agenda support
│   ├── export.py               # PDF export functionality
│   └── audio.py                # Audio transcription
├── templates/                  # Jinja2 templates
│   ├── base.html               # Base layout
│   ├── index.html              # Landing page with workflow choice
│   ├── define_objective.html   # Step 1: Define meeting objective (NEW)
│   ├── build_agenda.html       # Step 2: Build agenda with AI (NEW)
│   ├── edit.html               # Edit MOM with agenda reference panel
│   ├── validate.html           # Validation checklist page
│   └── preview.html            # Preview final MOM
├── static/                     # Static assets
│   ├── styles.css              # Corporate design system
│   ├── css/
│   │   └── main.css
│   └── js/
│       └── main.js
└── tests/                      # Test suite (169 tests, 100% pass rate)
    ├── test_parser.py          # Text processing tests
    ├── test_llm.py             # AI integration tests
    ├── test_agenda.py          # Agenda generation tests (NEW)
    ├── test_validation.py      # Quality validation tests
    ├── test_export.py          # PDF export tests
    ├── test_audio.py           # Audio transcription tests
    ├── test_render.py          # MOM rendering tests
    ├── test_routes.py          # Flask route tests
    ├── test_integration_workflow.py  # End-to-end workflow tests
    └── test_session_persistence.py   # Session management tests
```

## Setup Instructions

### Prerequisites

- Python 3.11+
- OpenAI API key
- Virtual environment (recommended)

### Local Development Setup

1. **Clone the repository**
```powershell
cd "C:\Users\evanl\Documents\development workspace\clearmeet"
```

2. **Verify virtual environment** (Prime Directive Principle 0)
```powershell
python -c "import sys; print(sys.executable)"
# Should show: ...\clearmeet\Scripts\python.exe
```

3. **Install dependencies**
```powershell
pip install -r requirements.txt
```

4. **Set up environment variables**
```powershell
# Copy example file
cp .env.example .env

# Edit .env and add your OpenAI API key
# OPENAI_API_KEY=sk-your-actual-api-key-here
```

5. **Run tests** (following TDD principles)
```powershell
pytest tests/ -v
```

6. **Run the application**
```powershell
python app.py
```

7. **Access the application**
Open browser to `http://localhost:5000`

## Environment Variables

Required variables (see `.env.example`):

```bash
# OpenAI API Configuration
OPENAI_API_KEY=sk-your-api-key-here        # Required

# Flask Configuration
FLASK_ENV=development                       # development | production
FLASK_DEBUG=True                            # True | False
SECRET_KEY=your-secret-key-here             # Change in production!

# Session Configuration
SESSION_TYPE=filesystem
PERMANENT_SESSION_LIFETIME=3600             # 1 hour

# File Upload Configuration
MAX_CONTENT_LENGTH=209715200                # 200MB (in bytes) - max audio file size
UPLOAD_FOLDER=temp_uploads                  # Temporary storage for uploaded audio files
ALLOWED_AUDIO_EXTENSIONS=mp3,wav,m4a,ogg    # Supported audio formats (comma-separated)
CHUNK_SIZE_MB=20                            # Target chunk size for splitting large files

# OpenAI Model Configuration
OPENAI_MODEL=gpt-4o-mini                    # Cost-effective option
OPENAI_TEMPERATURE=0.3                      # 0.0-1.0 (lower = more focused)
OPENAI_TRANSCRIBE_MODEL=whisper-1           # Transcription model
```

## Audio Upload Security

ClearMeet implements several security measures for audio file uploads:

### Supported Formats
- **MP3**, **WAV**, **M4A**, **OGG**, **WEBM**, **MP4**, **MPEG**, **MPGA**
- Format validation prevents execution of unexpected file types
- Invalid formats rejected with clear error messages

### File Size Handling
- **Maximum upload**: 200MB (configurable via `MAX_CONTENT_LENGTH`)
- **Large file chunking**: Files >20MB automatically split into chunks for Whisper API (which has 25MB limit)
- **Streaming transcription**: Progress updates sent via Server-Sent Events during processing
- **Automatic cleanup**: Temporary files deleted immediately after transcription

### Filename Security
- **Secure filename sanitization** using `werkzeug.utils.secure_filename`
- **Prevents path traversal attacks** (e.g., `../../etc/passwd`)
- **Stored in isolated directory**: `temp_uploads/` folder
- **Unique naming** for concurrent uploads

### Input Validation
- **File existence check**: Verifies file was actually created
- **Extension validation**: Only allowed formats accepted
- **Size validation**: Rejects files exceeding upload limit
- **Empty file detection**: Prevents zero-byte files
- **Require transcript**: Error if neither audio nor text transcript provided

### Session Management
- Large transcripts persisted to disk (not stored in session cookies)
- Temporary files cleaned up after processing
- Session size optimized to prevent cookie overflow

## Usage Workflows

ClearMeet supports **two workflows** to match your meeting management approach:

### Workflow 1: Pre-Meeting Planning → MOM Generation (Recommended)

**Best for**: Structured meetings with clear objectives and planned agendas

**Steps:**

#### **Step 1: Define Objective** (Pre-Meeting)
1. Click **"Plan Meeting"** on home page
2. Fill in three fields:
   - **Business Issue**: What problem/opportunity drives this meeting?
   - **Objective**: What specific outcome do you want to achieve?
   - **Expected Output**: What deliverables/decisions are needed?
3. Click **"Continue to Build Agenda"**

#### **Step 2: Build Agenda** (Pre-Meeting)
1. **Option A - AI Generation**: Click "Generate Agenda with AI" (uses GPT-4o-mini)
   - Reviews your objective and suggests agenda items
   - Estimates durations for each topic
   - Editable after generation
2. **Option B - Manual Entry**: Click "Add Item" to build agenda yourself
   - Set title, duration, and description for each item
   - Reorder items with drag-and-drop
3. **Validation**: Total duration must be 15-120 minutes
4. Click **"Return to Home"** when done

#### **Step 3: Generate MOM** (Post-Meeting)
1. On home page, click **"Generate MOM"**
2. Upload audio OR paste transcript (your pre-meeting data is automatically included)
3. AI generates MOM using:
   - Your planned objective (pre-populated in MOM)
   - Your agenda (included in AI prompt for better extraction)
   - Meeting transcript/audio
4. Result: Higher quality MOM with structured context

#### **Step 4: Edit & Refine**
- **Objective field**: Pre-populated from Step 1 (if not user-edited)
- **Agenda reference panel**: Shows your planned agenda for reference
- **Structured editing**: Edit decisions, action items, attendees
- **Full text override**: Edit complete MOM text directly
- Agenda section automatically included in MOM text

#### **Step 5: Validate Quality**
- Complete validation checklist (required items starred)
- Review content issues if any
- Preview final MOM with agenda section

#### **Step 6: Export to PDF**
- Professional PDF formatting
- Includes planned agenda section
- One-click download

---

### Workflow 2: Direct MOM Generation (Quick Mode)

**Best for**: Informal meetings or when no pre-planning was done

**Steps:**

#### **Step 1: Input Meeting Data**
1. Click **"Generate MOM"** on home page
2. **Option A**: Paste transcript text (minimum 50 words)
3. **Option B**: Upload audio file (MP3, WAV, M4A, OGG - max 200MB)
4. Optionally provide meeting context for better results

#### **Step 2: Review Generated MOM**
- AI extracts: title, date, objective, decisions, action items, attendees, notes
- Structured output rendered as formatted text
- No pre-meeting data used (still produces quality MOM)

#### **Step 3: Edit & Refine**
- **Structured editing**: Edit individual fields (objective, decisions, etc.)
- **Full text override**: Edit complete MOM text directly
- Add/remove decisions and action items dynamically

#### **Step 4: Validate Quality**
- Complete validation checklist (required items starred)
- Review content issues if any
- Preview final MOM

#### **Step 5: Export to PDF**
- Professional PDF formatting
- Includes metadata (date, title)
- One-click download

---

### When to Use Each Workflow?

| Situation | Recommended Workflow |
|-----------|---------------------|
| Important strategic meetings | Workflow 1 (Pre-Meeting Planning) |
| Recurring team meetings | Workflow 1 (Pre-Meeting Planning) |
| Client/stakeholder meetings | Workflow 1 (Pre-Meeting Planning) |
| Ad-hoc discussions | Workflow 2 (Direct Generation) |
| Past meetings (audio only) | Workflow 2 (Direct Generation) |
| Need to document existing meeting | Workflow 2 (Direct Generation) |

## API Usage & Costs

### AI Features Powered by OpenAI

ClearMeet uses three AI capabilities:

1. **AI Agenda Generation** (GPT-4o-mini)
   - Analyzes meeting objective and generates structured agenda
   - Suggests topic titles, durations, and descriptions
   - Validates total meeting duration (15-120 minutes)
   - Editable after generation

2. **Audio Transcription** (Whisper API)
   - Converts audio recordings to text transcripts
   - Supports multiple formats (MP3, WAV, M4A, etc.)
   - Automatic chunking for large files (>20MB)
   - Real-time progress updates

3. **MOM Generation** (GPT-4o-mini)
   - Extracts structured data from transcripts
   - **Context-aware**: Uses pre-meeting objective and agenda when available
   - Identifies decisions, action items, attendees, and notes
   - Enforces JSON schema for consistent output

### OpenAI API Costs (approximate, as of 2026)

**GPT-4o-mini** (MOM generation + Agenda generation):
- Input: ~$0.15 per 1M tokens
- Output: ~$0.60 per 1M tokens
- Typical meeting transcript (1000 words) ≈ $0.001-0.002 per MOM
- AI agenda generation ≈ $0.0003-0.0005 per agenda

**Whisper** (audio transcription):
- $0.006 per minute of audio
- 30-minute meeting ≈ $0.18

**Cost estimate per meeting**:
- **With pre-meeting planning**: $0.20-0.31 (agenda + transcription + MOM)
- **Without pre-meeting planning**: $0.20-0.30 (transcription + MOM only)
- **Text transcript only**: $0.001-0.002 (MOM generation only)

## Testing

Following TDD principles from Prime Directive:

```powershell
# Run all tests (169 tests total)
pytest tests/ -v

# Expected output: 169 passed in ~35-40s
# All tests maintain 100% pass rate

# Run specific test file
pytest tests/test_agenda.py -v      # New: Agenda generation tests
pytest tests/test_parser.py -v

# Run with coverage
pytest tests/ --cov=core --cov-report=html

# Run tests before any changes (establish baseline)
pytest tests/ -v | findstr "passed"
```

### Backward Compatibility Testing

ClearMeet maintains backward compatibility for users who skip pre-meeting planning:

```powershell
# Test direct MOM generation (without pre-meeting planning)
pytest tests/test_integration_workflow.py::TestCompleteTextWorkflow -v

# Test with pre-meeting planning
pytest tests/test_routes.py -v

# Verify all workflows pass
pytest tests/ -v
```

## Directive Compliance Session Log

Track directive compliance in `session_log.md` using the required KPI format from `prime_directive.md`.

- Create/update `session_log.md` at session start, major checkpoints, and handoff.
- Use the reusable entry template already included in `session_log.md`.
- Keep entries chronological and include KPI score, status breakdown, actions, blockers, and next steps.

### Test Coverage

- `test_parser.py` - 25 tests (text cleaning, speaker extraction, validation)
- `test_llm.py` - 27 tests (MOM generation, JSON validation, rendering)
- `test_agenda.py` - 21 tests (AI agenda generation, validation, serialization)
- `test_validation.py` - 28 tests (content validation, checklist, quality checks)
- `test_export.py` - 21 tests (PDF generation, formatting, metadata)
- `test_audio.py` - 23 tests (transcription, file validation, error handling)
- `test_render.py` - 9 tests (MOM text rendering, user edits)
- `test_routes.py` - 9 tests (Flask route handlers, session management)
- `test_integration_workflow.py` - 4 tests (end-to-end workflow validation)
- `test_session_persistence.py` - 2 tests (session data persistence)

**Total: 169 tests** covering all core modules and workflows (100% pass rate)

## Deployment to Heroku

### Prerequisites
- Heroku account
- Heroku CLI installed

### Quick Start (3 Steps)

```bash
# 1. Create a Heroku app (replace 'my-clearmeet' with your app name)
heroku create my-clearmeet

# 2. Set environment variables
heroku config:set OPENAI_API_KEY=sk-your-api-key-here \
                  SECRET_KEY=your-production-secret-key-here

# 3. Deploy
git push heroku main
```

### Full Deployment Steps

1. **Login to Heroku**
```bash
heroku login
```

2. **Create Heroku app**
```bash
heroku create your-app-name
```

**Note:** Replace `your-app-name` with your desired Heroku app name (must be globally unique).
Example: `heroku create clearmeet-demo` would deploy to `clearmeet-demo.herokuapp.com`

3. **Set environment variables**
```bash
heroku config:set OPENAI_API_KEY=sk-your-api-key-here
heroku config:set SECRET_KEY=your-production-secret-key-here
heroku config:set FLASK_ENV=production
heroku config:set FLASK_DEBUG=False
heroku config:set LOG_LEVEL=INFO
```

**Important Environment Variables:**
- `OPENAI_API_KEY` - Required. Your OpenAI API key (sk-...)
- `SECRET_KEY` - Required. Use a strong random key (e.g., `python -c "import secrets; print(secrets.token_hex(32))"`)
- `FLASK_ENV=production` - Recommended. Disables debug mode
- `LOG_LEVEL=INFO` - Optional. Set to DEBUG for more verbose logging

4. **Deploy**
```bash
git push heroku main
```

5. **Monitor deployment**
```bash
heroku logs --tail
```

6. **Open application**
```bash
heroku open
```

### Health Check

The application includes a health check endpoint for monitoring:
```bash
curl https://your-app-name.herokuapp.com/health
```

Returns:
```json
{
  "status": "ok",
  "timestamp": "2026-02-19T10:30:45.123456",
  "service": "clearmeet"
}
```

Use this endpoint with monitoring services (Uptime Robot, Datadog, New Relic, etc.)

### Generating a Strong SECRET_KEY

Generate a cryptographically secure secret key:
```bash
# On macOS/Linux
python3 -c "import secrets; print(secrets.token_hex(32))"

# On Windows PowerShell
python -c "import secrets; print(secrets.token_hex(32))"
```

Then use the generated key:
```bash
heroku config:set SECRET_KEY=<generated-key-here>
```

### Heroku Configuration

The project includes:
- `Procfile` - Specifies Gunicorn web server configuration
- `runtime.txt` - Specifies Python 3.11.8
- `.python-version` - Local development Python version (pyenv compatible)
- `requirements.txt` - All Python dependencies

**Heroku Eco Plan** ($5/month per dyno):
- 1000 dyno hours/month (sufficient for one always-on dyno)
- Suitable for internal corporate tools with moderate traffic
- Free tier also available (sleeps after 30 min inactivity)

### Troubleshooting

**Error: Application failed to initialize**
```bash
heroku logs --tail
```
Check logs for missing environment variables (especially `OPENAI_API_KEY` and `SECRET_KEY`)

**Error: Push rejected - no changes**
```bash
# Force push if code changed locally
git push heroku main --force
```

**App crashes after deploy**
```bash
# Check Heroku logs
heroku logs --tail

# Restart the app
heroku restart

# Scale up if needed
heroku ps:scale web=1
```

**Cannot connect to database** 
This is a free tier SQLite-based app (no external database). If you add database features, add Heroku Postgres.

## Architecture Overview

### Core Modules

**parser.py** - Text Processing
- Clean and normalize transcripts
- Extract speakers from various formats
- Estimate meeting duration
- Validate transcript quality

**llm.py** - AI Integration
- Generate structured MOM from transcript
- Enforce JSON schema output
- Render MOM text from structured data
- Handle API errors gracefully

**validation.py** - Quality Assurance
- Pre-defined validation checklist
- Content completeness checks
- Action item assignment validation
- Text length requirements

**export.py** - PDF Generation
- Professional PDF formatting
- Custom styles for corporate look
- Metadata support
- Multi-page handling

**audio.py** - Transcription
- Whisper API integration
- Audio file validation (format, size)
- Language parameter support
- Error handling

### Flask Routes

**Pre-Meeting Planning Routes:**
- `GET /meeting/new` - Step 1: Define meeting objective form
- `POST /meeting/define` - Save objective to session, redirect to agenda builder
- `GET /meeting/agenda` - Step 2: Build agenda with AI or manual entry
- `POST /meeting/agenda/generate` - AI agenda generation (JSON API)
- `POST /meeting/agenda/save` - Save agenda to session, redirect to home

**Core MOM Generation Routes:**
- `GET /` - Landing page with workflow choice (Plan Meeting vs Generate MOM)
- `POST /process` - Process transcript/audio input
- `POST /generate` - Generate MOM with AI (uses pre-meeting data if available)
- `GET /edit` - Edit MOM (shows agenda reference if available)
- `POST /update` - Update MOM from edits
- `GET /validate` - Validation checklist page
- `POST /validate` - Submit validation, proceed to preview
- `GET /preview` - Preview final MOM
- `POST /export` - Export MOM to PDF

**Utility Routes:**
- `GET /health` - Health check endpoint for monitoring
- `POST /reset` - Clear session data (restart workflow)

### Session Storage

Uses Flask server-side sessions stored in `flask_session/` directory:
- No database required for MVP
- **Pre-meeting data**: `meeting_objective` (dict), `agenda_items` (list)
- **MOM data**: `mom_data`, `mom_text`, `transcript`
- **Workflow state**: `validated`, `text_override`, `objective_user_edited`
- **Large content**: Persisted to disk with session storing path only
- Automatic cleanup after timeout (1 hour default)

**Session Keys:**
```python
session['meeting_objective']   # {business_issue, objective, expected_output}
session['agenda_items']         # [{title, duration_minutes, description}, ...]
session['mom_data']             # Structured MOM dict
session['mom_text']             # Full MOM text (or preview if large)
session['transcript']           # Original transcript
session['validated']            # bool - MOM approved
session['text_override']        # bool - user edited full text
```

## Security Considerations

⚠️ **Important Security Notes**:

1. **API Key Protection**
   - Never commit `.env` file to git
   - Use environment variables for all secrets
   - Rotate keys if exposed

2. **File Upload Security**
   - Use `secure_filename()` for uploads
   - Validate file extensions
   - Limit file size (25MB for audio)
   - Delete temporary files after processing

3. **Session Security**
   - Change `SECRET_KEY` in production
   - Use strong random keys (32+ characters)
   - Session timeout (1 hour default)

4. **Input Validation**
   - Sanitize all user inputs
   - Validate transcript length (min 50 words)
   - Check content quality before LLM processing

## Performance Optimization

### Current Performance

- Transcript processing: < 5 seconds (typical 1000-word transcript)
- Audio transcription: ~0.5x real-time (30-min meeting = 15-second transcription)
- PDF generation: < 1 second
- Total workflow: 10-20 seconds for audio, 5-10 seconds for text

### Optimization Tips

1. **Reduce API Costs**
   - Use `gpt-4o-mini` instead of `gpt-4` (10x cheaper)
   - Lower temperature (0.3) for consistency
   - Cache common prompts if possible

2. **Improve Response Time**
   - Async processing for long audio files
   - Progress indicators for user feedback
   - Pre-validate inputs before API calls

3. **Scale for Traffic**
   - Use Heroku hobby/standard dynos for higher traffic
   - Add Redis for session storage (if needed)
   - Implement rate limiting if public-facing

## Troubleshooting

### Common Issues

**Issue**: "OPENAI_API_KEY environment variable is required"
- **Solution**: Create `.env` file and add valid API key

**Issue**: AI agenda generation fails or returns empty result
- **Solution**: Ensure meeting objective is detailed (minimum 15 characters per field). Try again or build agenda manually.

**Issue**: Pre-meeting data not appearing in MOM
- **Solution**: Verify you completed Steps 1-2 before generating MOM. Check session storage in Flask logs.

**Issue**: Agenda not showing in edit page
- **Solution**: Agenda only displays if built in Step 2. Direct MOM generation (skipping pre-planning) won't show agenda panel.

**Issue**: Audio transcription fails
- **Solution**: Check file format (must be MP3, WAV, M4A, OGG) and size (< 25MB)

**Issue**: PDF export shows broken formatting
- **Solution**: Verify MOM text doesn't contain unsupported special characters

**Issue**: Empty or short MOM generated
- **Solution**: Ensure transcript is substantial (50+ words), provide additional context

**Issue**: Tests fail on import
- **Solution**: Verify virtual environment is activated, run `pip install -r requirements.txt`

## Prime Directive Compliance

This project follows Prime Directive principles:

✅ **Principle 0**: Virtual environment verification before all commands  
✅ **Principle 1**: 100% test pass rate (169 tests, all passing)  
✅ **Principle 2**: Verify first, code second (API research before implementation)  
✅ **Principle 3**: Defensive programming (None handling, input validation)  
✅ **Principle 4**: Test incrementally (TDD approach)  
✅ **Code Quality**: Type hints, error handling, documentation  
✅ **Modular Architecture**: Isolated pre-meeting features, backward compatible integration

## Dyna Electric Meeting Framework Alignment

ClearMeet currently supports **4 of 6 steps** from Dyna Electric's meeting management training:

| Step | Description | Status |
|------|-------------|--------|
| **Step 1** | Define Objective | ✅ Implemented |
| **Step 2** | Build Agenda | ✅ Implemented (with AI support) |
| **Step 3** | Send Invites | ⏳ Planned (Phase 3) |
| **Step 4** | Confirm Attendance | ⏳ Planned (Phase 3) |
| **Step 5** | Conduct Meeting & Document | ✅ Implemented (MOM generation) |
| **Step 6** | Follow-up on Action Items | ✅ Implemented (MOM validation & export) |

**Current Coverage**: Steps 1, 2, 5, 6 (67% framework alignment)  
**Roadmap**: Steps 3-4 planned for future development phases

## Contributing

When adding features:

1. **Write tests first** (TDD approach)
2. **Verify virtual environment** before running commands
3. **Run baseline tests** before making changes
4. **Implement feature** with type hints and defensive programming
5. **Run tests again** to ensure 100% pass rate
6. **Update documentation** if needed

## License

Internal corporate tool - All rights reserved.

## Support

For issues or questions:
- Review this README
- Check test files for API usage examples
- Review Prime Directive ([prime_directive.md](prime_directive.md))

---

**Version**: 0.2.0  
**Last Updated**: February 20, 2026  
**Python**: 3.13.12  
**Flask**: 3.0.0  
**Test Coverage**: 169 tests (100% pass rate)  
**Framework Alignment**: Dyna Electric 6-step framework (4/6 steps implemented)
