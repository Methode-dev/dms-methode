# -*- coding: utf-8 -*-
"""The certificate chatter, driven in a real browser.

``TestChatterTemplate`` proves the xpaths locate what they claim to in the
``mail.Chatter`` source. It cannot prove the browser applies them, nor that the
form picks up ``CertificateChatter`` at all — both happen client-side, and a
primary-inherit template whose parent moved fails there, silently, with the
chatter simply missing.

Needs a headless Chrome on PATH; the image installs one (see Dockerfile).
Without it Odoo raises SkipTest and this reports as skipped rather than failed.

    make test m=dms_certify_portal t=dms_certify_portal

On a database that also has ``outlook_chatter_theme``, that module swaps the
chatter on *every* form and its assets load after ours, which is why
``form_renderer_patch.js`` re-asserts the choice at render time rather than in
``setup()``. The theme is not a dependency and so is absent from the test
database, but the race can be run on demand — and was, both ways:

    make test m=dms_certify_portal,outlook_chatter_theme \
        t=/dms_certify_portal:TestCertificateChatterTour

passes as written, and fails ("A Send message button ... is on the certificate
chatter") the moment the override is moved back into ``setup()``.
"""
from odoo.tests import HttpCase, new_test_user, tagged

from .test_certificate import CREW, build_pdf


@tagged('post_install', '-at_install')
class TestCertificateChatterTour(HttpCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.tour_user = new_test_user(
            cls.env, login='certify_chatter_tour', password='Password!1',
            groups='base.group_user,dms_certify_portal.group_certify_manager')

        doc_type = cls.env['dms.certificate.type'].create({
            'name': 'Letter of Invitation',
            'code': 'tour_letter',
        })
        attachment = cls.env['ir.attachment'].create({
            'name': 'loi.pdf',
            'raw': build_pdf(),
            'mimetype': 'application/pdf',
        })
        cls.certificate = cls.env['dms.certificate'].issue(
            {'type_id': doc_type.id,
             'movement_date': '2026-09-03',
             'source_attachment_id': attachment.id},
            holders=[dict(member) for member in CREW],
        )

    def test_the_issuer_cannot_post_into_a_certificate_thread(self):
        self.start_tour(
            '/odoo/action-dms_certify_portal.action_dms_certificate',
            'dms_certify_portal_chatter_tour',
            login='certify_chatter_tour',
        )

    def _layout_tour(self, name, size):
        """Run *name* against the certificate form at *size*.

        Read when the browser starts, which is inside start_tour, so a test can
        choose its own viewport — and this pair has to, because which side of
        the sheet the page lands on is decided by the screen: FormController
        adds o_xxl_form_view, and with it the flex row, only at SIZES.XXL.
        """
        self.browser_size = size
        self.start_tour(
            '/odoo/dms.certificate/%d' % self.certificate.id, name,
            login='certify_chatter_tour')

    def test_the_stamped_page_sits_beside_the_sheet(self):
        self._layout_tour('dms_certify_portal_preview_aside_tour', '1920x1080')

    def test_the_stamped_page_stacks_under_a_narrow_screen(self):
        self._layout_tour('dms_certify_portal_preview_below_tour', '1366x768')
