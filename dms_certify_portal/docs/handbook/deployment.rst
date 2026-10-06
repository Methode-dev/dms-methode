Deployment
==========

The things that have to be right **before a document is printed**, because most
of them cannot be changed afterwards. An address printed beside a QR code is in
an embassy's filing cabinet for months and cannot be re-pointed.

Read this page before :doc:`quickstart` if you are standing up a production
instance, and all of it before you issue anything in anger.

.. contents::
   :local:
   :depth: 2

The checklist
-------------

.. list-table::
   :header-rows: 1
   :widths: 6 50 44

   * -
     - Do this
     - Because
   * - ☐
     - ``dms_certify_host`` in ``server_wide_modules``
     - Otherwise the portal has no address and every public URL 404s
   * - ☐
     - DNS for ``check.<your host>``, and TLS covering that name
     - The portal only answers on a host starting ``check.``
   * - ☐
     - ``proxy_mode = True``, and the proxy sets ``X-Forwarded-For``
     - Without it the per-address limit becomes **one global limit**
   * - ☐
     - :guilabel:`Public verification URL` set, scheme included
     - **It goes on paper.** Set it before issuing anything
   * - ☐
     - :guilabel:`Portal company` chosen
     - Otherwise the page presents itself as whatever company a public request
       resolves to
   * - ☐
     - ``web.base.url`` correct, ``web.base.url.freeze`` set to ``True``
     - The derived fallback for the public URL is built from it, and an
       unfrozen value is rewritten by the next admin login
   * - ☐
     - ``dms_certify_portal.passport_key`` in the backup procedure
     - Lose it and **no document opens**, ever again
   * - ☐
     - nginx: two ``limit_req`` zones on the check vhost, ``robots.txt``, and
       ``/_check`` refused on the ordinary vhost
     - :ref:`deployment-nginx`
   * - ☐
     - If the embassies have static egress addresses, allowlist them
     - Worth more than everything else on this list put together
   * - ☐
     - Seal house style agreed, and :guilabel:`Stamp on generation` ticked for
       the right document types
     - :doc:`administration`
   * - ☐
     - Retention period agreed with whoever signs off the processing record
     - :doc:`security-and-privacy`
   * - ☐
     - Optionally, ``google_recaptcha`` installed **and keyed**
     - It is silent when absent *and* when unconfigured

.. _deployment-check-host:

The check host
--------------

|addon| declares every public route under the internal prefix ``/_check``, and
**nothing is ever served at that path**. An ``ir.http`` override rewrites ``/``
to ``/_check``, ``/d/REF`` to ``/_check/d/REF`` and so on — but only when the
request arrived on a host beginning ``check.``. On any other host the same
override raises a 404 for anything under ``/_check``, so the namespace does not
exist outside the portal's own name.

Three pieces have to line up.

**1. The module, loaded server-wide.**

.. code-block:: ini

   [options]
   server_wide_modules = base,web,dms_certify_host
   proxy_mode = True

``dms_certify_host`` patches ``odoo.http.db_filter`` at import time so that
``check.erp.example`` resolves to the **same database** as ``erp.example``.
Odoo picks a database from the host name, and without the patch a ``dbfilter``
keyed on ``%h`` or ``%d`` goes looking for a database called *check*. The patch
has to be in place before any request has to resolve a database, which is what
``server_wide_modules`` means.

.. important::

   ``server_wide_modules`` **replaces** Odoo's default (``base,web``) rather
   than adding to it. Repeat both, or the web client stops loading.

   On start you should see:
   ``dms_certify_host: check.* hosts use their parent host's database``. If that
   line is absent, nothing below will work.

**2. DNS.** An ``A`` record, or a ``CNAME`` onto the parent name, for
``check.<host>`` — one per environment you intend the portal to answer on
(``check.erp.example``, ``check.preprod.example``).

**3. TLS covering the new name.** Either a wildcard certificate, or a SAN
certificate listing both ``erp.example`` and ``check.erp.example``. A name
mismatch here is the one failure an embassy agent will interpret as *"this
organisation's verification page is not trustworthy"*, which is the exact
opposite of the point.

**4. A proxy that passes ``Host`` through unchanged.** The host test is a string
comparison on the request's host, so a proxy that rewrites ``Host`` to the
upstream name defeats the whole mechanism: the request arrives looking like an
ordinary back-office request and Odoo serves the back office on your public
name.

.. code-block:: nginx

   proxy_set_header Host $host;    # not $proxy_host, not a literal

Confirm it from both sides before going further:

.. code-block:: bash

   # the portal answers at the bare path on the check host
   curl -sI -H 'Host: check.erp.example' http://127.0.0.1:8069/ | head -1

   # the internal prefix is a 404 on the ordinary host
   curl -sI -H 'Host: erp.example' http://127.0.0.1:8069/_check | head -1

A ``200`` then a ``404``. Anything else is :doc:`troubleshooting`.

.. note::

   A document issued **before** the check host existed carries whatever URL was
   derived at the time. The URL is a computed field, so the back office will
   show the new one — but the paper will not. That is the whole reason this
   section comes before the quickstart.

``--proxy-mode``, and what omitting it costs
--------------------------------------------

.. admonition:: Without it, the per-address limit becomes one global limit
   :class: important

   The portal reads the client address from ``request.httprequest.remote_addr``.
   Werkzeug only resolves that from ``X-Forwarded-For`` when Odoo runs with
   ``--proxy-mode``. Without it, **every request appears to come from the
   reverse proxy** — so every failure anywhere in the world lands in the same
   bucket, and ten of them pause the form for every embassy at once.

   Nothing fails loudly. The behaviour is simply wrong, and the symptom —
   *"checks from here are paused"* for agents who have not made a single
   mistake — is :doc:`troubleshooting`'s second entry.

Set it in ``odoo.conf`` as ``proxy_mode = True`` rather than relying on a
command-line flag somebody has to remember. And make sure the proxy actually
sets the header:

.. code-block:: nginx

   proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
   proxy_set_header X-Forwarded-Proto $scheme;
   proxy_set_header X-Real-IP $remote_addr;

The address is also what the attempt log records, so without ``--proxy-mode``
the audit trail is a column of identical values.

The address that goes on paper
------------------------------

:menuselection:`Settings --> General Settings --> Document verification portal
--> Public verification URL`.

.. warning::

   This is printed beside the QR code and encoded **inside** it, on documents
   that circulate for months. A document already in an embassy's file cannot be
   re-pointed, and there is no redirect you can add later that will help if the
   host name itself was wrong. **Set it before you issue anything.**

It is its own parameter rather than ``web.base.url`` precisely because the
address an embassy types has to be able to differ from wherever this Odoo
happens to answer — a migration, a new ERP hostname, a vanity name.

Leave it empty and the base is derived from ``web.base.url`` with ``check.``
prefixed: ``https://erp.example`` becomes ``https://check.erp.example``. That
fallback is convenient in development and a liability in production, because it
makes the printed address depend on a parameter that Odoo rewrites on every
administrator login unless you stop it:

.. code-block:: python

   >>> env["ir.config_parameter"].sudo().set_param(
   ...     "web.base.url.freeze", "True")

Confirm what will actually be printed, rather than trusting the Settings page:

.. code-block:: python

   >>> env["dms.certificate"]._public_base_url()
   'https://check.erp.example'

Then set :guilabel:`Portal company`, which is whose name, address, email and
phone the public page carries — including on the refusal pages, which tell an
agent to call the operations desk. Empty means whatever company a public request
resolves to, which is nobody's decision.

Back up the pepper
------------------

``dms_certify_portal.passport_key`` is generated once, at install: 48 random
URL-safe bytes in ``ir.config_parameter``. Every stored second-factor hash is an
HMAC under it.

.. warning::

   There is no key history, no secondary key and no re-derivation path. If the
   parameter is deleted or overwritten, **no document opens** — the lookup form
   refuses every correct passport with the same message it gives a wrong one.

   The stored passport numbers are still there, so a recovery script *could*
   re-hash from them; nothing in the module does that for you, and a holder
   whose number was never stored cannot be recovered at all.

So: back it up **with** the filestore, not instead of it. A database dump
contains it, which is one more reason a dump of this database is sensitive
(:doc:`security-and-privacy`). Rotating it is a migration that re-hashes from a
trusted source, not a settings change.

.. code-block:: bash

   # a one-line check that belongs in your post-restore smoke test
   psql -d <database> -tAc "SELECT value IS NOT NULL FROM ir_config_parameter \
       WHERE key = 'dms_certify_portal.passport_key'"

.. _deployment-nginx:

nginx
-----

Two things nginx does that Odoo cannot: it serves a ``robots.txt`` (there is no
``website`` module here, so Odoo serves none — :ref:`limits-no-website`), and it
refuses a flood **before** it costs a worker and a database connection.

Why two rate-limit zones
^^^^^^^^^^^^^^^^^^^^^^^^

**One lookup is not one request.** An agent checking a two-page letter costs the
form, the ``POST``, the result page, one image per page, and often the download —
six or more requests. So:

* a single limit sized for the ``POST`` (the guessing surface) throttles a busy
  counter doing its job;
* a single limit sized for the page images does not slow a guesser down at all.

Hence one zone keyed on the address **only for POSTs**, and a second, looser one
for all portal traffic. nginx does not account a request whose key evaluates
empty, which is what the ``map`` below exploits: ``GET``\ s never touch the
submit zone.

The configuration
^^^^^^^^^^^^^^^^^

At the top of the file:

.. code-block:: nginx

   map $request_method $check_submit_key {
       POST    $binary_remote_addr;
       default "";
   }

   limit_req_zone $check_submit_key   zone=check_submit:10m  rate=20r/m;
   limit_req_zone $binary_remote_addr zone=check_traffic:10m rate=120r/m;

On the **ordinary** vhost — a second lock in front of the one Odoo already
applies:

.. code-block:: nginx

   # The portal's internal prefix only means something on check.*.
   location ^~ /_check {
       return 404;
   }

And a server block of its own for the portal:

.. code-block:: nginx

   server {
       listen 443 ssl http2;
       server_name check.*;

       # Set once; no location below redefines these, so all inherit them.
       proxy_set_header Host               $host;
       proxy_set_header X-Forwarded-Host   $host;
       proxy_set_header X-Forwarded-For    $proxy_add_x_forwarded_for;
       proxy_set_header X-Forwarded-Proto  $scheme;
       proxy_set_header X-Real-IP          $remote_addr;

       # The portal only ever receives a reference and a passport number.
       client_max_body_size 64k;

       # Its own logs, so a flood on the portal is legible without
       # grepping it out of the back office's traffic.
       access_log /var/log/nginx/check.access.log;
       error_log  /var/log/nginx/check.error.log;

       # Odoo serves no robots.txt without `website`. The pages also send
       # X-Robots-Tag and a robots meta; this is the belt to those braces.
       location = /robots.txt {
           default_type text/plain;
           return 200 "User-agent: *\nDisallow: /\n";
       }

       # Unreachable anyway, since Odoo prefixes every path on this host —
       # unless database routing ever broke and Odoo fell back to no-db mode.
       location ^~ /web/database/ {
           return 404;
       }

       # Bundles and static files are not the guessing surface, and one page
       # load pulls several at once. Not rate-limited.
       location ^~ /web/assets/ {
           proxy_pass http://127.0.0.1:8069;
           proxy_http_version 1.1;
       }

       location ~ ^/[a-z0-9_]+/static/ {
           proxy_pass http://127.0.0.1:8069;
           proxy_http_version 1.1;
           expires 864000;
           add_header Cache-Control "public";
       }

       # Everything else is the portal.
       location / {
           limit_req zone=check_submit  burst=5  nodelay;
           limit_req zone=check_traffic burst=40 nodelay;
           # 429, not nginx's default 503: this is telling a person to slow
           # down, not reporting that the service is broken.
           limit_req_status 429;

           # If the set of embassies is known and they have static addresses:
           # allow 203.0.113.0/24;
           # deny all;

           proxy_pass http://127.0.0.1:8069;
           proxy_redirect off;
           proxy_http_version 1.1;
       }
   }

Note ``Disallow: /`` rather than a path: on this host *everything* is the
portal, so there is nothing a crawler should be reaching.

What those numbers mean in practice: ``rate=20r/m`` with ``burst=5 nodelay``
lets six rapid submissions through from cold and refuses the rest until the
bucket drains, while a realistic lookup — one ``POST`` and half a dozen ``GET``\
s — never touches the submit zone at all after its single ``POST``.

.. important::

   These limits sit **in front of** the application's own two
   (:doc:`administration`), which are the ones that actually protect a document.
   nginx caps a flood; the per-reference lock is what stops five careful
   guesses at one letter. Neither replaces the other.

.. todo::

   ``README.md``'s nginx section is written for the **old** layout: zones named
   ``verify_submit``/``verify_traffic``, ``location /verify`` on the main vhost,
   and ``Disallow: /verify``. The portal moved to the ``/_check`` namespace
   behind the check-host rewrite, so that block now rate-limits a path that
   returns 404 and leaves the real portal unlimited.

   This repository is half-migrated with it: ``nginx/nginx.dev.conf`` has the
   ``check.*`` server block and the ``check_submit``/``check_traffic`` zones
   above, while **``nginx/nginx.conf.template`` — the production one — still
   says** ``location /verify`` **and** ``Disallow: /verify``, **and has no**
   ``check.*`` **block at all**. ``odoo.conf`` sets no ``server_wide_modules``
   either. As it stands the portal is reachable in development and not in
   production. Port the dev block to the template, and fix the README.

The IP allowlist
----------------

If the set of embassies is known and they have static egress addresses, the two
commented lines in the ``location /`` block above are worth more than everything
else on this page combined:

.. code-block:: nginx

   allow 203.0.113.0/24;   # Consulate, Yangon
   allow 198.51.100.17;    # Consulate, Manila
   deny all;

It turns an anonymous public form into a private one, and no amount of guessing
at references matters to an address that cannot reach the port.

The reasons not to are real, though, and worth stating so the decision is made
rather than drifted into: embassies change providers without telling you, agents
check documents from home, and a 403 at the counter is indistinguishable from a
forged document from where the agent is standing. If you allowlist, keep the
operations desk's phone number on the 403 page.

reCAPTCHA
---------

Optional. ``google_recaptcha`` is **not** in ``depends``; the controller looks
for Odoo's own verifier at request time and, if it is not there, carries on.
Install the module, set the keys in :menuselection:`Settings --> General
Settings --> Integrations`, and enforcement begins with no code change — the
form grows an invisible v3 widget and the token travels with the submission.

.. warning::

   A misconfiguration here is **silent, twice over**. The controller returns
   *pass* when the module is absent, and Odoo's own hook returns *pass* when no
   site key is configured — so an installed-but-unkeyed instance is
   indistinguishable from one that never installed it, and the form keeps
   working with no captcha.

   The only signal is the absence of a value in ``recaptcha_public_key``, which
   is what the form reads to decide whether to render the widget at all. Check
   for the widget in the page source, not for the module in the apps list.

A third edge: the verifier's signature has moved between Odoo versions. The
controller tries two call shapes and treats anything else as a failure — which
fails closed, but also means a future signature change presents as *"every
lookup fails the captcha"* rather than as a traceback. See :doc:`../limits`.

After you deploy
----------------

Four things to check once, with a real browser, on the real host:

#. The form loads over HTTPS on ``check.<host>``, with the company's name and
   address in the footer and the language switcher offering the languages you
   expect.
#. ``https://<host>/_check`` is a 404, and ``https://check.<host>/web`` is
   **not** the back office.
#. A successful lookup from an external address shows a real client address in
   :menuselection:`Consular --> Reporting --> Verification attempts`, not your
   proxy's.
#. ``curl -sI https://check.<host>/`` carries ``Cache-Control: no-store`` and
   ``X-Robots-Tag: noindex, nofollow, noarchive``, and
   ``https://check.<host>/robots.txt`` returns ``Disallow: /``.

See also
--------

* :doc:`../installation` — the install itself, and
  :ref:`installation-check-host`
* :doc:`administration` — the two application-level limits these sit in front
  of
* :doc:`security-and-privacy` — the design refusals, and what to settle before
  going live
* :doc:`troubleshooting` — the portal 404s, everything throttled at once, the
  printed URL pointing at the wrong host
* :doc:`../reference/models/ir_http` — the rewrite itself, in 29 lines
* :doc:`../reference/controllers/verify` — every route these limits are in
  front of
* :doc:`../limits` — no ``robots.txt`` from Odoo, and reCAPTCHA's silence
