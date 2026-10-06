ir.http
=======

.. py:currentmodule:: odoo.addons.dms_certify_portal.models.ir_http

Source: :ghsrc:`models/ir_http.py`

.. py:class:: IrHttp

   Bases: ``odoo.models.AbstractModel`` with ``_inherit = "ir.http"`` — an
   extension of Odoo's own request dispatcher.

   :Odoo model: ``ir.http`` — abstract; there are no records and nothing to
      browse
   :Description: inherited from ``base``; not redeclared here
   :Order: not applicable
   :Constraints: none

   Twenty-nine lines, and they are the reason the public portal is reachable on
   ``check.<host>`` and nowhere else, and the reason the back office is
   reachable *everywhere* else and not there. Two classmethods, four lines of
   logic, and almost all of the module's security posture that is not in the
   controller.

   .. admonition:: Why the routes are declared under ``/_check`` and then rewritten
      :class: important

      The portal's pages want to live at the root of their own host: an agent
      retypes ``check.example.com/d/ICS-2026-DKK-4KQ7-9B`` off a faxed page, and
      every segment they do not have to type is a segment they cannot mistype.

      Odoo's routing map, though, is global. A controller declared at ``/``
      would answer on the ERP host too, colliding with the back office's own
      root, and ``@http.route`` has no notion of a host to scope it with.

      So the routes are declared in an internal namespace —
      :py:data:`PORTAL_PREFIX`, ``/_check`` — and this override is what maps
      the public shape onto it:

      .. code-block:: text

         check.example.com/                    ──▶  /_check
         check.example.com/d/ICS-…             ──▶  /_check/d/ICS-…
         check.example.com/r/<token>/page/1    ──▶  /_check/r/<token>/page/1
         check.example.com/web/assets/…        ──▶  /web/assets/…        (untouched)
         check.example.com/odoo               ──▶  /_check/odoo          → 404
         check.example.com/_check              ──▶  /_check/_check       → 404

         example.com/_check…                   ──▶  404, explicitly
         example.com/                          ──▶  the back office, untouched

      The namespace is an implementation detail and **must never be emitted**.
      :py:attr:`DmsCertificate.verify_url
      <odoo.addons.dms_certify_portal.models.dms_certificate.DmsCertificate.verify_url>`
      builds ``{public base}/d/{reference}``, and the controller's own
      ``FORM_URL`` and ``RESULT_URL`` are ``/`` and ``/r/%s`` — a ``/_check``
      in a redirect or a QR code would be rewritten a second time and 404.

   Which host is which is not decided here. ``is_check_host()`` comes from
   ``dms_certify_host``, a separate server-wide addon, because the decision has
   to be made before a database is even selected — see
   :ref:`installation-check-host` and :ref:`deployment-check-host`.

.. contents::
   :local:
   :depth: 2

Module constants
----------------

.. _ir_http-PORTAL_PREFIX:

.. py:data:: PORTAL_PREFIX
   :type: str
   :value: "/_check"

   The internal namespace every public route is declared under. Leading
   underscore so it cannot collide with a business path somebody adds later,
   and short enough that the rewrite does not push any URL past a length limit.

   It is the **only** prefix: the controller hard-codes ``/_check`` in its own
   ``@http.route`` decorators rather than importing this constant, so the two
   have to agree by hand. Changing it means changing both files.

.. _ir_http-PASSTHROUGH:

.. py:data:: PASSTHROUGH
   :type: tuple[str]
   :value: ("/web/assets/",)

   Path prefixes the rewrite leaves alone on the check host. One entry, and it
   is there because the public page is styled and scripted:
   ``verify.scss`` and ``verify.js`` are served out of
   ``web.assets_frontend`` from ``/web/assets/…`` (:doc:`../assets`), and a
   rewritten asset URL would 404.

   .. warning::

      This is the one back-office path open on the portal host, so it is the one
      to think about when adding to this tuple. Widening it widens the public
      surface of a host that is otherwise a dead end.

      The failure mode if it ever stops working is quiet, not loud: the page
      still returns **200** and still verifies documents, it merely renders
      unstyled and without its input mask. Nothing else in the module would
      notice, which is why there is a test that walks every asset URL the page
      references and asserts each one is served
      (``test_the_portal_assets_are_served_on_the_check_host``).

   A tuple rather than a list because it is passed straight to
   ``str.startswith``, which takes a tuple of candidates and not a list.

Dispatch
--------

.. _ir_http-match:

.. py:method:: IrHttp._match(path_info)
   :classmethod:

   Rewrite the path on the check host; refuse the internal namespace off it.
   Then ``super()``.

   :raises werkzeug.exceptions.NotFound: when a request **off** the check host
      asks for :py:data:`PORTAL_PREFIX` or anything under it.

   Three branches, and each one is a decision.

   **On the check host, prefix everything that is not an asset.** ``/`` becomes
   ``/_check`` and not ``/_check/`` — the special case is explicit in the
   expression — because the controller's form route is declared at ``/_check``
   exactly, and Odoo's routing map does not treat the two as the same rule.

   **Off the check host, 404 the namespace explicitly.** Without this branch
   ``example.com/_check`` would reach the real route and serve the verification
   form on the ERP host, where it has no business being: that host has no
   ``limit_req`` sized for it, it is the host with the back office on it, and a
   second address for the same form is a second address for an attacker to work
   from. The comment in the source is the whole justification — *"the internal
   namespace does not exist outside check.\*"*. Test:
   ``test_the_internal_namespace_is_closed_on_the_plain_host``.

   **On the check host the namespace is still not addressable**, and that falls
   out of the branches being ``if``/``elif`` rather than two independent
   checks. A request for ``/_check`` on the check host takes the first branch
   and is rewritten to ``/_check/_check``, which matches nothing. There is
   exactly one way to reach the routes — the rewrite — and no way to address
   them directly from either host. Test:
   ``test_the_internal_namespace_is_not_addressable_on_the_check_host``.

   .. note::

      The guard is ``if request and is_check_host()``, with the falsy-request
      case falling through to the ``elif``. ``is_check_host()`` already handles
      a missing request (it reads ``request.httprequest.host`` lazily and
      substitutes ``""``), so the explicit test is belt and braces — but note
      which way it fails. With no request there is no host to trust, and the
      code takes the *off-host* branch: the namespace is closed and nothing is
      rewritten. The safe default is the one that serves no portal.

   Overriding ``_match`` rather than hooking the request earlier is what keeps
   the rewrite invisible to everything downstream. ``_match`` is where Odoo
   turns a path into a routing rule, so by the time any controller, any
   ``request.redirect``, or any CSRF check sees the request, the path is already
   the internal one and no other layer needs to know the external shape exists.

.. _ir_http-serve_fallback:

.. py:method:: IrHttp._serve_fallback()
   :classmethod:

   Returns ``None`` on the check host. Delegates to ``super()`` everywhere else.

   ``_serve_fallback`` is the hook Odoo calls when nothing in the routing map
   matched — it is how ``ir.attachment`` records with a ``url`` get served, and
   it is where ``website`` plugs in its page lookup, its redirects and its
   rendered 404. Returning ``None`` means *there is nothing here*, and the
   request becomes a plain 404.

   .. admonition:: The check host has no fallback, on purpose
      :class: important

      This is what makes the portal host a dead end rather than a second front
      door. The portal's own routes are the complete inventory of what exists
      there; anything else — ``/web/login``, ``/odoo``, ``/web``,
      ``/web/database/manager``, ``/web/database/selector`` — is not merely
      unstyled or unauthorised, it does not resolve. Test:
      ``test_the_back_office_does_not_exist_on_the_check_host``.

      It also forecloses a problem the module does not have yet. This addon
      deliberately does not depend on ``website``
      (:ref:`limits-no-website`), but nothing stops somebody installing it
      later, and the day they do, ``website``'s fallback would start answering
      on the portal host: CMS pages, the website's 404 template, its redirect
      table, and — depending on configuration — its search. Returning ``None``
      first means that never happens regardless of what else is installed.

   .. note::

      nginx should be saying the same thing, and :ref:`deployment-nginx` shows
      how. This override is the lock that is still there when it does not —
      behind a misconfigured proxy, on a staging box with no proxy at all, and
      in a test run, which is the only environment where any of these
      assertions can actually be made.

Both halves, in one sentence
----------------------------

The two methods are symmetrical and neither is sufficient alone:

.. list-table::
   :header-rows: 1
   :widths: 24 38 38

   * -
     - ``check.example.com``
     - ``example.com``
   * - The portal
     - served, at the root
     - 404 — the namespace is closed
   * - The back office
     - 404 — no route matches, no fallback runs
     - served, untouched
   * - ``/web/assets/``
     - served (:py:data:`PASSTHROUGH`)
     - served

Test ``test_the_plain_host_does_not_serve_the_portal`` pins the top-right cell
and ``test_the_back_office_does_not_exist_on_the_check_host`` the bottom-left.
Both live in ``TestPortalHost``, which fakes the host with a ``Host`` header on
every request — nothing has to resolve, the request still goes to
``127.0.0.1``. See :doc:`../../development/testing`.

See also
--------

* :doc:`../controllers/verify` — the routes this rewrite maps onto, and why
  ``FORM_URL`` is ``/``
* :doc:`dms_certificate` —
  :py:attr:`~odoo.addons.dms_certify_portal.models.dms_certificate.DmsCertificate.verify_url`,
  the one place the public path is built, and the note on never emitting
  ``/_check``
* :doc:`../security/ir_rule` — the other half of the posture: the controller is
  the only door into the model, and there is no public ACL
* :doc:`../../handbook/deployment` — :ref:`deployment-check-host` and
  :ref:`deployment-nginx`
* :doc:`../../handbook/troubleshooting` — what a portal that 404s, or a check
  host that serves the back office, actually means
* :doc:`../../limits` — :ref:`limits-no-website`
