Known limits
============

What this addon deliberately does not do. It resolves a database from a
hostname; everything else that the phrase *"a separate verification host"*
suggests belongs somewhere else, and this page is mostly about naming where.

Behaviour that is confusing but *correct* is in
:doc:`handbook/troubleshooting`.

.. contents::
   :local:
   :depth: 1

One prefix, hard-coded
----------------------

``CHECK_PREFIX = "check."`` is a module-level constant in :doc:`reference/hosts`
with no setting, no ``ir.config_parameter`` and no environment variable behind
it. ``verify.`` or ``certificat.`` means editing the source.

That is a deliberate floor rather than an oversight: the value has to be known
before any database exists, so it cannot live in a database, and a configuration
option would be a second place for the DNS name, the TLS certificate, the proxy
block and the code to disagree with each other. One constant in one file is the
smallest number of places that can be wrong.

If you do need a second prefix, the honest change is a list and a loop in
``parent_of_check_host`` — not a per-database setting.

No isolation, only resolution
-----------------------------

**This is the limit most likely to bite.** The addon makes
``check.erp.example.com`` resolve to a database. It does nothing whatsoever to
narrow what that host serves. On its own, |addon| gives you a second hostname
that serves the whole of Odoo — the back office, the login page, every
installed module's routes.

The narrowing is ``dms_certify_portal``'s ``ir.http`` override
(``dms_certify_portal/models/ir_http.py``), which rewrites every path on a check
host under its own ``/_check`` prefix and disables the attachment fallback. That
addon imports ``is_check_host`` from here precisely so that both halves agree on
what a check host *is*, but the policy is entirely its own.

Consequences worth stating plainly:

* |addon| alone is not a security boundary, and must not be presented as one.
* A deployment that loads |addon| without ``dms_certify_portal`` has
  **widened** its exposure, not narrowed it.
* Adding a ``check.*`` block to your reverse proxy does not fix this. The proxy
  can refuse paths, but the moment it forwards ``/`` it is Odoo deciding what to
  serve.

``check.check.`` is not special-cased
-------------------------------------

``parent_of_check_host`` strips exactly one prefix. ``check.check.erp.example.com``
yields ``check.erp.example.com``, which is itself a check host, and which your
``dbfilter`` will not match either. ``is_check_host`` answers ``True`` for it.

Nothing is guarded against this because nothing creates it: the hostname comes
from DNS and from the URL printed on a document, both of which you control. It
is listed here so that nobody reads the single ``startswith`` as an oversight to
"fix" recursively — recursing would make ``check.check.x`` quietly serve the
same database as ``x``, which is a new and worse surprise.

The patch is global to the process
----------------------------------

``http.db_filter`` is one module-level name, and the wrapper replaces it for the
whole Python process. There is no per-database, per-worker or per-request
granularity, and no way to switch it off short of restarting the server with a
different ``server_wide_modules``.

In practice this is fine — the transformation is a no-op for every host that is
not a check host, and non-check hosts are passed through completely untouched
(see the ``or host`` fallback in :doc:`reference/post_load`). But it does mean:

* A server hosting unrelated databases on unrelated hostnames still has the
  wrapper in the call path for all of them.
* A restart is the only way to remove or replace it. ``-u dms_certify_host``
  does not touch a running process's ``odoo.http`` module.

.. _limits-inert:

Inert without a host-derived ``dbfilter``
-----------------------------------------

Odoo's ``db_filter`` only looks at the host when ``dbfilter`` is set **and**
contains ``%h`` or ``%d``. Reading ``odoo/http.py`` in order:

.. list-table::
   :header-rows: 1
   :widths: 38 62

   * - Configuration
     - What the host is used for
   * - ``dbfilter = %h`` / ``%d``
     - Substituted into the regex. **The addon matters here, and only here.**
   * - ``dbfilter = mydb`` (a literal)
     - Nothing. The regex has no ``%h`` or ``%d`` to substitute, so the
       transformed host changes no outcome.
   * - no ``dbfilter``, ``db_name`` set
     - Nothing. ``db_filter`` returns the intersection of ``db_name`` and the
       available databases, host unread.
   * - no ``dbfilter``, no ``db_name``
     - Nothing. Every database is returned, and a single-database server
       resolves by the monodb rule regardless of hostname.

On the last three the addon is **inert, not broken**: it loads, it logs its
startup line, and it changes no behaviour. If a check host works on such a
deployment, it works because Odoo had exactly one database to choose from — not
because of this module. Add a second database and it stops working, and this
addon will not be the thing that saves you.

This also means a green startup log line is not proof the host routing is
*needed*, only that the patch is installed. :doc:`handbook/administration` has
the comparison that actually proves the routing.

Only the database decision
--------------------------

Things a check host does **not** get from this addon, all of which have bitten
somebody somewhere:

* **No ``web.base.url`` rewriting.** URLs Odoo generates for itself still point
  at whatever ``web.base.url`` says — the parent host. Anything that has to
  produce a ``check.<host>`` URL builds it itself.
* **No session separation.** The check host resolves to the same database, so
  it shares the session cookie domain rules of that database like any other
  host. It is not a sandbox.
* **No routes.** The addon declares no controller. (Odoo does add a
  ``server_wide_modules`` entry's routes to the routing map whether or not it is
  installed — there simply are none here.)
* **No ``www.`` handling of its own.** Odoo's own ``db_filter`` strips a leading
  ``www.`` after this addon has handed it the parent host; the addon neither
  adds nor removes that behaviour.

.. _limits-no-tests:

No tests
--------

**The addon ships no tests at all.** There is no ``tests/`` directory, no
``__init__.py`` importing one, and nothing tagged for ``--test-tags``. Fifty-seven
lines and a single-expression helper is a thin excuse, and the honest statement
is that the untested part is not the helper — it is the patch.

``parent_of_check_host`` is pure, takes a string, returns a string or ``None``,
and imports nothing: it is the easiest function in this repository to test, and
the cases are already enumerated in :doc:`reference/hosts` — a check host with
and without a port, mixed case, a bare ``check.``, a non-check host, ``None``,
the empty string.

The patch is the part a test would have to work for, and it is why there is no
suite yet. A test would have to:

#. call ``post_load()`` against a stand-in for ``odoo.http`` whose ``db_filter``
   it can observe, since importing the real one inside a test run means patching
   a module the test framework is itself running on;
#. fake a WSGI environ — ``{"HTTP_HOST": "check.erp.example.com"}`` — reachable
   as ``http.request.httprequest.environ`` to exercise the ``host is None``
   branch, which is the branch no caller in ``odoo/http.py`` takes (the request
   path passes ``HTTP_HOST`` explicitly);
#. assert that the inner ``db_filter`` was called with ``host="erp.example.com"``
   and, separately, that a non-check host arrives **unmodified** — not
   lowercased, not stripped of its port;
#. call ``post_load()`` a second time and assert the wrapper was not nested, by
   checking the ``_dms_check_host`` marker rather than by counting calls.

None of that needs a database, which is the other reason its absence is hard to
defend.

See also
--------

* :doc:`reference/hosts` — the two functions, and the edge cases a test would
  cover.
* :doc:`reference/post_load` — the patch, and why it is shaped this way.
* :doc:`handbook/troubleshooting` — for a check host that is misbehaving rather
  than limited.
* :doc:`development/index` — the testing section says the same thing from the
  contributor's side.
