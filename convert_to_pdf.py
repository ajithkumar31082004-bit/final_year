"""
Convert Markdown Project Report to PDF
Uses markdown + weasyprint for conversion
"""

import markdown
from weasyprint import HTML, CSS
from pathlib import Path

# Read the markdown file
md_file = Path("PROJECT_REPORT.md")
if not md_file.exists():
    print("Error: PROJECT_REPORT.md not found!")
    exit(1)

print("Reading markdown file...")
md_content = md_file.read_text(encoding='utf-8')

# Convert markdown to HTML
print("Converting markdown to HTML...")
html_content = markdown.markdown(
    md_content,
    extensions=['tables', 'fenced_code', 'toc', 'nl2br']
)

# Create full HTML document with styling
html_template = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Blissful Abodes - Project Report</title>
    <style>
        @page {{
            size: A4;
            margin: 2cm;
            @bottom-center {{
                content: "Page " counter(page) " of " counter(pages);
                font-size: 10pt;
                color: #666;
            }}
        }}

        * {{
            box-sizing: border-box;
        }}

        body {{
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            font-size: 11pt;
            line-height: 1.6;
            color: #333;
            max-width: 100%;
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
            font-size: 28pt;
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
            page-break-inside: avoid;
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
            page-break-inside: avoid;
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

        .cover-page {{
            text-align: center;
            padding-top: 150px;
        }}

        .cover-page h1 {{
            font-size: 32pt;
            color: #2c3e50;
            margin-bottom: 50px;
        }}

        .cover-page .subtitle {{
            font-size: 18pt;
            color: #7f8c8d;
            margin: 20px 0;
        }}

        .cover-page .info {{
            font-size: 14pt;
            color: #34495e;
            margin-top: 100px;
        }}

        /* ASCII art styling */
        pre code {{
            white-space: pre;
            font-family: 'Courier New', monospace;
        }}

        /* Page break utilities */
        .page-break {{
            page-break-after: always;
        }}
    </style>
</head>
<body>
{html_content}
</body>
</html>"""

# Save HTML first (optional)
html_file = Path("PROJECT_REPORT.html")
html_file.write_text(html_template, encoding='utf-8')
print("HTML version saved as PROJECT_REPORT.html")

# Convert to PDF
print("Converting to PDF (this may take a moment)...")
pdf_file = Path("Blissful_Abodes_Project_Report.pdf")

HTML(string=html_template).write_pdf(
    str(pdf_file),
    stylesheets=[]
)

print(f"\n✅ PDF successfully created: {pdf_file.name}")
print(f"File size: {pdf_file.stat().st_size / 1024:.1f} KB")
