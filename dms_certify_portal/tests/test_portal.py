# -*- coding: utf-8 -*-
"""The public portal, exercised through its own routes.

What an embassy agent can see, and — mostly — what they cannot: the second
check is never bypassable, a failure never says which half was wrong, a
confirm-only document never leaks the other people on it, and a result stops
being readable once the session it belongs to is over.

The portal lives on check.<host> only. Every request in TestVerifyPortal is
sent with that Host header, as nginx would; TestPortalHost pins the other
half — that the portal is not reachable anywhere else, and that nothing but
the portal is reachable on its host.
"""

import base64
import re
from urllib.parse import urlsplit

import pymupdf

from odoo.tests.common import HttpCase, tagged

from .test_certificate import CREW, build_pdf

CSRF = re.compile(r'name="csrf_token"[^>]*value="([^"]+)"')

# Tests run without proxy_mode, so Odoo reads Host as sent. The request itself
# still goes to 127.0.0.1: nothing has to resolve this name.
CHECK_HOST = 'check.localhost'


@tagged('post_install', '-at_install')
class TestVerifyPortal(HttpCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.doc_type = cls.env['dms.certificate.type'].create({
            'name': 'Letter of Invitation',
            'code': 'test_letter',
        })
        cls.raw = build_pdf()
        cls.attachment = cls.env['ir.attachment'].create({
            'name': 'loi.pdf',
            'datas': base64.b64encode(cls.raw),
            'mimetype': 'application/pdf',
        })

    def url_open(self, url, *args, headers=None, **kwargs):
        """Every request here is an agent on the portal's own host.

        requests keeps the header across the POST-Redirect-GET, so the result
        page is reached on the check host too.
        """
        headers = dict(headers or {})
        headers.setdefault('Host', CHECK_HOST)
        return super().url_open(url, *args, headers=headers, **kwargs)

    def _issue(self, **overrides):
        values = {
            'type_id': self.doc_type.id,
            'movement_date': '2026-09-03',
            'source_attachment_id': self.attachment.id,
        }
        values.update(overrides)
        certificate = self.env['dms.certificate'].issue(
            values,
            holders=[dict(member) for member in CREW],
            redaction_secrets={index: [m['passport_number']]
                               for index, m in enumerate(CREW)},
        )
        self.env.flush_all()
        return certificate

    # -- helpers ---------------------------------------------------------
    def _stable(self, html):
        """Blank out what legitimately differs between two renders.

        A CSRF token is fresh per render and a reference is whatever was typed;
        neither says anything about whether a document exists. Everything else
        has to match, or the page is an oracle.
        """
        html = re.sub(r'value="[0-9a-f]{20,}o\d+"', 'value="CSRF"', html)
        html = re.sub(r'csrf_token: "[^"]+"', 'csrf_token: "CSRF"', html)
        html = re.sub(r'ICS[0-9A-Z-]+', 'REF', html)
        # Neither of these says anything about whether a reference exists, and
        # both move on their own: the asset URL is content-hashed and a bundle
        # may be rebuilt between two requests, and registry_hash changes
        # whenever the registry does.
        html = re.sub(r'/web/assets/[0-9a-f]+/', '/web/assets/HASH/', html)
        html = re.sub(r'"registry_hash": "[0-9a-f]+"',
                      '"registry_hash": "HASH"', html)
        return html

    def _csrf(self, html):
        found = CSRF.search(html)
        self.assertTrue(found, "The form must carry a CSRF token.")
        return found.group(1)

    def _submit(self, reference, passport):
        page = self.url_open('/')
        response = self.url_open('/', data={
            'csrf_token': self._csrf(page.text),
            'reference': reference,
            'passport': passport,
        })
        return response

    # ------------------------------------------------------------------
    # The form
    # ------------------------------------------------------------------
    def test_the_form_is_public_and_asks_for_both_details(self):
        response = self.url_open('/')
        self.assertEqual(response.status_code, 200)
        self.assertIn('name="reference"', response.text)
        self.assertIn('name="passport"', response.text)
        self.assertIn('A reference on its own opens nothing', response.text)

    def test_the_form_is_never_indexed(self):
        response = self.url_open('/')
        self.assertIn('noindex', response.headers.get('X-Robots-Tag', ''))
        self.assertEqual(response.headers.get('Referrer-Policy'), 'no-referrer')
        self.assertIn('no-store', response.headers.get('Cache-Control', ''))

    def test_a_scanned_qr_prefills_the_reference_and_nothing_else(self):
        certificate = self._issue()
        response = self.url_open('/d/%s' % certificate.reference)
        self.assertEqual(response.status_code, 200)
        self.assertIn(certificate.reference, response.text)
        self.assertIn('name="passport"', response.text)

    def test_the_printed_url_lands_on_the_prefilled_form(self):
        """The model builds the URL, the controller serves it: this is the one
        place the two are held to each other. A path that drifts on either side
        prints a QR code that 404s on every document issued since."""
        certificate = self._issue()
        path = urlsplit(certificate.verify_url).path
        response = self.url_open(path)
        self.assertEqual(response.status_code, 200)
        self.assertIn(certificate.reference, response.text)
        self.assertIn('name="passport"', response.text)

    def test_the_qr_route_says_nothing_about_whether_it_exists(self):
        """Echoing the scanned value back keeps this route from becoming a
        cheap existence oracle."""
        real = self._issue()
        known = self.url_open('/d/%s' % real.reference).text
        unknown = self.url_open('/d/ICS-2026-DKK-0000-00').text
        self.assertEqual(self._stable(known), self._stable(unknown))

    # ------------------------------------------------------------------
    # Refusals
    # ------------------------------------------------------------------
    def test_a_wrong_second_check_is_refused_without_saying_which_half(self):
        certificate = self._issue()
        response = self._submit(certificate.reference, '9999')
        self.assertIn('do not open a document', response.text)
        self.assertNotIn('passport is wrong', response.text)
        self.assertNotIn('unknown reference', response.text.lower())

    def test_an_unknown_reference_looks_exactly_like_a_wrong_passport(self):
        certificate = self._issue()
        wrong_check = self._submit(certificate.reference, '9999').text
        wrong_ref = self._submit('ICS-2026-DKK-0000-00', '4567').text
        self.assertEqual(
            self._stable(wrong_check), self._stable(wrong_ref),
            "Apart from the reference typed back, the two refusals must be "
            "the same page: any difference is an existence oracle.")

    def test_a_refusal_gives_the_reference_back_as_it_is_printed(self):
        certificate = self._issue()
        response = self._submit(certificate.reference, '9999')
        self.assertIn(
            'value="%s"' % certificate.reference, response.text,
            "Grouped as on the paper, so only the second check is retyped.")

    def test_a_refusal_says_how_many_tries_are_left(self):
        certificate = self._issue()
        self._submit(certificate.reference, '9999')
        response = self._submit(certificate.reference, '9998')
        self.assertIn('Attempts left on this reference', response.text)
        self.assertIn('<b>3</b>', response.text)

    def test_guessing_locks_the_reference_and_says_so(self):
        certificate = self._issue()
        for _index in range(5):
            self._submit(certificate.reference, '9999')
        response = self._submit(certificate.reference, '4567')
        self.assertIn('Reference locked', response.text)
        self.assertNotIn('Document is authentic', response.text)

    def test_a_draft_cannot_be_opened_from_the_portal(self):
        certificate = self.env['dms.certificate'].create({
            'type_id': self.doc_type.id,
            'holder_ids': [(0, 0, dict(CREW[0]))],
        })
        self.env.flush_all()
        response = self._submit(certificate.reference, '4567')
        self.assertIn('do not open a document', response.text)

    # ------------------------------------------------------------------
    # The verdicts
    # ------------------------------------------------------------------
    def test_an_authentic_document_shows_its_reference_and_fingerprint(self):
        certificate = self._issue()
        response = self._submit(certificate.reference, '4567')
        self.assertIn('Document is authentic', response.text)
        self.assertIn(certificate.reference, response.text)
        self.assertIn(certificate.source_hash, response.text)
        self.assertIn('Second check', response.text)

    def test_a_revoked_document_verifies_and_refuses(self):
        certificate = self._issue()
        certificate.action_revoke(reason='Crew change before departure')
        self.env.flush_all()
        response = self._submit(certificate.reference, '4567')
        self.assertIn('do not accept', response.text)
        self.assertIn('Crew change before departure', response.text)

    def test_an_expired_document_reads_as_out_of_date(self):
        certificate = self._issue(movement_date='2024-01-10', validity_days='30')
        response = self._submit(certificate.reference, '4567')
        self.assertIn('out of date', response.text)
        self.assertNotIn('do not open a document', response.text)

    def test_the_page_is_shown_as_an_image_not_a_pdf(self):
        certificate = self._issue()
        response = self._submit(certificate.reference, '4567')
        token = response.url.rstrip('/').split('/')[-1]
        self.assertIn('/r/%s/page/1' % token, response.text)
        image = self.url_open('/r/%s/page/1' % token)
        self.assertEqual(image.status_code, 200)
        self.assertEqual(image.headers['Content-Type'], 'image/png')
        self.assertEqual(image.content[:8], b'\x89PNG\r\n\x1a\n')

    # ------------------------------------------------------------------
    # Disclosure
    # ------------------------------------------------------------------
    def test_confirm_only_names_the_person_checked_and_nobody_else(self):
        certificate = self._issue(disclosure='confirm')
        response = self._submit(certificate.reference, '4567')
        self.assertIn('Shwe Moung', response.text)
        self.assertNotIn('Win Htike Moung', response.text)
        self.assertNotIn('MB1234567', response.text)
        self.assertIn('not shown', response.text)

    def test_full_disclosure_lists_everyone_on_the_document(self):
        certificate = self._issue(disclosure='full')
        response = self._submit(certificate.reference, '4567')
        self.assertIn('Shwe Moung', response.text)
        self.assertIn('Win Htike Moung', response.text)
        self.assertNotIn(
            'MB1234567', response.text,
            "Passport numbers are not stored, so they cannot be shown.")

    def test_the_served_file_matches_what_the_page_showed(self):
        """Download and page image are built from the same per-person copy, so
        the file cannot be whole while the screen was redacted."""
        certificate = self._issue(disclosure='confirm')
        response = self._submit(certificate.reference, '4567')
        token = response.url.rstrip('/').split('/')[-1]

        downloaded = self.url_open('/r/%s/file' % token)
        self.assertEqual(downloaded.status_code, 200)
        self.assertNotEqual(
            downloaded.content, certificate.sealed_attachment_id.raw,
            "A redacted result must not hand over the whole document.")

        document = pymupdf.open(stream=downloaded.content, filetype='pdf')
        text = document[0].get_text()
        document.close()
        self.assertIn(CREW[0]['passport_number'], text)
        self.assertNotIn(CREW[1]['passport_number'], text)

    # ------------------------------------------------------------------
    # The gate
    # ------------------------------------------------------------------
    def test_a_result_cannot_be_reached_with_a_made_up_token(self):
        self._issue()
        response = self.url_open('/r/not-a-real-token')
        self.assertIn('expired', response.text)
        self.assertNotIn('Document is authentic', response.text)

    def test_page_images_and_files_are_behind_the_same_gate(self):
        self._issue()
        self.assertEqual(self.url_open('/r/nope/page/1').status_code, 404)
        self.assertEqual(self.url_open('/r/nope/file').status_code, 404)

    def test_a_stray_browser_request_does_not_spoil_the_form(self):
        """Browsers ask for /favicon.ico on their own. Results live under /r/
        so that request cannot land on the result route, fail the token check,
        and leave an 'expired' error waiting on the agent's next form."""
        self.url_open('/favicon.ico')
        form = self.url_open('/')
        self.assertEqual(form.status_code, 200)
        self.assertNotIn('expired', form.text)

    def test_the_download_can_be_switched_off(self):
        self.env['ir.config_parameter'].sudo().set_param(
            'dms_certify_portal.allow_download', 'False')
        certificate = self._issue()
        response = self._submit(certificate.reference, '4567')
        token = response.url.rstrip('/').split('/')[-1]
        self.assertEqual(self.url_open('/r/%s/file' % token).status_code, 404)
        self.assertNotIn('Download the sealed PDF', response.text)

    # ------------------------------------------------------------------
    # Reporting a mismatch
    # ------------------------------------------------------------------
    def test_reporting_a_mismatch_reaches_the_desk(self):
        certificate = self._issue()
        response = self._submit(certificate.reference, '4567')
        token = response.url.rstrip('/').split('/')[-1]
        reported = self.url_open('/r/%s/mismatch' % token, data={
            'csrf_token': self._csrf(response.text),
        })
        self.assertIn('has been told', reported.text)
        self.env.invalidate_all()
        self.assertTrue(
            certificate.attempt_ids.filtered(lambda a: a.outcome == 'mismatch'))
        self.assertTrue(
            certificate.activity_ids,
            "A paper that does not match is a job for someone, not a log line.")

    # ------------------------------------------------------------------
    # Language
    # ------------------------------------------------------------------
    def _activate_french(self):
        self.env['res.lang']._activate_lang('fr_FR')
        self.env['ir.module.module'].search(
            [('name', '=', 'dms_certify_portal')])._update_translations(['fr_FR'])
        self.env.flush_all()

    def test_the_portal_speaks_french_when_asked(self):
        """No http_routing here, so no /fr/ prefix: the choice rides a query
        parameter and then sticks to the session."""
        self._activate_french()
        response = self.url_open('/?lang=fr')
        self.assertIn('Vérifier le document', response.text)
        self.assertIn('Un document présenté à votre guichet', response.text)
        self.assertNotIn('Verify document', response.text)

    def test_the_language_sticks_for_the_rest_of_the_visit(self):
        self._activate_french()
        self.url_open('/?lang=fr')
        later = self.url_open('/')
        self.assertIn('Vérifier le document', later.text)

    def test_a_french_verdict_is_french_all_through(self):
        self._activate_french()
        certificate = self._issue()
        self.url_open('/?lang=fr')
        response = self._submit(certificate.reference, '4567')
        self.assertIn('Document authentique', response.text)
        self.assertIn('Le document tel qu’émis', response.text)

    def test_a_french_refusal_uses_the_translated_message(self):
        """The generic refusal comes from Python, not the template, and Odoo's
        exporter does not walk Python source — so this is what proves the
        odoo-python entries in fr.po are actually being loaded."""
        self._activate_french()
        certificate = self._issue()
        self.url_open('/?lang=fr')
        response = self._submit(certificate.reference, '9999')
        self.assertIn('ne dirons pas lequel des deux', response.text)

    def test_an_unknown_language_falls_back_instead_of_breaking(self):
        response = self.url_open('/?lang=xx')
        self.assertEqual(response.status_code, 200)
        self.assertIn('Verify document', response.text)

    def test_the_designed_typefaces_are_requested(self):
        """Loaded from the CDN by an explicit decision. Each family keeps a
        local stack behind it, so a network that blocks the request still gets
        a readable page."""
        response = self.url_open('/')
        self.assertIn('fonts.googleapis.com', response.text)
        self.assertIn('Cormorant+Garamond', response.text)
        self.assertIn('display=swap', response.text)

    def test_the_language_switcher_is_offered(self):
        """Installing the module activates the languages it ships copy for —
        otherwise the switcher has nothing to switch to and the French sits in
        the file, unreachable."""
        response = self.url_open('/')
        self.assertIn('class="p-lang"', response.text)
        self.assertIn('href="/?lang=fr"', response.text)
        self.assertIn('href="/?lang=en"', response.text)

    def test_the_switcher_offers_only_languages_the_portal_speaks(self):
        """A back office running in six languages must not offer an embassy
        six buttons, five of which lead to an English page."""
        self.env['res.lang']._activate_lang('nl_NL')
        response = self.url_open('/')
        self.assertIn('href="/?lang=fr"', response.text)
        self.assertNotIn('?lang=nl', response.text)

    # ------------------------------------------------------------------
    # Whose portal it is
    # ------------------------------------------------------------------
    def test_the_portal_presents_the_configured_company(self):
        """A public request resolves to whatever company the public user
        happens to default to, which is nobody's decision."""
        company = self.env['res.company'].create({
            'name': 'Interport Crew Services',
            'email': 'ops@interportfrance.fr',
            'phone': '+33 2 35 00 00 00',
            'street': '52 rue de la République',
            'zip': '76700',
            'city': 'Harfleur',
        })
        self.env['ir.config_parameter'].sudo().set_param(
            'dms_certify_portal.company_id', str(company.id))

        response = self.url_open('/')
        self.assertIn('Interport Crew Services', response.text)
        self.assertIn('ops@interportfrance.fr', response.text)
        self.assertIn('Harfleur', response.text)

    def test_an_unset_company_falls_back_instead_of_breaking(self):
        self.env['ir.config_parameter'].sudo().set_param(
            'dms_certify_portal.company_id', '')
        response = self.url_open('/')
        self.assertEqual(response.status_code, 200)
        self.assertIn(self.env.company.name, response.text)

    def test_a_deleted_company_falls_back_instead_of_breaking(self):
        self.env['ir.config_parameter'].sudo().set_param(
            'dms_certify_portal.company_id', '999999')
        response = self.url_open('/')
        self.assertEqual(response.status_code, 200)
        self.assertIn(self.env.company.name, response.text)


@tagged('post_install', '-at_install')
class TestPortalHost(HttpCase):
    """The portal exists on check.<host> and nowhere else, and its host
    serves the portal and nothing else.

    nginx says the same thing, but nginx is not in front of a test run, and a
    misconfigured proxy is exactly when this is the only lock left.
    """

    def _check(self, url, **kwargs):
        return self.url_open(url, headers={'Host': CHECK_HOST}, **kwargs)

    # -- the plain host ------------------------------------------------
    def test_the_plain_host_does_not_serve_the_portal(self):
        response = self.url_open('/')
        self.assertNotIn('name="passport"', response.text)

    def test_the_internal_namespace_is_closed_on_the_plain_host(self):
        for path in ('/_check', '/_check/d/ICS-2026-DKK-0000-00',
                     '/_check/r/nope', '/_check/r/nope/file'):
            self.assertEqual(
                self.url_open(path).status_code, 404,
                "%s answered on the ERP host." % path)

    # -- the check host ------------------------------------------------
    def test_the_internal_namespace_is_not_addressable_on_the_check_host(self):
        """Only the rewrite reaches /_check; typing it gets /_check/_check."""
        self.assertEqual(self._check('/_check').status_code, 404)

    def test_the_back_office_does_not_exist_on_the_check_host(self):
        for path in ('/web/login', '/odoo', '/web',
                     '/web/database/manager', '/web/database/selector'):
            response = self._check(path, allow_redirects=False)
            self.assertEqual(
                response.status_code, 404,
                "%s answered on the portal host." % path)

    def test_the_portal_assets_are_served_on_the_check_host(self):
        """/web/assets/ is the one back-office path let through. If that ever
        stops, the page renders unstyled and without its input mask — and
        still returns 200, so nothing else here would notice."""
        page = self._check('/').text
        found = re.findall(r'(?:href|src)="(/web/assets/[^"]+)"', page)
        self.assertTrue(found, "The portal page references no asset bundle.")
        for url in found:
            self.assertEqual(
                self._check(url).status_code, 200,
                "%s is referenced by the page but not served." % url)
