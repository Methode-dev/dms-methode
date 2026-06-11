# License LGPL-3.0 or later (http://www.gnu.org/licenses/lgpl).
import re

from odoo import _, api, models
from odoo.exceptions import UserError


class PdfMergeMixin(models.AbstractModel):
    """Shared behaviour for records that can build a merged PDF and store it in
    the DMS (currently sale.order and project.task)."""

    _name = "pdf.merge.mixin"
    _description = "PDF Merge Mixin"

    # ------------------------------------------------------------------
    # Entry point (shared): open the merge wizard for this record.
    # ------------------------------------------------------------------
    def action_open_pdf_merge(self):
        self.ensure_one()
        return {
            "type": "ir.actions.client",
            "tag": "dms_pdf_merge_dialog",
            "target": "new",
            "props": {
                "model": self._name,
                "resId": self.id,
            },
        }

    # ------------------------------------------------------------------
    # Hooks to be implemented by each model.
    # ------------------------------------------------------------------
    def _pdf_merge_get_directory(self):
        """Return (and create if needed) the dms.directory where the merged
        PDF must be stored."""
        raise NotImplementedError()

    def _pdf_merge_report_action(self):
        """Return the ir.actions.report record to include as the first source,
        or an empty recordset / False when the model has no printable report."""
        return False

    def _pdf_merge_source_dms_files(self):
        """Return the dms.file records (PDFs) already stored for this record,
        offered as merge sources. Empty recordset by default."""
        return self.env["dms.file"]

    def _pdf_merge_default_filename(self):
        self.ensure_one()
        return "%s.pdf" % (self._pdf_merge_safe_name(self.display_name) or "document")

    # ------------------------------------------------------------------
    # DMS directory helpers (kept self-contained on purpose).
    # ------------------------------------------------------------------
    @api.model
    def _pdf_merge_safe_name(self, name):
        """Return a name valid as a DMS directory/file name
        (see dms.directory._check_name): no path separators or NUL."""
        return re.sub(r"[\\/\x00]+", "-", name or "").strip()

    def _pdf_merge_company_storage(self, company):
        """The (non-attachment) DMS storage that belongs to ``company``."""
        return (
            self.env["dms.storage"]
            .sudo()
            .search(
                [
                    ("company_id", "=", company.id),
                    ("save_type", "!=", "attachment"),
                ],
                order="id",
                limit=1,
            )
        )

    def _pdf_merge_storage_root(self, storage):
        """The storage's main root directory (e.g. 'All Documents'), or empty."""
        return (
            self.env["dms.directory"]
            .sudo()
            .search(
                [
                    ("storage_id", "=", storage.id),
                    ("is_root_directory", "=", True),
                ],
                order="id",
                limit=1,
            )
        )

    def _pdf_merge_find_or_create_dir(self, name, storage, parent, extra_vals=None):
        """Find or create a directory ``name`` under ``parent`` (or at the
        storage root when ``parent`` is empty). New directories inherit the
        parent's access groups."""
        Directory = self.env["dms.directory"].sudo()
        domain = [("storage_id", "=", storage.id), ("name", "=", name)]
        domain += (
            [("parent_id", "=", parent.id)]
            if parent
            else [("is_root_directory", "=", True)]
        )
        existing = Directory.search(domain, limit=1)
        if existing:
            return existing
        vals = {"name": name, "storage_id": storage.id}
        if parent:
            vals.update({"parent_id": parent.id, "inherit_group_ids": True})
        else:
            vals.update({"is_root_directory": True, "inherit_group_ids": False})
        if extra_vals:
            vals.update(extra_vals)
        return Directory.create(vals)

    # ------------------------------------------------------------------
    # Storage of the merged file.
    # ------------------------------------------------------------------
    def _pdf_merge_store(self, filename, pdf_bytes):
        """Create a dms.file with the merged ``pdf_bytes`` in this record's
        target directory and return it."""
        import base64

        self.ensure_one()
        directory = self._pdf_merge_get_directory()
        if not directory:
            raise UserError(_("No document folder could be resolved for this record."))
        name = self._pdf_merge_safe_name(filename) or self._pdf_merge_default_filename()
        if not name.lower().endswith(".pdf"):
            name += ".pdf"
        # Created with elevated rights: access is gated by the user's access to
        # the source record (Sale Order / Task), and the folders inherit the
        # company's document access groups.
        return (
            self.env["dms.file"]
            .sudo()
            .create(
                {
                    "name": name,
                    "content": base64.b64encode(pdf_bytes),
                    "directory_id": directory.id,
                }
            )
        )
