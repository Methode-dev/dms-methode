# -*- coding: utf-8 -*-
import base64
import hmac
import json
import logging
import re
import secrets
from datetime import timedelta

from markupsafe import Markup

from odoo import _, api, fields, models
from odoo.exceptions import UserError, ValidationError

from ..tools import seal as sealing

_logger = logging.getLogger(__name__)

# Crockford base32: no I, L, O or U. Agents retype these from a printed page
# that has often been scanned or faxed, and the public page tells them in so
# many words that those four letters are never used — so this alphabet and
# that sentence have to stay in step.
REFERENCE_ALPHABET = '0123456789ABCDEFGHJKMNPQRSTVWXYZ'
REFERENCE_GROUPS = (4, 2)

SEAL_MARKINGS = {
    'certified': 'CERTIFIED ORIGINAL',
    'embassy': 'FOR EMBASSY SUBMISSION',
    'copy': 'COPY — NOT FOR BOARDING',
    'void': 'VOID',
}

# States in which a document is a real, issued thing the portal will speak
# about. 'draft' is deliberately absent: an unsealed document has no printed
# reference, so nobody can be holding one.
LIVE_STATES = ('certified', 'delivered', 'revoked')

# What the public page is rasterised at. Measured, not guessed: the stamp's QR
# is 18 mm square and a version-4/5 code needs roughly 3 pixels per module to
# decode. At 110 dpi that came to 2.0-2.2 px/module — unscannable. 200 dpi
# gives 3.6-4.1 and costs about 460 KB for a dense A4 page, which a lookup pays
# once.
PUBLIC_PAGE_DPI = 200


class DmsCertificate(models.Model):
    """A document that can be verified anonymously from the public portal.

    This is not the document. It is a thin, verifiable projection of a file
    that lives elsewhere, holding only what the public page is allowed to show
    plus the artifacts the portal serves. Keeping it separate is what stops a
    bug in a QWeb template walking from the portal into business records.

    A document is sealed, not re-rendered: see ``tools/seal.py``. The source
    file stays exactly where it was produced and is never modified; the sealed
    copy and the redacted copy are attachments owned by this record.
    """

    _name = 'dms.certificate'
    _description = "Verifiable Certificate"
    # The thread lives here rather than on the document the certificate stands
    # for: certification is what the desk is being told about, and a producing
    # module can always mirror a message onto its own record.
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'create_date desc, id desc'
    _rec_name = 'reference'

    _reference_unique = models.Constraint(
        'UNIQUE(reference_key)',
        "This certificate reference already exists.",
    )

    # -- identification -----------------------------------------------------
    reference = fields.Char(
        string="Reference", required=True, copy=False, index=True, readonly=True,
        default=lambda self: self._generate_reference(),
        help="Printed on the document beside the QR code. High-entropy on "
             "purpose: a guessable reference would leave the second check as "
             "the only secret.")
    reference_key = fields.Char(
        compute='_compute_reference_key', store=True, index=True, copy=False,
        help="The reference with its separators stripped. What a lookup "
             "matches on, so spacing and dashes never decide the outcome.")

    # -- lifecycle ----------------------------------------------------------
    state = fields.Selection(
        [('draft', "Draft"),
         ('certified', "Certified"),
         ('delivered', "Delivered"),
         ('revoked', "Revoked")],
        string="Status", default='draft', required=True, copy=False, index=True,
        tracking=True)
    public_state = fields.Selection(
        [('valid', "Valid"),
         ('expired', "Expired"),
         ('revoked', "Revoked"),
         ('unpublished', "Not issued")],
        string="Shown as", compute='_compute_public_state',
        help="What the public page reports for this entry.")

    # -- who it names -------------------------------------------------------
    holder_ids = fields.One2many(
        'dms.certificate.holder', 'certificate_id', string="Listed people")
    holder_count = fields.Integer(compute='_compute_holder_count')

    # -- how it opens -------------------------------------------------------
    second_factor = fields.Selection(
        [('ppt4', "Last 4 characters of a listed passport"),
         ('pptfull', "Full passport number"),
         ('dob', "Date of birth of a listed person")],
        string="Second check", required=True, tracking=True,
        default=lambda self: self._default_param('second_factor', 'ppt4'),
        help="The reference alone never opens a document. This is what is "
             "asked for alongside it, and it cannot be switched off.")
    disclosure = fields.Selection(
        [('confirm', "Match confirmation, crew lines redacted"),
         ('full', "The full page as issued")],
        string="Portal shows", required=True, tracking=True,
        default=lambda self: self._default_param('disclosure', 'confirm'))

    # -- validity -----------------------------------------------------------
    movement_date = fields.Date(
        string="Movement date",
        help="The date the document is about. Validity is counted from here.")
    validity_days = fields.Selection(
        [('30', "30 days after movement"),
         ('90', "90 days after movement"),
         ('0', "Until revoked")],
        string="Valid for", required=True,
        default=lambda self: self._default_param('validity_days', '90'))
    valid_until = fields.Date(
        string="Valid until", compute='_compute_valid_until', store=True,
        help="Past this date the portal reports the document as authentic but "
             "out of date, which is more useful to an embassy than silence.")

    # -- the seal -----------------------------------------------------------
    seal_marking = fields.Selection(
        [('certified', "Certified original"),
         ('embassy', "For embassy submission"),
         ('copy', "Copy — not for boarding"),
         ('void', "Void / cancelled"),
         ('custom', "Custom text")],
        string="Marking", required=True, default='certified', tracking=True)
    seal_text = fields.Char(
        string="Marking text", compute='_compute_seal_text',
        store=True, readonly=False,
        help="What the diagonal watermark says. Follows the marking unless you "
             "type your own.")

    # -- fingerprints -------------------------------------------------------
    source_hash = fields.Char(
        string="Document fingerprint", readonly=True, copy=False,
        help="SHA-256 of the document as produced, before the seal was applied "
             "— a file cannot carry its own hash. This is the value "
             "printed on the page.")
    sealed_hash = fields.Char(
        string="Sealed file fingerprint", readonly=True, copy=False,
        help="SHA-256 of the sealed file the portal serves.")

    # -- artifacts ----------------------------------------------------------
    # The source is whatever the producing module points us at and is never
    # written to. Everything else is ours.
    source_attachment_id = fields.Many2one(
        'ir.attachment', string="Source document", copy=False,
        ondelete='set null',
        # Real documents only. Without this the picker fills up with the
        # internal attachments Odoo keeps behind binary fields — including the
        # ones holding a dms.file's own content, and the sealed copies this
        # module produces, neither of which is a source anybody means to pick.
        domain=[('res_field', '=', False),
                ('res_model', '!=', 'dms.certificate')],
        help="The document to seal. A producing module normally overrides "
             "_certify_source() and points this at its own storage instead.")
    sealed_attachment_id = fields.Many2one(
        'ir.attachment', string="Sealed document", copy=False,
        ondelete='set null', readonly=True)

    # -- what the portal says about it --------------------------------------
    # No default. This module ships no document types of its own: what a
    # document *is* comes from whoever produces it, and a generic fallback
    # would only fill the registry — and the public page — with "Other".
    type_id = fields.Many2one(
        'dms.certificate.type', string="Type", required=True, index=True,
        ondelete='restrict')
    type_code = fields.Char(related='type_id.code', string="Type code", store=True)
    facts_json = fields.Text(
        string="Public facts", default='[]',
        help="A JSON list of {label, value} the verification page prints under "
             "'Voyage'. Written by the producing module so the vocabulary of a "
             "port call never has to live in this module.")

    issuer_id = fields.Many2one(
        'res.users', string="Issued by", copy=False, readonly=True,
        default=lambda self: self.env.user)
    issued_on = fields.Datetime(string="Issued on", copy=False, readonly=True)
    company_id = fields.Many2one(
        'res.company', string="Company", required=True, index=True,
        default=lambda self: self.env.company)

    notify_on_lookup = fields.Boolean(
        string="Notify on every lookup",
        default=lambda self: self._default_param('notify_on_lookup', '1') == '1',
        help="Post every verification back to the issuing desk, not only the "
             "failures.")

    # -- revocation ---------------------------------------------------------
    revoke_reason = fields.Char(string="Revocation reason", copy=False)
    revoked_on = fields.Datetime(string="Revoked on", copy=False, readonly=True)
    revoked_uid = fields.Many2one(
        'res.users', string="Revoked by", copy=False, readonly=True)

    # -- link back and audit ------------------------------------------------
    res_model = fields.Char(string="Source model", index=True, copy=False)
    res_id = fields.Many2oneReference(
        string="Source record", model_field='res_model', index=True, copy=False)
    attempt_ids = fields.One2many(
        'dms.certificate.attempt', 'document_id', string="Lookups")
    verify_count = fields.Integer(string="Successful lookups", readonly=True, copy=False)
    last_verified_on = fields.Datetime(string="Last lookup", readonly=True, copy=False)

    verify_url = fields.Char(string="Verification URL", compute='_compute_verify_url')

    # -- the preview --------------------------------------------------------
    # The sealed document itself, not a picture of it. pdf.js then renders it
    # as vectors, with its own zoom and paging — so the marking is judged on a
    # page that stays sharp at any magnification, which a rasterised preview
    # cannot do.
    #
    # Deliberately the opposite choice to the public page, which *is*
    # rasterised: there the point is that the reader gets no viewer of their
    # own. Here the reader is the operator, and the viewer is what they need.
    preview_pdf = fields.Binary(
        string="Stamped output", compute='_compute_preview_pdf',
        attachment=False, readonly=True)

    # ------------------------------------------------------------------
    # Defaults and selections
    # ------------------------------------------------------------------
    @api.model
    def _default_param(self, name, fallback):
        return self.env['ir.config_parameter'].sudo().get_param(
            'dms_certify_portal.%s' % name, fallback)

    # ------------------------------------------------------------------
    # Computes
    # ------------------------------------------------------------------
    @api.depends('reference')
    def _compute_reference_key(self):
        for record in self:
            record.reference_key = self._normalize_reference(record.reference)

    @api.depends('holder_ids')
    def _compute_holder_count(self):
        for record in self:
            record.holder_count = len(record.holder_ids)

    @api.depends('movement_date', 'validity_days')
    def _compute_valid_until(self):
        for record in self:
            days = int(record.validity_days or 0)
            if days and record.movement_date:
                record.valid_until = record.movement_date + timedelta(days=days)
            else:
                record.valid_until = False

    @api.depends('seal_marking')
    def _compute_seal_text(self):
        for record in self:
            if record.seal_marking == 'custom':
                record.seal_text = record.seal_text or ''
            else:
                record.seal_text = SEAL_MARKINGS.get(record.seal_marking, '')

    @api.depends('state', 'valid_until')
    def _compute_public_state(self):
        today = fields.Date.context_today(self)
        for record in self:
            if record.state == 'revoked':
                record.public_state = 'revoked'
            elif record.state not in LIVE_STATES:
                record.public_state = 'unpublished'
            elif record.valid_until and record.valid_until < today:
                record.public_state = 'expired'
            else:
                record.public_state = 'valid'

    def _compute_verify_url(self):
        base = self._public_base_url()
        for record in self:
            record.verify_url = '%s/verify/d/%s' % (base, record.reference)

    @api.model
    def _public_base_url(self):
        """Where the printed URL points.

        Its own parameter rather than ``web.base.url``: the address an embassy
        types is printed on paper that stays in circulation for months, so it
        has to be able to differ from wherever this Odoo happens to answer.
        """
        icp = self.env['ir.config_parameter'].sudo()
        base = icp.get_param('dms_certify_portal.public_base_url') \
            or icp.get_param('web.base.url', '')
        return base.rstrip('/')

    # ------------------------------------------------------------------
    # Reference
    # ------------------------------------------------------------------
    @api.model
    def _normalize_reference(self, value):
        return re.sub(r'[^A-Z0-9]', '', (value or '').upper())

    @api.model
    def _generate_reference(self, place_code=None):
        """``PREFIX-YYYY-PPP-XXXX-XX``.

        Deliberately not sequential. A counter in the reference would tell
        anyone holding two documents how many were issued between them, and
        would make the space walkable; the thirty random bits here do not.
        """
        prefix = (self._default_param('reference_prefix', 'ICS') or 'ICS').upper()
        place = re.sub(r'[^A-Z0-9]', '', (place_code or 'FRA').upper())[:3] or 'FRA'
        year = fields.Date.context_today(self).year
        blocks = '-'.join(
            ''.join(secrets.choice(REFERENCE_ALPHABET) for _i in range(size))
            for size in REFERENCE_GROUPS
        )
        return '%s-%s-%s-%s' % (prefix, year, place.ljust(3, 'X'), blocks)

    # ------------------------------------------------------------------
    # Issuing
    # ------------------------------------------------------------------
    @api.model
    def issue(self, vals, holders=None, source=None, redaction_secrets=None):
        """Create a certificate and seal its document in one call.

        :param dict vals: certificate values.
        :param list holders: dicts of ``dms.certificate.holder`` values, each
            carrying ``passport_number`` so it can be hashed and dropped.
        :param source: recordset this entry stands for; its model and id are
            stored so the back office can navigate back to it.
        :param dict redaction_secrets: ``{index: [strings]}`` by position in
            *holders* — the passport numbers, printed on the page but stored
            nowhere, so where they sit can only be measured now.
        """
        vals = dict(vals)
        if source is not None and source:
            vals.setdefault('res_model', source._name)
            vals.setdefault('res_id', source.id)
        if holders:
            vals['holder_ids'] = [(0, 0, dict(holder)) for holder in holders]
        record = self.create(vals)
        if redaction_secrets:
            record.stash_redaction({
                holder.id: redaction_secrets.get(index, [])
                for index, holder in enumerate(record.holder_ids)
            })
        else:
            record.stash_redaction()
        record.certify()
        _logger.info("Issued verification entry %s", record.reference)
        return record

    def action_certify(self):
        """Seal (or re-seal) the document. The reference never changes: a
        re-stamp is a new marking on the same issued document, not a new one."""
        for record in self:
            record.certify()
        return True

    def certify(self):
        self.ensure_one()
        if self.state == 'revoked':
            raise UserError(_(
                "%s is revoked. Issue a new document rather than re-sealing "
                "this one, so the trail stays honest.", self.reference))
        if not self.holder_ids:
            raise UserError(_(
                "Add at least one listed person to %s, otherwise nobody can "
                "open it.", self.reference))

        first_time = self.state == 'draft'
        self._apply_seal()

        if first_time:
            self.write({'state': 'certified',
                        'issued_on': fields.Datetime.now(),
                        'issuer_id': self.env.user.id})
            self._notify_certified()
        else:
            marking = dict(self._fields['seal_marking']._description_selection(
                self.env)).get(self.seal_marking, '')
            self._post_service(Markup("<p>%s</p>") % _(
                "Re-stamped as \u201c%s\u201d. The reference and the printed "
                "fingerprint are unchanged, so copies already sent still "
                "verify.", marking))
        return True

    def _apply_seal(self):
        """Stamp the source and store the copies. No state, no guards."""
        self.ensure_one()
        filename, raw = self._certify_source()
        if not raw:
            raise UserError(_("There is no document to seal on %s.", self.reference))

        self.source_hash = sealing.fingerprint(raw)
        spec = self._seal_spec(self.source_hash)

        sealed = sealing.seal(raw, spec)
        self.sealed_attachment_id = self._store_artifact(
            self.sealed_attachment_id, 'sealed', filename, sealed)
        self.sealed_hash = sealing.fingerprint(sealed)

        return True

    def stash_redaction(self, secrets=None):
        """Record where each listed person appears on the source document.

        Measuring once, when the document is registered, means a lookup blanks
        exactly the places this person's details were found rather than
        searching the page again for strings that might also appear in the
        letter body. When the measurements no longer match the document,
        ``_public_bytes`` falls back to searching.

        :param dict secrets: ``{holder_id: [extra strings]}`` printed for that
            person on top of what the holder record already carries.
        """
        self.ensure_one()
        _filename, raw = self._certify_source()
        if not raw:
            return False
        source_hash = sealing.fingerprint(raw)
        secrets = secrets or {}
        for holder in self.holder_ids:
            needles = holder._redaction_needles() + list(secrets.get(holder.id, []))
            holder._store_boxes(sealing.locate(raw, needles), source_hash)
        return True

    # ------------------------------------------------------------------
    # What a given lookup is allowed to see
    # ------------------------------------------------------------------
    def _public_bytes(self, holder=None):
        """The sealed document this lookup may look at.

        Under full disclosure that is simply the sealed copy. Under
        confirm-only it is built here, per person: the source with everyone
        *else's* lines removed, then sealed. Built rather than stored because
        the alternative is one saved copy per person per document.

        Returns ``b''`` when the result cannot be shown to be safe. Every
        caller treats that as "show nothing" — an empty page is a nuisance, a
        page with somebody else's passport on it is a breach.
        """
        self.ensure_one()
        if self.disclosure != 'confirm':
            attachment = self.sealed_attachment_id.sudo()
            return attachment.raw if attachment else b''

        _filename, raw = self._certify_source()
        if not raw:
            return b''
        source_hash = sealing.fingerprint(raw)

        others = self.holder_ids - (holder or self.env['dms.certificate.holder'])
        boxes, unmeasured = [], self.env['dms.certificate.holder']
        for other in others:
            own = other._boxes(source_hash)
            if own is None:
                unmeasured |= other
            else:
                boxes.extend(own)

        redacted = sealing.redact_boxes(raw, boxes) if boxes else raw
        if unmeasured:
            # Positions were measured against a different version of this
            # document, or never measured at all. Falling back to searching for
            # the values is safe now that they are stored, and beats refusing
            # to show a page that an agent is standing at a counter waiting for.
            _logger.info(
                "dms_certify_portal: %s has no current positions for %s; "
                "redacting by value instead",
                self.reference, ', '.join(unmeasured.mapped('display_name_public')))
            needles = []
            for other in unmeasured:
                needles.extend(other._redaction_needles())
            redacted = sealing.redact(redacted, needles)

        # Closed loop. The boxes were measured against this document, but a
        # measurement is not a guarantee — so check the result against what is
        # actually stored, including the passport hashes, which is the only way
        # to look for a number nobody kept.
        tokens = sealing.text_tokens(redacted)
        for other in others:
            leaked = other._survives(tokens)
            if leaked:
                _logger.error(
                    "dms_certify_portal: redacting %s left %s behind; refusing "
                    "to serve it", self.reference, ', '.join(sorted(set(leaked))))
                return b''

        return sealing.seal(redacted, self._seal_spec(self.source_hash))

    def _seal_spec(self, source_hash=None):
        """*source_hash* is passed in rather than read off the record so the
        preview can stamp a document that has not been certified yet."""
        self.ensure_one()
        param = self._default_param
        return sealing.SealSpec(
            reference=self.reference,
            verify_url=self.verify_url,
            source_hash=source_hash or self.source_hash,
            company_name=self.company_id.name or '',
            watermark_text=self.seal_text or '',
            watermark_opacity=int(param('seal_opacity', '9')),
            watermark_angle=int(param('seal_angle', '-32')),
            watermark_size=int(param('seal_size', '24')),
            watermark_mode=param('seal_mode', 'tile'),
            watermark_color=param('seal_color', '#10314F'),
            guilloche=param('seal_guilloche', '1') == '1',
            microtext=param('seal_microtext', '1') == '1',
            qr_corner=param('seal_qr_corner', 'br'),
            band=param('seal_band', 'auto'),
        )

    # -- storage seams ------------------------------------------------------
    def _certify_source(self):
        """Return ``(filename, bytes)`` of the document to seal.

        Overridden by the producing module — the operations bridge points this
        at the ``dms.file`` the generation wizard produced, which is never
        modified. The default reads an attachment, so this module stands alone.
        """
        self.ensure_one()
        attachment = self.source_attachment_id.sudo()
        if not attachment:
            return None, None
        return attachment.name, attachment.raw

    def _store_artifact(self, existing, kind, filename, content):
        """Keep *content* as an attachment owned by this certificate.

        Deliberately not filed back into the DMS: the folder shows the document
        as it was produced, and the sealed and redacted copies are the
        portal's, not the operator's.
        """
        self.ensure_one()
        name = '%s-%s.pdf' % (
            re.sub(r'[^A-Za-z0-9._-]+', '-', filename or 'document')[:60].rsplit('.', 1)[0],
            kind)
        values = {
            'name': name,
            'datas': base64.b64encode(content),
            'mimetype': 'application/pdf',
            'res_model': self._name,
            'res_id': self.id,
        }
        attachment = existing.sudo()
        if attachment:
            attachment.write(values)
            return attachment
        return self.env['ir.attachment'].sudo().create(values)

    # ------------------------------------------------------------------
    # Preview
    # ------------------------------------------------------------------
    @api.depends('seal_marking', 'seal_text', 'source_attachment_id', 'state')
    def _compute_preview_pdf(self):
        """Stamp the source as it stands.

        Deliberately re-sealed rather than read back from the stored copy: the
        point of the panel is to show what the marking currently selected would
        produce, including before anything has been certified.
        """
        for record in self:
            record.preview_pdf = False
            try:
                _name, raw = record._certify_source()
            except Exception:  # noqa: BLE001 - a preview never breaks the form
                raw = None
            if not raw:
                continue
            try:
                spec = record._seal_spec(sealing.fingerprint(raw))
                record.preview_pdf = base64.b64encode(sealing.seal(raw, spec))
            except Exception:  # noqa: BLE001
                _logger.exception("dms_certify_portal: preview failed for %s",
                                  record.reference)

    # ------------------------------------------------------------------
    # Telling the desk
    # ------------------------------------------------------------------
    def _post_service(self, body):
        """A note from the certificate service itself, not from a person."""
        self.ensure_one()
        return self.message_post(body=body, message_type='notification',
                                 subtype_xmlid='mail.mt_note')

    def _notify_certified(self):
        self.ensure_one()
        factor = dict(self._fields['second_factor']._description_selection(
            self.env)).get(self.second_factor, '')
        disclosure = _(
            "The portal will confirm the match and keep the listed people "
            "redacted."
        ) if self.disclosure == 'confirm' else _(
            "The portal will show the full page, listed people included.")
        self._post_service(Markup(
            "<p>%s</p>"
        ) % Markup(_(
            "Reference <b>%(reference)s</b> issued, page stamped and sealed. "
            "Fingerprint <code>%(hash)s…</code>. %(validity)s<br/>"
            "Opening it needs the reference <b>and</b> %(factor)s. %(disclosure)s"
        )) % {
            'reference': self.reference,
            'hash': (self.source_hash or '')[:16],
            'validity': _("Valid until %s.", self.valid_until)
                        if self.valid_until else _("Valid until revoked."),
            'factor': factor.lower(),
            'disclosure': disclosure,
        })

    def _notify_verification(self, outcome, minutes=0):
        """Post a lookup back to the desk.

        With notifications off only the outcomes that need someone to act —
        a lockout, or a reported mismatch — still come through; a successful
        check by an embassy is routine and does not.
        """
        self.ensure_one()
        needs_attention = outcome in ('locked', 'mismatch')
        if not self.notify_on_lookup and not needs_attention:
            return
        bodies = {
            'matched': _("An external user looked up %s — shown as %s.",
                         self.reference,
                         dict(self._fields['public_state']._description_selection(
                             self.env)).get(self.public_state, '').lower()),
            'no_match': _("An external user failed to open %s.", self.reference),
            'locked': _("An external user was locked out of %s after too many "
                        "failed attempts. It stays locked for %s minutes.",
                        self.reference, minutes),
            'mismatch': _("An external user reports that the paper in front of "
                          "them does not match %s.", self.reference),
        }
        body = bodies.get(outcome)
        if not body:
            return
        self.sudo()._post_service(Markup("<p>%s</p>") % body)
        if needs_attention:
            self.sudo()._flag_for_attention(body)

    def _flag_for_attention(self, summary):
        """Put it on someone's plate rather than only in the log."""
        self.ensure_one()
        user = self.issuer_id or self.create_uid
        if not user:
            return
        try:
            self.activity_schedule(
                'mail.mail_activity_data_warning',
                user_id=user.id,
                summary=summary[:250],
            )
        except ValueError:
            # The warning activity type is not guaranteed to exist in every
            # database; the note is already posted either way.
            _logger.info("dms_certify_portal: no warning activity type available")

    # ------------------------------------------------------------------
    # State transitions
    # ------------------------------------------------------------------
    def action_download_sealed(self):
        """Hand the issuer the file the embassy will be looking at."""
        self.ensure_one()
        attachment = self.sealed_attachment_id
        if not attachment:
            raise UserError(_("Seal %s before downloading it.", self.reference))
        return {
            'type': 'ir.actions.act_url',
            'url': '/web/content/%d?download=true' % attachment.id,
            'target': 'self',
        }

    def action_send_to_embassy(self):
        """Open the composer with the sealed document attached.

        Sending is what makes a certified document a delivered one, so the
        state follows the message rather than a separate button.
        """
        self.ensure_one()
        if not self.sealed_attachment_id:
            raise UserError(_("Seal %s before sending it.", self.reference))
        return {
            'type': 'ir.actions.act_window',
            'name': _("Send to embassy"),
            'res_model': 'mail.compose.message',
            'views': [(False, 'form')],
            'target': 'new',
            'context': {
                'default_model': self._name,
                'default_res_ids': self.ids,
                'default_composition_mode': 'comment',
                'default_subject': _("Certified document %s", self.reference),
                'default_attachment_ids': [(6, 0, self.sealed_attachment_id.ids)],
                'dms_certify_delivery': True,
            },
        }

    def message_post(self, **kwargs):
        message = super().message_post(**kwargs)
        # A note to ourselves is not a delivery; an email with recipients is.
        if (self.env.context.get('dms_certify_delivery')
                and self.state == 'certified'):
            self.sudo().write({'state': 'delivered'})
        return message

    def action_mark_delivered(self):
        self.filtered(lambda r: r.state == 'certified').write({'state': 'delivered'})

    def action_revoke(self, reason=None):
        """Withdraw the document. Irreversible on purpose.

        The stored copies are re-stamped VOID first. The paper already in
        someone's hand cannot change, but the page the portal shows beside the
        refusal should not look like a document in good standing.
        """
        reason = reason or self.env.context.get('revoke_reason') \
            or _("No reason recorded.")
        for record in self:
            if record.state in ('certified', 'delivered') and record.sealed_attachment_id:
                record.seal_marking = 'void'
                record._apply_seal()
        self.write({
            'state': 'revoked',
            'revoke_reason': reason,
            'revoked_on': fields.Datetime.now(),
            'revoked_uid': self.env.user.id,
        })
        for record in self:
            record._post_service(Markup("<p>%s</p>") % _(
                "Reference %(reference)s revoked. Anyone checking it now sees a "
                "refusal notice and the reason: %(reason)s",
                reference=record.reference, reason=reason))
        return True

    def action_open_portal(self):
        """Open the public page for this document, prefilled as a scan would."""
        self.ensure_one()
        return {'type': 'ir.actions.act_url', 'url': self.verify_url, 'target': 'new'}

    # ------------------------------------------------------------------
    # Matching -- called by the public controller only
    # ------------------------------------------------------------------
    @api.model
    def _match(self, reference, factor_value):
        """Return ``(certificate, holder)`` matching both inputs, or empties.

        Constant-time on the comparison, and a throwaway hash is computed when
        nothing is found, so a wrong reference and a wrong passport cost about
        the same wall time.
        """
        Holder = self.env['dms.certificate.holder'].sudo()
        empty = (self.browse(), Holder.browse())

        key = self._normalize_reference(reference)
        if not key or not factor_value:
            return empty

        certificate = self.sudo().search(
            [('reference_key', '=', key), ('state', 'in', LIVE_STATES)], limit=1)
        if not certificate:
            Holder._submitted_factor_hash('pptfull', secrets.token_hex(16))
            return empty

        submitted = Holder._submitted_factor_hash(
            certificate.second_factor, factor_value)
        if not submitted:
            return empty

        for holder in certificate.holder_ids:
            stored = holder._stored_factor_hash(certificate.second_factor)
            if stored and hmac.compare_digest(stored, submitted):
                return certificate, holder
        return empty

    def _register_verification(self):
        self.sudo().write({
            'verify_count': self.verify_count + 1,
            'last_verified_on': fields.Datetime.now(),
        })

    # ------------------------------------------------------------------
    # What the public page is allowed to see
    # ------------------------------------------------------------------
    def _get_public_values(self, holder=None):
        """Whitelist. Returns plain data, never a recordset.

        The single most important method in the module: templates receive this
        dict and nothing else, so a later edit cannot reach a partner's email
        or a message thread even by accident.
        """
        self.ensure_one()
        states = dict(self._fields['public_state']._description_selection(self.env))
        try:
            facts = json.loads(self.facts_json or '[]')
        except ValueError:
            facts = []
        facts = [
            {'label': self._resolve_fact_label(fact.get('label')),
             'value': fact.get('value')}
            for fact in facts if isinstance(fact, dict)
        ]

        confirm_only = self.disclosure == 'confirm'
        values = {
            'reference': self.reference,
            'document_type': self.type_id.name or '',
            'public_state': self.public_state,
            'public_state_label': states.get(self.public_state, ''),
            'issued_on': self.issued_on,
            'valid_until': self.valid_until,
            'issuer': self.issuer_id.name or '',
            'company': self.company_id.name or '',
            'revoke_reason': self.revoke_reason if self.public_state == 'revoked' else False,
            'facts': facts,
            'source_hash': self.source_hash or '',
            'sealed_hash': self.sealed_hash or '',
            'holder_count': len(self.holder_ids),
            'verify_count': self.verify_count,
            'confirm_only': confirm_only,
            'has_file': bool(self.sealed_attachment_id),
            'page_count': self._public_page_count(),
            'issuer_notified': self.notify_on_lookup,
            'revoked_on': self.revoked_on,
            'matched': False,
            'crew': [],
        }
        if holder:
            values['matched'] = {
                'name': holder.display_name_public,
                'surname': holder.name or '',
                'rank': holder.rank or '',
            }
        if not confirm_only:
            values['crew'] = [{
                'surname': line.name or '',
                'first_name': line.first_name or '',
                'date_of_birth': line.date_of_birth,
                'rank': line.rank or '',
            } for line in self.holder_ids]
        return values

    def _resolve_fact_label(self, label):
        """Fact labels may be a plain string or a mapping of language to string.

        The portal is read in French by people the producing module knows about
        and this one does not, so the vocabulary of a port call stays in the
        producing module — it just has to be able to give that vocabulary in
        more than one language.
        """
        if not isinstance(label, dict):
            return label or ''
        lang = self.env.lang or 'en_US'
        return (label.get(lang)
                or label.get(lang.split('_')[0])
                or label.get('en')
                or next(iter(label.values()), ''))

    def _public_page_count(self):
        self.ensure_one()
        attachment = self.sealed_attachment_id.sudo()
        if not attachment:
            return 0
        try:
            return sealing.page_count(attachment.raw)
        except Exception:  # noqa: BLE001 - never let a broken file 500 the page
            _logger.exception("dms_certify_portal: unreadable public copy of %s",
                              self.reference)
            return 0

    def _public_page_image(self, page_number, dpi=PUBLIC_PAGE_DPI, holder=None):
        """One page of the public copy, as PNG bytes.

        Rendered per request rather than cached: lookups are rare, the session
        that asks has already passed the second check, and a cache would have
        to be invalidated on every re-stamp and revocation.
        """
        self.ensure_one()
        raw = self._public_bytes(holder)
        if not raw:
            return b''
        try:
            return sealing.render_page(raw, page_number, dpi=dpi)
        except Exception:  # noqa: BLE001
            _logger.exception("dms_certify_portal: cannot render %s page %s",
                              self.reference, page_number)
            return b''

    # ------------------------------------------------------------------
    # Guards
    # ------------------------------------------------------------------
    @api.constrains('movement_date', 'valid_until')
    def _check_dates(self):
        for record in self:
            if (record.movement_date and record.valid_until
                    and record.valid_until < record.movement_date):
                raise ValidationError(_("A document cannot expire before its movement date."))

    @api.constrains('seal_marking', 'seal_text')
    def _check_seal_text(self):
        for record in self:
            if record.seal_marking == 'custom' and not (record.seal_text or '').strip():
                raise ValidationError(_("Type the marking the document should carry."))

    @api.ondelete(at_uninstall=False)
    def _unlink_except_issued(self):
        if any(record.state in LIVE_STATES for record in self):
            raise UserError(_(
                "Revoke an issued entry instead of deleting it. Deleting it "
                "makes a genuine document read as forged, and erases the trail."))

    def copy(self, default=None):
        raise UserError(_(
            "Verification entries are not duplicated. Issue a new document so "
            "it gets its own reference."))
