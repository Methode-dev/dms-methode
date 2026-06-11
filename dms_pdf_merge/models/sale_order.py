# License LGPL-3.0 or later (http://www.gnu.org/licenses/lgpl).
from odoo import _, api, fields, models
from odoo.exceptions import UserError


class SaleOrder(models.Model):
    _name = "sale.order"
    _inherit = ["sale.order", "pdf.merge.mixin"]

    pdf_merge_button_visible = fields.Boolean(
        compute="_compute_pdf_merge_button_visible"
    )

    def _compute_pdf_merge_button_visible(self):
        enabled = (
            self.env["ir.config_parameter"]
            .sudo()
            .get_param("dms_pdf_merge.enable_sale_order", "True")
            == "True"
        )
        for order in self:
            order.pdf_merge_button_visible = enabled

    # ------------------------------------------------------------------
    # PDF merge hooks
    # ------------------------------------------------------------------
    def _pdf_merge_report_action(self):
        return self.env.ref("sale.action_report_saleorder", raise_if_not_found=False)

    def _pdf_merge_source_dms_files(self):
        self.ensure_one()
        directories = (
            self.env["dms.directory"]
            .sudo()
            .search([("res_model", "=", "sale.order"), ("res_id", "=", self.id)])
        )
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
        """Store quotation merges under: <company storage> / Quotations /
        {quotation name}. Folders are created on demand."""
        self.ensure_one()
        storage = self._pdf_merge_company_storage(self.company_id)
        if not storage:
            raise UserError(
                _(
                    "No document storage is configured for company %s.",
                    self.company_id.display_name,
                )
            )
        root = self._pdf_merge_storage_root(storage)
        quotations = self._pdf_merge_find_or_create_dir("Quotations", storage, root)
        name = self._pdf_merge_safe_name(self.display_name) or _("Quotation %s", self.id)
        return self._pdf_merge_find_or_create_dir(
            name,
            storage,
            quotations,
            extra_vals={"res_model": "sale.order", "res_id": self.id},
        )
