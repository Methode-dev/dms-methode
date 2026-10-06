DMS Certificate Portal
======================

|addon| does two things to a document that has already been produced: it **seals**
it, and it lets somebody outside your organisation **check** it.

Sealing stamps the PDF — a diagonal marking, a guilloche border, a microtext footer,
and a block carrying the QR code, the reference and the document's fingerprint. It is
a post-process on finished bytes, so no report template is ever touched, a re-stamp
costs no re-render, and a document nobody here generated — a scanned attestation
dropped into a folder — can be sealed the same way.

Verification is a public page with no account behind it. An agent at an embassy types
the reference printed beside the QR code plus the second check the issuer chose, and
gets the document's current status and the page itself. No ``res.users`` record, no
portal invitation, no shared password.

.. code-block:: text

   your module produces a PDF
        │
        ▼
   dms.certificate.issue()           ── registers it, and seals it
        │
        ├──► sealed PDF              ── watermark, guilloche, microtext, QR block
        └──► reference + verify_url   ── printed on the page, encoded in the QR
                 │
                 ▼
        the embassy types them in    ── public, account-free, rate-limited
                 │
                 ▼
        status + the page itself     ── redacted to the person who asked

This module owns sealing and verification **for any document**. It does not produce
documents and knows nothing about what they are for: ships, ports, crews and the
vocabulary that goes with them live in whichever module generates the files. That
separation is what keeps the public attack surface small — a bug in a QWeb template
here cannot reach your business records, because the public templates only ever
receive a whitelisted dict.

What it gives you
-----------------

.. list-table::
   :header-rows: 1
   :widths: 24 76

   * - Feature
     - What it does
   * - **The seal**
     - A post-process on finished PDF bytes: marking, guilloche frame, microtext
       footer, and a block with the QR code, the reference and the fingerprint.
       See :doc:`handbook/sealing`.
   * - **The registry**
     - One ``dms.certificate`` per verifiable document, with the people listed on
       it, what may be disclosed, and how long it stays valid. See
       :doc:`reference/models/dms_certificate`.
   * - **The public page**
     - Two inputs and a verdict, on a host of its own, with no website builder
       behind it. See :doc:`handbook/verification`.
   * - **Redaction**
     - Under confirm-only disclosure the page hides everyone except the person
       whose document opened it — and the result is re-checked for what should
       have gone before it is served. See :ref:`sealing-redaction`.
   * - **Rate limiting**
     - Per address and per reference, in the application, underneath whatever
       your proxy already does. See :doc:`handbook/deployment`.
   * - **The audit trail**
     - Every lookup recorded in ``dms.certificate.attempt``, with the desk told
       about the ones that matter. See
       :doc:`reference/models/dms_certificate_attempt`.
   * - **An integration API**
     - ``issue()``, three documented override points, and document types as
       records rather than a selection. See :doc:`handbook/issuing`.

At a glance
-----------

.. list-table::
   :widths: 30 70

   * - Odoo version
     - 19.0 (``base_setup``, ``web``, ``mail``, ``dms_certify_host``)
   * - Module version
     - |release|
   * - Technical name
     - |addon|
   * - Licence
     - LGPL-3
   * - Python packages
     - ``fitz`` (PyMuPDF), ``qrcode``
   * - Deliberately **not** depending on
     - ``website`` — see :ref:`limits-no-website`
   * - Soft dependency
     - ``google_recaptcha``, picked up with no code change if installed
   * - Source
     - :ghsrc:`__manifest__.py`

Where to start
--------------

* **Never seen this addon before?** Read :doc:`handbook/concepts` — the two halves,
  the second factor, disclosure, and what a reference is.
* **Setting it up?** :doc:`installation`, then :doc:`handbook/quickstart`.
* **Putting it in front of real embassies?** :doc:`handbook/deployment` and
  :doc:`handbook/security-and-privacy`. Read both before you issue anything that
  goes on paper.
* **Writing the module that produces the documents?** :doc:`handbook/issuing`,
  then :doc:`development/extending`.
* **Something is broken?** :doc:`handbook/troubleshooting`.
* **Changing this addon?** :doc:`development/architecture`, then
  :doc:`development/contributing` and :doc:`reference/index`.

.. toctree::
   :maxdepth: 2
   :caption: Getting started

   installation
   handbook/quickstart

.. toctree::
   :maxdepth: 2
   :caption: Handbook

   handbook/index

.. toctree::
   :maxdepth: 2
   :caption: Reference

   reference/index

.. toctree::
   :maxdepth: 2
   :caption: Development

   development/index

.. toctree::
   :maxdepth: 1
   :caption: About

   changelog
   limits

Indices and tables
------------------

* :ref:`genindex`
* :ref:`modindex`
* :ref:`search`
