#!/usr/bin/env python3
"""
Convert Project Report Markdown to PDF using FPDF2
Simpler approach without external dependencies
"""

from fpdf import FPDF
import re
from pathlib import Path

class PDF(FPDF):
    def header(self):
        # Only add header on non-first pages
        if self.page_no() > 1:
            self.set_font('Arial', 'I', 8)
            self.set_text_color(100, 100, 100)
            self.cell(0, 10, 'Blissful Abodes - Final Year Project Report', 0, 0, 'C')
            self.ln(5)
            # Line under header
            self.set_draw_color(200, 200, 200)
            self.line(10, 20, 200, 20)
            self.ln(10)

    def footer(self):
        self.set_y(-15)
        self.set_font('Arial', 'I', 8)
        self.set_text_color(100, 100, 100)
        self.cell(0, 10, f'Page {self.page_no()}', 0, 0, 'C')

    def chapter_title(self, title, level=1):
        if level == 1:
            self.set_font('Arial', 'B', 16)
            self.set_text_color(44, 62, 80)
            self.ln(10)
            self.multi_cell(0, 10, title)
            # Line under title
            self.set_draw_color(52, 152, 219)
            self.line(10, self.get_y(), 200, self.get_y())
            self.ln(8)
        elif level == 2:
            self.set_font('Arial', 'B', 13)
            self.set_text_color(52, 73, 94)
            self.ln(8)
            self.multi_cell(0, 8, title)
            self.ln(4)
        else:
            self.set_font('Arial', 'B', 11)
            self.set_text_color(44, 62, 80)
            self.ln(6)
            self.multi_cell(0, 6, title)
            self.ln(2)

    def chapter_body(self, body):
        self.set_font('Arial', '', 10)
        self.set_text_color(50, 50, 50)
        self.multi_cell(0, 5, body)
        self.ln()

    def add_code_block(self, code):
        self.set_font('Courier', '', 8)
        self.set_text_color(40, 40, 40)
        self.set_fill_color(245, 245, 245)
        self.multi_cell(0, 4, code, fill=True)
        self.ln(3)

    def add_list_item(self, text, bullet='•'):
        self.set_font('Arial', '', 10)
        self.set_text_color(50, 50, 50)
        self.cell(5)  # Indent
        self.cell(5, 5, bullet, 0, 0, 'L')
        self.multi_cell(0, 5, text)

def parse_markdown_line(line):
    """Parse markdown line and return type and content"""
    line = line.rstrip()

    # Empty line
    if not line:
        return 'empty', None

    # Headers
    if line.startswith('# '):
        return 'h1', line[2:]
    elif line.startswith('## '):
        return 'h2', line[3:]
    elif line.startswith('### '):
        return 'h3', line[4:]
    elif line.startswith('#### '):
        return 'h4', line[5:]

    # Horizontal rule
    if line.strip() == '---':
        return 'hr', None

    # List items
    if line.startswith('- ') or line.startswith('* '):
        return 'li', line[2:]

    # Numbered list
    match = re.match(r'^(\d+)\.\s+(.+)$', line)
    if match:
        return 'li_num', (match.group(1), match.group(2))

    # Code block start/end
    if line.startswith('```'):
        return 'code_fence', line[3:].strip()

    # Table row
    if line.startswith('|') and '|' in line[1:]:
        return 'table_row', line

    # Blockquote
    if line.startswith('>'):
        return 'blockquote', line[1:].strip()

    # Regular paragraph
    return 'p', line

def create_pdf():
    # Read markdown file
    md_file = Path("PROJECT_REPORT.md")
    if not md_file.exists():
        print("Error: PROJECT_REPORT.md not found!")
        print("Please ensure the report file exists.")
        return

    print("Reading markdown file...")
    content = md_file.read_text(encoding='utf-8')

    # Create PDF
    pdf = PDF()
    pdf.set_auto_page_break(auto=True, margin=15)
    pdf.add_page()

    # Title page
    pdf.set_font('Arial', 'B', 28)
    pdf.set_text_color(44, 62, 80)
    pdf.ln(60)
    pdf.cell(0, 20, 'Blissful Abodes', 0, 1, 'C')
    pdf.set_font('Arial', 'B', 18)
    pdf.set_text_color(52, 73, 94)
    pdf.cell(0, 12, 'AI-Powered Hotel Management System', 0, 1, 'C')
    pdf.ln(20)
    pdf.set_font('Arial', '', 14)
    pdf.set_text_color(100, 100, 100)
    pdf.cell(0, 10, 'Final Year Project Report', 0, 1, 'C')
    pdf.ln(40)

    # Info box
    pdf.set_font('Arial', '', 12)
    pdf.set_text_color(80, 80, 80)
    pdf.cell(0, 8, 'Department of Computer Science', 0, 1, 'C')
    pdf.cell(0, 8, 'Academic Year 2025-2026', 0, 1, 'C')

    pdf.add_page()

    # Process markdown
    print("Converting markdown to PDF...")

    lines = content.split('\n')
    in_code_block = False
    code_content = []
    in_table = False
    table_rows = []

    for i, line in enumerate(lines):
        line_type, line_content = parse_markdown_line(line)

        # Handle code blocks
        if line_type == 'code_fence':
            if in_code_block:
                # End code block
                if code_content:
                    pdf.add_code_block('\n'.join(code_content))
                code_content = []
                in_code_block = False
            else:
                # Start code block
                in_code_block = True
            continue

        if in_code_block:
            code_content.append(line)
            continue

        # Handle tables
        if line_type == 'table_row':
            if not in_table:
                in_table = True
                table_rows = []
            # Skip separator rows
            if not re.match(r'^\|[-:|\s]+\|$', line.strip()):
                # Parse table cells
                cells = [cell.strip() for cell in line.split('|')[1:-1]]
                table_rows.append(cells)
            continue
        elif in_table:
            # Render table
            if table_rows:
                render_table(pdf, table_rows)
            table_rows = []
            in_table = False

        # Handle other elements
        if line_type == 'h1':
            pdf.chapter_title(line_content, 1)
        elif line_type == 'h2':
            pdf.chapter_title(line_content, 2)
        elif line_type == 'h3':
            pdf.chapter_title(line_content, 3)
        elif line_type == 'h4':
            pdf.chapter_title(line_content, 4)
        elif line_type == 'hr':
            pdf.ln(5)
            pdf.set_draw_color(200, 200, 200)
            pdf.line(20, pdf.get_y(), 190, pdf.get_y())
            pdf.ln(5)
        elif line_type == 'li':
            pdf.add_list_item(line_content)
        elif line_type == 'li_num':
            num, text = line_content
            pdf.add_list_item(f'{num}. {text}', '  ')
        elif line_type == 'blockquote':
            pdf.set_font('Arial', 'I', 10)
            pdf.set_text_color(80, 80, 80)
            pdf.cell(5)  # Indent
            pdf.multi_cell(0, 5, line_content)
            pdf.ln(2)
        elif line_type == 'p':
            # Check if it's a bold line
            if line_content.startswith('**') and line_content.endswith('**'):
                pdf.set_font('Arial', 'B', 10)
                pdf.multi_cell(0, 5, line_content[2:-2])
                pdf.ln(2)
            else:
                pdf.chapter_body(line_content)

    # Handle any remaining table
    if in_table and table_rows:
        render_table(pdf, table_rows)

    # Save PDF
    output_file = "Blissful_Abodes_Project_Report.pdf"
    pdf.output(output_file)
    print(f"\nPDF successfully created: {output_file}")

    file_size = Path(output_file).stat().st_size
    print(f"File size: {file_size / 1024:.1f} KB")
    print(f"Total pages: {pdf.page_no()}")

def render_table(pdf, rows):
    """Render a simple table"""
    if not rows:
        return

    pdf.set_font('Arial', 'B', 9)
    pdf.set_fill_color(52, 73, 94)
    pdf.set_text_color(255, 255, 255)

    # Calculate column widths
    num_cols = len(rows[0])
    col_width = 180 / num_cols

    # Header row
    for cell in rows[0]:
        pdf.cell(col_width, 7, cell[:25], 1, 0, 'L', True)
    pdf.ln()

    # Data rows
    pdf.set_font('Arial', '', 9)
    pdf.set_text_color(50, 50, 50)
    fill = False
    pdf.set_fill_color(248, 249, 250)

    for row in rows[1:]:
        for cell in row:
            pdf.cell(col_width, 6, cell[:25], 1, 0, 'L', fill)
        pdf.ln()
        fill = not fill

    pdf.ln(5)

if __name__ == '__main__':
    create_pdf()
