from reportlab.pdfgen import canvas
from io import BytesIO
from django.http import HttpResponse

def generate_certificate_pdf(certificate):
    buffer = BytesIO()
    p = canvas.Canvas(buffer)
    p.setTitle("Consultant Certificate")

    p.setFont("Helvetica-Bold", 16)
    p.drawString(150, 780, "Consultant Certificate")

    p.setFont("Helvetica", 12)
    p.drawString(100, 740, f"Consultant: {certificate.consultant.get_full_name()}")
    p.drawString(100, 720, f"Certificate No: {certificate.certificate_number}")
    p.drawString(100, 700, f"Issued On: {certificate.issued_on}")
    p.drawString(100, 680, f"Valid Until: {certificate.valid_until}")
    p.setFont("Helvetica-Oblique", 10)
    p.drawString(100, 650, f"Remarks: {certificate.remarks or 'N/A'}")
    p.showPage()
    p.save()
    buffer.seek(0)
    return HttpResponse(buffer, content_type='application/pdf')
