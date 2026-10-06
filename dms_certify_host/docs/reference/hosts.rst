hosts
=====

Source: :ghsrc:`hosts.py`

One constant and two functions, in twenty lines, with **no imports at all** at
module level. That is the module's defining property rather than an accident of
its size: it is what lets ``autodoc`` read the real source below instead of a
hand-written copy of it, what lets ``parent_of_check_host`` be called with no
Odoo and no database, and what keeps ``__init__.py`` — imported by
``load_server_wide_modules`` before the HTTP application exists — from dragging
``odoo.http`` in a step too early.

.. contents::
   :local:
   :depth: 2

.. automodule:: dms_certify_host.hosts
   :members:
   :undoc-members:

``CHECK_PREFIX``
----------------

.. py:data:: CHECK_PREFIX
   :type: str
   :value: "check."

   The hostname prefix that marks a verification host.

.. note::

   This is the one entry on this page written by hand rather than read from the
   source: ``autodoc`` emits the two functions but not the module-level
   constant, even with ``:undoc-members:``. Check the value against
   :ghsrc:`hosts.py` if it matters to you.

The prefix, as a module-level constant with nothing behind it — no setting, no
``ir.config_parameter``, no environment variable. Changing it is a source edit,
and that is deliberate: the value has to be known before any database exists, so
it cannot live in one. See :doc:`../limits` for the longer version of that
argument.

Note the trailing dot. It is part of the constant, which is why
``checkout.example.com`` is not a check host.

It is read in exactly one place, ``parent_of_check_host``, which is also the
only place that knows how long it is. Both uses matter — see the next section.

``parent_of_check_host``
------------------------

The whole of the logic. Everything else in the addon is plumbing around this
function.

The bare ``check.`` guard
^^^^^^^^^^^^^^^^^^^^^^^^^

.. code-block:: python

   if name.startswith(CHECK_PREFIX) and len(name) > len(CHECK_PREFIX):

``startswith`` alone is not enough. A ``Host`` of exactly ``check.`` passes it,
and the slice that follows would yield the empty string — so the function would
report a *parent host* of ``""`` for a hostname that has no parent at all. With
a port, ``check.:443``, it is worse: the reassembly produces ``":443"``, which is
not a hostname in any sense.

The length guard turns both into ``None``, which is the same answer the function
gives for any other non-check host. That keeps the two functions in agreement:
``parent_of_check_host("check.")`` is ``None``, so ``is_check_host("check.")`` is
``False``, so neither the database patch nor ``dms_certify_portal``'s routing
treats a degenerate host as a verification host.

The port survives
^^^^^^^^^^^^^^^^^

.. code-block:: python

   name, sep, port = host.partition(":")
   ...
   return name[len(CHECK_PREFIX):] + sep + port

``partition`` rather than ``split(":")`` because it always returns three values:
``sep`` is ``""`` when there is no port, so the reassembly is one expression with
no branch for the common case. ``"check.erp.example.com"`` and
``"check.erp.example.com:8069"`` go through the same two lines.

The port is preserved because the patch must change **one** thing about the host
and nothing else. Odoo's own ``%h`` substitution strips the port itself; a
wrapper that also stripped it would make the patched and unpatched code paths
differ in a second way, and the next person debugging a ``dbfilter`` would have
two suspects instead of one.

Splitting on the first colon means a bracketed IPv6 literal is mangled — but it
is mangled into a name that does not start with ``check.``, so the function
returns ``None`` and the host is passed through untouched. An IPv6 literal is
never a check host, which is the right answer for the wrong reason, and is
harmless.

Case
^^^^

``name = name.lower()`` because a ``Host`` header is case-insensitive and
``CHECK.erp.example.com`` is a check host whether or not anybody meant to type
it that way.

The lowercased name is also what is **returned**, so the parent host handed on is
always lowercase. That only applies on the check-host path: for every other host
the function returns ``None`` and the caller in :doc:`post_load` falls back to
the original string, so no non-check host is ever lowercased on its way to
``db_filter``. The port is reattached exactly as received.

Behaviour, case by case
^^^^^^^^^^^^^^^^^^^^^^^

.. list-table::
   :header-rows: 1
   :widths: 44 34 22

   * - ``host``
     - Returns
     - ``is_check_host``
   * - ``"check.erp.example.com"``
     - ``"erp.example.com"``
     - ``True``
   * - ``"check.erp.example.com:8069"``
     - ``"erp.example.com:8069"``
     - ``True``
   * - ``"CHECK.Erp.Example.COM"``
     - ``"erp.example.com"``
     - ``True``
   * - ``"check.localhost"``
     - ``"localhost"``
     - ``True``
   * - ``"check.check.erp.example.com"``
     - ``"check.erp.example.com"``
     - ``True``
   * - ``"check."``
     - ``None``
     - ``False``
   * - ``"check.:443"``
     - ``None``
     - ``False``
   * - ``"erp.example.com"``
     - ``None``
     - ``False``
   * - ``"checkout.example.com"``
     - ``None``
     - ``False``
   * - ``""``
     - ``None``
     - ``False``
   * - ``None``
     - ``None``
     - ``False``

Two rows are worth pausing on. ``checkout.example.com`` is not a check host
because the constant includes the dot — the prefix is ``check.``, not ``check``.
And ``check.check.erp.example.com`` has exactly one prefix stripped, which leaves
a host that is itself a check host and that your ``dbfilter`` will not match
either; :doc:`../limits` explains why recursing would be worse than not.

This table is also the test suite that does not exist. Every row is a pure
string-to-string assertion needing no Odoo, no database and no request — see
:ref:`limits-no-tests`.

``is_check_host``
-----------------

A predicate over the same function, for the benefit of callers that have a
request but no interest in the parent host. ``parent_of_check_host`` answers
*"which database?"*; ``is_check_host`` answers *"is this request on the
verification host?"*, which is a routing question asked per request, long after
the database is known.

Both read the same constant through the same guards, which is the point of
exporting the predicate rather than letting each consumer write its own
``startswith``.

Why ``request`` is imported inside the function
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

.. code-block:: python

   if host is None:
       from odoo.http import request
       host = request.httprequest.host if request else ""

The import sits in the function body, not at the top of the file. Three reasons,
in ascending order of importance:

#. **Import order.** ``hosts.py`` is imported by the package's ``__init__.py``,
   which ``load_server_wide_modules`` imports before the WSGI application is
   initialised. A module-level ``from odoo.http import request`` would pull
   ``odoo.http`` in from the package that exists to patch it.
#. **Testability.** ``parent_of_check_host`` — the half that carries all of the
   logic — is reachable without importing anything from Odoo. A test for it needs
   no environment at all.
#. **The documentation build.** ``conf.py`` mocks ``odoo`` precisely because most
   of this repository cannot be imported without it. ``hosts.py`` can, which is
   why this page is generated from the source above rather than transcribed, and
   why it cannot drift.

.. note::

   ``request`` is a thread-local proxy that is falsy outside a request, so
   ``is_check_host()`` called with no argument and no request in flight returns
   ``False`` rather than raising. ``dms_certify_portal`` still writes
   ``if request and is_check_host():`` — the guard is cheap and it states the
   precondition at the call site.

Who calls it
^^^^^^^^^^^^

One addon, twice: ``dms_certify_portal``'s ``ir.http`` override
(``dms_certify_portal/models/ir_http.py``).

.. list-table::
   :header-rows: 1
   :widths: 26 74

   * - Override
     - What it does when ``is_check_host()``
   * - ``_match``
     - Prefixes the incoming path with ``/_check``, so every route on the check
       host is a portal route; ``/`` becomes ``/_check``, and only
       ``/web/assets/`` is left alone. On any other host the test runs in
       reverse — an explicit request for ``/_check`` raises ``NotFound``, so the
       internal namespace exists nowhere else.
   * - ``_serve_fallback``
     - Returns ``None`` instead of deferring to ``super()``, so no attachment
       fallback runs on the check host.

The division of labour is worth stating plainly, because it is the thing most
often got wrong about this addon: |addon| supplies the vocabulary, the portal
supplies the policy. A deployment that loads |addon| without the portal has a
second hostname serving the whole of Odoo. See :doc:`../limits`.

See also
--------

* :doc:`post_load` — the other half of the module, and the only caller of
  ``parent_of_check_host`` inside this addon.
* :doc:`../handbook/concepts` — what ``dbfilter`` does, and the before/after
  diagram these functions sit inside.
* :doc:`../development/index` — importing ``is_check_host`` from your own addon,
  with a worked example.
* :doc:`../limits` — the hard-coded prefix, ``check.check.``, and the missing
  tests, each argued at length.
