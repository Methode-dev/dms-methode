# License LGPL-3.0 or later (http://www.gnu.org/licenses/lgpl).
from odoo import fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = "res.config.settings"

    pdf_merge_on_sale_order = fields.Boolean(
        string="PDF Merge on Quotations / Sales Orders",
        help="Show the 'Merge PDF' button on the Sales Order form.",
        config_parameter="dms_pdf_merge.enable_sale_order",
        default=True,
    )
    pdf_merge_on_task = fields.Boolean(
        string="PDF Merge on Tasks",
        help="Show the 'Merge PDF' button on the (parent) Task form.",
        config_parameter="dms_pdf_merge.enable_task",
        default=True,
    )
