# -*- coding: utf-8 -*-
"""Turn report bodies into one PDF."""

import logging
import re
import threading

import weasyprint

# WeasyPrint narrates every rendering step at INFO, several lines per page.
logging.getLogger('weasyprint.progress').setLevel(logging.WARNING)

# Parsing Bootstrap produces the same twenty-odd warnings on every render:
# vendor prefixes and properties that only mean something on screen.
UNACTIONABLE_CSS_WARNING = re.compile(
    r'^(Ignored `|Expected a media type|Invalid media type)')


class _QuietRepeats(logging.Filter):
    """Drop the warnings a render repeats, keep the first of each.

    Odoo's font stacks end in a face hosted on its CDN, which this module
    refuses on purpose, so every render would otherwise report the same
    refusal once per glyph run. Said once it is information; said thirty times
    it buries everything else.
    """

    _seen = threading.local()

    @classmethod
    def start_render(cls):
        cls._seen.messages = set()

    def filter(self, record):
        message = record.getMessage()
        if UNACTIONABLE_CSS_WARNING.match(message):
            return False
        seen = getattr(self._seen, 'messages', None)
        if seen is None:
            return True
        if message in seen:
            return False
        seen.add(message)
        return True


logging.getLogger('weasyprint').addFilter(_QuietRepeats())

# web.minimal_layout is shaped for wkhtmltopdf, which ignores both of these:
# it clips the body and pins the document to no height at all. WeasyPrint
# honours them, and a crew table longer than one page is silently cut off at
# the first rather than flowing onto the next.
MINIMAL_LAYOUT_RESET = """
html { height: auto !important; }
body { overflow: visible !important; }
"""

# WeasyPrint resolves a CSS pixel at the standard 96 dpi; wkhtmltopdf drew
# these reports smaller, and measuring the same spans in both put it at
# 1.1712x. The report stylesheets size everything in px, so neither the root
# font size nor any other CSS lever reaches it — the whole page has to be
# painted down, which is what `zoom` does. The paperformat is declared
# correspondingly larger so the paper itself still comes out A4.
#
# Overridable with the `report_weasyprint.zoom` config parameter, for a
# deployment that would rather have the standard 96 dpi (1.0) than parity with
# what wkhtmltopdf used to produce.
WKHTMLTOPDF_PARITY_ZOOM = 1 / 1.1712


def render(bodies, page_css, url_fetcher, base_url, zoom=1.0):
    """Render *bodies* into a single PDF, in order.

    Odoo hands a list of complete HTML documents — one per record — and expects
    one PDF back, which it then splits again if it has to. The pages are
    collected into a single WeasyPrint document rather than concatenated as
    PDFs, so links and bookmarks survive the join.

    *page_css* is either one rule for every body, or a sequence of one per
    body. Per body is what lets a single PDF mix paperformats — a landscape
    manifeste followed by a portrait letter — because each body is laid out
    under its own ``@page`` before the pages are collected.
    """
    if not bodies:
        return b''

    if isinstance(page_css, str):
        page_csss = [page_css] * len(bodies)
    else:
        page_csss = list(page_css)
        if len(page_csss) != len(bodies):
            raise ValueError(
                "render() got %d page_css for %d bodies; pass one rule for "
                "all of them or exactly one each."
                % (len(page_csss), len(bodies)))

    _QuietRepeats.start_render()
    # Parsed once per distinct rule rather than once per body: a run of five
    # documents sharing two paperformats parses two stylesheets, not five.
    stylesheets = {}
    for css in page_csss:
        if css not in stylesheets:
            stylesheets[css] = weasyprint.CSS(
                string=css + MINIMAL_LAYOUT_RESET,
                url_fetcher=url_fetcher, base_url=base_url)

    documents = [
        weasyprint.HTML(
            string=body, url_fetcher=url_fetcher, base_url=base_url,
        ).render(stylesheets=[stylesheets[css]])
        for body, css in zip(bodies, page_csss)
    ]
    pages = [page for document in documents for page in document.pages]
    return documents[0].copy(pages).write_pdf(zoom=zoom)
