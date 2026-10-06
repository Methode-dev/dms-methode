# -*- coding: utf-8 -*-
"""Defects found while documenting the module. **These tests are expected to
fail.**

Each one asserts the behaviour the module is supposed to have, against a defect
that is still present. They exist so the defects cannot be forgotten: a failing
test is harder to lose than a note in a changelog.

Every test names the source line and the candidate fix in its docstring. When
one is fixed, the test should start passing unchanged — if you find yourself
editing the assertion to make it green, the fix is not a fix.

Run just these:

    odoo-bin -c odoo.conf -d <db> -u dms_certify_portal --test-enable \\
        --test-tags /dms_certify_portal:TestKnownDefects --stop-after-init

They are tagged ``known_defects`` as well, so a pipeline that wants a green
run can exclude them explicitly with ``--test-tags '-known_defects'`` rather
than by not noticing them.
"""

import base64
from datetime import date, timedelta

import pymupdf

from odoo import fields
from odoo.tests.common import TransactionCase, tagged

from odoo.addons.dms_certify_portal.tools import seal as sealing

CREW = [
    {'name': 'Shwe Moung', 'first_name': 'Aung', 'rank': 'Able seaman',
     'date_of_birth': '1990-02-06', 'passport_number': 'MB1234567'},
    {'name': 'Win Htike Moung', 'first_name': 'Zaw', 'rank': 'Oiler',
     'date_of_birth': '1994-11-14', 'passport_number': 'MC7654321'},
]


def build_pdf():
    """A one-page stand-in carrying the crew lines a letter would print."""
    document = pymupdf.open()
    page = document.new_page(width=595.28, height=841.89)
    page.insert_text((60, 90), 'LETTER OF INVITATION', fontsize=15, fontname='hebo')
    y = 140
    for member in CREW:
        line = '%s   %s   %s   %s' % (
            member['name'], member['first_name'],
            '/'.join(reversed(member['date_of_birth'].split('-'))),
            member['passport_number'])
        page.insert_text((60, y), line, fontsize=9)
        y += 20
    raw = document.tobytes()
    document.close()
    return raw


@tagged('post_install', '-at_install', 'known_defects')
class TestKnownDefects(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.doc_type = cls.env['dms.certificate.type'].create({
            'name': 'Letter of Invitation',
            'code': 'defect_letter',
        })
        cls.Certificate = cls.env['dms.certificate']
        cls.raw = build_pdf()
        cls.attachment = cls.env['ir.attachment'].create({
            'name': 'loi.pdf',
            'datas': base64.b64encode(cls.raw),
            'mimetype': 'application/pdf',
        })

    def _issue(self, **overrides):
        values = {
            'type_id': self.doc_type.id,
            'movement_date': '2026-09-03',
            'source_attachment_id': self.attachment.id,
        }
        values.update(overrides)
        return self.Certificate.issue(
            values,
            holders=[dict(member) for member in CREW],
            redaction_secrets={index: [member['passport_number']]
                               for index, member in enumerate(CREW)},
        )

    def _save_settings(self, **values):
        """Save through create() and execute(), the way the web client does.

        This is the whole point of the first three tests: the parameters are
        correct as shipped, and only a *save* breaks them. Writing
        ``ir.config_parameter`` directly would prove nothing.
        """
        self.env['res.config.settings'].create(values).execute()

    # ------------------------------------------------------------------
    # Defect 1 — a Settings save silently disarms the seal
    #
    # data/ir_config_parameter.xml ships seal_guilloche, seal_microtext and
    # notify_on_lookup as "1". They are read strictly:
    #
    #   models/dms_certificate.py:535  param('seal_guilloche', '1') == '1'
    #   models/dms_certificate.py:536  param('seal_microtext', '1') == '1'
    #   models/dms_certificate.py:210  _default_param('notify_on_lookup', '1') == '1'
    #
    # res.config.settings writes a Boolean config_parameter as "True", so the
    # first time anybody saves the Settings page the comparison stops matching
    # and the feature switches itself off. Nothing is logged.
    #
    # allow_download is immune: controllers/main.py:69 _bool_param() accepts
    # ('True', 'true', '1'). That is the shape the three readers below want.
    #
    # Candidate fix: make the three readers tolerant like _bool_param, or ship
    # the XML values as "True". Prefer the former — it survives both spellings.
    # ------------------------------------------------------------------
    def test_the_seal_keeps_its_guilloche_border_after_a_settings_save(self):
        """The guilloche is an anti-forgery feature of a document that goes to
        an embassy. Saving an unrelated setting must not remove it."""
        self._save_settings(certify_seal_guilloche=True)

        certificate = self._issue()

        self.assertTrue(
            certificate._seal_spec().guilloche,
            "The guilloche border switched itself off because Settings wrote "
            "'True' where the reader compares against '1'. Documents sealed "
            "after the first Settings save carry no guilloche.")

    def test_the_seal_keeps_its_microtext_footer_after_a_settings_save(self):
        """Same defect, same cause, second anti-forgery feature."""
        self._save_settings(certify_seal_microtext=True)

        certificate = self._issue()

        self.assertTrue(
            certificate._seal_spec().microtext,
            "The microtext footer switched itself off: Settings wrote 'True' "
            "where the reader compares against '1'.")

    def test_lookup_notifications_stay_on_after_a_settings_save(self):
        """The desk is told about verifications because somebody ticked it.
        A later save of any other setting must not untick it."""
        self._save_settings(certify_notify_on_lookup=True)

        certificate = self._issue()

        self.assertTrue(
            certificate.notify_on_lookup,
            "notify_on_lookup defaulted to False after a Settings save: the "
            "default compares the parameter against '1' and Settings wrote "
            "'True'. The desk silently stops hearing about lookups.")

    def test_a_shipped_boolean_parameter_reads_the_same_before_and_after_a_save(self):
        """The invariant underneath the three tests above, stated once.

        Whatever spelling reaches ``ir.config_parameter``, a reader must get the
        same answer. This is the test to keep if the three above are replaced.
        """
        Parameter = self.env['ir.config_parameter'].sudo()
        certificate = self._issue()

        as_shipped = Parameter.get_param('dms_certify_portal.seal_guilloche')
        before = certificate._seal_spec().guilloche

        self._save_settings(certify_seal_guilloche=True)

        as_saved = Parameter.get_param('dms_certify_portal.seal_guilloche')
        after = certificate._seal_spec().guilloche

        self.assertEqual(
            before, after,
            "The same setting, left on, reads %r as shipped (%r) and %r after "
            "a save (%r). A boolean parameter must survive the round trip."
            % (before, as_shipped, after, as_saved))

    # ------------------------------------------------------------------
    # Defect 2 — the disclosure branch fails open
    #
    # models/dms_certificate.py:471
    #     if self.disclosure != 'confirm':
    #         return <the unredacted sealed copy>
    #
    # Redaction is the exception rather than the rule, so any disclosure mode
    # that is not exactly 'confirm' serves the whole document with every
    # holder's name, date of birth and passport visible. A module adding a mode
    # through selection_add inherits a breach it never wrote.
    #
    # second_factor is the counter-example: an unrecognised value there fails
    # closed, because the matching code asks for a specific hash.
    #
    # Candidate fix: branch on `== 'full'`, so an unknown mode redacts.
    # ------------------------------------------------------------------
    def test_an_unrecognised_disclosure_mode_does_not_serve_the_whole_document(self):
        """A disclosure mode nobody taught _public_bytes about must redact.

        Simulates what ``selection_add`` would give a downstream module: the
        field accepts a third value, and nothing else changes.
        """
        certificate = self._issue(disclosure='confirm')
        asking, other = certificate.holder_ids[0], certificate.holder_ids[1]

        # Put a third mode in the column the way `selection_add` would, without
        # needing a second module in the test. Selection validation is
        # Python-side on write only, so the ORM reads this back happily — which
        # is the whole point: `_public_bytes` never checks either.
        self.env.cr.execute(
            "UPDATE dms_certificate SET disclosure = %s WHERE id = %s",
            ('embassy_only', certificate.id))
        certificate.invalidate_recordset(['disclosure'])
        self.assertEqual(
            certificate.disclosure, 'embassy_only',
            "Fixture is wrong — the third mode was not stored.")

        served = certificate._public_bytes(holder=asking)

        self.assertTrue(
            served, "Nothing was served at all, which is a different bug.")
        tokens = {token.upper() for token in sealing.text_tokens(served)}
        self.assertNotIn(
            other.passport_number.upper(), tokens,
            "An unrecognised disclosure mode served the unredacted document: "
            "%s's passport is on the page handed to %s. The branch at "
            "dms_certificate.py:471 treats everything that is not 'confirm' "
            "as full disclosure."
            % (other.name, asking.name))

    # ------------------------------------------------------------------
    # Defect 3 — an advertised extension point does not exist
    #
    # README.md and the manifest both document `_hide_expired()` as an override
    # point: "Decide whether an expired document reads as expired or as not
    # found." dms_certify_portal.hide_expired ships as a parameter
    # (data/ir_config_parameter.xml) and has a Settings field and widget
    # (models/res_config_settings.py, views/res_config_settings_views.xml).
    #
    # Nothing reads any of it. _compute_public_state always reports 'expired',
    # so the setting is inert and the override point is absent.
    #
    # Either implement it or remove the parameter, the field, the widget and
    # the README claim. The documentation currently says three override points
    # exist, which is the true count.
    # ------------------------------------------------------------------
    def test_hide_expired_hides_an_expired_document(self):
        """With the setting on, an expired document must not announce itself.

        The point of the setting is that "this reference expired" still confirms
        the reference is real. A deployment that does not want to confirm that
        turns this on and expects expiry to be indistinguishable from an
        unknown reference.
        """
        self.env['ir.config_parameter'].sudo().set_param(
            'dms_certify_portal.hide_expired', 'True')

        # Backdating the issuance, not the movement: validity runs from when
        # the document was sealed.
        certificate = self._issue(validity_days='30')
        certificate.issued_on = fields.Datetime.now() - timedelta(days=400)

        # Fixture check, not the assertion under test: the document really is
        # past its validity window.
        self.assertTrue(certificate.valid_until, "No validity window was set.")
        self.assertLess(
            certificate.valid_until, date.today(),
            "Fixture is wrong — this document was supposed to have expired.")

        self.assertNotEqual(
            certificate.public_state, 'expired',
            "hide_expired is ticked and the document still reads as 'expired' "
            "to the public page, which confirms to a stranger that the "
            "reference is real. The parameter, the Settings field and the "
            "widget all exist; nothing reads any of them.")

    def test_the_documented_hide_expired_override_point_exists(self):
        """README and manifest both name `_hide_expired()` as overridable."""
        self.assertTrue(
            hasattr(self.Certificate, '_hide_expired'),
            "README.md and __manifest__.py document _hide_expired() as an "
            "override point for the producing module. It is not defined "
            "anywhere in the addon, so a module that overrides it silently "
            "does nothing.")
