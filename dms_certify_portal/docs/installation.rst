Installation
============

.. contents::
   :local:
   :depth: 2

Requirements
------------

Odoo
^^^^

.. list-table::
   :header-rows: 1
   :widths: 24 20 56

   * - Requirement
     - Version
     - Notes
   * - Odoo
     - **19.0**
     - Declared in the manifest as |release|. The addon uses Odoo 19 internals
       directly — ``models.Constraint``, ``res.groups.privilege`` instead of
       ``category_id``, ``res.users.group_ids`` instead of ``groups_id`` — and
       is not expected to load on 17.0 or 18.0 unchanged.
   * - Odoo addons
     - —
     - ``base_setup``, ``web``, ``mail``, ``dms_certify_host``. The first three
       are Community; the fourth is a sibling addon in the same repository and
       needs the extra step below.
   * - Deliberately **not** ``website``
     - —
     - The portal is a plain public controller rendering
       ``web.frontend_layout``. What that costs you is listed in
       :ref:`limits-no-website`.
   * - ``google_recaptcha``
     - optional
     - A *soft* dependency: not in ``depends``, picked up at runtime if
       present. See :doc:`handbook/deployment`.
   * - Python
     - whatever your Odoo 19 server runs
     - The addon declares no interpreter constraint of its own.

Python packages
^^^^^^^^^^^^^^^

The manifest declares two, both used by :doc:`reference/tools/seal`:

.. list-table::
   :header-rows: 1
   :widths: 24 76

   * - Package
     - For
   * - ``fitz`` (PyMuPDF)
     - Everything the stamp does: the watermark, the guilloche frame, the
       microtext, placing the QR, rasterising a page for the public copy, and
       the redaction — which is a real ``apply_redactions``, not a black
       rectangle drawn on top.
   * - ``qrcode``
     - Draws the square. That is its whole job.

Both already ship in this stack, so there is normally nothing extra to
install. Confirm it on your server rather than taking this page's word for it:

.. code-block:: bash

   python3 -c "import fitz, qrcode; print('ok')"

.. note::

   The code imports ``pymupdf`` (the modern name) inside ``tools/seal.py``
   while the manifest declares ``fitz`` (the legacy one). Both names come from
   the same distribution, so this works; it is listed as ``fitz`` because
   ``dms_pdf_merge`` in the same repository declares it that way and a
   consistent manifest is easier to audit than a correct one.

.. _installation-check-host:

The ``dms_certify_host`` prerequisite
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

**Without this one, the portal has no address and every public URL 404s.** It
is the only prerequisite on this page that is not an ordinary install, so it
gets its own section.

``dms_certify_portal`` declares every public route under the internal prefix
``/_check``. Nothing is ever served at that path: ``ir.http._match``
(:doc:`reference/models/ir_http`) rewrites ``/`` to ``/_check``, ``/d/REF`` to
``/_check/d/REF`` and so on — **but only when the request arrived on a host
beginning** ``check.``. On any other host the same override raises
``NotFound`` for anything under ``/_check``, so the namespace does not exist
outside the portal's own name.

That host test comes from ``dms_certify_host.hosts.is_check_host``, which is
why ``dms_certify_host`` is a hard dependency rather than a deployment detail.

It also carries a ``post_load`` entry that patches ``odoo.http.db_filter`` so
that ``check.erp.example`` resolves to the **same database** as
``erp.example``. Odoo picks a database from the host name, and without the
patch a ``dbfilter`` keyed on ``%h`` or ``%d`` would go looking for a database
called *check*. Add the module to ``server_wide_modules`` so that patch is in
place at server start, before any request has to resolve a database:

.. code-block:: ini

   [options]
   server_wide_modules = base,web,dms_certify_host

.. important::

   ``server_wide_modules`` **replaces** Odoo's default (``base,web``) rather
   than adding to it. Repeat both, or the web client stops loading.

The host itself — DNS, TLS, and the nginx vhost — is
:ref:`deployment-check-host`. Do that before you issue anything, because the
address goes on paper.

.. todo::

   This repository's ``odoo.conf`` sets no ``server_wide_modules`` at all, and
   ``nginx/nginx.conf.template`` (the production one) has no ``check.*``
   server block — only ``nginx/nginx.dev.conf`` does. As it stands the portal
   is reachable in development and not in production. Which is the intended
   production topology: a ``check.`` subdomain on the same certificate, or a
   separate hostname with its own?

Getting the code
----------------

The addon is a folder inside the ``dms-methode`` repository, which is a
submodule of this deployment:

.. code-block:: text

   addons/dms-methode/              ← this goes on addons_path
     dms_certify_portal/            ← the addon Odoo will find
       __manifest__.py
     dms_certify_host/              ← its prerequisite, same repository
       __manifest__.py

.. code-block:: bash

   git submodule update --init --recursive

   # pulling a newer version later
   cd addons/dms-methode
   git fetch origin && git checkout main && git pull
   cd - && git add addons/dms-methode
   git commit -m "Bump dms-methode"

.. important::

   The addons path must point at ``addons/dms-methode``, **not** at
   ``addons/dms-methode/dms_certify_portal``. Odoo scans a directory for addon
   folders, so it needs the parent — which is also what makes
   ``dms_certify_host`` visible without a second entry.

Putting it on the addons path
-----------------------------

In ``odoo.conf``:

.. code-block:: ini

   [options]
   addons_path = /mnt/custom-addons,/mnt/custom-addons/dms-methode
   server_wide_modules = base,web,dms_certify_host
   proxy_mode = True

Or on the command line:

.. code-block:: bash

   odoo-bin --addons-path=/odoo/odoo/addons,/odoo/addons/dms-methode

Verify Odoo can see both addons before trying to install either:

.. code-block:: bash

   odoo-bin --addons-path=... -d <database> --stop-after-init --log-level=debug 2>&1 \
       | grep dms_certify

Installing the module
---------------------

From the command line
^^^^^^^^^^^^^^^^^^^^^

.. code-block:: bash

   odoo-bin -c odoo.conf -d <database> -i dms_certify_portal \
       --proxy-mode --stop-after-init

``--proxy-mode`` is not optional once this is in front of real embassies.
Without it every request appears to come from the reverse proxy, so the
per-address rate limit becomes **one global limit** and the first agent to
mistype a passport locks out every other agent in the world. Set it in
``odoo.conf`` (``proxy_mode = True``) rather than relying on a flag somebody
has to remember. See :doc:`handbook/deployment`.

From the interface
^^^^^^^^^^^^^^^^^^

#. Enable :guilabel:`Developer mode` (:menuselection:`Settings --> General
   Settings --> Developer Tools`).
#. :menuselection:`Apps --> Update Apps List`.
#. Search for ``DMS Certificate Portal`` and press :guilabel:`Activate`. The
   module declares ``application: True``, so the default **Apps** filter finds
   it.

In Docker
^^^^^^^^^

.. code-block:: bash

   docker compose run --rm --no-deps odoo \
       odoo -d <database> -i dms_certify_portal --stop-after-init

What installation does
^^^^^^^^^^^^^^^^^^^^^^

Beyond the usual tables and views, ``post_init_hook``
(:doc:`reference/hooks`) and the data files do four things:

* **Generates the HMAC pepper** into the system parameter
  ``dms_certify_portal.passport_key`` — 48 random URL-safe bytes. Every stored
  second-factor hash is keyed with it. It is never shown in the interface and
  never leaves the database.

  .. warning::

     **Back it up with your filestore.** Lose the pepper and every stored hash
     becomes unverifiable: no document opens, and the only repair is to
     re-issue them. Rotating it is a migration that re-hashes from a trusted
     source, not a settings change. See :doc:`handbook/deployment`.

* **Activates the portal's languages.** The module ships ``i18n/fr.po``, and a
  fresh database has only English active — so without this step the French
  copy would sit in the file and never reach a page, and the language switcher
  would have nothing to switch to. The hook reads the two-letter codes off the
  ``i18n/`` folder rather than a hard-coded list, resolves each to a variant
  this Odoo knows (``fr`` → ``fr_FR``), and activates it. Activating a
  language is a database-wide change, and it is reversible from
  :menuselection:`Settings --> Translations --> Languages`.

* **Ships 22 system parameters**, all ``noupdate="1"`` — the two rate limits,
  the result lifetime, log retention, the defaults a new certificate starts
  from, and the nine that make up the seal's house style. Once installed they
  are yours: a module upgrade will never overwrite a value you changed. See
  :doc:`reference/data/ir_config_parameter`.

  Three parameters that the Settings page writes are deliberately **not**
  shipped — ``public_base_url``, ``company_id`` and ``default_lang``. Their
  absence is meaningful: no public URL means "derive one from
  ``web.base.url``", no company means "whatever the request resolves to".

* **Ships no document types, on purpose.** What a document *is* belongs to
  whoever produces it, and a generic fallback would only fill the registry —
  and the public page — with *Other*. Version 19.0.5.0.0 went further and
  deleted the four generic ones this module used to ship. Declaring your own
  is :doc:`handbook/issuing`.

It also schedules one cron, *Verification: purge old attempt logs*, running
daily. Nothing else in the module is scheduled.

Verifying the install
---------------------

#. A :guilabel:`Consular` menu appears, with :guilabel:`Verification entries`,
   :menuselection:`Configuration --> Document types` and
   :menuselection:`Reporting --> Verification attempts`.
#. :menuselection:`Settings --> General Settings` has three new blocks:
   :guilabel:`Document verification portal`, :guilabel:`Certified documents:
   defaults` and :guilabel:`Certified documents: the seal`.
#. :guilabel:`Document types` is **empty**. That is correct — see above.

Then from the shell:

.. code-block:: bash

   odoo-bin shell -c odoo.conf -d <database>

.. code-block:: python

   >>> env["ir.module.module"].search([("name", "=", "dms_certify_portal")]).state
   'installed'
   >>> env["ir.module.module"].search([("name", "=", "dms_certify_host")]).state
   'installed'
   >>> bool(env["ir.config_parameter"].sudo().get_param(
   ...     "dms_certify_portal.passport_key"))
   True
   >>> env["res.lang"].search([("active", "=", True)]).mapped("code")
   ['en_US', 'fr_FR']
   >>> env["dms.certificate"]._public_base_url()
   'http://check.localhost'

That last line is the one worth reading carefully: it is the address that gets
printed on paper. If it is not what an embassy should type, fix it before you
issue anything — :doc:`handbook/deployment`.

Finally, prove the host routing works. On the check host the portal answers at
the bare path; on the ordinary host the same path is the back office and
``/_check`` is a 404:

.. code-block:: bash

   curl -sI -H 'Host: check.localhost' http://127.0.0.1:8069/     | head -1
   curl -sI -H 'Host: localhost'       http://127.0.0.1:8069/_check | head -1

Nothing observable happens to an existing document until a producing module
registers one. Continue with :doc:`handbook/quickstart`.

Upgrading
---------

.. code-block:: bash

   odoo-bin -c odoo.conf -d <database> -u dms_certify_portal --stop-after-init

Because the parameters are ``noupdate="1"``, an upgrade will not restore a
rate limit you widened or a watermark colour you changed. It *will* pick up new
fields, views, templates and code, and it will run any migration step between
your installed version and the manifest's — see :doc:`changelog` for what each
one does, and :doc:`reference/migrations` for how.

.. warning::

   Upgrade the scratch database first, and pass the production database name
   explicitly and deliberately. ``-u`` on the wrong database is not something
   you can undo from here.

Running the tests
-----------------

.. code-block:: bash

   odoo-bin -c odoo.conf -d <database> \
       -u dms_certify_portal --test-enable \
       --test-tags /dms_certify_portal --stop-after-init

See :doc:`development/testing` for what the four test modules cover, how to
narrow to one class, and the audited list of what they do not cover yet.

Uninstalling
------------

:menuselection:`Apps --> DMS Certificate Portal --> Uninstall`, or:

.. code-block:: bash

   odoo-bin -c odoo.conf -d <database> \
       --uninstall dms_certify_portal --stop-after-init

.. warning::

   Uninstalling drops this addon's tables, and with them:

   * every ``dms.certificate`` — so **every document in circulation stops
     verifying**, and an embassy checking one is told it does not exist;
   * every ``dms.certificate.holder``, including the stored passport numbers
     and their hashes;
   * the whole attempt log, which is also your audit trail;
   * the document types, and the ``auto_stamp`` choices on them.

   The documents themselves survive: the source file is never written to, and
   the sealed and redacted copies are ``ir.attachment`` rows owned by the
   certificate. The pepper in ``ir.config_parameter`` is *not* removed by the
   uninstall, which is the one thing in your favour if you reinstall.

   ``@api.ondelete`` guards stop you deleting an *issued* certificate record
   by record, precisely because deleting one makes a genuine document read as
   forged. An uninstall is not subject to them — ``at_uninstall=False``. If
   documents are out there, do not uninstall; revoke instead.
