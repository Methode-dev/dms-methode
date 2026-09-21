# -*- coding: utf-8 -*-
from odoo import _, api, fields, models


class DmsCertificateRevoke(models.TransientModel):
    """Ask for the reason before withdrawing a document.

    The reason is not paperwork: it is printed on the public refusal notice, so
    the agent reading it learns why a genuine-looking paper must be turned
    away. Revocation is irreversible, which is the other reason for the stop.
    """

    _name = 'dms.certificate.revoke'
    _description = "Revoke a certified document"

    certificate_id = fields.Many2one(
        'dms.certificate', required=True, ondelete='cascade', readonly=True)
    reference = fields.Char(related='certificate_id.reference', readonly=True)
    reason = fields.Char(
        string="Reason", required=True,
        help="Shown to whoever checks this document from now on.",
        default=lambda self: _("Movement cancelled by the vessel operator."))

    @api.model
    def default_get(self, fields_list):
        values = super().default_get(fields_list)
        if self.env.context.get('active_model') == 'dms.certificate':
            values.setdefault('certificate_id', self.env.context.get('active_id'))
        return values

    def action_revoke(self):
        self.ensure_one()
        self.certificate_id.action_revoke(reason=self.reason)
        return {'type': 'ir.actions.act_window_close'}
