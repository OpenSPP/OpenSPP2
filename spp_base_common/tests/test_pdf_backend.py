import io

from odoo.tests import TransactionCase
from odoo.tools.pdf import PdfFileReader, PdfFileWriter


class TestPdfBackend(TransactionCase):
    """Guard the PDF backend selected by odoo.tools.pdf.

    Printing a report for multiple records splits the combined document in
    ir.actions.report._render_qweb_pdf_prepare_streams using the legacy
    PyPDF2 1.x API (numPages, getPage, addPage). If the image ships legacy
    PyPDF2 3.x, odoo.tools.pdf selects it over pypdf and that API raises
    DeprecationError, so multi-record printing crashes while single-record
    printing still works (OP#1168).
    """

    def _make_two_page_pdf(self):
        from reportlab.pdfgen import canvas

        buffer = io.BytesIO()
        pdf_canvas = canvas.Canvas(buffer)
        pdf_canvas.drawString(100, 750, "page 1")
        pdf_canvas.showPage()
        pdf_canvas.drawString(100, 750, "page 2")
        pdf_canvas.showPage()
        pdf_canvas.save()
        buffer.seek(0)
        return buffer

    def test_01_multi_record_split_legacy_api(self):
        # Mirrors the multi-record path of _render_qweb_pdf_prepare_streams
        reader = PdfFileReader(self._make_two_page_pdf())
        self.assertEqual(reader.numPages, 2)
        for page_index in range(reader.numPages):
            writer = PdfFileWriter()
            writer.addPage(reader.getPage(page_index))
            stream = io.BytesIO()
            writer.write(stream)
            self.assertTrue(stream.getvalue().startswith(b"%PDF"))
