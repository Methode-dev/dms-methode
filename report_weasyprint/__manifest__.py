# -*- coding: utf-8 -*-
{
    'name': "Report rendering with WeasyPrint",
    'summary': "Render selected QWeb reports with WeasyPrint instead of wkhtmltopdf",
    'description': """
Render a report with WeasyPrint
===============================

Tick **Render with WeasyPrint** on an ``ir.actions.report`` and that report is
laid out in-process by WeasyPrint. Every other report still goes through
wkhtmltopdf, which stays installed.

Two things follow from rendering in-process:

* No asset callback. wkhtmltopdf fetches the report's stylesheets back over
  HTTP, which is why rendering one inside a test needs a server answering on
  the side. WeasyPrint is handed the bundle directly.
* No network. The URL fetcher resolves asset bundles and module static files
  out of the database and the addons path, and refuses anything else — a
  render cannot come to depend on a font CDN being reachable.

A report that opts in has to lay its own page out. wkhtmltopdf's separate
header/footer documents have no equivalent here, so a template still relying on
them is refused rather than rendered without its letterhead.

Several reports as one document
-------------------------------

``_render_weasyprint_combined(parts)`` renders a sequence of reports into a
single PDF, **each page keeping the paperformat its own report asked for**. A
landscape manifeste followed by a portrait letter is one two-page file, not two
files stapled together::

    pdf = env['ir.actions.report']._render_weasyprint_combined([
        ('operations.action_report_manifeste', manifeste_ids),
        ('operations.action_report_loi', loi_ids, {'operations_office_id': office.id}),
    ])

Each part is ``(report_ref, res_ids)``, or ``(report_ref, res_ids, context)``
where one needs its own — a per-document letterhead, say. Order is page order.
A part that overflows flows onto further pages of its own size before the next
part begins, so this is "several documents, each of several pages", not one
page per part.

Why it is not a PDF concatenation: joining finished PDFs loses links and
bookmarks, and pays to parse the shared stylesheets once per part. Here the
pages are collected into one WeasyPrint document, and each distinct
``@page`` rule is parsed once however many parts share it.

A part whose report is not ticked for WeasyPrint is refused rather than
quietly sent through wkhtmltopdf into a file of its own.

Mixing paperformats inside one template
---------------------------------------

``report.paperformat._weasyprint_page_css(name=...)`` emits a CSS *named* page
rule instead of the anonymous one, and
``_weasyprint_named_page_css(parts)`` builds several at once and returns the
name given to each. A template can then put ``page: <name>`` on a section to
choose its paper — which is how one QWeb document can carry both orientations
without being split into separate reports.
""",
    'author': "Méthode",
    'website': "https://methode.dev/",
    'category': 'Technical Settings',
    'version': '19.0.1.1.0',
    'license': 'LGPL-3',

    'depends': ['base'],
    'external_dependencies': {'python': ['weasyprint']},

    'data': [
        'views/ir_actions_report_views.xml',
    ],

    'installable': True,
    'auto_install': False,
}
