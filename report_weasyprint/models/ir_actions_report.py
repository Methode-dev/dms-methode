# -*- coding: utf-8 -*-
import logging

from lxml import html as lxml_html

from odoo import _, fields, models
from odoo.exceptions import UserError

from ..tools import fetch, render

_logger = logging.getLogger(__name__)

# web.minimal_layout collects every report's header and footer into these two
# divs, then wkhtmltopdf picks the right one per page with a script. A report
# rendered here must lay its own page out instead.
RUNNING_PART_IDS = (
    'minimal_layout_report_headers',
    'minimal_layout_report_footers',
)


class IrActionsReport(models.Model):
    _inherit = 'ir.actions.report'

    use_weasyprint = fields.Boolean(
        string="Render with WeasyPrint",
        help="Lay this report out with WeasyPrint instead of wkhtmltopdf. "
             "The template must render its own letterhead inside the page: "
             "wkhtmltopdf's separate header and footer documents have no "
             "equivalent.")

    def _run_wkhtmltopdf(self, bodies, report_ref=False, header=None,
                         footer=None, landscape=False,
                         specific_paperformat_args=None,
                         set_viewport_size=False):
        report = self._get_report(report_ref) if report_ref else self
        if not report.use_weasyprint:
            return super()._run_wkhtmltopdf(
                bodies, report_ref=report_ref, header=header, footer=footer,
                landscape=landscape,
                specific_paperformat_args=specific_paperformat_args,
                set_viewport_size=set_viewport_size)

        self._weasyprint_refuse_running_parts(report, header, footer)
        base_url = self._get_report_url()
        zoom = self._weasyprint_zoom()
        _logger.info("Rendering %s with WeasyPrint (%d body/bodies, zoom %.4f)",
                     report.report_name, len(bodies), zoom)
        return render.render(
            bodies,
            page_css=report.get_paperformat()._weasyprint_page_css(
                landscape=landscape, zoom=zoom),
            url_fetcher=fetch.OdooUrlFetcher(self.env, base_url),
            base_url=base_url,
            zoom=zoom,
        )

    def _render_weasyprint_combined(self, parts):
        """Render several reports into one PDF, each under its own paperformat.

        *parts* is a sequence of ``(report_ref, res_ids)``, or
        ``(report_ref, res_ids, context)`` when a part needs its own context —
        a per-document letterhead, say. Order is the page order.

        The point is mixed paperformats in one file: a landscape manifeste
        followed by a portrait letter comes out as a single two-page PDF, with
        each page the size its own report asked for. Concatenating two finished
        PDFs gets the same pages but loses the links and bookmarks, and costs a
        second render of the shared stylesheets.

        Every part must be a WeasyPrint report; one that is not is refused
        rather than silently rendered by wkhtmltopdf into a separate file.
        """
        if not parts:
            return b''

        bodies, page_csss = [], []
        zoom = self._weasyprint_zoom()
        base_url = self._get_report_url()

        for part in parts:
            report_ref, res_ids = part[0], part[1]
            part_context = part[2] if len(part) > 2 else None
            renderer = self.with_context(**part_context) if part_context else self
            report = renderer._get_report(report_ref)
            if not report.use_weasyprint:
                raise UserError(_(
                    "Report “%s” is not rendered with WeasyPrint, so it cannot "
                    "be combined into one document with the others.",
                    report.name))
            self._weasyprint_refuse_running_parts(report, None, None)

            html, _kind = renderer._render_qweb_html(report.report_name, res_ids)
            bodies.append(html.decode() if isinstance(html, bytes) else html)
            page_csss.append(
                report.get_paperformat()._weasyprint_page_css(zoom=zoom))

        _logger.info("Rendering %d reports into one document with WeasyPrint "
                     "(zoom %.4f)", len(parts), zoom)
        return render.render(
            bodies,
            page_css=page_csss,
            url_fetcher=fetch.OdooUrlFetcher(self.env, base_url),
            base_url=base_url,
            zoom=zoom,
        )

    def _weasyprint_zoom(self):
        setting = self.env['ir.config_parameter'].sudo().get_param(
            'report_weasyprint.zoom')
        try:
            return float(setting) if setting else render.WKHTMLTOPDF_PARITY_ZOOM
        except ValueError:
            _logger.warning(
                "report_weasyprint.zoom is %r, which is not a number; "
                "falling back to %.4f", setting, render.WKHTMLTOPDF_PARITY_ZOOM)
            return render.WKHTMLTOPDF_PARITY_ZOOM

    def _weasyprint_refuse_running_parts(self, report, header, footer):
        """Refuse a template still relying on wkhtmltopdf's running parts.

        Dropping them silently would print a consular letter with no
        letterhead, which is worse than not printing it.
        """
        for label, part in (("header", header), ("footer", footer)):
            if self._weasyprint_part_has_content(part):
                raise UserError(_(
                    "Report “%(report)s” renders with WeasyPrint, which has no "
                    "equivalent for wkhtmltopdf's separate %(part)s document. "
                    "Move the %(part)s into the template's own page layout, or "
                    "untick Render with WeasyPrint.",
                    report=report.name, part=label,
                ))

    @staticmethod
    def _weasyprint_part_has_content(part):
        """Whether *part* carries a real header/footer rather than an empty shell.

        The rendered part is always a full HTML document, so truthiness says
        nothing; what matters is whether the collecting div has children.
        """
        if not part or not part.strip():
            return False
        root = lxml_html.fromstring(part)
        return any(
            len(node)
            for node_id in RUNNING_PART_IDS
            for node in root.xpath("//*[@id=$node_id]", node_id=node_id)
        )
