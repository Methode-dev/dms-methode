Concepts
========

One mechanism, one transformation, one predicate. Everything |addon| does fits
on this page.

.. contents::
   :local:
   :depth: 2

What ``dbfilter`` is for
------------------------

An Odoo server can hold many databases, and an anonymous HTTP request carries no
hint of which one it belongs to. ``dbfilter`` is how the server guesses: a
regular expression, matched against every available database name, with two
substitutions made first from the request's ``Host`` header.

.. list-table::
   :header-rows: 1
   :widths: 10 90

   * - Token
     - Replaced with
   * - ``%h``
     - The **host**, port removed, and a leading ``www.`` stripped —
       ``erp.example.com``.
   * - ``%d``
     - The **domain**: everything before the first dot of that host — ``erp``.

The filter then returns the databases whose name the regex matches. Odoo
proceeds only when exactly one survives; it is the *monodb* rule that turns a
one-element list into a resolved database. No survivors and the request is a 404
before any addon sees it.

So ``dbfilter = %h`` means *"the database is named after the host"*, and
``dbfilter = %d`` means *"after the first label of the host"*. Both are common,
and both are statements about the hostname — which is the whole reason this
addon exists.

.. note::

   ``dbfilter`` is consulted at three points in ``odoo/http.py``: validating the
   database already in the session cookie, validating an ``X-Odoo-Database``
   header, and listing candidates for the monodb rule. The patch covers all
   three, because it replaces the function rather than intercepting one caller.

What this addon changes
-----------------------

Exactly one thing: the host that ``db_filter`` is given.

``post_load`` replaces ``odoo.http.db_filter`` with a wrapper that asks
``parent_of_check_host`` whether the host starts with ``check.``. If it does,
the inner — real — ``db_filter`` receives the parent host instead. If it does
not, the inner function receives the original host, byte for byte.

.. code-block:: text

   BEFORE                                 AFTER
   ──────                                 ─────
   Host: check.erp.example.com            Host: check.erp.example.com
        │                                      │
        ▼                                      ▼
   db_filter(dbs, "check.erp.example.com")  wrapper(dbs, "check.erp.example.com")
        │                                      │
        │  %h → check.erp.example.com          │  parent_of_check_host(...)
        │  %d → check                          │       → "erp.example.com"
        ▼                                      ▼
   no database matches                    db_filter(dbs, "erp.example.com")
        │                                      │
        ▼                                      │  %h → erp.example.com
   404 — database not found                    │  %d → erp
                                               ▼
                                          the same database <host> resolves to


   Host: erp.example.com                  Host: erp.example.com
        │                                      │
        ▼                                      ▼
   db_filter(dbs, "erp.example.com")      wrapper → parent_of_check_host → None
        │                                      │       → falls back to `or host`
        ▼                                      ▼
   resolves normally                      db_filter(dbs, "erp.example.com")
                                               │
                                               ▼
                                          resolves identically — unchanged

The right-hand column is the entire behavioural difference the addon makes. A
non-check host is not merely *also* resolved: it is handed the same string the
unpatched function would have received, un-lowercased and with its port intact.

Why it cannot be an ordinary module
-----------------------------------

The transformation has to be in place before the server answers its first
request, because the first request is already a database decision. A module
installed in a database cannot help with a decision that *selects* the database
— see :ref:`installation-server-wide` for the loop that creates.

``post_load`` plus ``server_wide_modules`` is the one pair of mechanisms Odoo
offers that runs at process start, with no database and no registry. That is why
the manifest declares ``post_load`` and depends on ``base`` alone, and why
|addon| is a line in ``odoo.conf`` rather than a tile in the Apps list.

What ``is_check_host`` is for
-----------------------------

Resolving the database is only half of what a verification host needs. The other
half is that the host must serve the verification portal and nothing else, and
that is a **routing** decision made per request, long after the database is
known.

``is_check_host`` is the shared answer to *"is this request on a check host?"*,
so that the two halves cannot drift apart. It reads ``request.httprequest.host``
when called with no argument, and defers to ``parent_of_check_host`` for the
verdict — the same function, the same prefix, the same guards.

Its consumer is ``dms_certify_portal``'s ``ir.http`` override
(``dms_certify_portal/models/ir_http.py``), which uses it twice:

.. list-table::
   :header-rows: 1
   :widths: 24 76

   * - Override
     - What it does when ``is_check_host()``
   * - ``_match``
     - Rewrites the incoming path under the portal's internal ``/_check``
       prefix, leaving only ``/web/assets/`` alone. ``/`` becomes ``/_check``.
       On a non-check host it does the reverse: a request for ``/_check``
       raises ``NotFound``, so the internal namespace does not exist anywhere
       but here.
   * - ``_serve_fallback``
     - Returns ``None`` instead of calling ``super()``, so the check host
       serves no attachment fallback.

That addon owns the policy; |addon| owns the vocabulary. The division matters:
loading this module without ``dms_certify_portal`` gives you a second hostname
serving the *whole* of Odoo, which is the opposite of the intent. See
:doc:`../limits`.

See also
--------

* :doc:`../installation` — the ``server_wide_modules`` line, and how to verify
  the patch is live.
* :doc:`administration` — DNS, TLS and the proxy, which have to agree with the
  prefix this page describes.
* :doc:`troubleshooting` — when the diagram above does not match what you are
  seeing.
* :doc:`../reference/post_load` — the wrapper, its guard and its two fallbacks.
* :doc:`../reference/hosts` — ``parent_of_check_host`` and ``is_check_host``,
  generated from the source.
