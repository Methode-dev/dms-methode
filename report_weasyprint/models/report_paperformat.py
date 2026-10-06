# -*- coding: utf-8 -*-
from odoo import _, api, models
from odoo.exceptions import UserError

# Millimetres, portrait. Explicit rather than CSS's own `size: A4`, because
# the page box is declared pre-zoom (see tools/render.py) and a named size
# cannot be divided.
PAGE_SIZES_MM = {
    'A3': (297, 420),
    'A4': (210, 297),
    'A5': (148, 210),
    'B4': (250, 353),
    'B5': (176, 250),
    'Letter': (215.9, 279.4),
    'Legal': (215.9, 355.6),
    'Tabloid': (279.4, 431.8),
}


class ReportPaperformat(models.Model):
    _inherit = 'report.paperformat'

    def _weasyprint_page_css(self, landscape=False, zoom=1.0, name=None):
        """This paperformat as an ``@page`` rule, divided by *zoom*.

        Everything is declared *zoom* times too big so that painting the page
        back down at that factor lands on the real paper size — which is how
        the content ends up the size wkhtmltopdf drew it. See
        ``tools/render.py`` for why that is the only lever available.

        ``header_spacing`` is not translated: a report rendered by WeasyPrint
        lays its own letterhead out inside the page, so there is no separate
        header document to leave room for.

        *name* makes it a CSS named page (``@page portrait { … }``) instead of
        the anonymous rule, so one document can carry several paperformats —
        see ``_weasyprint_named_page_css``.
        """
        self.ensure_one()
        width, height = self._weasyprint_size_mm(landscape)
        return '@page%s { size: %gmm %gmm; margin: %gmm %gmm %gmm %gmm; }' % (
            ' %s' % name if name else '',
            width / zoom, height / zoom,
            self.margin_top / zoom, self.margin_right / zoom,
            self.margin_bottom / zoom, self.margin_left / zoom,
        )

    @api.model
    def _weasyprint_page_name(self, index):
        """A CSS identifier for the *index*-th page type of a document."""
        return 'ops-page-%d' % index

    @api.model
    def _weasyprint_named_page_css(self, parts, zoom=1.0):
        """Named ``@page`` rules for several paperformats at once.

        *parts* is a sequence of ``(paperformat, landscape)``. Returns the
        rules and the page name each part was given, in order, so a caller can
        put ``page: <name>`` on the section that belongs to it.

        This is what lets a single document mix orientations: CSS resolves
        ``page:`` per element, and WeasyPrint sizes each page from the rule it
        names.
        """
        rules, names = [], []
        for index, (paperformat, landscape) in enumerate(parts):
            name = self._weasyprint_page_name(index)
            names.append(name)
            rules.append(paperformat._weasyprint_page_css(
                landscape=landscape, zoom=zoom, name=name))
        return '\n'.join(rules), names

    def _weasyprint_size_mm(self, landscape=False):
        self.ensure_one()
        if self.format == 'custom':
            size = (self.page_width, self.page_height)
        else:
            size = PAGE_SIZES_MM.get(self.format)
        if not size:
            raise UserError(_(
                "Paper format “%(format)s” has no size this renderer knows, so "
                "it cannot be rendered by WeasyPrint. Use one of %(known)s, or "
                "set the format to Custom and give explicit dimensions.",
                format=self.format,
                known=', '.join(sorted(PAGE_SIZES_MM)),
            ))

        short, long_ = sorted(size)
        is_landscape = bool(landscape) or self.orientation == 'Landscape'
        return (long_, short) if is_landscape else (short, long_)
