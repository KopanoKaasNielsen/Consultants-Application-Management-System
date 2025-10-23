import os

from django.conf import settings
from django.http import HttpResponse
from reportlab.graphics import renderPDF
from reportlab.graphics.barcode import qr
from reportlab.lib.pagesizes import letter
from reportlab.lib.units import inch
from reportlab.pdfgen import canvas
from io import BytesIO


def generate_certificate_pdf(certificate):
    buffer = BytesIO()
    p = canvas.Canvas(buffer, pagesize=letter)
    p.setTitle("Consultant Certificate")

    width, height = letter
    margin = inch
    text_y = height - margin

    p.setFont("Helvetica-Bold", 16)
    p.drawCentredString(width / 2, text_y, "Consultant Certificate")

    text_y -= 0.5 * inch
    p.setFont("Helvetica", 12)
    p.drawString(margin, text_y, f"Consultant: {certificate.consultant.get_full_name()}")

    text_y -= 0.25 * inch
    p.drawString(margin, text_y, f"Certificate No: {certificate.certificate_number}")

    text_y -= 0.25 * inch
    p.drawString(margin, text_y, f"Issued On: {certificate.issued_on}")

    text_y -= 0.25 * inch
    p.drawString(margin, text_y, f"Valid Until: {certificate.valid_until}")

    text_y -= 0.35 * inch
    p.setFont("Helvetica-Oblique", 10)
    p.drawString(margin, text_y, f"Remarks: {certificate.remarks or 'N/A'}")

    # Signature block
    signature_path = os.path.join(settings.BASE_DIR, "static", "img", "signature.png")
    signature_y = margin + 1.2 * inch
    if os.path.exists(signature_path):
        signature_width = 140
        p.drawImage(
            signature_path,
            margin,
            signature_y,
            width=signature_width,
            preserveAspectRatio=True,
        )
    p.setFont("Helvetica", 10)
    p.drawString(margin, signature_y - 0.2 * inch, "Authorized Officer Signature")
    p.line(margin, signature_y - 0.25 * inch, margin + 2.5 * inch, signature_y - 0.25 * inch)

    # QR code block
    verify_url = (
        f"https://consultant-app.gov.bw/verify/{certificate.certificate_number}"
    )
    qr_code = qr.QrCodeWidget(verify_url)
    bounds = qr_code.getBounds()
    qr_size = 1.6 * inch
    width_qr = bounds[2] - bounds[0]
    height_qr = bounds[3] - bounds[1]
    drawing = qr_code.draw()
    drawing.scale(qr_size / width_qr, qr_size / height_qr)
    renderPDF.draw(drawing, p, width - margin - qr_size, margin)
    p.setFont("Helvetica", 8)
    p.drawCentredString(width - margin - (qr_size / 2), margin - 0.15 * inch, "Scan to Verify")

    p.showPage()
    p.save()
    buffer.seek(0)
    response = HttpResponse(buffer.getvalue(), content_type='application/pdf')
    response['Content-Disposition'] = (
        f"attachment; filename=certificate_{certificate.certificate_number}.pdf"
    )
    return response
