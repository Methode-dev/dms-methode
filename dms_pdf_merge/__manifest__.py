# License LGPL-3.0 or later (http://www.gnu.org/licenses/lgpl).
{
    "name": "DMS PDF Merge",
    "summary": """
        Merge a record's report, chatter PDFs and existing documents into a
        single PDF and store it in the DMS, from Sale Orders and Tasks.
    """,
    "version": "19.0.1.0.0",
    "category": "Document Management",
    "license": "LGPL-3",
    "author": "Methode",
    "depends": [
        "dms_field",
        "sale",
        "project",
        "operations",
    ],
    "data": [
        "views/res_config_settings_views.xml",
        "views/sale_order_views.xml",
        "views/project_task_views.xml",
    ],
    "assets": {
        "web.assets_backend": [
            "dms_pdf_merge/static/src/js/**/*",
            "dms_pdf_merge/static/src/xml/**/*",
        ],
    },
    "external_dependencies": {
        "python": ["fitz"],  # PyMuPDF (also uses Pillow)
    },
    "installable": True,
    "application": False,
    "auto_install": False,
}
