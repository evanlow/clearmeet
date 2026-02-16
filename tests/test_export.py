"""
Tests for PDF export module.

Tests cover:
- PDF generation from MOM text
- Metadata handling
- Style formatting
- Buffer operations
- Edge cases (empty text, special characters)
"""
import pytest
from io import BytesIO
from core.export import PDFExporter


class TestPDFExporter:
    """Test suite for PDFExporter class."""
    
    @pytest.fixture
    def exporter(self):
        """Create PDFExporter instance."""
        return PDFExporter()
    
    @pytest.fixture
    def sample_mom_text(self):
        """Provide sample MOM text."""
        return """
MINUTES OF MEETING
============================================================

MEETING OBJECTIVE:
Discuss Q1 budget allocation

ATTENDEES:
  • Alice Johnson
  • Bob Smith
  • Carol Davis

SUMMARY:
Team met to discuss Q1 budget allocation and resource planning.

DECISIONS MADE:
  1. Increase marketing budget by 15%
  2. Reduce travel expenses by 10%

ACTION ITEMS:
  1. Update budget spreadsheet
     Owner: Carol
     Deadline: Friday

============================================================
End of Minutes
"""
    
    def test_exporter_initialization_default(self):
        """Test exporter initialization with default settings."""
        exporter = PDFExporter()
        assert exporter.page_size is not None
        assert exporter.styles is not None
    
    def test_exporter_has_required_styles(self, exporter):
        """Test that exporter has all required styles."""
        assert 'title' in exporter.styles
        assert 'heading' in exporter.styles
        assert 'body' in exporter.styles
        assert 'list' in exporter.styles
    
    def test_export_to_pdf_returns_bytesio(self, exporter, sample_mom_text):
        """Test that export returns BytesIO buffer."""
        result = exporter.export_to_pdf(sample_mom_text)
        assert isinstance(result, BytesIO)
    
    def test_export_to_pdf_creates_non_empty_pdf(self, exporter, sample_mom_text):
        """Test that exported PDF has content."""
        buffer = exporter.export_to_pdf(sample_mom_text)
        pdf_data = buffer.getvalue()
        assert len(pdf_data) > 0
        assert pdf_data.startswith(b'%PDF')  # PDF header
    
    def test_export_to_pdf_raises_error_with_empty_text(self, exporter):
        """Test that empty text raises ValueError."""
        with pytest.raises(ValueError, match="MOM text cannot be empty"):
            exporter.export_to_pdf("")
    
    def test_export_to_pdf_raises_error_with_none_text(self, exporter):
        """Test that None text raises ValueError."""
        with pytest.raises(ValueError, match="MOM text cannot be empty"):
            exporter.export_to_pdf(None)
    
    def test_export_to_pdf_with_metadata(self, exporter, sample_mom_text):
        """Test PDF export with metadata."""
        metadata = {
            'meeting_date': '2026-02-16',
            'meeting_title': 'Q1 Planning Meeting'
        }
        buffer = exporter.export_to_pdf(sample_mom_text, metadata=metadata)
        pdf_data = buffer.getvalue()
        
        # PDF should be created successfully
        assert len(pdf_data) > 0
        # Note: Can't easily verify text content in PDF without parsing library
    
    def test_export_to_pdf_with_empty_metadata(self, exporter, sample_mom_text):
        """Test PDF export with empty metadata dictionary."""
        buffer = exporter.export_to_pdf(sample_mom_text, metadata={})
        pdf_data = buffer.getvalue()
        assert len(pdf_data) > 0
    
    def test_export_to_pdf_handles_special_characters(self, exporter):
        """Test PDF export with special characters."""
        text = "MOM with special chars: < > & ' \""
        buffer = exporter.export_to_pdf(text)
        pdf_data = buffer.getvalue()
        assert len(pdf_data) > 0
    
    def test_export_to_pdf_handles_unicode(self, exporter):
        """Test PDF export with unicode characters."""
        text = "Meeting notes: Café • résumé • naïve"
        buffer = exporter.export_to_pdf(text)
        pdf_data = buffer. getvalue()
        assert len(pdf_data) > 0
    
    def test_export_to_pdf_handles_long_text(self, exporter):
        """Test PDF export with very long text (multiple pages)."""
        long_text = "LINE\n" * 200  # Create multi-page document
        buffer = exporter.export_to_pdf(long_text)
        pdf_data = buffer.getvalue()
        assert len(pdf_data) > 0
    
    def test_export_to_pdf_handles_multiple_section_types(self, exporter):
        """Test PDF with various section formats."""
        text = """
TITLE SECTION

Regular paragraph text here.

ANOTHER HEADING:

  • Bullet point one
  • Bullet point two

  1. Numbered item one
  2. Numbered item two

  - Dashed item
"""
        buffer = exporter.export_to_pdf(text)
        pdf_data = buffer.getvalue()
        assert len(pdf_data) > 0
    
    def test_escape_html_escapes_special_chars(self):
        """Test HTML escaping for ReportLab."""
        text = "Test <tag> & 'quotes'"
        result = PDFExporter._escape_html(text)
        assert '<' not in result
        assert '>' not in result
        assert '&lt;' in result
        assert '&gt;' in result
        assert '&amp;' in result
    
    def test_escape_html_handles_empty_string(self):
        """Test HTML escaping with empty string."""
        result = PDFExporter._escape_html("")
        assert result == ""
    
    def test_escape_html_handles_none(self):
        """Test HTML escaping with None."""
        result = PDFExporter._escape_html(None)
        assert result == ""
    
    def test_save_buffer_to_file_creates_file(self, exporter, sample_mom_text, tmp_path):
        """Test saving buffer to file."""
        buffer = exporter.export_to_pdf(sample_mom_text)
        filepath = tmp_path / "test_mom.pdf"
        
        PDFExporter.save_buffer_to_file(buffer, str(filepath))
        
        assert filepath.exists()
        assert filepath.stat().st_size > 0
    
    def test_save_buffer_to_file_creates_valid_pdf(self, exporter, sample_mom_text, tmp_path):
        """Test that saved file is valid PDF."""
        buffer = exporter.export_to_pdf(sample_mom_text)
        filepath = tmp_path / "test_mom.pdf"
        
        PDFExporter.save_buffer_to_file(buffer, str(filepath))
        
        # Read file and verify PDF header
        with open(filepath, 'rb') as f:
            data = f.read()
            assert data.startswith(b'%PDF')
    
    def test_buffer_position_reset_after_export(self, exporter, sample_mom_text):
        """Test that buffer position is at start after export."""
        buffer = exporter.export_to_pdf(sample_mom_text)
        assert buffer.tell() == 0  # Position should be at start
    
    def test_export_multiple_times_returns_different_buffers(self, exporter, sample_mom_text):
        """Test that multiple exports return independent buffers."""
        buffer1 = exporter.export_to_pdf(sample_mom_text)
        buffer2 = exporter.export_to_pdf(sample_mom_text)
        
        assert buffer1 is not buffer2
        # Both should be valid PDFs (timestamps may differ)
        assert buffer1.getvalue().startswith(b'%PDF')
        assert buffer2.getvalue().startswith(b'%PDF')
        assert len(buffer1.getvalue()) > 0
        assert len(buffer2.getvalue()) > 0
    
    def test_export_with_filename_parameter(self, exporter, sample_mom_text):
        """Test export with filename parameter (stored as metadata)."""
        # Note: filename parameter exists but may not be used in current implementation
        buffer = exporter.export_to_pdf(sample_mom_text, filename="meeting_notes.pdf")
        pdf_data = buffer.getvalue()
        assert len(pdf_data) > 0
