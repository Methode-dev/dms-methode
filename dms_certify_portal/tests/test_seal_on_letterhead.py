# -*- coding: utf-8 -*-
"""The seal on a page printed on a letterhead.

A letterhead is a full-page image behind the text, with a dark band at the
foot kept free for the seal. Two things follow:

* the image covers the seal's corner by definition, and must not count as
  something already printed there — or every such letter would be shrunk to
  make room for a seal whose place was reserved for it;
* the seal sits on the band itself, so its text is printed light, and bold
  enough to read there. The QR keeps its own white quiet zone.

    make test m=dms_certify_portal t=/dms_certify_portal:TestSealOnLetterhead
"""
import pymupdf

from odoo.addons.dms_certify_portal.tools import seal as sealing
from odoo.tests.common import BaseCase, tagged

NAVY = (31, 45, 79)


def _page_on(color):
    """A one-page PDF whose whole sheet is an image of *color*, with a line of
    text at the head, the way a letter on a letterhead is laid out."""
    doc = pymupdf.open()
    page = doc.new_page(width=595, height=842)
    pix = pymupdf.Pixmap(pymupdf.csRGB, pymupdf.IRect(0, 0, 60, 84), False)
    pix.set_rect(pix.irect, color)
    page.insert_image(page.rect, pixmap=pix)
    page.insert_text((60, 120), 'LETTER OF INVITATION', fontsize=14)
    return doc.tobytes()


def _spec(pdf):
    return sealing.SealSpec(
        reference='LEH-2026-0042',
        verify_url='https://verify.example.com/v/LEH-2026-0042',
        source_hash=sealing.fingerprint(pdf),
        company_name='Example', watermark_text='Certified original')


def _span(pdf, text):
    """The largest span printing *text*: the seal block's, not the microtext
    border, which repeats the reference in 1 pt grey."""
    spans = [
        span
        for block in pymupdf.open(stream=pdf, filetype='pdf')[-1].get_text('dict')['blocks']
        for line in block.get('lines', ())
        for span in line['spans']
        if text in span['text']
    ]
    return max(spans, key=lambda span: span['size'], default=None)


@tagged('post_install', '-at_install')
class TestSealOnLetterhead(BaseCase):

    def test_a_full_page_image_does_not_occupy_the_corner(self):
        page = pymupdf.open(stream=_page_on(NAVY), filetype='pdf')[0]
        self.assertTrue(sealing._corner_is_free(page, 'br'))

    def test_the_page_is_not_shrunk_for_the_seal(self):
        pdf = _page_on(NAVY)
        sealed = pymupdf.open(stream=sealing.seal(pdf, _spec(pdf)), filetype='pdf')[0]
        head = sealed.search_for('LETTER OF INVITATION')[0]
        original = pymupdf.open(stream=pdf, filetype='pdf')[0].search_for(
            'LETTER OF INVITATION')[0]
        self.assertAlmostEqual(head.x0, original.x0, delta=0.5)
        self.assertAlmostEqual(head.y0, original.y0, delta=0.5)

    def test_on_a_dark_band_the_text_is_white_and_bold(self):
        pdf = _page_on(NAVY)
        reference = _span(sealing.seal(pdf, _spec(pdf)), 'LEH-2026-0042')
        self.assertEqual(reference['color'], 0xFFFFFF)
        self.assertIn('Bold', reference['font'])
        url = _span(sealing.seal(pdf, _spec(pdf)), 'verify.example.com')
        self.assertEqual(url['color'], 0xFFFFFF)
        self.assertIn('Bold', url['font'])

    def test_on_a_white_page_it_keeps_its_ink(self):
        pdf = _page_on((255, 255, 255))
        reference = _span(sealing.seal(pdf, _spec(pdf)), 'LEH-2026-0042')
        # SEAL_INK, give or take the rounding to 8-bit channels.
        self.assertLess(reference['color'] >> 16, 0x20)
        self.assertLess(reference['color'] & 0xFF, 0x60)
