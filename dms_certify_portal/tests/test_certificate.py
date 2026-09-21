# -*- coding: utf-8 -*-
"""What sealing and verification are supposed to guarantee.

These assert the promises the public page makes to an embassy agent, not the
shape of the code: that a reference alone opens nothing, that the fingerprint
printed on the paper is the fingerprint of the paper, that a redacted copy
carries no crew identity, and that guessing at one reference stops working.
"""

import base64
import hashlib
import io
import re

import pymupdf
from PIL import Image
from lxml import etree

from odoo.exceptions import AccessError, UserError

from odoo.addons.dms_certify_portal.tools import seal as sealing
from odoo.tests.common import TransactionCase, tagged

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


@tagged('post_install', '-at_install')
class TestCertificate(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.doc_type = cls.env['dms.certificate.type'].create({
            'name': 'Letter of Invitation',
            'code': 'test_letter',
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

    # ------------------------------------------------------------------
    # The reference
    # ------------------------------------------------------------------
    def test_reference_has_the_printed_shape(self):
        certificate = self._issue()
        self.assertRegex(
            certificate.reference,
            r'^ICS-\d{4}-[A-Z0-9]{3}-[0-9A-Z]{4}-[0-9A-Z]{2}$',
            "The reference is what an agent retypes; its shape is part of the "
            "portal's input mask.")

    def test_reference_never_uses_the_ambiguous_letters(self):
        """The public page promises I, L, O and U are never used."""
        references = ''.join(
            self.Certificate._generate_reference('DKK') for _i in range(60))
        body = references.replace('ICS-', '').replace('DKK', '')
        for letter in 'ILOU':
            self.assertNotIn(letter, body)

    def test_reference_carries_no_counter(self):
        """Two consecutive references must not be adjacent: a counter would
        leak how many documents were issued between them."""
        first = self.Certificate._generate_reference('DKK')
        second = self.Certificate._generate_reference('DKK')
        self.assertNotEqual(first, second)
        self.assertNotEqual(first.split('-')[-2], second.split('-')[-2])

    def test_place_code_lands_in_the_reference(self):
        self.assertIn('-DKK-', self.Certificate._generate_reference('DKK'))

    # ------------------------------------------------------------------
    # Sealing
    # ------------------------------------------------------------------
    def test_certifying_seals_the_document_and_leaves_the_source_alone(self):
        certificate = self._issue()
        self.assertEqual(certificate.state, 'certified')
        self.assertTrue(certificate.sealed_attachment_id)
        self.assertEqual(
            self.attachment.raw, self.raw,
            "The document the operator produced is never written to.")
        self.assertNotEqual(certificate.sealed_attachment_id.raw, self.raw)

    def test_printed_fingerprint_is_of_the_document_before_sealing(self):
        """A file cannot contain its own hash, so the value printed on the page
        is the hash of the document as produced."""
        certificate = self._issue()
        self.assertEqual(certificate.source_hash,
                         hashlib.sha256(self.raw).hexdigest())
        self.assertEqual(
            certificate.sealed_hash,
            hashlib.sha256(certificate.sealed_attachment_id.raw).hexdigest())
        self.assertNotEqual(certificate.source_hash, certificate.sealed_hash)

    def test_the_reference_is_printed_on_the_sealed_page(self):
        certificate = self._issue()
        document = pymupdf.open(
            stream=certificate.sealed_attachment_id.raw, filetype='pdf')
        text = document[0].get_text()
        document.close()
        self.assertIn(certificate.reference, text)
        self.assertIn(certificate.source_hash[:12], text)

    def test_re_stamping_keeps_the_reference(self):
        """A new marking is a new seal on the same issued document, not a new
        document: the reference on paper already in circulation must hold."""
        certificate = self._issue()
        reference, issued = certificate.reference, certificate.issued_on
        certificate.write({'seal_marking': 'copy'})
        certificate.action_certify()
        self.assertEqual(certificate.reference, reference)
        self.assertEqual(certificate.issued_on, issued)

    def test_a_revoked_document_cannot_be_re_sealed(self):
        certificate = self._issue()
        certificate.action_revoke(reason='Movement cancelled')
        with self.assertRaises(UserError):
            certificate.action_certify()

    def test_a_document_with_nobody_listed_cannot_be_certified(self):
        certificate = self.Certificate.create({
            'type_id': self.doc_type.id,
            'source_attachment_id': self.attachment.id,
        })
        with self.assertRaises(UserError):
            certificate.action_certify()

    # ------------------------------------------------------------------
    # Redaction
    # ------------------------------------------------------------------
    def test_confirm_only_shows_the_person_checked_and_hides_the_rest(self):
        certificate = self._issue(disclosure='confirm')
        matched = certificate.holder_ids[0]

        document = pymupdf.open(
            stream=certificate._public_bytes(matched), filetype='pdf')
        text = document[0].get_text()
        document.close()

        self.assertIn(CREW[0]['name'], text,
                      "The agent has to be able to compare the line they are "
                      "checking against the paper in front of them.")
        self.assertIn(CREW[0]['passport_number'], text)
        self.assertNotIn(CREW[1]['name'], text)
        self.assertNotIn(CREW[1]['passport_number'], text)
        self.assertIn(certificate.reference, text)

    def test_each_person_gets_their_own_view_of_the_page(self):
        certificate = self._issue(disclosure='confirm')
        for index, holder in enumerate(certificate.holder_ids):
            document = pymupdf.open(
                stream=certificate._public_bytes(holder), filetype='pdf')
            text = document[0].get_text()
            document.close()
            for other, member in enumerate(CREW):
                if other == index:
                    self.assertIn(member['passport_number'], text)
                else:
                    self.assertNotIn(member['passport_number'], text)

    def test_nothing_but_the_crew_is_redacted(self):
        """The needles are only ever a person's own details, so the voyage the
        agent is checking against survives."""
        certificate = self._issue(disclosure='confirm')
        document = pymupdf.open(
            stream=certificate._public_bytes(certificate.holder_ids[0]),
            filetype='pdf')
        text = document[0].get_text()
        document.close()
        self.assertIn('LETTER OF INVITATION', text)

    def test_the_page_image_is_rendered_fine_enough_to_read(self):
        """The stamp's QR is 18 mm square and needs roughly 3 pixels per module
        to decode. At the old 110 dpi that came to 2.0-2.2 — unscannable."""
        certificate = self._issue(disclosure='full')
        certificate.certify()
        png = certificate._public_page_image(0)
        width, height = Image.open(io.BytesIO(png)).size

        expected = 8.27 * 200  # A4 width in inches, at the portal's dpi
        self.assertGreater(width, expected * 0.95)
        self.assertGreater(height, width)

        qr_px = 18 / 25.4 * 200
        self.assertGreater(
            qr_px / 39, 3.0,
            "39 modules is the longest verify URL we produce; below three "
            "pixels each, no reader decodes it.")

    def test_redactions_are_black(self):
        """Grey invites the reader to wonder whether the page printed badly."""
        certificate = self._issue(disclosure='confirm')
        matched, other = certificate.holder_ids[0], certificate.holder_ids[1]

        _name, raw = certificate._certify_source()
        boxes = other._boxes(sealing.fingerprint(raw))
        self.assertTrue(boxes, "The other holder has to have been measured.")

        document = pymupdf.open(
            stream=certificate._public_bytes(matched), filetype='pdf')
        page = document[0]
        pixmap = page.get_pixmap(dpi=72)
        box = boxes[0]['r']
        pixel = pixmap.pixel(int((box[0] + box[2]) / 2), int((box[1] + box[3]) / 2))
        document.close()

        self.assertEqual(
            pixel[:3], (0, 0, 0),
            "The middle of a redacted box should be black, not %s." % (pixel,))

    def test_a_lookup_with_no_person_hides_everybody(self):
        certificate = self._issue(disclosure='confirm')
        document = pymupdf.open(
            stream=certificate._public_bytes(), filetype='pdf')
        text = document[0].get_text()
        document.close()
        for member in CREW:
            self.assertNotIn(member['passport_number'], text)

    def test_stale_positions_fall_back_to_searching(self):
        """Measurements belong to one version of a document. Point the
        certificate at another and they describe the wrong places — so the
        lookup searches for the values instead, and the page is still safe."""
        certificate = self._issue(disclosure='confirm')
        certificate.holder_ids.sudo().write({'boxes_source_hash': 'stale'})

        document = pymupdf.open(
            stream=certificate._public_bytes(certificate.holder_ids[0]),
            filetype='pdf')
        text = document[0].get_text()
        document.close()

        self.assertIn(CREW[0]['passport_number'], text)
        self.assertNotIn(CREW[1]['passport_number'], text)
        self.assertNotIn(CREW[1]['name'], text)

    def test_a_document_with_no_positions_recorded_is_still_safe(self):
        """Nothing measured at all — an entry created by hand rather than by a
        producing module. The values are there to search for."""
        certificate = self.Certificate.create({
            'type_id': self.doc_type.id,
            'disclosure': 'confirm',
            'source_attachment_id': self.attachment.id,
            'holder_ids': [(0, 0, dict(member)) for member in CREW],
        })
        certificate.certify()

        document = pymupdf.open(
            stream=certificate._public_bytes(certificate.holder_ids[0]),
            filetype='pdf')
        text = document[0].get_text()
        document.close()
        self.assertNotIn(CREW[1]['passport_number'], text)

    def test_a_page_that_still_leaks_is_not_served(self):
        """The last line of defence: whatever the redaction did, the result is
        checked against what is stored before anybody sees it."""
        certificate = self._issue(disclosure='confirm')
        other = certificate.holder_ids[1]
        # Measured boxes that point nowhere, and a value search that cannot
        # match either, so the leak check is the only thing left.
        certificate.holder_ids.sudo().write({'redaction_boxes': '[]'})
        other.sudo().write({'name': 'Nobody', 'first_name': False})

        self.assertEqual(
            certificate._public_bytes(certificate.holder_ids[0]), b'',
            "A page with somebody's passport still on it must not be served.")

    # ------------------------------------------------------------------
    # Matching
    # ------------------------------------------------------------------
    def test_the_reference_alone_opens_nothing(self):
        certificate = self._issue()
        found, holder = self.Certificate._match(certificate.reference, '')
        self.assertFalse(found)
        self.assertFalse(holder)

    def test_any_listed_person_opens_the_document(self):
        certificate = self._issue(second_factor='ppt4')
        for member in CREW:
            found, holder = self.Certificate._match(
                certificate.reference, member['passport_number'][-4:])
            self.assertEqual(found, certificate)
            self.assertEqual(holder.name, member['name'])

    def test_separators_and_case_do_not_decide_the_outcome(self):
        certificate = self._issue()
        typed = certificate.reference.lower().replace('-', ' ')
        found, _holder = self.Certificate._match(typed, '4567')
        self.assertEqual(found, certificate)

    def test_a_passport_from_another_document_does_not_open_it(self):
        certificate = self._issue()
        found, _holder = self.Certificate._match(certificate.reference, '9999')
        self.assertFalse(found)

    def test_an_unknown_reference_opens_nothing(self):
        found, _holder = self.Certificate._match('ICS-2026-DKK-0000-00', '4567')
        self.assertFalse(found)

    def test_a_draft_is_not_verifiable(self):
        certificate = self.Certificate.create({
            'type_id': self.doc_type.id,
            'holder_ids': [(0, 0, dict(CREW[0]))],
        })
        found, _holder = self.Certificate._match(certificate.reference, '4567')
        self.assertFalse(found, "Nothing is printed yet, so nobody holds it.")

    def test_a_revoked_document_still_verifies_and_says_it_is_revoked(self):
        certificate = self._issue()
        certificate.action_revoke(reason='Crew change before departure')
        found, _holder = self.Certificate._match(certificate.reference, '4567')
        self.assertEqual(found, certificate)
        self.assertEqual(found.public_state, 'revoked')

    def test_switching_the_second_check_needs_no_re_entry(self):
        """Every mode is hashed up front, so an issuer can tighten a document
        without the crew having to be typed again."""
        certificate = self._issue(second_factor='ppt4')
        certificate.second_factor = 'pptfull'
        found, holder = self.Certificate._match(
            certificate.reference, 'MB1234567')
        self.assertEqual(found, certificate)
        self.assertEqual(holder.name, 'Shwe Moung')
        short, _none = self.Certificate._match(certificate.reference, '4567')
        self.assertFalse(short)

    def test_date_of_birth_mode(self):
        certificate = self._issue(second_factor='dob')
        found, holder = self.Certificate._match(certificate.reference, '06021990')
        self.assertEqual(found, certificate)
        self.assertEqual(holder.name, 'Shwe Moung')

    def test_the_passport_number_reads_back(self):
        """Stored deliberately: the same numbers are already inside the sealed
        PDF and on the crew contact, and an operator correcting a mistyped one
        has to be able to see what is there."""
        certificate = self._issue()
        holder = certificate.holder_ids[0]
        self.assertEqual(holder.passport_number, 'MB1234567')

    def test_matching_still_goes_through_the_hashes(self):
        """Storing the number must not turn the lookup into a plaintext
        comparison: the hashes are what a lookup is checked against."""
        certificate = self._issue()
        holder = certificate.holder_ids[0]
        self.assertTrue(holder.passport_hash)
        self.assertTrue(holder.passport4_hash)
        self.assertNotEqual(holder.passport_hash, holder.passport_number)

        holder.passport_number = 'ZZ9998887'
        found, matched = self.Certificate._match(certificate.reference, '8887')
        self.assertEqual(found, certificate)
        self.assertEqual(matched, holder,
                         "Correcting the number has to move the hashes with it.")

    def test_reading_a_passport_needs_more_than_agent_access(self):
        agent = self.env['res.users'].create({
            'name': 'Counter agent',
            'login': 'certify-agent-test',
            'group_ids': [(6, 0, [
                self.env.ref('dms_certify_portal.group_certify_user').id,
                self.env.ref('base.group_user').id,
            ])],
        })
        holder = self._issue().holder_ids[0]
        with self.assertRaises(AccessError):
            holder.with_user(agent).read(['passport_number'])

    def test_the_hashes_are_keyed_to_this_instance(self):
        """Four characters would fall to a wordlist in milliseconds if the
        digest were unkeyed. The pepper is what makes hashing them worth it."""
        holder = self._issue().holder_ids[0]
        plain = hashlib.sha256('4567'.encode()).hexdigest()
        self.assertNotEqual(holder.passport4_hash, plain)

    # ------------------------------------------------------------------
    # Throttling
    # ------------------------------------------------------------------
    def test_guessing_at_one_reference_locks_it(self):
        certificate = self._issue()
        Attempt = self.env['dms.certificate.attempt']
        key = self.Certificate._normalize_reference(certificate.reference)
        self.assertFalse(Attempt.is_reference_locked(key))
        for index in range(5):
            Attempt.log(key, '198.51.100.%d' % index, 'agent', outcome='no_match')
        self.assertTrue(
            Attempt.is_reference_locked(key),
            "The lock counts across addresses: moving to another one is "
            "exactly what an attacker would do.")

    def test_a_successful_lookup_does_not_count_against_the_reference(self):
        certificate = self._issue()
        Attempt = self.env['dms.certificate.attempt']
        key = self.Certificate._normalize_reference(certificate.reference)
        for _index in range(8):
            Attempt.log(key, '198.51.100.7', 'agent',
                        outcome='matched', document=certificate)
        self.assertFalse(Attempt.is_reference_locked(key))

    # ------------------------------------------------------------------
    # What the public page receives
    # ------------------------------------------------------------------
    def test_public_values_redact_the_crew_in_confirm_mode(self):
        certificate = self._issue(disclosure='confirm')
        _found, holder = self.Certificate._match(certificate.reference, '4567')
        values = certificate._get_public_values(holder)
        self.assertEqual(values['crew'], [])
        self.assertEqual(values['holder_count'], 2)
        self.assertEqual(values['matched']['surname'], 'Shwe Moung')
        self.assertNotIn('MB1234567', str(values))

    def test_public_values_list_the_crew_in_full_mode(self):
        certificate = self._issue(disclosure='full')
        values = certificate._get_public_values()
        self.assertEqual(len(values['crew']), 2)
        self.assertNotIn('MB1234567', str(values),
                         "Even full disclosure shows the page, not the "
                         "registry: passports are not stored to show.")

    def test_public_values_are_plain_data(self):
        certificate = self._issue()
        for value in certificate._get_public_values().values():
            self.assertNotIsInstance(
                value, type(certificate),
                "A recordset in here is a template one dot away from a leak.")

    def test_facts_travel_as_given(self):
        certificate = self._issue(
            facts_json='[{"label": "Vessel", "value": "M/V MADDOX"}]')
        values = certificate._get_public_values()
        self.assertEqual(values['facts'],
                         [{'label': 'Vessel', 'value': 'M/V MADDOX'}])

    # ------------------------------------------------------------------
    # Validity
    # ------------------------------------------------------------------
    def test_validity_counts_from_the_movement_date(self):
        certificate = self._issue(validity_days='90')
        self.assertEqual(str(certificate.valid_until), '2026-12-02')

    def test_until_revoked_leaves_no_expiry(self):
        certificate = self._issue(validity_days='0')
        self.assertFalse(certificate.valid_until)
        self.assertEqual(certificate.public_state, 'valid')

    def test_an_out_of_date_document_reads_as_expired_not_missing(self):
        certificate = self._issue(movement_date='2024-01-10', validity_days='30')
        self.assertEqual(certificate.public_state, 'expired')
        found, _holder = self.Certificate._match(certificate.reference, '4567')
        self.assertEqual(
            found, certificate,
            "Telling an embassy a document is genuine but expired beats "
            "telling them it does not exist.")

    def test_an_issued_document_cannot_be_deleted(self):
        certificate = self._issue()
        with self.assertRaises(UserError):
            certificate.unlink()

    def test_the_verify_url_uses_the_public_base_url(self):
        self.env['ir.config_parameter'].sudo().set_param(
            'dms_certify_portal.public_base_url', 'https://verify.example.com/')
        certificate = self._issue()
        self.assertEqual(
            certificate.verify_url,
            'https://verify.example.com/verify/d/%s' % certificate.reference)
        self.assertTrue(re.match(r'^https://', certificate.verify_url))


@tagged('post_install', '-at_install')
class TestCertificateDesk(TransactionCase):
    """The issuing screen: what the operator sees and what the desk is told."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.doc_type = cls.env['dms.certificate.type'].create({
            'name': 'Letter of Invitation',
            'code': 'test_letter',
        })
        cls.Certificate = cls.env['dms.certificate']
        cls.raw = build_pdf()
        cls.attachment = cls.env['ir.attachment'].create({
            'name': 'loi.pdf',
            'datas': base64.b64encode(cls.raw),
            'mimetype': 'application/pdf',
        })

    def _draft(self, **overrides):
        values = {
            'type_id': self.doc_type.id,
            'movement_date': '2026-09-03',
            'source_attachment_id': self.attachment.id,
            'holder_ids': [(0, 0, dict(member)) for member in CREW],
        }
        values.update(overrides)
        return self.Certificate.create(values)

    def _certified(self, **overrides):
        certificate = self._draft(**overrides)
        certificate.stash_redaction({
            holder.id: [CREW[index]['passport_number']]
            for index, holder in enumerate(certificate.holder_ids)
        })
        certificate.certify()
        return certificate

    # ------------------------------------------------------------------
    # Preview
    # ------------------------------------------------------------------
    def test_preview_is_the_sealed_pdf_not_a_picture_of_it(self):
        """A rasterised preview cannot stay sharp when the operator zooms in
        to check a stamp; the document itself can."""
        certificate = self._draft()
        self.assertTrue(certificate.preview_pdf)
        self.assertEqual(
            base64.b64decode(certificate.preview_pdf)[:5], b'%PDF-')

    def test_preview_renders_before_anything_is_certified(self):
        """The marking is chosen by looking at the result, which means the
        preview has to work on a draft."""
        certificate = self._draft()
        self.assertEqual(certificate.state, 'draft')
        document = pymupdf.open(
            stream=base64.b64decode(certificate.preview_pdf), filetype='pdf')
        text = document[0].get_text()
        document.close()
        self.assertIn(certificate.reference, text,
                      "The preview shows what the marking would produce, "
                      "reference and all.")

    def test_preview_follows_the_marking(self):
        certificate = self._draft(seal_marking='certified')
        first = certificate.preview_pdf
        certificate.seal_marking = 'void'
        certificate.invalidate_recordset(['preview_pdf'])
        self.assertNotEqual(first, certificate.preview_pdf)

        document = pymupdf.open(
            stream=base64.b64decode(certificate.preview_pdf), filetype='pdf')
        text = document[0].get_text()
        document.close()
        self.assertIn('VOID', text)

    def test_preview_survives_a_document_it_cannot_read(self):
        """A broken preview must never be what stops someone opening the form."""
        broken = self.env['ir.attachment'].create({
            'name': 'not-a.pdf',
            'datas': base64.b64encode(b'this is not a pdf'),
            'mimetype': 'application/pdf',
        })
        certificate = self._draft(source_attachment_id=broken.id)
        self.assertFalse(certificate.preview_pdf)

    # ------------------------------------------------------------------
    # What the desk is told
    # ------------------------------------------------------------------
    def test_certifying_posts_the_reference_and_the_rules(self):
        certificate = self._certified(second_factor='ppt4', disclosure='confirm')
        body = certificate.message_ids[0].body
        self.assertIn(certificate.reference, body)
        self.assertIn(certificate.source_hash[:16], body)
        self.assertIn('redacted', body)

    def test_re_stamping_says_the_sent_copies_still_verify(self):
        certificate = self._certified()
        before = len(certificate.message_ids)
        certificate.seal_marking = 'copy'
        certificate.action_certify()
        self.assertGreater(len(certificate.message_ids), before)
        self.assertIn('unchanged', certificate.message_ids[0].body)

    def test_a_lookup_is_reported_as_an_external_user(self):
        certificate = self._certified()
        certificate._notify_verification('matched')
        body = certificate.message_ids[0].body
        self.assertIn('An external user', body)
        self.assertIn(certificate.reference, body)

    def test_routine_lookups_stay_quiet_when_notifications_are_off(self):
        certificate = self._certified(notify_on_lookup=False)
        before = len(certificate.message_ids)
        certificate._notify_verification('matched')
        self.assertEqual(len(certificate.message_ids), before)

    def test_a_lockout_reaches_the_desk_even_with_notifications_off(self):
        certificate = self._certified(notify_on_lookup=False)
        before = len(certificate.message_ids)
        certificate._notify_verification('locked', minutes=30)
        self.assertGreater(len(certificate.message_ids), before)
        self.assertIn('locked out', certificate.message_ids[0].body)

    def test_a_reported_mismatch_lands_on_someones_plate(self):
        certificate = self._certified(notify_on_lookup=False)
        certificate._notify_verification('mismatch')
        self.assertTrue(
            certificate.activity_ids,
            "A paper that does not match is not a log line, it is a job.")

    def test_the_requester_is_never_named_or_addressed(self):
        certificate = self._certified()
        attempt = self.env['dms.certificate.attempt'].log(
            certificate.reference_key, '203.0.113.9', 'Mozilla',
            outcome='matched', document=certificate)
        self.assertEqual(attempt.requester_label, 'An external user')
        self.assertNotIn('203.0.113.9', attempt.requester_label)
        self.assertEqual(
            attempt.ip_address, '203.0.113.9',
            "Still recorded: the rate limit and the audit trail both need it.")

    # ------------------------------------------------------------------
    # Revocation
    # ------------------------------------------------------------------
    def test_revoking_restamps_the_stored_copy_as_void(self):
        certificate = self._certified()
        certificate.action_revoke(reason='Crew change before departure')
        self.assertEqual(certificate.seal_marking, 'void')
        document = pymupdf.open(
            stream=certificate.sealed_attachment_id.raw, filetype='pdf')
        text = document[0].get_text()
        document.close()
        self.assertIn('VOID', text)
        self.assertIn(
            certificate.reference, text,
            "It is still the same document, and still identifies itself.")

    def test_revoking_keeps_the_printed_fingerprint(self):
        """The paper in someone's hand cannot change, so the value printed on
        it must keep meaning what it meant."""
        certificate = self._certified()
        printed = certificate.source_hash
        certificate.action_revoke(reason='Superseded')
        self.assertEqual(certificate.source_hash, printed)

    def test_revoking_posts_the_reason_the_embassy_will_read(self):
        certificate = self._certified()
        certificate.action_revoke(reason='Movement cancelled by the operator')
        self.assertIn('Movement cancelled by the operator',
                      certificate.message_ids[0].body)

    def test_the_revoke_wizard_carries_the_reason_through(self):
        certificate = self._certified()
        wizard = self.env['dms.certificate.revoke'].with_context(
            active_model='dms.certificate', active_id=certificate.id
        ).create({'reason': 'Replaced by a later letter'})
        wizard.action_revoke()
        self.assertEqual(certificate.state, 'revoked')
        self.assertEqual(certificate.revoke_reason, 'Replaced by a later letter')

    # ------------------------------------------------------------------
    # Delivery
    # ------------------------------------------------------------------
    def test_sending_is_what_makes_it_delivered(self):
        certificate = self._certified()
        self.assertEqual(certificate.state, 'certified')
        certificate.with_context(dms_certify_delivery=True).message_post(
            body='Sent to the consulate', partner_ids=[])
        self.assertEqual(certificate.state, 'delivered')

    def test_an_ordinary_note_is_not_a_delivery(self):
        certificate = self._certified()
        certificate.message_post(body='Waiting on flight numbers')
        self.assertEqual(certificate.state, 'certified')

    def test_nothing_is_sent_or_downloaded_before_it_is_sealed(self):
        certificate = self._draft()
        with self.assertRaises(UserError):
            certificate.action_send_to_embassy()
        with self.assertRaises(UserError):
            certificate.action_download_sealed()

    def test_the_composer_opens_with_the_sealed_copy_attached(self):
        certificate = self._certified()
        action = certificate.action_send_to_embassy()
        context = action['context']
        self.assertEqual(context['default_attachment_ids'],
                         [(6, 0, certificate.sealed_attachment_id.ids)])
        self.assertTrue(context['dms_certify_delivery'])

    # ------------------------------------------------------------------
    # The screen itself
    # ------------------------------------------------------------------
    def test_the_chatter_sits_under_the_form_not_beside_it(self):
        """Left outside the sheet, Odoo's form compiler lifts the chatter into
        the right-hand aside — which is the space the stamped page needs."""
        view = self.env.ref('dms_certify_portal.view_dms_certificate_form')
        arch = etree.fromstring(view.arch)
        self.assertFalse(arch.xpath('/form/chatter'))
        self.assertTrue(arch.xpath('//sheet/chatter'))

    def test_the_source_picker_ignores_the_copies_we_generate(self):
        """The sealed and redacted copies are attachments too. Offering them
        as a source invites sealing a seal."""
        certificate = self._certified()
        domain = self.env['dms.certificate']._fields['source_attachment_id'].domain
        candidates = self.env['ir.attachment'].search(domain)
        self.assertIn(self.attachment, candidates)
        self.assertNotIn(certificate.sealed_attachment_id, candidates)

    # ------------------------------------------------------------------
    # Document types
    # ------------------------------------------------------------------
    def test_the_public_page_shows_the_type_s_name(self):
        kind = self.env['dms.certificate.type'].create(
            {'name': 'Letter of Invitation', 'code': 'test_loi'})
        certificate = self._draft(type_id=kind.id)
        self.assertEqual(
            certificate._get_public_values()['document_type'],
            'Letter of Invitation')

    def test_a_type_in_use_cannot_be_deleted(self):
        """Deleting one would leave issued documents unable to say what they
        are, on a page whose whole job is to say so."""
        kind = self.env['dms.certificate.type'].create(
            {'name': 'Temporary', 'code': 'test_temp'})
        self._draft(type_id=kind.id)
        with self.assertRaises(UserError):
            kind.unlink()

    def test_codes_are_unique(self):
        self.env['dms.certificate.type'].create(
            {'name': 'First', 'code': 'test_dup'})
        with self.assertRaises(Exception):
            with self.env.cr.savepoint():
                self.env['dms.certificate.type'].create(
                    {'name': 'Second', 'code': 'test_dup'})

    def test_settings_opens_showing_the_current_choice(self):
        Type = self.env['dms.certificate.type']
        ticked = Type.create({'name': 'On', 'code': 'test_on', 'auto_stamp': True})
        unticked = Type.create({'name': 'Off', 'code': 'test_off'})

        values = self.env['res.config.settings'].create({}).get_values()
        selected = values['certify_auto_stamp_type_ids'][0][2]

        self.assertIn(ticked.id, selected)
        self.assertNotIn(unticked.id, selected)

    def test_unticking_a_kind_survives_the_save(self):
        """Through create() and execute(), the way the client saves.

        Calling set_values() directly proves nothing: the bug this guards was
        that a non-stored computed field recomputed between the client's write
        and set_values() reading it, so an untick was quietly undone before
        anything reached the database.
        """
        Type = self.env['dms.certificate.type']
        kept = Type.create(
            {'name': 'Kept', 'code': 'test_kept', 'auto_stamp': True})
        dropped = Type.create(
            {'name': 'Dropped', 'code': 'test_dropped', 'auto_stamp': True})

        self.env['res.config.settings'].create({
            'certify_auto_stamp_type_ids': [(6, 0, kept.ids)],
        }).execute()

        self.assertTrue(kept.auto_stamp)
        self.assertFalse(
            dropped.auto_stamp,
            "Unticking a kind has to stick, not come back on the next save.")

    def test_ticking_a_kind_survives_the_save(self):
        Type = self.env['dms.certificate.type']
        kind = Type.create({'name': 'New', 'code': 'test_new'})

        self.env['res.config.settings'].create({
            'certify_auto_stamp_type_ids': [(6, 0, kind.ids)],
        }).execute()

        self.assertTrue(kind.auto_stamp)


@tagged('post_install', '-at_install')
class TestAssets(TransactionCase):
    """Our stylesheets have to survive Sass.

    A single bad declaration takes down the whole bundle, not just its own
    rule: `height: min(78vh, 900px)` once failed every backend asset in the
    database with "Incompatible units: 'px' and 'vh'", because Sass evaluates
    min() itself rather than leaving it to the browser. Nothing else in the
    suite compiles assets, so nothing else would notice.
    """

    def _compile(self, bundle):
        """Compile *bundle*, failing if Sass complained.

        Odoo does not raise on a bad stylesheet: it logs a warning and returns
        a bundle whose content *is* the error message, so the browser shows
        "Internal Error" and every other rule in it is gone. Asserting on the
        returned value therefore proves nothing — the log is the signal.
        """
        assets = self.env['ir.qweb']._get_asset_bundle(bundle, js=False)
        with self.assertNoLogs('odoo.addons.base.models.assetsbundle',
                               level='WARNING'):
            return assets.css()

    def test_the_backend_bundle_compiles(self):
        self.assertTrue(
            self._compile('web.assets_web'),
            "certificate_form.scss is in this bundle.")

    def test_the_frontend_bundle_compiles(self):
        self.assertTrue(
            self._compile('web.assets_frontend'),
            "verify.scss is in this bundle.")
