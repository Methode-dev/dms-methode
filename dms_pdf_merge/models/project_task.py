# License LGPL-3.0 or later (http://www.gnu.org/licenses/lgpl).
from odoo import _, fields, models
from odoo.exceptions import UserError


class ProjectTask(models.Model):
    _name = "project.task"
    _inherit = ["project.task", "pdf.merge.mixin"]

    pdf_merge_button_visible = fields.Boolean(
        compute="_compute_pdf_merge_button_visible"
    )

    def _compute_pdf_merge_button_visible(self):
        enabled = (
            self.env["ir.config_parameter"]
            .sudo()
            .get_param("dms_pdf_merge.enable_task", "True")
            == "True"
        )
        for task in self:
            # Only parent (main) tasks.
            task.pdf_merge_button_visible = enabled and not task.parent_id

    # ------------------------------------------------------------------
    # PDF merge hooks
    # ------------------------------------------------------------------
    def _pdf_merge_source_dms_files(self):
        self.ensure_one()
        directories = self.dms_directory_ids
        if not directories:
            return self.env["dms.file"]
        return (
            self.env["dms.file"]
            .sudo()
            .search(
                [
                    ("directory_id", "child_of", directories.ids),
                    ("mimetype", "=", "application/pdf"),
                ]
            )
        )

    def _pdf_merge_get_directory(self):
        """Store task merges in the task's own DMS folder, creating it if it
        does not exist yet."""
        self.ensure_one()
        directory = self.dms_directory_ids[:1]
        if not directory:
            self._ensure_dms_directory()
            directory = self.dms_directory_ids[:1]
        if not directory:
            raise UserError(_("No document folder could be created for this task."))
        return directory
