#!/usr/bin/env python3
"""
Convert Markdown Project Report to styled HTML
Can be printed to PDF from any browser
"""

from pathlib import Path

# Read the markdown file
md_file = Path("PROJECT_REPORT.md")
if not md_file.exists():
    print("Error: PROJECT_REPORT.md not found!")
    exit(1)

print("Reading markdown file...")
content = md_file.read_text(encoding='utf-8')

# Split into lines for processing
lines = content.split('\n')
html_lines = []
in_code_block = False
code_content = []

for line in lines:
    # Handle code blocks
    if line.strip().startswith('```'):
        if in_code_block:
            html_lines.append('<pre><code>' + '\n'.join(code_content) + '</code></pre>')
            code_content = []
            in_code_block = False
        else:
            in_code_block = True
        continue

    if in_code_block:
        code_content.append(line)
        continue

    # Handle headers
    if line.startswith('# '):
        html_lines.append(f'<h1>{line[2:]}</h1>')
    elif line.startswith('## '):
        html_lines.append(f'<h2>{line[3:]}</h2>')
    elif line.startswith('### '):
        html_lines.append(f'<h3>{line[4:]}</h3>')
    elif line.startswith('#### '):
        html_lines.append(f'<h4>{line[5:]}</h4>')
    # Handle horizontal rule
    elif line.strip() == '---':
        html_lines.append('<hr>')
    # Handle list items
    elif line.startswith('- ') or line.startswith('* '):
        html_lines.append(f'<li>{line[2:]}</li>')
    # Handle blockquote
    elif line.startswith('>'):
        html_lines.append(f'<blockquote>{line[1:].strip()}</blockquote>')
    # Handle empty lines
    elif not line.strip():
        html_lines.append('<br>')
    # Handle regular paragraphs
    else:
        # Process inline formatting
        text = line
        # Bold
        text = text.replace('**', '<strong>', 1)
        text = text.replace('**', '</strong>', 1)
        text = text.replace('**', '<strong>', 1)
        text = text.replace('**', '</strong>', 1)
        # Italic
        text = text.replace('*', '<em>', 1)
        text = text.replace('*', '</em>', 1)
        html_lines.append(f'<p>{text}</p>')

# Wrap list items in ul
final_html = []
i = 0
while i < len(html_lines):
    if html_lines[i].startswith('<li>'):
        final_html.append('<ul>')
        while i < len(html_lines) and html_lines[i].startswith('<li>'):
            final_html.append(html_lines[i])
            i += 1
        final_html.append('</ul>')
    else:
        final_html.append(html_lines[i])
        i += 1

html_content = '\n'.join(final_html)

# Create full HTML document
html_template = f'''<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Blissful Abodes - Project Report</title>
    <style>
        @page {{
            size: A4;
            margin: 2cm;
        }}

        * {{
            box-sizing: border-box;
        }}

        body {{
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            font-size: 11pt;
            line-height: 1.6;
            color: #333;
            max-width: 210mm;
            margin: 0 auto;
            padding: 20px;
        }}

        h1 {{
            font-size: 24pt;
            color: #2c3e50;
            border-bottom: 3px solid #3498db;
            padding-bottom: 10px;
            margin-top: 30px;
            page-break-before: always;
        }}

        h1:first-of-type {{
            page-break-before: avoid;
            text-align: center;
            border-bottom: none;
            margin-top: 100px;
            font-size: 32pt;
        }}

        h2 {{
            font-size: 18pt;
            color: #34495e;
            border-bottom: 2px solid #ecf0f1;
            padding-bottom: 8px;
            margin-top: 25px;
        }}

        h3 {{
            font-size: 14pt;
            color: #34495e;
            margin-top: 20px;
        }}

        h4 {{
            font-size: 12pt;
            color: #2c3e50;
            margin-top: 15px;
        }}

        p {{
            text-align: justify;
            margin: 10px 0;
        }}

        table {{
            width: 100%;
            border-collapse: collapse;
            margin: 15px 0;
        }}

        th, td {{
            border: 1px solid #bdc3c7;
            padding: 8px 12px;
            text-align: left;
        }}

        th {{
            background-color: #34495e;
            color: white;
            font-weight: bold;
        }}

        tr:nth-child(even) {{
            background-color: #f8f9fa;
        }}

        code {{
            background-color: #f4f4f4;
            padding: 2px 6px;
            border-radius: 3px;
            font-family: 'Courier New', monospace;
            font-size: 10pt;
        }}

        pre {{
            background-color: #f8f9fa;
            border: 1px solid #e9ecef;
            border-radius: 5px;
            padding: 15px;
            overflow-x: auto;
            font-size: 9pt;
            line-height: 1.4;
            white-space: pre-wrap;
            word-wrap: break-word;
        }}

        pre code {{
            background-color: transparent;
            padding: 0;
        }}

        blockquote {{
            border-left: 4px solid #3498db;
            margin: 15px 0;
            padding: 10px 20px;
            background-color: #f8f9fa;
            font-style: italic;
        }}

        ul, ol {{
            margin: 10px 0;
            padding-left: 25px;
        }}

        li {{
            margin: 5px 0;
        }}

        hr {{
            border: none;
            border-top: 2px solid #ecf0f1;
            margin: 30px 0;
        }}

        strong {{
            color: #2c3e50;
        }}

        .cover {{
            text-align: center;
            padding-top: 150px;
        }}

        .cover h1 {{
            border-bottom: none;
            margin-top: 50px;
        }}

        .subtitle {{
            font-size: 18pt;
            color: #7f8c8d;
            margin: 20px 0;
            text-align: center;
        }}

        .info {{
            font-size: 14pt;
            color: #34495e;
            margin-top: 100px;
            text-align: center;
        }}

        @media print {{
            body {{
                padding: 0;
            }}

            h1 {{
                page-break-before: always;
            }}

            h1:first-of-type {{
                page-break-before: avoid;
            }}

            pre {{
                page-break-inside: avoid;
            }}

            table {{
                page-break-inside: avoid;
            }}
        }}
    </style>
</head>
<body>
{html_content}
</body>
</html>'''

# Save HTML
output_file = Path("PROJECT_REPORT.html")
output_file.write_text(html_template, encoding='utf-8')

print(f"HTML report created: {output_file.name}")
print(f"File size: {output_file.stat().st_size / 1024:.1f} KB")
print("\nTo convert to PDF:")
print("1. Open PROJECT_REPORT.html in your browser")
print("2. Press Ctrl+P (or Cmd+P on Mac)")
print("3. Select 'Save as PDF' as the destination")
print("4. Click Save")
