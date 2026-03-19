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
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, PageBreak, Table, TableStyle
from reportlab.lib import colors


class PDFExporter:
    """Export MOM to PDF format."""
    
    @staticmethod
    def _format_deadline(deadline_str: str) -> str:
        """
        Format deadline string to be more human-friendly.
        
        Args:
            deadline_str: Raw deadline string (ISO format, relative date, etc.)
            
        Returns:
            Human-friendly formatted deadline
        """
        if not deadline_str or deadline_str.strip().lower() in ['no deadline', 'none', '', 'n/a']:
            return 'No deadline'
        
        deadline_str = deadline_str.strip()
        
        # Try to parse ISO datetime formats
        for fmt in [
            '%Y-%m-%dT%H:%M:%S',  # 2023-10-03T17:00:00
            '%Y-%m-%dT%H:%M',     # 2023-10-03T17:00
            '%Y-%m-%d',           # 2023-10-04
        ]:
            try:
                dt = datetime.strptime(deadline_str, fmt)
                # Format with time if it was included
                if 'T' in deadline_str:
                    # Format: "Oct 3, 2023 at 5:00 PM"
                    formatted = dt.strftime('%b %d, %Y at %I:%M %p')
                    # Remove leading zeros from day and hour
                    formatted = formatted.replace(' 0', ' ').replace(' at 0', ' at ')
                    return formatted
                else:
                    # Format: "Oct 3, 2023"
                    formatted = dt.strftime('%b %d, %Y')
                    # Remove leading zero from day
                    formatted = formatted.replace(' 0', ' ')
                    return formatted
            except ValueError:
                continue
        
        # If not ISO format, return as-is (could be "Next week", "Friday", etc.)
        return deadline_str
    
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
            fontSize=20,
            textColor=colors.HexColor('#1a1a1a'),
            spaceAfter=12,
            spaceBefore=0,
            alignment=TA_LEFT,
            fontName='Helvetica-Bold'
        )
        
        # Section heading style  
        section_style = ParagraphStyle(
            'SectionHeading',
            parent=styles['Heading2'],
            fontSize=14,
            textColor=colors.HexColor('#2c3e50'),
            spaceAfter=10,
            spaceBefore=16,
            fontName='Helvetica-Bold'
        )
        
        # Body style
        body_style = ParagraphStyle(
            'CustomBody',
            parent=styles['BodyText'],
            fontSize=10,
            textColor=colors.HexColor('#333333'),
            spaceAfter=6,
            alignment=TA_LEFT,
            fontName='Helvetica',
            leading=14
        )
        
        # List item style
        list_style = ParagraphStyle(
            'CustomList',
            parent=styles['BodyText'],
            fontSize=10,
            textColor=colors.HexColor('#333333'),
            spaceAfter=4,
            leftIndent=20,
            fontName='Helvetica',
            bulletIndent=10
        )
        
        # Small text style
        small_style = ParagraphStyle(
            'SmallText',
            parent=styles['BodyText'],
            fontSize=8,
            textColor=colors.HexColor('#666666'),
            spaceAfter=4,
            alignment=TA_LEFT,
            fontName='Helvetica'
        )
        
        return {
            'title': title_style,
            'section': section_style,
            'body': body_style,
            'list': list_style,
            'small': small_style
        }
    
    def _parse_action_items_table(self, lines: list[str], start_idx: int) -> tuple[list[list[str]], int]:
        """
        Parse ASCII action items table into structured data.
        
        Args:
            lines: All lines from MOM text
            start_idx: Index where action items section starts
            
        Returns:
            Tuple of (table_data, end_idx)
        """
        table_data = []
        idx = start_idx
        
        # Skip "Action Items:" header and look for table header
        while idx < len(lines):
            line = lines[idx].strip()
            idx += 1
            
            # Look for table header (contains # | Action | Owner | Deadline | Status)
            if '|' in line and 'Action' in line and 'Owner' in line:
                # Found header - skip the divider line
                if idx < len(lines) and '---' in lines[idx]:
                    idx += 1
                
                # Parse table rows
                while idx < len(lines):
                    row_line = lines[idx].strip()
                    
                    # Stop if we hit a new section or empty line followed by a section
                    if not row_line or (row_line and not '|' in row_line and ':' in row_line):
                        break
                    
                    # Parse table row
                    if '|' in row_line:
                        parts = [p.strip() for p in row_line.split('|')]
                        if len(parts) >= 5:  # num | action | owner | deadline | status
                            num = parts[0].strip()
                            action = parts[1].strip()
                            owner = parts[2].strip()
                            deadline = self._format_deadline(parts[3].strip())
                            status = parts[4].strip()
                            
                            # Only add if it's a real row (not continuation or header)
                            if num and (num.isdigit() or action):
                                # If this row has a number, it's a new action item
                                if num.isdigit():
                                    table_data.append([num, action, owner, deadline, status])
                                # If no number but action exists, it's a continuation
                                elif action and table_data:
                                    # Append to previous row's action
                                    table_data[-1][1] += ' ' + action
                    
                    idx += 1
                break
            
            # If we find a new section before the table, stop
            if line and line.endswith(':') and not '|' in line:
                break
        
        return table_data, idx
    
    def _create_action_items_table(self, action_data: list[list[str]]) -> Table:
        """
        Create a styled ReportLab table for action items.
        
        Args:
            action_data: List of [num, action, owner, deadline, status] rows
            
        Returns:
            Styled Table object
        """
        if not action_data:
            return None
        
        # Wrap text cells in Paragraph so ReportLab word-wraps long content
        cell_style = ParagraphStyle(
            'TableCell',
            parent=self.styles['body'],
            fontSize=9,
            leading=13,
            spaceAfter=0,
        )
        
        # Add header row (plain strings — styled via TableStyle)
        table_data = [['#', 'Action', 'Owner', 'Deadline', 'Status']]
        for row in action_data:
            table_data.append([
                row[0],
                Paragraph(self._escape_html(row[1]), cell_style),
                Paragraph(self._escape_html(row[2]), cell_style),
                Paragraph(self._escape_html(row[3] if len(row) > 3 else ''), cell_style),
                row[4] if len(row) > 4 else '',
            ])
        
        # Create table — Action column widened to 3.2" for long descriptions
        table = Table(table_data, colWidths=[0.4*inch, 3.2*inch, 1.1*inch, 1.1*inch, 0.8*inch])
        
        # Style the table
        style = TableStyle([
            # Header row styling
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#2c3e50')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 10),
            ('ALIGN', (0, 0), (-1, 0), 'CENTER'),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 10),
            ('TOPPADDING', (0, 0), (-1, 0), 10),
            
            # Data rows styling
            ('BACKGROUND', (0, 1), (-1, -1), colors.white),
            ('TEXTCOLOR', (0, 1), (-1, -1), colors.HexColor('#333333')),
            ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
            ('FONTSIZE', (0, 1), (-1, -1), 9),
            ('ALIGN', (0, 1), (0, -1), 'CENTER'),  # # column centered
            ('ALIGN', (1, 1), (1, -1), 'LEFT'),    # Action column left
            ('ALIGN', (2, 1), (2, -1), 'LEFT'),    # Owner column left
            ('ALIGN', (3, 1), (3, -1), 'LEFT'),    # Deadline column left
            ('ALIGN', (4, 1), (4, -1), 'CENTER'),  # Status column centered
            ('VALIGN', (0, 0), (-1, 0), 'MIDDLE'),  # header middle-aligned
            ('VALIGN', (0, 1), (-1, -1), 'TOP'),    # data rows top-aligned for multi-line
            ('TOPPADDING', (0, 1), (-1, -1), 8),
            ('BOTTOMPADDING', (0, 1), (-1, -1), 8),
            ('LEFTPADDING', (0, 0), (-1, -1), 6),
            ('RIGHTPADDING', (0, 0), (-1, -1), 6),
            
            # Grid
            ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#cccccc')),
            ('LINEBELOW', (0, 0), (-1, 0), 2, colors.HexColor('#2c3e50')),
            
            # Alternating row colors
            ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#f8f9fa')]),
        ])
        
        # Add status-specific coloring
        for i, row in enumerate(action_data, start=1):
            status = row[4].lower() if len(row) > 4 else ''
            if 'open' in status or 'pending' in status:
                # Orange background for open items
                style.add('BACKGROUND', (4, i), (4, i), colors.HexColor('#fff3cd'))
                style.add('TEXTCOLOR', (4, i), (4, i), colors.HexColor('#856404'))
            elif 'complete' in status or 'done' in status or 'closed' in status:
                # Green background for completed
                style.add('BACKGROUND', (4, i), (4, i), colors.HexColor('#d4edda'))
                style.add('TEXTCOLOR', (4, i), (4, i), colors.HexColor('#155724'))
        
        table.setStyle(style)
        return table
    
    def export_to_pdf(
        self,
        mom_text: str,
        filename: Optional[str] = None,
        metadata: Optional[dict] = None
    ) -> BytesIO:
        """
        Export MOM text to PDF with professional formatting.
        
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
            rightMargin=0.75*inch,
            leftMargin=0.75*inch,
            topMargin=0.75*inch,
            bottomMargin=0.5*inch,
        )
        
        # Build story (content)
        story = []
        lines = mom_text.split('\n')
        idx = 0
        
        # Extract metadata from header lines
        title_text = None
        date_text = None
        start_time = None
        end_time = None
        venue_text = None
        attendees_list = []
        objective_text = None
        
        while idx < min(30, len(lines)):  # Increased range to capture attendees
            line = lines[idx].strip()
            if line.startswith('Title:'):
                title_text = line.replace('Title:', '').strip()
            elif line.startswith('Date:'):
                date_text = line.replace('Date:', '').strip()
            elif line.startswith('Start:'):
                # Parse "Start: 09:00 | End: 10:00" format
                parts = line.split('|')
                start_time = parts[0].replace('Start:', '').strip()
                if len(parts) > 1 and 'End:' in parts[1]:
                    end_time = parts[1].replace('End:', '').strip()
            elif line.startswith('Venue:'):
                venue_text = line.replace('Venue:', '').strip()
            elif line.startswith('Attendees:'):
                # Parse attendees list (following lines starting with dash)
                idx += 1
                while idx < len(lines):
                    attendee_line = lines[idx].strip()
                    if attendee_line.startswith(('-', '•', '*')):
                        attendees_list.append(attendee_line.lstrip('-•* ').strip())
                        idx += 1
                    elif attendee_line.lower() == 'none':
                        idx += 1
                        break
                    elif not attendee_line or attendee_line.endswith(':'):
                        # Reached next section
                        idx -= 1  # Back up one line
                        break
                    else:
                        idx += 1
                continue  # Skip the normal idx increment
            elif line.startswith('Objective:'):
                idx += 1
                if idx < len(lines):
                    objective_text = lines[idx].strip()
            idx += 1
        
        # Add header section
        if title_text:
            story.append(Paragraph(title_text, self.styles['title']))
        else:
            story.append(Paragraph('Minutes of Meeting', self.styles['title']))
        
        # Add meeting metadata in a compact format
        metadata_parts = []
        if date_text:
            metadata_parts.append(f'<b>Date:</b> {date_text}')
        if start_time or end_time:
            time_str = ''
            if start_time:
                time_str = f'<b>Start:</b> {start_time}'
            if end_time:
                if time_str:
                    time_str += f' | <b>End:</b> {end_time}'
                else:
                    time_str = f'<b>End:</b> {end_time}'
            metadata_parts.append(time_str)
        if venue_text:
            metadata_parts.append(f'<b>Venue:</b> {venue_text}')
        
        # Display metadata
        for part in metadata_parts:
            story.append(Paragraph(f'<font size=9 color="#666666">{part}</font>', self.styles['body']))
        
        # Add attendees if present
        if attendees_list:
            attendees_str = ', '.join(attendees_list[:5])  # First 5 attendees
            if len(attendees_list) > 5:
                attendees_str += f' (+{len(attendees_list) - 5} more)'
            story.append(Paragraph(f'<font size=9 color="#666666"><b>Attendees:</b> {self._escape_html(attendees_str)}</font>', self.styles['body']))
        
        # Add horizontal line
        story.append(Spacer(1, 0.15*inch))
        story.append(Paragraph('<para alignment="left"><b>___________________________________________________________________________</b></para>', self.styles['small']))
        story.append(Spacer(1, 0.15*inch))
        
        # Parse content sections
        idx = 0
        current_section = None
        in_action_items = False
        
        while idx < len(lines):
            line = lines[idx].strip()
            
            # Skip empty lines
            if not line:
                idx += 1
                continue
            
            # Skip the header section we already processed
            if line.startswith(('MINUTES OF MEETING', '===', 'Title:', 'Date:', 'Start:', 'Venue:')) or line == '=' * 72:
                idx += 1
                continue
                continue
            
            # Detect section headers
            if line.endswith(':') and len(line.split()) <= 3:
                section_name = line.rstrip(':')
                current_section = section_name
                
                # Add section header with styling
                story.append(Spacer(1, 0.1*inch))
                if section_name == 'Objective':
                    story.append(Paragraph(f'<font color="#2c3e50"><b>{section_name}</b></font>', self.styles['section']))
                    # Add the objective text
                    idx += 1
                    if idx < len(lines) and lines[idx].strip():
                        obj_text = lines[idx].strip()
                        story.append(Paragraph(self._escape_html(obj_text), self.styles['body']))
                elif section_name == 'Action Items':
                    story.append(Paragraph(f'<font color="#2c3e50"><b>{section_name}</b></font>', self.styles['section']))
                    story.append(Spacer(1, 0.05*inch))
                    # Parse and create table
                    action_data, idx = self._parse_action_items_table(lines, idx + 1)
                    if action_data:
                        action_table = self._create_action_items_table(action_data)
                        if action_table:
                            story.append(action_table)
                    else:
                        story.append(Paragraph('<i>No action items</i>', self.styles['body']))
                    continue
                else:
                    story.append(Paragraph(f'<font color="#2c3e50"><b>{section_name}</b></font>', self.styles['section']))
                
                idx += 1
                continue
            
            # Handle content based on current section
            if current_section == 'Attendees':
                # List attendees
                if line.startswith(('-', '•', '*')):
                    attendee = line.lstrip('-•* ').strip()
                    story.append(Paragraph(f'• {self._escape_html(attendee)}', self.styles['list']))
                elif line.lower() != 'none':
                    story.append(Paragraph(self._escape_html(line), self.styles['body']))
                    
            elif current_section == 'Executive Summary':
                # Render executive summary as body text
                if not line.startswith(('Audit:', '#')):
                    story.append(Paragraph(self._escape_html(line), self.styles['body']))
                    
            elif current_section == 'Discussion Summary':
                # Render discussion summary as body text
                if not line.startswith(('Audit:', '#')):
                    story.append(Paragraph(self._escape_html(line), self.styles['body']))
                    
            elif current_section == 'Planned Agenda':
                # List planned agenda items
                if line[0:2].rstrip('.').isdigit():
                    # Main agenda item (numbered)
                    agenda_text = line[line.find('.')+1:].strip() if '.' in line else line
                    story.append(Paragraph(f'{self._escape_html(line)}', self.styles['list']))
                elif line.startswith('Total:'):
                    # Total duration line
                    story.append(Paragraph(f'<b>{self._escape_html(line)}</b>', self.styles['list']))
                elif line.lower() != 'none' and not line.startswith('Audit:'):
                    # Description lines (indented)
                    story.append(Paragraph(f'{self._escape_html(line)}', self.styles['body']))
                    
            elif current_section == 'Key Decisions' or current_section == 'Decisions':
                # List decisions with blue accent
                if line[0:2].rstrip('.').isdigit():
                    decision_text = line[line.find('.')+1:].strip() if '.' in line else line
                    story.append(Paragraph(f'<font color="#1a73e8">●</font> {self._escape_html(decision_text)}', self.styles['list']))
                elif line.lower() != 'none':
                    story.append(Paragraph(self._escape_html(line), self.styles['body']))
                    
            elif current_section == 'Parking Lot':
                # List parking lot items
                if line[0:2].rstrip('.').isdigit():
                    item_text = line[line.find('.')+1:].strip() if '.' in line else line
                    story.append(Paragraph(f'• {self._escape_html(item_text)}', self.styles['list']))
                elif line.lower() != 'none':
                    story.append(Paragraph(self._escape_html(line), self.styles['body']))
                    
            elif current_section == 'Notes':
                # Handle notes section
                if not line.startswith(('Audit:', '#')):
                    story.append(Paragraph(self._escape_html(line), self.styles['body']))
            
            idx += 1
        
        # Add footer
        story.append(Spacer(1, 0.2*inch))
        footer_text = f'Generated by ClearMeet on {datetime.now().strftime("%Y-%m-%d at %H:%M")}'
        story.append(Paragraph(f'<font size=8 color="#999999"><i>{footer_text}</i></font>', self.styles['small']))
        
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
    
    def export_agenda_to_pdf(
        self,
        objective_data: dict,
        agenda_items: list[dict],
        metadata: Optional[dict] = None
    ) -> BytesIO:
        """
        Export meeting agenda to professional PDF format.
        
        Args:
            objective_data: Meeting objective data (objective, start_time, end_time, venue, attendees)
            agenda_items: List of agenda items
            metadata: Optional metadata (meeting_title, etc.)
            
        Returns:
            BytesIO buffer containing PDF data
        """
        # Create BytesIO buffer
        buffer = BytesIO()
        
        # Create PDF document
        doc = SimpleDocTemplate(
            buffer,
            pagesize=self.page_size,
            rightMargin=0.75*inch,
            leftMargin=0.75*inch,
            topMargin=0.75*inch,
            bottomMargin=0.5*inch,
        )
        
        # Build story (content)
        story = []
        
        # Title
        story.append(Paragraph('Meeting Agenda', self.styles['title']))
        
        # Generation timestamp
        generated_date = datetime.now().strftime('%Y-%m-%d %H:%M')
        story.append(Paragraph(f'<font size=9 color="#999999">Generated: {generated_date}</font>', self.styles['body']))
        story.append(Spacer(1, 0.15*inch))
        
        # Add horizontal divider
        story.append(Paragraph('<para alignment="left">________________________________________________________________________________________________</para>', self.styles['small']))
        story.append(Spacer(1, 0.2*inch))
        
        # Meeting Details Section
        # Extract date and time from ISO 8601
        start_time_iso = objective_data.get('start_time', '')
        end_time_iso = objective_data.get('end_time', '')
        venue = objective_data.get('venue', '')
        attendees = objective_data.get('attendees', [])
        
        meeting_date = ''
        start_time = ''
        end_time = ''
        
        if start_time_iso and 'T' in start_time_iso:
            meeting_date = start_time_iso.split('T')[0]
            start_time = start_time_iso.split('T')[1]
        
        if end_time_iso and 'T' in end_time_iso:
            end_time = end_time_iso.split('T')[1]
        
        # Date
        if meeting_date:
            story.append(Paragraph(f'<b>Date:</b> {meeting_date}', self.styles['body']))
        
        # Time
        if start_time or end_time:
            time_text = f'<b>Time:</b> '
            if start_time:
                time_text += start_time
            if end_time:
                if start_time:
                    time_text += f' – {end_time}'
                else:
                    time_text += f'Until {end_time}'
            story.append(Paragraph(time_text, self.styles['body']))
        
        # Venue
        if venue:
            story.append(Paragraph(f'<b>Venue:</b> {self._escape_html(venue)}', self.styles['body']))
        
        # Attendees
        if attendees and len(attendees) > 0:
            attendees_text = '<b>Expected Attendees:</b> '
            attendees_text += ', '.join([self._escape_html(name) for name in attendees])
            story.append(Paragraph(attendees_text, self.styles['body']))
        
        story.append(Spacer(1, 0.25*inch))
        
        # Objective Section
        objective_text = objective_data.get('objective', '').strip()
        if objective_text:
            story.append(Paragraph('<font color="#2c3e50"><b>Objective:</b></font>', self.styles['section']))
            story.append(Paragraph(self._escape_html(objective_text), self.styles['body']))
            story.append(Spacer(1, 0.2*inch))
        
        # Agenda Items Section
        story.append(Paragraph('<font color="#2c3e50"><b>Agenda Items:</b></font>', self.styles['section']))
        story.append(Spacer(1, 0.1*inch))
        
        total_minutes = 0
        for index, item in enumerate(agenda_items, start=1):
            title = str(item.get('title', '')).strip() or f'Agenda Item {index}'
            duration = int(item.get('duration_minutes', 0) or 0)
            description = str(item.get('description', '')).strip()
            total_minutes += duration
            
            # Item number and title
            item_text = f'<b>{index}. {self._escape_html(title)}</b> <font color="#666666">({duration} min)</font>'
            story.append(Paragraph(item_text, self.styles['body']))
            
            # Description if available
            if description:
                desc_text = f'<font color="#555555">&nbsp;&nbsp;&nbsp;&nbsp;{self._escape_html(description)}</font>'
                story.append(Paragraph(desc_text, self.styles['body']))
            
            story.append(Spacer(1, 0.08*inch))
        
        # Total Duration
        story.append(Spacer(1, 0.1*inch))
        story.append(Paragraph(f'<b>Total Duration:</b> {total_minutes} minutes', self.styles['body']))
        
        # Footer
        story.append(Spacer(1, 0.3*inch))
        story.append(Paragraph('<para alignment="center"><font size=8 color="#999999">This document was automatically generated by ClearMeet</font></para>', self.styles['small']))
        
        # Build PDF
        doc.build(story)
        buffer.seek(0)
        
        return buffer
    
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
