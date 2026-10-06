# -*- coding: utf-8 -*-
"""These render PDFs for real, and need no server answering on the side.

That is the whole point of the module: wkhtmltopdf fetches a report's
stylesheets back over HTTP, so a test that renders one needs a live HTTP
worker. Nothing here is an HttpCase.
"""

import pymupdf

from odoo.exceptions import UserError
from odoo.tests import TransactionCase, tagged

from ..tools.fetch import OdooUrlFetcher, UnfetchableUrl

PAGE = '<div class="page">%s</div>'


@tagged('post_install', '-at_install')
class TestWeasyprintRender(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.paperformat = cls.env['report.paperformat'].create({
            'name': "Probe A4",
            'format': 'A4',
            'orientation': 'Portrait',
            'margin_top': 5, 'margin_bottom': 10,
            'margin_left': 7, 'margin_right': 7,
            'header_spacing': 0,
        })
        cls.partner = cls.env['res.partner'].create({'name': "Probe Partner"})

    def _report(self, key, inner, layout='web.basic_layout', paperformat=None):
        self.env['ir.ui.view'].create({
            'name': key,
            'type': 'qweb',
            'key': 'report_weasyprint.%s' % key,
            'arch_db': '<t t-name="report_weasyprint.%s">'
                       '<t t-foreach="docs" t-as="o"><t t-call="%s">%s</t></t>'
                       '</t>' % (key, layout, inner),
        })
        return self.env['ir.actions.report'].create({
            'name': key,
            'model': 'res.partner',
            'report_type': 'qweb-pdf',
            'report_name': 'report_weasyprint.%s' % key,
            'report_file': 'report_weasyprint.%s' % key,
            'paperformat_id': (paperformat or self.paperformat).id,
            'use_weasyprint': True,
        })

    def _render(self, report):
        pdf, kind = self.env['ir.actions.report'].with_context(
            force_report_rendering=True)._render_qweb_pdf(
                report.report_name, self.partner.ids)
        self.assertEqual(kind, 'pdf')
        return pymupdf.open(stream=pdf, filetype='pdf')

    # ------------------------------------------------------------------
    # The page
    # ------------------------------------------------------------------
    def test_the_paperformat_becomes_the_page_box(self):
        document = self._render(self._report('probe_page', PAGE % '<p>hello</p>'))
        self.assertEqual(document.page_count, 1)
        # A4 in points, to the rounding PDF user space allows.
        self.assertAlmostEqual(document[0].rect.width, 595.3, delta=0.5)
        self.assertAlmostEqual(document[0].rect.height, 841.9, delta=0.5)

    def test_landscape_turns_the_page_not_the_content(self):
        landscape = self.paperformat.copy({'orientation': 'Landscape'})
        document = self._render(
            self._report('probe_land', PAGE % '<p>hello</p>',
                         paperformat=landscape))
        self.assertGreater(document[0].rect.width, document[0].rect.height)

    def test_a_long_table_flows_onto_further_pages(self):
        """web.minimal_layout clips the body and gives the document no height,
        which wkhtmltopdf ignores and WeasyPrint obeys. Without the reset the
        crew table is cut off at the first page and nobody is told."""
        rows = ('<table><tbody>'
                '<tr t-foreach="range(120)" t-as="n">'
                '<td>crew <t t-out="n"/></td></tr>'
                '</tbody></table>')
        document = self._render(self._report('probe_flow', PAGE % rows))

        self.assertGreater(document.page_count, 1)
        printed = ''.join(page.get_text() for page in document)
        self.assertIn('crew 119', printed)

    def test_the_report_font_is_embedded(self):
        """A silent fallback to a default font is the failure mode worth
        catching: it means the stylesheet did not reach the renderer."""
        document = self._render(self._report('probe_font', PAGE % '<p>hello</p>'))
        fonts = {name for _x, _y, _z, name, *_rest in document[0].get_fonts()}
        self.assertTrue(any('Lato' in name for name in fonts), fonts)

    # ------------------------------------------------------------------
    # What it refuses
    # ------------------------------------------------------------------
    def test_a_running_header_is_refused_not_dropped(self):
        report = self._report(
            'probe_header',
            '<div class="header"><p>LETTERHEAD</p></div>'
            '<div class="article">%s</div>' % (PAGE % '<p>body</p>'),
            layout='web.html_container')
        with self.assertRaises(UserError):
            self._render(report)

    def test_an_unticked_report_still_uses_wkhtmltopdf(self):
        report = self._report('probe_off', PAGE % '<p>hello</p>')
        report.use_weasyprint = False
        called = []

        def spy(report_model, *args, **kwargs):
            called.append(True)
            return b'%PDF-1.4 stub'

        self.patch(type(self.env['ir.actions.report']),
                   '_run_wkhtmltopdf', spy)
        self.env['ir.actions.report'].with_context(
            force_report_rendering=True)._render_qweb_pdf(
                report.report_name, self.partner.ids)
        self.assertTrue(called)

    # ------------------------------------------------------------------
    # The fetcher
    # ------------------------------------------------------------------
    def test_a_module_file_resolves_off_the_addons_path(self):
        fetcher = OdooUrlFetcher(self.env, 'http://localhost:8069')
        response = fetcher.fetch(
            'http://localhost:8069/web/static/src/libs/fontawesome/css/'
            '../fonts/fontawesome-webfont.woff2?v=4.7.0')
        self.assertTrue(response.read())

    def test_an_asset_bundle_resolves_out_of_the_database(self):
        fetcher = OdooUrlFetcher(self.env, 'http://localhost:8069')
        response = fetcher.fetch(
            'http://localhost:8069/web/assets/any/'
            'web.report_assets_common.min.css')
        self.assertIn('text/css', response.content_type)
        self.assertTrue(response.read())

    def test_another_host_is_refused(self):
        """Odoo declares its Noto faces against a CDN. A consular document
        must not stop rendering because that CDN is unreachable."""
        fetcher = OdooUrlFetcher(self.env, 'http://localhost:8069')
        with self.assertRaises(UnfetchableUrl):
            fetcher.fetch('https://fonts.odoocdn.com/fonts/noto/NotoSans-Bol.woff2')

    def test_a_missing_local_file_is_refused_rather_than_fetched(self):
        fetcher = OdooUrlFetcher(self.env, 'http://localhost:8069')
        with self.assertRaises(UnfetchableUrl):
            fetcher.fetch('http://localhost:8069/nope/static/missing.css')


@tagged('post_install', '-at_install')
class TestPaperformatCss(TransactionCase):

    def _format(self, **values):
        return self.env['report.paperformat'].create({
            'name': "Probe",
            'margin_top': 5, 'margin_bottom': 10,
            'margin_left': 7, 'margin_right': 7,
            **values,
        })

    def test_a_named_format_becomes_millimetres(self):
        css = self._format(format='A4', orientation='Portrait')._weasyprint_page_css()
        self.assertIn('size: 210mm 297mm', css)
        self.assertIn('margin: 5mm 7mm 10mm 7mm', css)

    def test_landscape_comes_from_either_the_format_or_the_caller(self):
        portrait = self._format(format='A4', orientation='Portrait')
        self.assertIn('size: 297mm 210mm',
                      portrait._weasyprint_page_css(landscape=True))
        landscape = self._format(format='A4', orientation='Landscape')
        self.assertIn('size: 297mm 210mm', landscape._weasyprint_page_css())

    def test_a_custom_format_gets_its_own_dimensions(self):
        custom = self._format(format='custom', orientation='Portrait',
                              page_width=210, page_height=297)
        self.assertIn('size: 210mm 297mm', custom._weasyprint_page_css())
        self.assertIn('size: 297mm 210mm',
                      custom._weasyprint_page_css(landscape=True))

    def test_zoom_declares_the_page_larger_so_it_can_be_painted_down(self):
        """The page is declared 1/zoom too big and painted back at zoom, which
        is what lands the content at the size wkhtmltopdf drew it."""
        css = self._format(format='A4', orientation='Portrait')._weasyprint_page_css(
            zoom=0.5)
        self.assertIn('size: 420mm 594mm', css)
        self.assertIn('margin: 10mm 14mm 20mm 14mm', css)

    def test_a_format_with_no_known_size_is_refused(self):
        with self.assertRaises(UserError):
            self._format(format='A2', orientation='Portrait')._weasyprint_page_css()


@tagged('post_install', '-at_install')
class TestCombinedDocument(TestWeasyprintRender):
    """Several reports, one PDF, each page the size its own report asked for.

    Run:
        make test m=report_weasyprint t=/report_weasyprint:TestCombinedDocument
    """

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.landscape = cls.env['report.paperformat'].create({
            'name': "Probe A4 landscape",
            'format': 'A4',
            'orientation': 'Landscape',
            'margin_top': 5, 'margin_bottom': 5,
            'margin_left': 5, 'margin_right': 5,
            'header_spacing': 0,
        })

    def _combined(self, parts):
        pdf = self.env['ir.actions.report'].with_context(
            force_report_rendering=True)._render_weasyprint_combined(parts)
        return pymupdf.open(stream=pdf, filetype='pdf')

    def test_one_document_carries_both_orientations(self):
        """The reason this exists: a landscape manifeste and a portrait letter
        as one file, rather than two PDFs stapled together."""
        wide = self._report('combined_wide', PAGE % '<h1>MANIFESTE</h1>',
                            paperformat=self.landscape)
        tall = self._report('combined_tall', PAGE % '<h1>LETTER</h1>')

        document = self._combined([
            (wide.report_name, self.partner.ids),
            (tall.report_name, self.partner.ids),
        ])

        self.assertEqual(document.page_count, 2)
        first, second = document[0].rect, document[1].rect
        self.assertGreater(first.width, first.height,
                           "The manifeste keeps its landscape paper.")
        self.assertLess(second.width, second.height,
                        "The letter keeps its portrait paper.")
        self.assertIn('MANIFESTE', document[0].get_text())
        self.assertIn('LETTER', document[1].get_text())
        document.close()

    def test_order_is_the_order_given(self):
        wide = self._report('combined_order_wide', PAGE % '<h1>SECOND</h1>',
                            paperformat=self.landscape)
        tall = self._report('combined_order_tall', PAGE % '<h1>FIRST</h1>')

        document = self._combined([
            (tall.report_name, self.partner.ids),
            (wide.report_name, self.partner.ids),
        ])

        self.assertIn('FIRST', document[0].get_text())
        self.assertIn('SECOND', document[1].get_text())
        document.close()

    def test_a_part_that_runs_long_keeps_its_own_pages(self):
        """Multiple pages per part, not one page per part: a part that
        overflows flows onto further pages of its own size, and the next part
        starts after them."""
        rows = ''.join('<tr><td>row %d</td></tr>' % i for i in range(220))
        long_part = self._report(
            'combined_long', PAGE % ('<table>%s</table>' % rows))
        tall = self._report('combined_after', PAGE % '<h1>AFTER</h1>')

        document = self._combined([
            (long_part.report_name, self.partner.ids),
            (tall.report_name, self.partner.ids),
        ])

        self.assertGreater(document.page_count, 2,
                           "The long part has to flow onto further pages.")
        self.assertIn('AFTER', document[-1].get_text(),
                      "and the next part starts after all of them.")
        document.close()

    def test_a_part_may_carry_its_own_context(self):
        report = self._report('combined_ctx',
                              PAGE % '<h1 t-esc="env.context.get(\'probe_mark\')"/>')
        document = self._combined([
            (report.report_name, self.partner.ids, {'probe_mark': 'FROM-CONTEXT'}),
        ])
        self.assertIn('FROM-CONTEXT', document[0].get_text())
        document.close()

    def test_a_report_not_rendered_here_is_refused(self):
        """Silently letting it through would produce a separate file through
        wkhtmltopdf, which is not what the caller asked for."""
        wide = self._report('combined_refused_wide', PAGE % 'wide',
                            paperformat=self.landscape)
        plain = self._report('combined_refused_plain', PAGE % 'plain')
        plain.use_weasyprint = False

        with self.assertRaises(UserError) as caught:
            self._combined([
                (wide.report_name, self.partner.ids),
                (plain.report_name, self.partner.ids),
            ])
        self.assertIn('combined_refused_plain', str(caught.exception))

    def test_nothing_to_combine_is_empty_not_an_error(self):
        self.assertEqual(
            self.env['ir.actions.report']._render_weasyprint_combined([]), b'')


@tagged('post_install', '-at_install')
class TestNamedPageCss(TransactionCase):
    """``@page`` rules that a single document can choose between."""

    def _format(self, **values):
        return self.env['report.paperformat'].create({
            'name': "Probe",
            'margin_top': 5, 'margin_bottom': 10,
            'margin_left': 7, 'margin_right': 7,
            **values,
        })

    def test_a_name_makes_it_a_named_page_rule(self):
        page = self._format(format='A4', orientation='Portrait')
        self.assertTrue(page._weasyprint_page_css().startswith('@page {'))
        self.assertTrue(
            page._weasyprint_page_css(name='letter').startswith('@page letter {'))

    def test_several_formats_become_several_named_rules(self):
        portrait = self._format(format='A4', orientation='Portrait')
        landscape = self._format(format='A4', orientation='Landscape')

        css, names = self.env['report.paperformat']._weasyprint_named_page_css(
            [(landscape, False), (portrait, False)])

        self.assertEqual(len(names), 2)
        self.assertEqual(len(set(names)), 2, "Each part needs its own name.")
        self.assertIn('@page %s { size: 297mm 210mm' % names[0], css)
        self.assertIn('@page %s { size: 210mm 297mm' % names[1], css)

    def test_the_names_are_usable_css_identifiers(self):
        import re
        name = self.env['report.paperformat']._weasyprint_page_name(0)
        self.assertRegex(name, r'^[A-Za-z][A-Za-z0-9_-]*$')
