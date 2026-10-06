verify
======

.. py:currentmodule:: odoo.addons.dms_certify_portal.controllers.main

Source: :ghsrc:`controllers/main.py`

.. py:class:: DmsCertifyPortalController

   Bases: ``odoo.http.Controller``

   :Routes: seven, all under ``/_check``, all ``type="http"``, all ``auth="public"``

   The whole public surface of the module. There is no account behind it, no
   portal user, and no ``website`` dependency — see :ref:`limits-no-website`.
   Everything an embassy agent can reach, they reach through one of these seven
   routes, and every one of them either refuses or hands back plain data.

.. contents::
   :local:
   :depth: 2

The routes
----------

.. list-table::
   :header-rows: 1
   :widths: 20 24 10 10 10 26

   * - Method
     - Path
     - ``type``
     - ``auth``
     - ``methods``
     - Other options
   * - :py:meth:`~DmsCertifyPortalController.verify_form`
     - ``/_check``
     - ``http``
     - ``public``
     - ``GET``
     - ``readonly=True``
   * - :py:meth:`~DmsCertifyPortalController.verify_form_prefilled`
     - ``/_check/d/<string:reference>``
     - ``http``
     - ``public``
     - ``GET``
     - ``readonly=True``
   * - :py:meth:`~DmsCertifyPortalController.verify_submit`
     - ``/_check``
     - ``http``
     - ``public``
     - ``POST``
     - ``csrf=True``, ``readonly=False``
   * - :py:meth:`~DmsCertifyPortalController.verify_result`
     - ``/_check/r/<string:token>``
     - ``http``
     - ``public``
     - ``GET``
     - ``readonly=True``
   * - :py:meth:`~DmsCertifyPortalController.verify_page_image`
     - ``/_check/r/<string:token>/page/<int:page>``
     - ``http``
     - ``public``
     - ``GET``
     - ``readonly=True``
   * - :py:meth:`~DmsCertifyPortalController.verify_download`
     - ``/_check/r/<string:token>/file``
     - ``http``
     - ``public``
     - ``GET``
     - ``readonly=True``
   * - :py:meth:`~DmsCertifyPortalController.verify_mismatch`
     - ``/_check/r/<string:token>/mismatch``
     - ``http``
     - ``public``
     - ``POST``
     - ``csrf=True``, ``readonly=False``

``csrf`` is left at its default on the five ``GET`` routes and set explicitly on
the two ``POST`` routes. Both posts come from a form this module renders itself,
so there is a session and a token to check — the opposite of a machine-to-machine
webhook, where the only sane value is ``False``.

``readonly=True`` on the five reading routes lets Odoo serve them from a
read-only cursor. ``verify_submit`` writes an attempt row and a session, and
``verify_mismatch`` writes an attempt row and a chatter message, so both are
``readonly=False``.

Never write ``/_check`` into a page
-----------------------------------

The declared paths are an internal namespace. :doc:`../models/ir_http` rewrites
``/x`` on the check host to ``/_check/x`` before routing, and raises
``NotFound`` for anything that asks for ``/_check…`` directly on any other host.
The two module constants are what the controller actually emits:

.. py:data:: FORM_URL
   :type: str
   :value: '/'

.. py:data:: RESULT_URL
   :type: str
   :value: '/r/%s'

Every redirect in this file goes through one of those two, so the public URLs
stay host-relative and the ``/_check`` prefix never appears in a browser, a QR
code or a printed line. See :ref:`deployment-check-host`.

.. todo::

   ``README.md`` still documents the portal as living at ``/verify`` — the
   introduction, the "No ``/fr/verify`` language prefixes" note, and the whole
   nginx section (``location /verify``, ``Disallow: /verify``). The code has
   moved to the ``/_check`` namespace behind the check-host rewrite. Does the
   repository's ``nginx/nginx.conf.template`` and ``nginx/nginx.dev.conf`` still
   say ``location /verify`` too, or only the README? Fix both, and confirm which
   location block the rate-limit zones are attached to now.

Decisions worth naming
----------------------

POST-Redirect-GET
^^^^^^^^^^^^^^^^^

The second check — four characters of a passport, under the default
:ref:`second factor <concepts-second-factor>` — arrives in a ``POST`` body, is
matched, and is then dropped. It is never put into a URL, so it never reaches
browser history, never leaves in a ``Referer`` header, and never lands in an
nginx access log. What the browser is redirected to is an opaque session-bound
token, which identifies a result the server already computed and nothing else.

``Referrer-Policy: no-referrer`` in :py:data:`NO_STORE` closes the remaining
leak, which is the *reference* rather than the passport: without it, clicking any
link on the result page would hand ``/r/<token>`` to the link target.

One refusal for every failure
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

.. admonition:: Splitting the refusal would make the form an oracle
   :class: important

   ``no_match`` covers both "no such reference" and "that reference exists but
   the second check is wrong". Separating them would let anyone walk the
   reference space with an arbitrary passport value and keep the hits — an
   enumeration oracle, handed out for free in the name of a helpful error
   message. The comment saying so is in
   :py:meth:`~DmsCertifyPortalController.verify_submit` itself.

:py:meth:`~DmsCertifyPortalController.verify_form_prefilled` observes the same
rule from the other direction: it looks nothing up, it just echoes the scanned
value back into the form, so the QR landing page is equally silent about whether
the reference exists.

The one thing the refusal *does* disclose is how many tries are left on that
reference, via
:meth:`dms.certificate.attempt.reference_attempts_left`. An agent who mistyped
needs it, and somebody guessing can count their own failures anyway. The
wording of each refusal is in :doc:`../templates`; see
:ref:`verification-refusals` for the catalogue.

The session token
^^^^^^^^^^^^^^^^^

:py:meth:`~DmsCertifyPortalController.verify_submit` mints
``secrets.token_urlsafe(32)`` and stores it, the document id, the holder id and
an absolute expiry in the session.
:py:meth:`~DmsCertifyPortalController._session_document` compares the token from
the URL against the stored one with ``hmac.compare_digest`` — constant time, so
the comparison leaks nothing about how close a guess was — **after** checking
the expiry, and clears the session when it has passed.

The token on its own is worthless: it only resolves against the session that
minted it. Pasting ``/r/<token>`` into another browser gets the ``expired``
refusal, which is the point. Expiry is ``session_minutes`` (15 by default, see
:doc:`../data/ir_config_parameter`).

The order of the checks on submission
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

.. code-block:: text

   address throttle  ──▶ 429-shaped page, attempt logged 'throttled'
          │ open
   per-reference lock ──▶ throttled page, logged 'locked', desk notified
          │ open
   captcha            ──▶ _fail('captcha'), logged 'captcha'
          │ ok
   completeness       ──▶ _fail('incomplete'), logged 'no_match'
          │ both present
   match              ──▶ _fail('no_match'), logged, desk notified
          │ matched
   token + redirect to /r/<token>#result

That order is not arbitrary.

* **Both limits before the captcha.** The captcha is an outbound HTTP call to
  Google. Putting it first would let a flood turn into one upstream request per
  hit, which is a denial of service with extra steps.
* **The address limit before the reference lock**, because an address that has
  already burned its budget should not get to spend a database query on
  someone else's document.
* **The reference lock counted across every address.** The address limit stops
  one client hammering the whole registry; the reference lock is what actually
  protects a single document, and moving to a second address must not help.
  ``reference_lock_left`` returns minutes so the page can say *how long*.
* **Completeness after the captcha**, so an empty form still costs an attempt
  row and still counts against the limits. An empty submission is logged as
  ``no_match`` but refused as ``incomplete`` — the agent is told they left a box
  empty, and the counter is not fooled by it.
* **The match last**, because it is the only step that touches the hashes.

Every branch writes an attempt row through
:meth:`dms.certificate.attempt.log`, including the ones that never reach the
registry — the log is the throttle counter as well as the audit trail. See
:doc:`../models/dms_certificate_attempt`.

The captcha is a soft dependency
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

``google_recaptcha`` is **not** in the manifest's ``depends``.
:py:meth:`~DmsCertifyPortalController._captcha_ok` looks for
``ir.http._verify_recaptcha_token`` with ``getattr`` and returns ``True`` when it
is absent, so an instance without the module installed works unchanged. Odoo's
own hook also returns ``True`` when no site key is configured, so an installed
but unconfigured instance works too.

.. warning::

   The two fallbacks mean a misconfiguration is **silent**: the form keeps
   working, with no captcha. The only signal that the verifier is being skipped
   for a reason you did not intend is the absence of a site key in
   ``recaptcha_public_key``, which the form page reads for its widget.

The signature has moved between Odoo versions, so the call is tried as
``verifier(ip, token, action=…)`` first and as ``verifier(token, action=…)`` on
``TypeError``. Any other exception is logged and treated as a failure — a broken
captcha must refuse, not 500 the page, and must not pass either.

``_client_ip`` needs ``--proxy-mode``
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

.. important::

   :py:meth:`~DmsCertifyPortalController._client_ip` returns
   ``request.httprequest.remote_addr``. Werkzeug only resolves that from
   ``X-Forwarded-For`` when Odoo runs with ``--proxy-mode``. Without it, every
   request appears to come from the reverse proxy, and the per-address limit
   quietly becomes **one global limit** — ten failures from anyone in the world
   locks the form for everyone. Nothing fails loudly; the behaviour is just
   wrong. See :ref:`deployment-nginx`.

``NO_STORE`` on every response
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

.. py:data:: NO_STORE
   :type: list

   Applied by :py:meth:`~DmsCertifyPortalController._render` to every rendered
   page, and passed explicitly to ``make_response`` on the page images and the
   download.

   .. list-table::
      :header-rows: 1
      :widths: 24 76

      * - Header
        - Why
      * - ``Cache-Control: no-store, no-cache, must-revalidate, private``
        - A result page names a person and shows their document. It must not
          survive in a shared browser's cache or in an intermediate proxy
      * - ``Pragma: no-cache``
        - For the proxies that still only understand HTTP/1.0
      * - ``X-Robots-Tag: noindex, nofollow, noarchive``
        - There is no ``website`` module here, so Odoo serves no
          ``robots.txt``; this header is the module's own instruction to a
          crawler that finds the host
      * - ``Referrer-Policy: no-referrer``
        - Keeps the reference out of the ``Referer`` sent to any link target

The download streams through this controller
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

:py:meth:`~DmsCertifyPortalController.verify_download` reads the bytes and
writes the response itself. The docstring is explicit about the alternative:
never link ``/web/content/<id>``. That route is readable by anybody who knows
the attachment id once the attachment is public, which detaches the file from
the second check entirely — no token, no session, no rate limit. Streaming it
here keeps one gate in front of the bytes, and the gate is
:py:meth:`~DmsCertifyPortalController._session_document`.

The same reasoning runs one step further on
:py:meth:`~DmsCertifyPortalController.verify_page_image`, which hands back a PNG
rather than the PDF: a PDF viewer carries its own save, print and
text-extraction, none of which pass back through this gate.

Language, without ``http_routing``
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

There is no ``http_routing`` dependency, so there are no ``/fr/`` URL prefixes
and nothing in the path says which language a page is in. The choice rides a
``lang`` query parameter, and then sticks to the session under
``dms_certify_token``'s neighbour key ``dms_certify_lang``:

.. code-block:: text

   ?lang=fr  ──▶  session['dms_certify_lang']  ──▶  default_lang parameter  ──▶  'en_US'

:py:meth:`~DmsCertifyPortalController._install_language` resolves a two-letter
choice against the languages *actually active* in the database, matching on the
part before the underscore so ``fr`` finds ``fr_FR``, ``fr_BE`` or whatever this
instance loaded. Forcing ``fr_FR`` on a database that never loaded it renders
the source strings and looks broken, which is why the fallback matters more
than it looks.

Session keys
------------

All module-level, all prefixed ``dms_certify_`` so they cannot collide with
anything else sharing the session:

.. list-table::
   :header-rows: 1
   :widths: 26 30 44

   * - Constant
     - Session key
     - Holds
   * - ``SESSION_TOKEN``
     - ``dms_certify_token``
     - The result token minted on a successful match
   * - ``SESSION_DOC``
     - ``dms_certify_doc_id``
     - The matched ``dms.certificate`` id
   * - ``SESSION_HOLDER``
     - ``dms_certify_holder_id``
     - The matched ``dms.certificate.holder`` id — what scopes the result
   * - ``SESSION_EXPIRY``
     - ``dms_certify_expiry``
     - Absolute ``time.time()`` deadline for the token
   * - ``SESSION_ERROR``
     - ``dms_certify_error``
     - Refusal code, popped by the form page
   * - ``SESSION_NOTICE``
     - ``dms_certify_notice``
     - One-shot notice, popped by the result page
   * - ``SESSION_REFERENCE``
     - ``dms_certify_reference``
     - The reference as typed, given back so only the second check is retyped
   * - ``SESSION_LANG``
     - ``dms_certify_lang``
     - Resolved language code

The first four are the ones :py:meth:`~DmsCertifyPortalController._clear_session`
drops. The error, notice and reference keys are *popped* where they are read, so
a refusal shows once and a reload shows a clean form.

Request helpers
---------------

.. py:method:: DmsCertifyPortalController._client_ip()

   ``request.httprequest.remote_addr``. See the warning above about
   ``--proxy-mode``.

.. py:method:: DmsCertifyPortalController._param(name, default)

   Read ``dms_certify_portal.<name>`` as an ``int``, falling back to *default*
   on anything unparseable. Every caller passes the same default the data file
   ships, so a parameter somebody deleted or filled with a word behaves as
   though it were untouched rather than crashing the public page.

.. py:method:: DmsCertifyPortalController._text_param(name, default='')

   The same lookup without the integer coercion.

.. py:method:: DmsCertifyPortalController._bool_param(name, default='True')

   True for ``'True'``, ``'true'`` and ``'1'``. Anything else — including an
   empty string — is false, so a parameter set to ``0`` or ``False`` by hand
   works whichever spelling the administrator reached for.

Language
--------

.. py:method:: DmsCertifyPortalController._install_language(wanted=None)

   Resolve a requested two-letter code against the active ``res.lang`` records,
   matching on the part before the underscore. Precedence: the argument, then
   the session, then the ``default_lang`` parameter (``fr``), then
   ``request.env.context['lang']`` or ``en_US``.

.. py:method:: DmsCertifyPortalController._language_values(current)

   The switcher. Filtered by :py:func:`~odoo.addons.dms_certify_portal.hooks.portal_language_codes`,
   so only the languages the **portal copy** exists in are offered — a database
   with six back-office languages installed should not show an embassy six
   buttons, five of which lead to an English page. Each option's ``url`` is
   ``FORM_URL`` with ``?lang=<short>``, which is why switching language from the
   result page returns to the form.

.. py:method:: DmsCertifyPortalController._use_language(requested=None)

   Resolve, store in the session, and ``request.update_context(lang=…)``.
   Called first in every route, including
   :py:meth:`~DmsCertifyPortalController.verify_mismatch`, which has no page to
   render but can still end up redirecting to one.

Captcha
-------

.. py:method:: DmsCertifyPortalController._captcha_ok(token)

   See `The captcha is a soft dependency`_. Returns ``True`` when
   ``google_recaptcha`` is not installed.

   .. note::

      If this ever starts failing silently after an Odoo upgrade, the thing to
      check is the signature of ``_verify_recaptcha_token`` in
      ``google_recaptcha/models/ir_http.py`` — the controller already handles
      two shapes of it and would need a third.

Rendering
---------

Nothing in this file hands a recordset to a template. The result page is built
from :meth:`dms.certificate._get_public_values`, a whitelisted dict, so a later
edit to a template cannot walk from the portal into business records. The same
rule produces the two methods below.

.. py:method:: DmsCertifyPortalController._portal_company()

   The organisation the public page presents itself as — the
   ``company_id`` parameter when set, otherwise ``request.env.company``.
   Configurable because an embassy is looking at one organisation whichever of
   its companies issued the document, and because a public request otherwise
   resolves to whatever company the public user happens to default to, which is
   nobody's decision.

.. py:method:: DmsCertifyPortalController._company_values()

   Seven strings: name, street, street2, zip, city, email, phone. The company
   *record* stays out of the templates deliberately — one dot from it sits a
   partner, and one more a bank account.

.. py:method:: DmsCertifyPortalController._chrome(lang)

   What every page needs: the language options, ``reference_groups``,
   ``reference_sample`` and the company block. ``reference_groups`` is
   ``[len(prefix), 4, 3, 4, 2]`` — derived from ``reference_prefix`` rather than
   hard-coded, so an instance that renamed its prefix to something other than
   three characters still gets an input mask that formats the way its documents
   print. It drives both the browser mask (:doc:`../static/verify`) and
   :py:meth:`~DmsCertifyPortalController._format_reference`.

.. py:method:: DmsCertifyPortalController._format_reference(value)

   Re-group a reference the way it is printed, by normalising it through
   :meth:`dms.certificate._normalize_reference` and re-splitting on
   ``reference_groups``. A refusal has to give back what the agent typed, not
   the stripped lookup form — answering a careful reader with a run-on string
   invites them to mistype it again. Anything longer than the groups account
   for is appended as a final group rather than dropped.

.. py:method:: DmsCertifyPortalController._form_values(lang, **extra)

   Pops the refusal code and the remembered reference out of the session, and
   when both are present asks
   :meth:`dms.certificate.attempt.reference_attempts_left` how many tries are
   left. Also passes ``recaptcha_public_key`` straight through, which is how the
   template knows whether to render the widget at all.

.. py:method:: DmsCertifyPortalController._render(template, values, headers=None)

   ``request.render`` plus :py:data:`NO_STORE` and anything extra. Every page in
   this controller goes through it, which is what makes the no-store guarantee
   structural rather than something each route has to remember.

.. py:method:: DmsCertifyPortalController._fail(code, reference=None)

   Refuse, carrying a reason *code* rather than a sentence, and redirect to
   ``FORM_URL + '#result'``.

   Two decisions in four lines:

   * **A code, not a sentence.** Odoo's translation exporter does not walk
     Python source in this layout, so a sentence built here would be invisible
     to the export and would sit in English on a French page for ever. The
     wording lives in :doc:`../templates` with the rest of the portal's copy.
   * **The ``#result`` fragment.** The verdict renders below the lookup form on
     the same page. A plain redirect lands the browser at the top of it and
     leaves the agent to scroll for the refusal; the fragment jumps straight
     to it.

Session
-------

.. py:method:: DmsCertifyPortalController._clear_session()

   Drops the token, document, holder and expiry keys. The language is not
   touched — somebody whose session expired is still reading French.

.. py:method:: DmsCertifyPortalController._session_document(token)

   The gate in front of all four result routes. Returns
   ``(certificate, holder)``, both empty recordsets on any failure, so a caller
   can test it as falsy *and* call ``.id`` on it.

   In order: a stored token and document id must exist; the expiry must not have
   passed (and if it has, the session is cleared); the token must match under
   ``hmac.compare_digest``; the document must still ``exists()``. The holder is
   then loaded and **discarded if it does not belong to that certificate** —
   under confirm-only :ref:`disclosure <concepts-disclosure>` the holder is what
   the page is allowed to name, so a stale holder id must not carry over onto
   another document's result.

.. py:method:: DmsCertifyPortalController._tell_the_desk(reference_key, outcome, minutes=0, document=None)

   Post a lookup onto the certificate it was aimed at, via
   :meth:`dms.certificate._notify_verification`.

   When no document matched there is nothing to post onto, so the certificate is
   searched by ``reference_key`` instead. That is the case worth notifying: the
   reference is right and the second check is not, which an operator at the
   issuing desk wants to know about *their* document.

The form
--------

.. py:method:: DmsCertifyPortalController.verify_form(lang=None, **kw)

   .. code-block:: python

      @http.route('/_check', type='http', auth='public',
                  methods=['GET'], readonly=True)

   Renders ``dms_certify_portal.verify_form``. Any refusal from a previous
   ``POST`` surfaces here, which is why this route and the submission share a
   path.

.. py:method:: DmsCertifyPortalController.verify_form_prefilled(reference, lang=None, **kw)

   .. code-block:: python

      @http.route('/_check/d/<string:reference>', type='http', auth='public',
                  methods=['GET'], readonly=True)

   The landing page for the QR code printed in the seal block.

   **Nothing is looked up.** The scanned value is echoed straight back into the
   form, truncated to 32 characters, which keeps this route silent about whether
   the reference exists.

   The QR carries the reference itself rather than a second token, which is what
   makes scanning and retyping exactly equivalent — the printed line beside it
   says so in as many words. It is not a credential either way: whoever
   photographs the document gets this URL, so the second check still gates the
   result.

The submission
--------------

.. py:method:: DmsCertifyPortalController.verify_submit(reference=None, passport=None, **kw)

   .. code-block:: python

      @http.route('/_check', type='http', auth='public',
                  methods=['POST'], csrf=True, readonly=False)

   See `The order of the checks on submission`_ for the sequence and the
   reasons. On success it logs the attempt as ``matched``, calls
   :meth:`dms.certificate._register_verification`, notifies the desk, mints the
   token and redirects to ``/r/<token>#result``.

   The two throttle branches render ``dms_certify_portal.verify_throttled``
   rather than redirecting, and pass ``locked_reference`` so the page can tell
   an agent whether the wait is theirs or the document's:

   .. list-table::
      :header-rows: 1
      :widths: 26 20 54

      * - Branch
        - ``locked_reference``
        - ``window_minutes``
      * - Address throttle
        - ``False``
        - the ``window_minutes`` parameter
      * - Reference lock
        - ``True``
        - minutes left, from ``reference_lock_left``

   The parameter name ``passport`` is the field name on the form, not a claim
   about what it contains — which second factor the value is checked against is
   per certificate, and matching is
   :meth:`dms.certificate._match`'s job.

The result
----------

.. py:method:: DmsCertifyPortalController.verify_result(token, lang=None, **kw)

   .. code-block:: python

      @http.route('/_check/r/<string:token>', type='http', auth='public',
                  methods=['GET'], readonly=True)

   Renders ``dms_certify_portal.verify_result`` from
   :meth:`dms.certificate._get_public_values`, plus the one-shot notice,
   ``allow_download`` and ``expires_in``.

   An unresolvable token is ``_fail('expired')`` — a redirect back to the form
   with a refusal, not a 404. Somebody whose fifteen minutes ran out should land
   somewhere they can try again.

.. py:method:: DmsCertifyPortalController.verify_page_image(token, page, **kw)

   .. code-block:: python

      @http.route('/_check/r/<string:token>/page/<int:page>', type='http',
                  auth='public', methods=['GET'], readonly=True)

   One page of the document, rasterised to PNG by
   :func:`~dms_certify_portal.tools.seal.render_page` behind
   :meth:`dms.certificate._public_page_image`. The page number is 1-based in the
   URL and clamped with ``max(0, page - 1)``, so ``/page/0`` and ``/page/1``
   both give the first page rather than an error.

   The holder is passed through, because under confirm-only disclosure the copy
   is built to hide everyone except the person the agent actually checked — see
   :ref:`sealing-redaction`.

   Both a bad token and a page past the end return ``request.not_found()``: this
   route is a sub-resource of a page the caller is already looking at, so there
   is no refusal worth rendering.

.. py:method:: DmsCertifyPortalController.verify_download(token, **kw)

   .. code-block:: python

      @http.route('/_check/r/<string:token>/file', type='http', auth='public',
                  methods=['GET'], readonly=True)

   The sealed PDF, as an attachment named ``<reference>.pdf`` with ``/``
   replaced by ``-``. Returns ``not_found()`` when ``allow_download`` is off —
   checked here as well as in the template, so turning the setting off actually
   closes the route rather than only hiding the button.

   See `The download streams through this controller`_ for why this is not a
   link to ``/web/content``.

.. py:method:: DmsCertifyPortalController.verify_mismatch(token, **kw)

   .. code-block:: python

      @http.route('/_check/r/<string:token>/mismatch', type='http',
                  auth='public', methods=['POST'], csrf=True, readonly=False)

   *"The paper does not match."*

   The most valuable thing this portal can collect. A document that verifies
   while the paper in front of the agent differs from it is either a forgery
   built on a real reference or a stale copy, and either way somebody at the
   issuing desk needs to know within minutes — so this logs an attempt with
   outcome ``mismatch`` **and** calls
   :meth:`dms.certificate._notify_verification` directly rather than going
   through :py:meth:`~DmsCertifyPortalController._tell_the_desk` (the document is
   already in hand).

   It then sets the ``mismatch_reported`` notice and redirects back to
   ``/r/<token>#result``, so the agent sees that the report landed. An
   unresolvable token redirects to the form and writes nothing.

Everything runs ``sudo``
------------------------

There is no user behind these routes, so every ORM call is ``sudo()``. That is
why there is no public ACL and must never be one — see :doc:`../security/ir_rule`.
The token, the session expiry and the two rate limits are the authorisation; the
``ir.model.access`` matrix has no part in it.

See also
--------

* :doc:`../../handbook/verification` — the agent's view, and every refusal the
  form can give
* :doc:`../models/dms_certificate` — ``_match``, ``_get_public_values`` and what
  the public dict is allowed to contain
* :doc:`../models/dms_certificate_attempt` — the attempt log, and both rate
  limits in full
* :doc:`../models/ir_http` — the check-host rewrite that turns ``/`` into
  ``/_check``
* :doc:`../tools/seal` — what the QR code in the seal block points at, and the
  rasterising the page images go through
* :doc:`../templates` — the three public templates and where the refusal wording
  lives
* :doc:`../static/verify` — the input mask and the form's client side
* :doc:`../data/ir_config_parameter` — ``session_minutes``, ``allow_download``,
  ``default_lang`` and the throttle settings
* :doc:`../../handbook/deployment` — ``--proxy-mode``, the check host, and the
  nginx limits in front of these routes
