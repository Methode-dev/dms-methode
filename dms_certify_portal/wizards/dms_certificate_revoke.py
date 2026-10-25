# -*- coding: utf-8 -*-
from odoo import _, api, fields, models
from odoo.exceptions import UserError


class DmsCertificateRevoke(models.TransientModel):
    """Ask for the reason before withdrawing a document.

    The reason is not paperwork: it is printed on the public refusal notice, so
    the agent reading it learns why a genuine-looking paper must be turned
    away. Revocation is irreversible, which is the other reason for the stop.

    Opened on one entry (the certificate form) or on several (a producing
    module's batch, see operations_certify): with several, each is listed,
    ticked, and whoever revokes unticks the ones to keep. One reason covers
    all of them.
    """

    _name = 'dms.certificate.revoke'
    _description = "Revoke a certified document"

    certificate_id = fields.Many2one(
        'dms.certificate', ondelete='cascade', readonly=True)
    reference = fields.Char(related='certificate_id.reference', readonly=True)
    # What may be revoked here, and what will be. Separate fields because the
    # checkbox list draws its options from the first and ticks the second.
    candidate_ids = fields.Many2many(
        'dms.certificate', 'dms_certificate_revoke_candidate_rel',
        'wizard_id', 'certificate_id', readonly=True)
    candidate_count = fields.Integer(compute='_compute_candidate_count')
    certificate_ids = fields.Many2many(
        'dms.certificate', 'dms_certificate_revoke_rel',
        'wizard_id', 'certificate_id', string="Documents to revoke")
    reason = fields.Char(
        string="Reason", required=True,
        help="Shown to whoever checks this document from now on.",
        default=lambda self: _("Movement cancelled by the vessel operator."))

    @api.depends('candidate_ids')
    def _compute_candidate_count(self):
        for wizard in self:
            wizard.candidate_count = len(wizard.candidate_ids)

    @api.model
    def default_get(self, fields_list):
        values = super().default_get(fields_list)
        context = self.env.context
        if context.get('active_model') == 'dms.certificate':
            ids = context.get('active_ids') or (
                [context['active_id']] if context.get('active_id') else [])
            candidates = self.env['dms.certificate'].browse(ids).filtered(
                lambda certificate: certificate.state != 'revoked')
            values.setdefault('certificate_id', candidates[:1].id)
            values.setdefault('candidate_ids', [(6, 0, candidates.ids)])
            values.setdefault('certificate_ids', [(6, 0, candidates.ids)])
        return values

    def action_revoke(self):
        self.ensure_one()
        # The ticked list once there was a list to tick, even emptied: falling
        # back to the first entry would revoke one somebody just unticked.
        # Only ever what the dialog offered: the ticked list is client data.
        targets = (self.certificate_ids & self.candidate_ids if self.candidate_ids
                   else self.certificate_id).filtered(
            lambda certificate: certificate.state != 'revoked')
        if not targets:
            raise UserError(_("Tick at least one document to revoke."))
        targets.action_revoke(reason=self.reason)
        return {'type': 'ir.actions.act_window_close'}
