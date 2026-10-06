# -*- coding: utf-8 -*-
"""Resolve a report's own URLs without leaving the process.

wkhtmltopdf fetches a report's stylesheets back over HTTP, which is why
rendering one needs a server answering on the side. WeasyPrint asks its
``url_fetcher`` instead, so asset bundles come out of the database and module
files off the addons path.

Anything on another host is refused. A report is a document a consulate relies
on; it must not stop rendering because a font CDN is unreachable, and a missing
local file must not quietly become a network call. Odoo declares its Noto faces
against ``fonts.odoocdn.com``, so this is reached whenever a company's report
font is not one of the locally shipped ones.

A raising fetcher means "try the next ``src``" to WeasyPrint, which is what the
``.eot`` and ``.svg`` entries Odoo lists ahead of its readable formats need.
"""

import logging
import mimetypes
import os
from urllib.parse import urlparse

from weasyprint.urls import URLFetcher, URLFetcherResponse

from odoo.tools import file_path

_logger = logging.getLogger(__name__)

ASSETS_PREFIX = '/web/assets/'


class UnfetchableUrl(Exception):
    """Raised for a URL this fetcher will not resolve."""


class OdooUrlFetcher(URLFetcher):
    """Serves a report its own assets straight out of the running process."""

    def __init__(self, env, base_url, **kwargs):
        super().__init__(**kwargs)
        self.env = env
        self.own_netloc = urlparse(base_url).netloc

    def fetch(self, url, headers=None):
        parsed = urlparse(url)
        if parsed.scheme == 'data':
            return super().fetch(url, headers)
        if parsed.netloc and parsed.netloc != self.own_netloc:
            raise UnfetchableUrl(
                "refusing %s: a render may not depend on the network" % url)

        if parsed.path.startswith(ASSETS_PREFIX):
            return self._asset_bundle(url, parsed.path)
        return self._module_file(url, parsed.path)

    def _asset_bundle(self, url, path):
        """``/web/assets/<unique>/<filename>`` out of the database.

        Mirrors what the ``/web/assets`` route serves: the stored bundle when
        there is one, a freshly built bundle when there is not.
        """
        filename = path[len(ASSETS_PREFIX):].split('/')[-1]
        if not filename:
            raise UnfetchableUrl("no asset filename in %s" % path)

        bundle_name, rtl, asset_type, autoprefix = (
            self.env['ir.asset']._parse_bundle_name(filename, False))
        is_css = asset_type == 'css'
        bundle = self.env['ir.qweb']._get_asset_bundle(
            bundle_name, css=is_css, js=not is_css, rtl=rtl,
            autoprefix=autoprefix)
        attachments = bundle.css() if is_css else bundle.js()
        if not attachments:
            raise UnfetchableUrl("bundle %s is empty" % bundle_name)

        return URLFetcherResponse(
            url,
            b''.join(attachment.raw for attachment in attachments),
            {'Content-Type': 'text/css; charset=utf-8' if is_css
                             else 'text/javascript; charset=utf-8'},
        )

    def _module_file(self, url, path):
        """``/<module>/static/<path>`` off the addons path."""
        relative = path.lstrip('/')
        if not relative:
            raise UnfetchableUrl("nothing to resolve in %s" % url)
        try:
            resolved = file_path(relative)
        except (FileNotFoundError, ValueError) as error:
            raise UnfetchableUrl("cannot resolve %s: %s" % (path, error))

        with open(resolved, 'rb') as handle:
            body = handle.read()
        mime_type = mimetypes.guess_type(resolved)[0] or 'application/octet-stream'
        return URLFetcherResponse(
            url, body,
            {'Content-Type': mime_type,
             'Content-Disposition': 'inline; filename="%s"'
                                    % os.path.basename(resolved)},
        )
