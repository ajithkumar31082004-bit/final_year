#!/usr/bin/env python3
"""
Convert Project Report to PDF using ReportLab
Better Unicode support
"""

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch, cm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from pathlib import Path
import re

def create_pdf_report():
    # Read markdown
    md_file = Path("PROJECT_REPORT.md")
    if not md_file.exists():
        print("Error: PROJECT_REPORT.md not found!")
        return

    print("Reading markdown file...")
    content = md_file.read_text(encoding='utf-8')

    # Create PDF document
    output_file = "Blissful_Abodes_Project_Report.pdf"
    doc = SimpleDocTemplate(
        output_file,
        pagesize=A4,
        rightMargin=2*cm,
        leftMargin=2*cm,
        topMargin=2*cm,
        bottomMargin=2*cm
    )

    # Container for the 'Flowable' objects
    elements = []

    # Styles
    styles = getSampleStyleSheet()

    # Custom styles
    title_style = ParagraphStyle(
        'CustomTitle',
        parent=styles['Heading1'],
        fontSize=28,
        textColor=colors.HexColor('#2c3e50'),
        spaceAfter=30,
        alignment=1  # Center
    )

    subtitle_style = ParagraphStyle(
        'Subtitle',
        parent=styles['Normal'],
        fontSize=16,
        textColor=colors.HexColor('#7f8c8d'),
        spaceAfter=20,
        alignment=1
    )

    heading1_style = ParagraphStyle(
        'CustomH1',
        parent=styles['Heading1'],
        fontSize=20,
        textColor=colors.HexColor('#2c3e50'),
        spaceAfter=12,
        spaceBefore=20,
        borderColor=colors.HexColor('#3498db'),
        borderWidth=2,
        borderPadding=5,
        leftIndent=0,
        borderWidth=0,
        borderWidthBottom=3
    )

    heading2_style = ParagraphStyle(
        'CustomH2',
        parent=styles['Heading2'],
        fontSize=16,
        textColor=colors.HexColor('#34495e'),
        spaceAfter=10,
        spaceBefore=15
    )

    heading3_style = ParagraphStyle(
        'CustomH3',
        parent=styles['Heading3'],
        fontSize=13,
        textColor=colors.HexColor('#34495e'),
        spaceAfter=8,
        spaceBefore=12
    )

    normal_style = ParagraphStyle(
        'CustomNormal',
        parent=styles['Normal'],
        fontSize=10,
        leading=14,
        spaceAfter=8
    )

    code_style = ParagraphStyle(
        'Code',
        parent=styles['Code'],
        fontSize=8,
        fontName='Courier',
        textColor=colors.HexColor('#333'),
        backColor=colors.HexColor('#f4f4f4'),
        leftIndent=10,
        spaceAfter=6
    )

    # Cover page
    elements.append(Spacer(1, 3*inch))
    elements.append(Paragraph("Blissful Abodes", title_style))
    elements.append(Spacer(1, 0.2*inch))
    elements.append(Paragraph("AI-Powered Hotel Management System", subtitle_style))
    elements.append(Spacer(1, 0.3*inch))
    elements.append(Paragraph("Final Year Project Report", subtitle_style))
    elements.append(Spacer(1, 2*inch))
    elements.append(Paragraph("Department of Computer Science", subtitle_style))
    elements.append(Paragraph("Academic Year 2025-2026", subtitle_style))

    elements.append(PageBreak())

    # Process markdown content
    print("Converting to PDF...")

    lines = content.split('\n')
    i = 0
    in_code_block = False
    code_lines = []

    while i < len(lines):
        line = lines[i]

        # Code blocks
        if line.strip().startswith('```'):
            if in_code_block:
                # End code block
                if code_lines:
                    code_text = '\n'.join(code_lines)
                    elements.append(Paragraph(code_text.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;'), code_style))
                code_lines = []
                in_code_block = False
            else:
                in_code_block = True
            i += 1
            continue

        if in_code_block:
            code_lines.append(line)
            i += 1
            continue

        # Empty line
        if not line.strip():
            elements.append(Spacer(1, 0.1*inch))
            i += 1
            continue

        # Headers
        if line.startswith('# '):
            text = line[2:].strip()
            elements.append(Paragraph(text, heading1_style))
            i += 1
            continue

        if line.startswith('## '):
            text = line[3:].strip()
            elements.append(Paragraph(text, heading2_style))
            i += 1
            continue

        if line.startswith('### '):
            text = line[4:].strip()
            elements.append(Paragraph(text, heading3_style))
            i += 1
            continue

        if line.startswith('#### '):
            text = line[5:].strip()
            elements.append(Paragraph(text, heading3_style))
            i += 1
            continue

        # Horizontal rule
        if line.strip() == '---':
            elements.append(Spacer(1, 0.2*inch))
            i += 1
            continue

        # Tables
        if line.strip().startswith('|') and '|' in line[1:]:
            # Collect table rows
            table_rows = []
            while i < len(lines) and lines[i].strip().startswith('|'):
                row_text = lines[i].strip()
                # Skip separator rows
                if not re.match(r'^\|[-:\s|]+\|$', row_text):
                    cells = [cell.strip() for cell in row_text.split('|')[1:-1]]
                    table_rows.append(cells)
                i += 1

            # Create table
            if table_rows and len(table_rows) > 1:
                # Use first row as header
                header = table_rows[0]
                data = table_rows[1:]

                # Create table data
                table_data = [header] + data

                # Calculate column widths
                num_cols = len(header)
                col_width = [450/num_cols] * num_cols

                table = Table(table_data, colWidths=col_width, repeatRows=1)
                table.setStyle(TableStyle([
                    ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#34495e')),
                    ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                    ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
                    ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                    ('FONTSIZE', (0, 0), (-1, 0), 9),
                    ('BOTTOMPADDING', (0, 0), (-1, 0), 8),
                    ('BACKGROUND', (0, 1), (-1, -1), colors.HexColor('#f8f9fa')),
                    ('GRID', (0, 0), (-1, -1), 1, colors.HexColor('#bdc3c7')),
                    ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
                    ('FONTSIZE', (0, 1), (-1, -1), 8),
                    ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
                ]))
                elements.append(table)
                elements.append(Spacer(1, 0.1*inch))
            continue

        # List items
        if line.strip().startswith(('- ', '* ')):
            text = line.strip()[2:]
            # Process inline formatting
            text = process_inline_formatting(text)
            elements.append(Paragraph(f'• {text}', normal_style))
            i += 1
            continue

        # Numbered list
        match = re.match(r'^(\d+)\.\s+(.+)$', line.strip())
        if match:
            num, text = match.groups()
            text = process_inline_formatting(text)
            elements.append(Paragraph(f'{num}. {text}', normal_style))
            i += 1
            continue

        # Blockquote
        if line.strip().startswith('>'):
            text = line.strip()[1:].strip()
            text = process_inline_formatting(text)
            quote_style = ParagraphStyle(
                'Quote',
                parent=normal_style,
                leftIndent=20,
                borderColor=colors.HexColor('#3498db'),
                borderWidth=0,
                borderWidthLeft=3,
                borderPadding=10,
                backColor=colors.HexColor('#f8f9fa')
            )
            elements.append(Paragraph(text, quote_style))
            i += 1
            continue

        # Regular paragraph
        text = line.strip()
        if text:
            text = process_inline_formatting(text)
            elements.append(Paragraph(text, normal_style))
        i += 1

    # Build PDF
    print("Building PDF...")
    doc.build(elements)

    print(f"\nPDF successfully created: {output_file}")
    file_size = Path(output_file).stat().st_size
    print(f"File size: {file_size / 1024:.1f} KB")

def process_inline_formatting(text):
    """Process bold and italic in text"""
    # Bold
    text = re.sub(r'\*\*(.+?)\*\*', r'<b>\1</b>', text)
    # Italic
    text = re.sub(r'\*(.+?)\*', r'<i>\1</i>', text)
    # Code inline
    text = re.sub(r'`(.+?)`', r'<code>\1</code>', text)
    # Escape special XML characters
    text = text.replace('&', '&amp;')
    text = text.replace('<', '&lt;')
    text = text.replace('>', '&gt;')
    # Restore HTML tags
    text = text.replace('&lt;b&gt;', '<b>').replace('&lt;/b&gt;', '</b>')
    text = text.replace('&lt;i&gt;', '<i>').replace('&lt;/i&gt;', '</i>')
    text = text.replace('&lt;code&gt;', '<code>').replace('&lt;/code&gt;', '</code>')
    return text

if __name__ == '__main__':
    create_pdf_report()
