# -*- coding: utf-8 -*-
from odoo import fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    # -- throttling ---------------------------------------------------------
    certify_max_failures = fields.Integer(
        string="Failed attempts allowed per address",
        config_parameter='dms_certify_portal.max_failures', default=10)
    certify_window_minutes = fields.Integer(
        string="Rate limit window (minutes)",
        config_parameter='dms_certify_portal.window_minutes', default=15)
    certify_max_reference_failures = fields.Integer(
        string="Failed attempts allowed per reference",
        config_parameter='dms_certify_portal.max_reference_failures', default=5,
        help="Counted across every address. This is the limit that actually "
             "protects a document when the second check is only four "
             "characters long.")
    certify_reference_lock_minutes = fields.Integer(
        string="Reference lockout (minutes)",
        config_parameter='dms_certify_portal.reference_lock_minutes', default=30)
    certify_session_minutes = fields.Integer(
        string="Result page lifetime (minutes)",
        config_parameter='dms_certify_portal.session_minutes', default=15,
        help="How long a result stays readable after a successful lookup. "
             "Keep it short: embassy workstations are shared.")
    certify_retention_days = fields.Integer(
        string="Keep attempt logs for (days)",
        config_parameter='dms_certify_portal.retention_days', default=90)

    # -- what the portal does -----------------------------------------------
    certify_hide_expired = fields.Boolean(
        string="Hide expired documents",
        config_parameter='dms_certify_portal.hide_expired',
        help="When off, an expired document is reported as genuine but out of "
             "date. When on it reads as 'no match', which shrinks the "
             "searchable set but can make an agent reject a real holder.")
    certify_allow_download = fields.Boolean(
        string="Allow downloading the sealed document",
        config_parameter='dms_certify_portal.allow_download', default=True)
    certify_portal_company_id = fields.Many2one(
        'res.company', string="Portal company",
        config_parameter='dms_certify_portal.company_id',
        help="Whose name, address and contact details the public page carries. "
             "An embassy is looking at one organisation, whichever company "
             "issued the document they are checking. Leave empty to use the "
             "company the request resolves to.")
    certify_public_base_url = fields.Char(
        string="Public verification URL",
        config_parameter='dms_certify_portal.public_base_url',
        help="Printed on every document and encoded in its QR code, so it "
             "stays in circulation for months. Leave empty to use this "
             "instance's own address.")

    # -- what gets registered automatically ----------------------------------
    # Not a config parameter: the flag lives on the type itself, so a producing
    # module can ship a sensible default with its type and an administrator can
    # change it here without either side knowing about the other.
    #
    # A plain field filled by get_values(), not a computed one. A non-stored
    # compute recomputes when the cache is invalidated — which happens between
    # the client saving the record and set_values() reading it back, so an
    # unticked box was recomputed straight back to ticked before anything was
    # written.
    certify_auto_stamp_type_ids = fields.Many2many(
        'dms.certificate.type', string="Stamp on generation",
        help="Documents of these kinds are registered for verification the "
             "moment a producing module generates them, as drafts. Sealing "
             "stays a separate, deliberate act.")

    # -- defaults for a new certificate -------------------------------------
    certify_second_factor = fields.Selection(
        [('ppt4', "Last 4 characters of a listed passport"),
         ('pptfull', "Full passport number"),
         ('dob', "Date of birth of a listed person")],
        string="Default second check",
        config_parameter='dms_certify_portal.second_factor', default='ppt4')
    certify_disclosure = fields.Selection(
        [('confirm', "Match confirmation, crew lines redacted"),
         ('full', "The full page as issued")],
        string="Default disclosure",
        config_parameter='dms_certify_portal.disclosure', default='confirm')
    certify_validity_days = fields.Selection(
        [('30', "30 days after movement"),
         ('90', "90 days after movement"),
         ('0', "Until revoked")],
        string="Default validity",
        config_parameter='dms_certify_portal.validity_days', default='90')
    certify_reference_prefix = fields.Char(
        string="Reference prefix",
        config_parameter='dms_certify_portal.reference_prefix', default='ICS')
    certify_notify_on_lookup = fields.Boolean(
        string="Notify the desk on every lookup",
        config_parameter='dms_certify_portal.notify_on_lookup', default=True)

    # -- the seal -----------------------------------------------------------
    # Per document the issuer picks a marking and sees the result; everything
    # below is the house style and is set once, here.
    certify_seal_opacity = fields.Integer(
        string="Watermark opacity (%)",
        config_parameter='dms_certify_portal.seal_opacity', default=9)
    certify_seal_angle = fields.Integer(
        string="Watermark angle",
        config_parameter='dms_certify_portal.seal_angle', default=-32)
    certify_seal_size = fields.Integer(
        string="Watermark size",
        config_parameter='dms_certify_portal.seal_size', default=24)
    certify_seal_mode = fields.Selection(
        [('tile', "Tiled across the page"),
         ('single', "One diagonal band")],
        string="Watermark coverage",
        config_parameter='dms_certify_portal.seal_mode', default='tile')
    certify_seal_color = fields.Char(
        string="Watermark ink",
        config_parameter='dms_certify_portal.seal_color', default='#10314F')
    certify_seal_guilloche = fields.Boolean(
        string="Guilloche border",
        config_parameter='dms_certify_portal.seal_guilloche', default=True,
        help="Engraved line pattern around the page. It moirés on a photocopy.")
    certify_seal_microtext = fields.Boolean(
        string="Microtext line in the footer",
        config_parameter='dms_certify_portal.seal_microtext', default=True,
        help="Repeats the reference at 1 pt. Legible under a loupe, a grey "
             "smear once scanned.")
    certify_seal_qr_corner = fields.Selection(
        [('br', "Bottom right, next to the signature"),
         ('bl', "Bottom left")],
        string="Stamp position",
        config_parameter='dms_certify_portal.seal_qr_corner', default='br')
    certify_seal_band = fields.Selection(
        [('auto', "Only when the corner is taken"),
         ('scale', "Always"),
         ('overlay', "Never — stamp over the page")],
        string="Make room for the stamp",
        config_parameter='dms_certify_portal.seal_band', default='auto',
        help="Sealing cannot reflow a page. When the stamp's corner is already "
             "occupied, the page can be shrunk slightly to free a strip for it; "
             "'Only when the corner is taken' keeps most documents at their "
             "exact size and protects the rest.")

    def get_values(self):
        values = super().get_values()
        values['certify_auto_stamp_type_ids'] = [(6, 0, self.env[
            'dms.certificate.type'].with_context(active_test=False).search(
                [('auto_stamp', '=', True)]).ids)]
        return values

    def set_values(self):
        super().set_values()
        Type = self.env['dms.certificate.type'].sudo().with_context(
            active_test=False)
        chosen = self.certify_auto_stamp_type_ids
        every = Type.search([])
        (every - chosen).filtered('auto_stamp').auto_stamp = False
        chosen.filtered(lambda kind: not kind.auto_stamp).auto_stamp = True
