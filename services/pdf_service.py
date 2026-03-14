"""
Blissful Abodes - PDF Invoice Generator
Generates GST-compliant hotel invoices using ReportLab
"""

import os
import uuid
from datetime import datetime


def generate_gst_invoice(booking_data, user_data):
    """Generate a GST-compliant PDF invoice"""
    os.makedirs("reports", exist_ok=True)

    invoice_number = (
        f"INV-{datetime.now().year}-{booking_data.get('booking_id', 'XXXXXX')[-5:]}"
    )
    filename = f"invoice_{booking_data.get('booking_id', 'unknown')}.pdf"
    filepath = os.path.join("reports", filename)

    try:
        from reportlab.lib.pagesizes import A4
        from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
        from reportlab.lib.colors import HexColor, white, black
        from reportlab.lib.units import mm, cm
        from reportlab.platypus import (
            SimpleDocTemplate,
            Paragraph,
            Table,
            TableStyle,
            Spacer,
            HRFlowable,
        )
        from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT

        doc = SimpleDocTemplate(
            filepath,
            pagesize=A4,
            rightMargin=15 * mm,
            leftMargin=15 * mm,
            topMargin=15 * mm,
            bottomMargin=15 * mm,
        )

        primary = HexColor("#FF6B35")
        dark = HexColor("#1A1A2E")
        gold = HexColor("#D4AF37")
        grey = HexColor("#F5F5F5")

        styles = getSampleStyleSheet()

        title_style = ParagraphStyle(
            "title",
            fontName="Helvetica-Bold",
            fontSize=22,
            textColor=white,
            alignment=TA_CENTER,
            spaceAfter=2,
        )

        subtitle_style = ParagraphStyle(
            "subtitle",
            fontName="Helvetica",
            fontSize=10,
            textColor=white,
            alignment=TA_CENTER,
        )

        normal_style = ParagraphStyle(
            "normal_custom", fontName="Helvetica", fontSize=9, leading=14
        )

        story = []

        # Header
        header_data = [
            [
                Paragraph(f"<b>🏨 Blissful Abodes Chennai</b>", title_style),
            ]
        ]
        header_table = Table(header_data, colWidths=[180 * mm])
        header_table.setStyle(
            TableStyle(
                [
                    ("BACKGROUND", (0, 0), (-1, -1), primary),
                    ("PADDING", (0, 0), (-1, -1), 12),
                    ("ROUNDEDCORNERS", [8]),
                ]
            )
        )
        story.append(header_table)
        story.append(Spacer(1, 8 * mm))

        # Hotel Details + Invoice Info
        hotel_info = f"""
        <b>Blissful Abodes Chennai</b><br/>
        123 Marina Beach Road, Chennai<br/>
        Tamil Nadu - 600001, India<br/>
        Phone: +91 44 2345 6789<br/>
        Email: info@blissfulabodes.com<br/>
        <b>GSTIN: 33AAACB1234F1Z5</b><br/>
        HSN Code: 9963 (Accommodation Services)
        """

        invoice_info = f"""
        <b>TAX INVOICE</b><br/>
        Invoice No: {invoice_number}<br/>
        Date: {datetime.now().strftime('%d-%m-%Y')}<br/>
        Booking ID: #{booking_data.get('booking_id', 'N/A')}<br/>
        Status: <b>PAID</b>
        """

        info_data = [
            [
                Paragraph(hotel_info, normal_style),
                Paragraph(
                    invoice_info,
                    ParagraphStyle(
                        "right",
                        fontName="Helvetica",
                        fontSize=9,
                        leading=14,
                        alignment=TA_RIGHT,
                    ),
                ),
            ]
        ]
        info_table = Table(info_data, colWidths=[90 * mm, 90 * mm])
        info_table.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "TOP")]))
        story.append(info_table)
        story.append(Spacer(1, 5 * mm))
        story.append(HRFlowable(width="100%", thickness=1, color=primary))
        story.append(Spacer(1, 5 * mm))

        # Guest Details
        guest_details = f"""
        <b>Guest Details:</b><br/>
        Name: {user_data.get('first_name', '')} {user_data.get('last_name', '')}<br/>
        Email: {user_data.get('email', 'N/A')}<br/>
        Phone: {user_data.get('phone', 'N/A')}<br/>
        Guests: {booking_data.get('num_guests', 1)}
        """
        story.append(Paragraph(guest_details, normal_style))
        story.append(Spacer(1, 5 * mm))

        # Booking Details Table
        check_in = booking_data.get("check_in", "N/A")
        check_out = booking_data.get("check_out", "N/A")
        try:
            ci = datetime.strptime(check_in, "%Y-%m-%d")
            co = datetime.strptime(check_out, "%Y-%m-%d")
            nights = (co - ci).days
        except Exception:
            nights = 1

        booking_table_data = [
            ["#", "Description", "Rate/Night", "Nights", "Amount"],
            [
                "1",
                f"Room {booking_data.get('room_number', 'N/A')}\n{booking_data.get('room_type', 'N/A')} Room\nCheck-in: {check_in}\nCheck-out: {check_out}",
                f"₹{booking_data.get('base_amount', 0)/max(nights,1):,.0f}",
                str(nights),
                f"₹{booking_data.get('base_amount', 0):,.0f}",
            ],
        ]

        book_table = Table(
            booking_table_data, colWidths=[10 * mm, 85 * mm, 30 * mm, 20 * mm, 35 * mm]
        )
        book_table.setStyle(
            TableStyle(
                [
                    ("BACKGROUND", (0, 0), (-1, 0), primary),
                    ("TEXTCOLOR", (0, 0), (-1, 0), white),
                    ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                    ("FONTSIZE", (0, 0), (-1, -1), 9),
                    ("ALIGN", (2, 0), (-1, -1), "RIGHT"),
                    ("ROWBACKGROUNDS", (0, 1), (-1, -1), [white, grey]),
                    ("GRID", (0, 0), (-1, -1), 0.5, HexColor("#DDDDDD")),
                    ("PADDING", (0, 0), (-1, -1), 6),
                ]
            )
        )
        story.append(book_table)
        story.append(Spacer(1, 5 * mm))

        # GST Breakdown
        base = booking_data.get("base_amount", 0)
        discount = booking_data.get("discount_amount", 0)
        taxable = base - discount
        cgst = taxable * 0.09
        sgst = taxable * 0.09
        total = taxable + cgst + sgst

        gst_data = [
            ["", "Subtotal", f"₹{base:,.0f}"],
            ["", "Discount", f"-₹{discount:,.0f}"],
            ["", "Taxable Amount", f"₹{taxable:,.0f}"],
            ["", "CGST @ 9%", f"₹{cgst:,.0f}"],
            ["", "SGST @ 9%", f"₹{sgst:,.0f}"],
        ]

        gst_table = Table(gst_data, colWidths=[80 * mm, 60 * mm, 40 * mm])
        gst_table.setStyle(
            TableStyle(
                [
                    ("ALIGN", (1, 0), (2, -1), "RIGHT"),
                    ("FONTSIZE", (0, 0), (-1, -1), 9),
                    ("PADDING", (0, 0), (-1, -1), 5),
                ]
            )
        )
        story.append(gst_table)

        # Total
        total_data = [["", f"GRAND TOTAL", f"₹{total:,.0f}"]]
        total_table = Table(total_data, colWidths=[80 * mm, 60 * mm, 40 * mm])
        total_table.setStyle(
            TableStyle(
                [
                    ("BACKGROUND", (1, 0), (-1, 0), primary),
                    ("TEXTCOLOR", (1, 0), (-1, 0), white),
                    ("FONTNAME", (0, 0), (-1, -1), "Helvetica-Bold"),
                    ("FONTSIZE", (0, 0), (-1, -1), 11),
                    ("ALIGN", (1, 0), (2, 0), "RIGHT"),
                    ("PADDING", (0, 0), (-1, -1), 8),
                    ("ROUNDEDCORNERS", [4]),
                ]
            )
        )
        story.append(total_table)
        story.append(Spacer(1, 8 * mm))

        # Footer
        footer_text = """
        <b>Terms & Conditions:</b> Check-in time is 2:00 PM | Check-out time is 12:00 PM<br/>
        Cancellation within 24 hours: 100% refund | Within 48 hours: 50% refund<br/>
        For disputes, please contact: billing@blissfulabodes.com<br/>
        <br/>
        <i>This is a computer-generated invoice and does not require a physical signature.</i>
        """
        story.append(
            Paragraph(
                footer_text,
                ParagraphStyle(
                    "footer",
                    fontName="Helvetica",
                    fontSize=8,
                    textColor=HexColor("#888888"),
                    leading=14,
                ),
            )
        )

        doc.build(story)
        return filepath

    except ImportError:
        # Create a simple text invoice if reportlab not available
        with open(filepath.replace(".pdf", ".txt"), "w") as f:
            f.write(
                f"""
BLISSFUL ABODES CHENNAI
123 Marina Beach Road, Chennai - 600001
GSTIN: 33AAACB1234F1Z5
================================
TAX INVOICE: {invoice_number}
Date: {datetime.now().strftime('%d-%m-%Y')}
Booking ID: #{booking_data.get('booking_id')}
================================
Guest: {user_data.get('first_name')} {user_data.get('last_name')}
Room: {booking_data.get('room_number')} - {booking_data.get('room_type')}
Check-in:  {booking_data.get('check_in')} at 14:00
Check-out: {booking_data.get('check_out')} at 12:00
================================
Base Amount: Rs. {booking_data.get('base_amount', 0):,.0f}
CGST (9%): Rs. {booking_data.get('gst_amount', 0)/2:,.0f}
SGST (9%): Rs. {booking_data.get('gst_amount', 0)/2:,.0f}
TOTAL: Rs. {booking_data.get('total_amount', 0):,.0f}
================================
Thank you for staying with us!
            """
            )
        return filepath.replace(".pdf", ".txt")


def generate_booking_qr(booking_id):
    """Generate QR code for booking check-in"""
    os.makedirs("static/qr", exist_ok=True)

    qr_path = f"static/qr/{booking_id}.png"

    try:
        import qrcode

        url = f"http://localhost:5000/checkin/{booking_id}"
        qr = qrcode.QRCode(version=1, box_size=8, border=4)
        qr.add_data(url)
        qr.make(fit=True)
        img = qr.make_image(fill_color="#1A1A2E", back_color="white")
        img.save(qr_path)
    except ImportError:
        # Create placeholder
        with open(qr_path.replace(".png", ".txt"), "w") as f:
            f.write(f"QR Code for booking: {booking_id}")
        qr_path = qr_path.replace(".png", ".txt")

    return qr_path
