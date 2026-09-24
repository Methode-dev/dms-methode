# -*- coding: utf-8 -*-
{
    'name': "DMS Certificate Portal",
    'summary': "Seal consular documents and let embassies verify them",
    'description': """
Seal a document, then let an embassy check it
=============================================

Two halves of one job.

**Sealing** stamps an already-produced PDF: a diagonal marking, a guilloche
border, a microtext footer, and a block carrying the QR code, the reference and
the document's fingerprint. It is a post-process, so no report template is ever
touched and a re-stamp costs no re-render.

**Verification** is a public page, with no account behind it. An agent types the
reference printed beside the QR code plus the second check the issuer chose,
and gets the document's current status and the page itself.

This module owns both, for any document. Producing the documents belongs in a
separate module that depends on this one, points ``_certify_source()`` at its
own files and calls ``dms.certificate.issue()``. See ``models/dms_certificate.py``
for the integration API and ``tools/seal.py`` for the stamping itself.
""",
    'author': "Méthode",
    'website': "https://methode.dev/",
    'category': 'Website',
    'version': '19.0.5.0.0',
    'license': 'LGPL-3',

    # Deliberately NOT depending on `website`. This portal is a plain public
    # controller, not a builder page: pulling in `website` would install the
    # site builder, themes, snippets, the editor and the first-run configurator
    # for what is two inputs and a verdict, and every one of those is public
    # surface area this module does not want.
    #
    # `google_recaptcha` is a soft dependency: install it separately and the
    # controller picks it up on its own (see _captcha_ok in controllers/main.py).
    'depends': ['base_setup', 'web', 'mail', 'dms_certify_host'],

    # PyMuPDF does the sealing (watermark, guilloche, microtext, QR block) and
    # the redaction of the crew lines; qrcode draws the square. Both already
    # ship in this stack — dms_pdf_merge declares fitz the same way.
    'external_dependencies': {'python': ['fitz', 'qrcode']},

    'data': [
        'security/dms_certify_portal_groups.xml',
        'security/ir.model.access.csv',
        'security/ir_rule.xml',
        'data/ir_config_parameter.xml',
        'data/ir_cron.xml',
        # The revoke wizard first: the certificate form's header binds its
        # action by xmlid, which has to exist by then.
        'views/dms_certificate_type_views.xml',
        'views/dms_certificate_revoke_views.xml',
        'views/dms_certificate_views.xml',
        'views/dms_certificate_attempt_views.xml',
        'views/res_config_settings_views.xml',
        'views/menus.xml',
        'templates/verify_templates.xml',
    ],

    'assets': {
        'web.assets_backend': [
            'dms_certify_portal/static/src/scss/certificate_form.scss',
            'dms_certify_portal/static/src/js/certificate_chatter.js',
            'dms_certify_portal/static/src/js/certificate_chatter.xml',
            'dms_certify_portal/static/src/js/form_renderer_patch.js',
        ],
        'web.assets_frontend': [
            'dms_certify_portal/static/src/scss/verify.scss',
            'dms_certify_portal/static/src/js/verify.js',
        ],
        'web.assets_tests': [
            'dms_certify_portal/static/tests/tours/certificate_chatter_tour.js',
        ],
    },

    'post_init_hook': 'post_init_hook',
    'installable': True,
    'application': True,
    'auto_install': False,
}
