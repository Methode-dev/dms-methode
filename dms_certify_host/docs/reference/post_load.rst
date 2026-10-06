post_load
=========

.. py:currentmodule:: odoo.addons.dms_certify_host

Source: :ghsrc:`__init__.py`. Registered in the manifest as
``"post_load": "post_load"``.

Hand-written rather than generated. ``__init__.py`` reaches into ``odoo.http``
and replaces a module-level name at import time, so importing it in a
documentation build would mean patching a module that is not there — ``conf.py``
mocks ``odoo``. The ``[source]`` links below still land on the real lines.

.. contents::
   :local:
   :depth: 2

.. py:function:: post_load()

   Replace ``odoo.http.db_filter`` with a wrapper that hands it the **parent**
   host whenever the request's host starts with ``check.``.

   Called by ``load_server_wide_modules()`` at process start, and again by
   ``load_openerp_module()`` whenever a registry loads the module as an ordinary
   database record. Both calls are expected; only the first one is early enough
   to be useful, and the second is why the guard below exists.

   :returns: ``None``. The effect is entirely a side effect on ``odoo.http``.

Eleven statements, and four of them are decisions.

The closure
-----------

.. code-block:: python

   original = http.db_filter
   ...
   return original(dbs, host=parent_of_check_host(host) or host)

``original`` is captured once, at patch time, by value. The wrapper therefore
calls whatever ``db_filter`` was installed at the moment ``post_load`` ran —
Odoo's own, normally, but another ``server_wide_modules`` entry's wrapper if one
got there first.

That is the composable choice. Reading ``http.db_filter`` inside the wrapper
instead would be a self-reference and an infinite recursion, and chasing it
through a module-level attribute at call time would make the behaviour depend on
load order in a way nobody could see from here.

The re-entrancy guard
---------------------

.. code-block:: python

   original = http.db_filter
   if getattr(original, "_dms_check_host", False):
       return
   ...
   db_filter._dms_check_host = True

The marker is set on the wrapper and tested on the thing about to be wrapped:
*"am I about to wrap myself?"*. ``getattr`` with a default because Odoo's own
``db_filter`` carries no such attribute.

.. admonition:: Nesting is not merely wasteful — it changes the answer
   :class: important

   Two stacked wrappers strip **two** prefixes. Given
   ``check.check.erp.example.com``:

   .. code-block:: text

      wrapper #2  →  parent_of_check_host → "check.erp.example.com"
      wrapper #1  →  parent_of_check_host → "erp.example.com"
      Odoo's db_filter                    → resolves erp.example.com

   One wrapper strips one prefix and leaves ``check.erp.example.com``, which your
   ``dbfilter`` does not match — a 404, which is the documented behaviour (see
   :doc:`../limits`). Two wrappers make ``check.check.erp.example.com`` quietly
   serve the live database. The guard is not hygiene, it is the difference
   between a 404 and an extra undeclared hostname on your ERP.

   And the second call genuinely happens: ``dms_certify_portal`` depends on this
   module, so a registry load runs ``post_load`` again on every worker that
   loads that database.

The guard returns **before** the log line, which is why that line appears once
per server process even though ``post_load`` is called again on every registry
load. A second line in one process would mean a second wrapper installed over
one that had lost its marker — see :ref:`installation-verify`.

The ``host is None`` fallback
-----------------------------

.. code-block:: python

   def db_filter(dbs, host=None):
       if host is None and http.request:
           host = http.request.httprequest.environ.get("HTTP_HOST", "")

The signature mirrors Odoo's — ``db_filter(dbs, host=None)`` — so positional and
keyword callers both keep working, and the inner call passes ``host`` by keyword.

The branch exists for a caller that omits the host while a request is in flight.
No caller in ``odoo/http.py`` takes it: the request path passes ``HTTP_HOST``
explicitly. It is there for everything else — a ``db_filter(dbs)`` from a
controller, from another addon, or typed into a shell during a request — and for
the property that the wrapper never silently resolves a *different* host than
the one being served.

Two details in one line:

* ``host is None`` is tested **before** ``http.request``, so the thread-local
  proxy is only touched when it is needed, and an explicit ``host=""`` is left
  alone rather than being replaced from the environ. An empty host is a caller's
  statement, not a gap to fill.
* With no request in flight, ``host`` stays ``None``,
  ``parent_of_check_host(None)`` returns ``None``, and ``None or None`` is
  ``None`` — so the inner function receives exactly what it would have received
  unpatched.

It reads ``environ["HTTP_HOST"]`` rather than ``httprequest.host``, which is the
same raw value Odoo's own callers pass along, so the filled-in branch and the
explicit branch cannot disagree about what the host was.

.. todo::

   ``is_check_host`` reads ``request.httprequest.host`` while this fallback reads
   ``environ["HTTP_HOST"]``. Under ``proxy_mode = True`` — where a proxy sends
   both ``Host`` and ``X-Forwarded-Host`` — can those two ever return different
   strings for the same request, and if so which one is the check host? Both
   values are ``$host`` in the reference nginx configuration, so the question has
   never been forced, but somebody should read Odoo 19's proxy handling and
   settle it rather than leaving two spellings of "the host" in one addon.

The ``or host`` fallback
------------------------

.. code-block:: python

   return original(dbs, host=parent_of_check_host(host) or host)

``parent_of_check_host`` returns ``None`` for anything that is not a check host,
and ``or host`` then passes the original string through — **byte for byte**, not
lowercased, port intact, ``www.`` untouched.

That is the single most important property of this patch. It is installed for
the whole process, on every database and every hostname the server answers for
(see :doc:`../limits`), so it must be a strict no-op off the check host. If it
instead returned ``parent_of_check_host``'s lowercased name for every host, then
every ``dbfilter`` regex on the server would suddenly be matching against a
lowercased host — a change in behaviour for hostnames that have nothing to do
with this addon.

.. list-table::
   :header-rows: 1
   :widths: 40 36 24

   * - ``host`` the wrapper receives
     - ``host`` the real ``db_filter`` receives
     - Changed?
   * - ``"check.erp.example.com"``
     - ``"erp.example.com"``
     - **yes**
   * - ``"check.erp.example.com:8069"``
     - ``"erp.example.com:8069"``
     - **yes**
   * - ``"erp.example.com"``
     - ``"erp.example.com"``
     - no
   * - ``"ERP.Example.com"``
     - ``"ERP.Example.com"``
     - no — not lowercased
   * - ``""``
     - ``""``
     - no
   * - ``None`` (no request)
     - ``None``
     - no

The log line
------------

.. code-block:: python

   _logger.info("dms_certify_host: check.* hosts use their parent host's database")

The last statement in the function, so it is only reached once the wrapper is
actually installed, and it is skipped entirely by the re-entrancy guard. It is
the only observable the addon has: there is no model to inspect, no setting to
read back, and a module named in ``server_wide_modules`` that fails to import
does not stop the server. :ref:`installation-verify` makes that line the
verification step.

What it deliberately does not do
--------------------------------

* **No ``try``/``except`` around the patch.** If ``odoo.http`` has no
  ``db_filter``, the import or the attribute access fails loudly at startup, and
  the message says this module's name. A swallowed failure would present as a
  check host that 404s with a clean log, which is the worst outcome available.
* **No un-patch.** There is no ``pre_init``, no uninstall hook and no way to
  restore the original short of restarting the process. See :doc:`../limits`.
* **No routing, no ``web.base.url``, no session handling.** The wrapper answers
  *"which database?"* and stops. Confining what the check host serves belongs to
  ``dms_certify_portal``.

See also
--------

* :doc:`hosts` — ``parent_of_check_host``, the function this wrapper is built
  around, generated from the source.
* :doc:`../handbook/concepts` — the before/after diagram, and why a database
  decision cannot be made by a module installed in a database.
* :doc:`../installation` — ``server_wide_modules``, and how to confirm the patch
  is live.
* :doc:`../limits` — the deployments on which this patch is inert, and why it is
  global to the process.
* :doc:`../development/index` — the architecture section argues why a
  monkey-patch is the only mechanism that runs early enough.
