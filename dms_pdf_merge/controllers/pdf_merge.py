# License LGPL-3.0 or later (http://www.gnu.org/licenses/lgpl).
import base64
import io
import time

import fitz  # PyMuPDF
from PIL import Image

from odoo import http
from odoo.http import request


class DmsPdfMergeController(http.Controller):
    """Build a merged PDF for a Sale Order / Task from its report, chatter PDF
    attachments, existing DMS documents and ad-hoc uploads, then store it in
    the DMS."""

    SUPPORTED_MODELS = ("sale.order", "project.task")

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------
    def _pdf_to_pages(self, pdf_data, source_type, source_id=None, source_name=None):
        """Render a PDF (bytes) to a list of page dicts, each with a JPEG
        preview and the single-page PDF content (base64)."""
        pages = []
        pdf = fitz.open(stream=pdf_data, filetype="pdf")
        try:
            for i in range(len(pdf)):
                page = pdf.load_page(i)
                pix = page.get_pixmap(dpi=120, alpha=False)
                img_bytes = io.BytesIO()
                Image.frombytes("RGB", [pix.width, pix.height], pix.samples).save(
                    img_bytes, format="JPEG", quality=85
                )
                img_b64 = base64.b64encode(img_bytes.getvalue()).decode()

                single = fitz.open()
                single.insert_pdf(pdf, from_page=i, to_page=i)
                content = base64.b64encode(single.tobytes()).decode()
                single.close()

                pages.append(
                    {
                        "type": source_type,
                        "id": "%s_%s_%s" % (source_type, source_id or "report", i),
                        "source_id": source_id,
                        "name": source_name or "Report",
                        "page_number": i + 1,
                        "preview_url": "data:image/jpeg;base64,%s" % img_b64,
                        "content": content,
                    }
                )
        finally:
            pdf.close()
        return pages

    def _get_record(self, model, res_id):
        if model not in self.SUPPORTED_MODELS:
            return None
        record = request.env[model].browse(int(res_id))
        return record if record.exists() else None

    # ------------------------------------------------------------------
    # Routes
    # ------------------------------------------------------------------
    @http.route("/dms_pdf_merge/load_data", type="jsonrpc", auth="user")
    def load_data(self, model, res_id, **kwargs):
        try:
            record = self._get_record(model, res_id)
            if not record:
                return {"error": "Record not found"}

            result = {
                "pages": [],
                "record_name": record.display_name,
                "default_filename": record._pdf_merge_default_filename(),
            }

            # 1. The record's printable report (e.g. the quotation report).
            report_action = record._pdf_merge_report_action()
            if report_action:
                try:
                    pdf_content, _dummy = request.env[
                        "ir.actions.report"
                    ].sudo()._render_qweb_pdf(report_action, [record.id])
                    result["pages"].extend(
                        self._pdf_to_pages(
                            pdf_content,
                            source_type="report",
                            source_name="%s - Report" % record.display_name,
                        )
                    )
                except Exception as error:  # noqa: BLE001
                    result["report_error"] = str(error)

            # 2. PDF attachments from the chatter.
            attachments = request.env["ir.attachment"].search(
                [
                    ("res_model", "=", model),
                    ("res_id", "=", int(res_id)),
                    ("mimetype", "=", "application/pdf"),
                ],
                order="create_date asc",
            )
            for attachment in attachments:
                try:
                    result["pages"].extend(
                        self._pdf_to_pages(
                            base64.b64decode(attachment.datas),
                            source_type="attachment",
                            source_id=attachment.id,
                            source_name=attachment.name,
                        )
                    )
                except Exception:  # noqa: BLE001
                    continue

            # 3. PDFs already stored in the record's DMS folder(s).
            for dms_file in record._pdf_merge_source_dms_files():
                try:
                    result["pages"].extend(
                        self._pdf_to_pages(
                            base64.b64decode(dms_file.content),
                            source_type="dms",
                            source_id=dms_file.id,
                            source_name=dms_file.name,
                        )
                    )
                except Exception:  # noqa: BLE001
                    continue

            return result
        except Exception as error:  # noqa: BLE001
            return {"error": "Error loading data: %s" % error}

    @http.route("/dms_pdf_merge/process_uploaded_file", type="jsonrpc", auth="user")
    def process_uploaded_file(self, file_content, start_page=1, **kwargs):
        try:
            pdf = fitz.open(stream=base64.b64decode(file_content), filetype="pdf")
            pages = []
            stamp = int(time.time())
            for i in range(len(pdf)):
                page = pdf.load_page(i)
                pix = page.get_pixmap(dpi=120, alpha=False)
                img_bytes = io.BytesIO()
                Image.frombytes("RGB", [pix.width, pix.height], pix.samples).save(
                    img_bytes, format="JPEG", quality=85
                )
                img_b64 = base64.b64encode(img_bytes.getvalue()).decode()

                single = fitz.open()
                single.insert_pdf(pdf, from_page=i, to_page=i)
                content = base64.b64encode(single.tobytes()).decode()
                single.close()

                pages.append(
                    {
                        "type": "uploaded",
                        "id": "uploaded_%s_%s" % (stamp, i),
                        "page_number": start_page + i,
                        "preview_url": "data:image/jpeg;base64,%s" % img_b64,
                        "content": content,
                    }
                )
            pdf.close()
            return {"pages": pages}
        except Exception as error:  # noqa: BLE001
            return {"error": "Error processing uploaded file: %s" % error}

    @http.route("/dms_pdf_merge/save", type="jsonrpc", auth="user")
    def save(self, model, res_id, pages, filename=None, **kwargs):
        try:
            record = self._get_record(model, res_id)
            if not record:
                return {"success": False, "error": "Record not found"}
            if not pages:
                return {"success": False, "error": "No page selected"}

            output = fitz.open()
            try:
                for page in pages:
                    content = page.get("content")
                    if not content:
                        return {
                            "success": False,
                            "error": "Missing content for a page",
                        }
                    src = fitz.open(stream=base64.b64decode(content), filetype="pdf")
                    output.insert_pdf(src)
                    src.close()
                merged_bytes = output.tobytes()
            finally:
                output.close()

            dms_file = record._pdf_merge_store(filename, merged_bytes)
            return {
                "success": True,
                "file_id": dms_file.id,
                "directory_name": dms_file.directory_id.complete_name,
                "filename": dms_file.name,
            }
        except Exception as error:  # noqa: BLE001
            return {"success": False, "error": str(error)}
