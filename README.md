# ClearMeet - Minutes of Meeting Generator

**ClearMeet** is an internal corporate tool that helps managers generate structured Minutes of Meeting (MOM) from meeting transcripts or audio recordings. It uses OpenAI's GPT and Whisper APIs to automatically extract key information and create professional MOM documents.

## Features

✅ **Multiple Input Methods**
- Paste meeting transcript (text)
- Upload audio recording (auto-transcribed using Whisper)

✅ **AI-Powered Generation**
- Structured JSON output from GPT (objective, decisions, action items, attendees)
- Automatic extraction of key meeting information

✅ **Flexible Editing**
- Edit structured components (decisions, action items, objective)
- Full text editor override for complete control

✅ **Quality Validation**
- Built-in validation checklist
- Content quality checks
- Manager approval workflow

✅ **Professional Export**
- PDF export with professional formatting
- Metadata support (meeting date, title)

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
├── app.py                      # Main Flask application
├── config.py                   # Configuration management
├── requirements.txt            # Python dependencies
├── Procfile                    # Heroku deployment
├── runtime.txt                 # Python version
├── .env.example                # Environment variables template
├── core/                       # Core business logic
│   ├── __init__.py
│   ├── parser.py               # Text parsing utilities
│   ├── llm.py                  # OpenAI LLM integration
│   ├── validation.py           # MOM validation logic
│   ├── export.py               # PDF export functionality
│   └── audio.py                # Audio transcription
├── templates/                  # Jinja2 templates
│   ├── base.html
│   ├── index.html              # Input page
│   ├── edit.html               # Editing page
│   ├── validate.html           # Validation page
│   └── preview.html            # Preview page
├── static/                     # Static assets
│   ├── css/
│   │   └── main.css
│   └── js/
│       └── main.js
└── tests/                      # Test suite
    ├── test_parser.py
    ├── test_llm.py
    ├── test_validation.py
    ├── test_export.py
    └── test_audio.py
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
MAX_CONTENT_LENGTH=16777216                 # 16MB (in bytes)
UPLOAD_FOLDER=temp_uploads
ALLOWED_AUDIO_EXTENSIONS=mp3,wav,m4a,ogg

# OpenAI Model Configuration
OPENAI_MODEL=gpt-4o-mini                    # Cost-effective option
OPENAI_TEMPERATURE=0.3                      # 0.0-1.0 (lower = more focused)
WHISPER_MODEL=whisper-1                     # Transcription model
```

## Usage Workflow

### 1. Input Meeting Data
- **Option A**: Paste transcript text (minimum 50 words)
- **Option B**: Upload audio file (MP3, WAV, M4A, OGG - max 25MB)
- Optionally provide meeting context for better results

### 2. Review Generated MOM
- AI extracts: objective, decisions, action items, attendees, summary
- Structured output rendered as formatted text

### 3. Edit & Refine
- **Structured editing**: Edit individual fields (objective, decisions, etc.)
- **Full text override**: Edit complete MOM text directly
- Add/remove decisions and action items dynamically

### 4. Validate Quality
- Complete validation checklist (required items starred)
- Review content issues if any
- Preview final MOM

### 5. Export to PDF
- Professional PDF formatting
- Includes metadata (date, title)
- One-click download

## API Usage & Costs

### OpenAI API Costs (approximate, as of 2026)

**GPT-4o-mini** (MOM generation):
- Input: ~$0.15 per 1M tokens
- Output: ~$0.60 per 1M tokens
- Typical meeting transcript (1000 words) ≈ $0.001-0.002 per MOM

**Whisper** (audio transcription):
- $0.006 per minute of audio
- 30-minute meeting ≈ $0.18

**Cost estimate**: $0.20-0.30 per meeting (including both transcription and generation)

## Testing

Following TDD principles from Prime Directive:

```powershell
# Run all tests
pytest tests/ -v

# Run specific test file
pytest tests/test_parser.py -v

# Run with coverage
pytest tests/ --cov=core --cov-report=html

# Run tests before any changes (establish baseline)
pytest tests/ -v | findstr "passed"
```

### Test Coverage

- `test_parser.py` - 25 tests (text cleaning, speaker extraction, validation)
- `test_llm.py` - 27 tests (MOM generation, JSON validation, rendering)
- `test_validation.py` - 28 tests (content validation, checklist, quality checks)
- `test_export.py` - 21 tests (PDF generation, formatting, metadata)
- `test_audio.py` - 23 tests (transcription, file validation, error handling)

**Total: 124 tests** covering all core modules

## Deployment to Heroku

### Prerequisites
- Heroku account
- Heroku CLI installed

### Deployment Steps

1. **Login to Heroku**
```bash
heroku login
```

2. **Create Heroku app**
```bash
heroku create your-app-name
```

3. **Set environment variables**
```bash
heroku config:set OPENAI_API_KEY=sk-your-api-key-here
heroku config:set SECRET_KEY=your-production-secret-key
heroku config:set FLASK_ENV=production
heroku config:set FLASK_DEBUG=False
```

4. **Deploy**
```bash
git push heroku main
```

5. **Open application**
```bash
heroku open
```

### Heroku Configuration

The project includes:
- `Procfile` - Specifies Gunicorn web server
- `runtime.txt` - Specifies Python 3.11.8
- `requirements.txt` - All dependencies

**Heroku Eco Plan** ($5/month per dyno):
- 1000 dyno hours/month
- Suitable for internal corporate tools with moderate traffic

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

- `GET /` - Landing page with input options
- `POST /process` - Process transcript/audio input
- `GET /edit` - Edit structured MOM data
- `POST /update` - Update MOM from edits
- `GET /validate` - Validation checklist page
- `POST /export` - Export MOM to PDF
- `GET /preview` - Preview final MOM

### Session Storage

Uses Flask server-side sessions stored in `flask_session/` directory:
- No database required for MVP
- Session data: transcript, mom_data, mom_text
- Automatic cleanup after timeout (1 hour default)

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
✅ **Principle 1**: 100% test pass rate (124 tests, all passing)
✅ **Principle 2**: Verify first, code second (API research before implementation)
✅ **Principle 3**: Defensive programming (None handling, input validation)
✅ **Principle 4**: Test incrementally (TDD approach)  
✅ **Code Quality**: Type hints, error handling, documentation

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

**Version**: 0.1.0  
**Last Updated**: February 16, 2026  
**Python**: 3.11+  
**Flask**: 3.0.0
