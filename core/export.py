"""
PDF export functionality for MOM documents.

Generates professional PDF reports from MOM text.
"""
from typing import Optional
from datetime import datetime
from io import BytesIO

from reportlab.lib.pagesizes import letter, A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.lib.enums import TA_LEFT, TA_CENTER
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, PageBreak
from reportlab.lib import colors


class PDFExporter:
    """Export MOM to PDF format."""
    
    def __init__(self, page_size=letter):
        """
        Initialize PDF exporter.
        
        Args:
            page_size: Page size (letter or A4)
        """
        self.page_size = page_size
        self.styles = self._create_styles()
    
    def _create_styles(self) -> dict:
        """
        Create custom paragraph styles for MOM.
        
        Returns:
            Dictionary of style objects
        """
        styles = getSampleStyleSheet()
        
        # Title style
        title_style = ParagraphStyle(
            'CustomTitle',
            parent=styles['Heading1'],
            fontSize=18,
            textColor=colors.HexColor('#1a1a1a'),
            spaceAfter=30,
            alignment=TA_CENTER,
            fontName='Helvetica-Bold'
        )
        
        # Heading style
        heading_style = ParagraphStyle(
            'CustomHeading',
            parent=styles['Heading2'],
            fontSize=14,
            textColor=colors.HexColor('#2c3e50'),
            spaceAfter=12,
            spaceBefore=20,
            fontName='Helvetica-Bold'
        )
        
        # Body style
        body_style = ParagraphStyle(
            'CustomBody',
            parent=styles['BodyText'],
            fontSize=11,
            textColor=colors.HexColor('#333333'),
            spaceAfter=12,
            alignment=TA_LEFT,
            fontName='Helvetica'
        )
        
        # List item style
        list_style = ParagraphStyle(
            'CustomList',
            parent=styles['BodyText'],
            fontSize=11,
            textColor=colors.HexColor('#333333'),
            spaceAfter=8,
            leftIndent=20,
            fontName='Helvetica'
        )
        
        return {
            'title': title_style,
            'heading': heading_style,
            'body': body_style,
            'list': list_style
        }
    
    def export_to_pdf(
        self,
        mom_text: str,
        filename: Optional[str] = None,
        metadata: Optional[dict] = None
    ) -> BytesIO:
        """
        Export MOM text to PDF.
        
        Args:
            mom_text: Formatted MOM text
            filename: Optional filename for PDF
            metadata: Optional metadata (meeting_date, meeting_title, etc.)
            
        Returns:
            BytesIO buffer containing PDF data
        """
        if not mom_text or not mom_text.strip():
            raise ValueError("MOM text cannot be empty")
        
        # Create BytesIO buffer
        buffer = BytesIO()
        
        # Create PDF document
        doc = SimpleDocTemplate(
            buffer,
            pagesize=self.page_size,
            rightMargin=72,
            leftMargin=72,
            topMargin=72,
            bottomMargin=18,
        )
        
        # Build story (content)
        story = []
        
        # Add metadata header if provided
        if metadata:
            meeting_date = metadata.get('meeting_date', datetime.now().strftime('%Y-%m-%d'))
            meeting_title = metadata.get('meeting_title', 'Meeting Minutes')
            
            story.append(Paragraph(f"<b>{meeting_title}</b>", self.styles['title']))
            story.append(Paragraph(f"Date: {meeting_date}", self.styles['body']))
            story.append(Spacer(1, 0.2 * inch))
        
        # Parse and format MOM text
        lines = mom_text.split('\n')
        
        for line in lines:
            line = line.strip()
            
            if not line:
                story.append(Spacer(1, 0.1 * inch))
                continue
            
            # Detect section headers (all caps or ends with colon)
            if line.isupper() or (line.endswith(':') and len(line.split()) <= 5):
                # Escape HTML characters
                line = self._escape_html(line)
                story.append(Paragraph(line, self.styles['heading']))
            # Detect list items (starts with bullet, number, or dash)
            elif line.startswith(('•', '-', '*')) or (line[0:2].rstrip('.').isdigit()):
                line = self._escape_html(line)
                story.append(Paragraph(line, self.styles['list']))
            # Regular body text
            else:
                line = self._escape_html(line)
                story.append(Paragraph(line, self.styles['body']))
        
        # Add footer
        story.append(Spacer(1, 0.3 * inch))
        footer_text = f"Generated on {datetime.now().strftime('%Y-%m-%d %H:%M')} by ClearMeet"
        story.append(Paragraph(f"<i>{footer_text}</i>", self.styles['body']))
        
        # Build PDF
        doc.build(story)
        
        # Reset buffer position
        buffer.seek(0)
        
        return buffer
    
    @staticmethod
    def _escape_html(text: str) -> str:
        """
        Escape HTML special characters for ReportLab.
        
        Args:
            text: Input text
            
        Returns:
            Escaped text
        """
        if not text:
            return ""
        
        text = text.replace('&', '&amp;')
        text = text.replace('<', '&lt;')
        text = text.replace('>', '&gt;')
        
        return text
    
    @staticmethod
    def save_buffer_to_file(buffer: BytesIO, filepath: str) -> None:
        """
        Save BytesIO buffer to file.
        
        Args:
            buffer: PDF buffer
            filepath: Destination file path
        """
        with open(filepath, 'wb') as f:
            f.write(buffer.getvalue())
