Development
===========

One page, where the sibling projects in this repository split the same material
across *architecture*, *extending*, *contributing* and *testing*. That is not a
shortcut: |addon| is fifty-seven lines across three files, it defines no model,
and it has exactly one extension point. Four pages would be four places to keep
a paragraph in step, and three of them would be mostly cross-references.

.. contents::
   :local:
   :depth: 2

Layout
------

.. code-block:: text

   __manifest__.py   eight lines: depends on `base`, declares "post_load"
   __init__.py       the db_filter patch — the only code that runs at import time
   hosts.py          the prefix, the transformation, the predicate — no imports
   docs/             this documentation

There is no ``models/``, no ``views/``, no ``security/``, no ``data/``, no
``static/``, no ``i18n/`` and no ``tests/``. The last one is a gap rather than a
property — see `Testing`_.

The division between the two code files is the one structural decision in the
addon, and it is worth keeping:

* ``hosts.py`` holds everything that can be reasoned about as a string
  transformation, and imports **nothing** at module level. That is what makes it
  readable by ``autodoc`` for real (:doc:`../reference/hosts` is generated, not
  transcribed), unit-testable with no Odoo, and safe to import from any other
  addon at any point in the load order.
* ``__init__.py`` holds everything that touches Odoo — one wrapper, one guard,
  one log line — and nothing that needs thinking about.

Architecture
------------

Why a monkey-patch
^^^^^^^^^^^^^^^^^^

The transformation has to be in place before the server answers its first
request, because *the first request is already a database decision*. That single
constraint rules out almost everything.

.. list-table::
   :header-rows: 1
   :widths: 30 70

   * - Alternative
     - What it would cost
   * - An ``ir.http`` override, or anything else on a model
     - Impossible, not merely expensive. A model lives in a registry, a registry
       belongs to a database, and the database is the thing being chosen. See
       the loop drawn out at :ref:`installation-server-wide`.
   * - A cleverer ``dbfilter`` regex
     - Cannot be written. ``%h`` and ``%d`` are substituted **from** the host
       into the pattern, and are then matched against database *names* — so
       ``%d`` of ``check.erp.example.com`` is the literal string ``check``, and
       no regex has access to the rest of the hostname.
   * - A literal ``dbfilter`` per host
     - Works, and gives up host-based multi-database routing: one Odoo process
       per hostname, each pinned to one database. For a single-database
       deployment this is a legitimate choice, and it makes this addon
       unnecessary — and inert. See :ref:`limits-inert`.
   * - WSGI middleware rewriting ``HTTP_HOST``
     - Would resolve the database, and would **destroy the feature it exists
       for**. Odoo would then see the parent host on every request: generated
       URLs would point at the parent, and ``is_check_host()`` would answer
       ``False``, so ``dms_certify_portal`` could no longer tell the two hosts
       apart and could not confine the check host to the portal.
   * - The reverse proxy rewriting ``Host``
     - The same loss, one layer further out and harder to see from inside Odoo.
       This is a mistake people make by accident — it is the subject of
       :ref:`troubleshooting-proxy-host`.
   * - Patching the call sites instead of the function
     - ``dbfilter`` is consulted at three points in ``odoo/http.py``. Replacing
       ``db_filter`` itself covers all three and keeps working if a fourth
       appears.
   * - Forking ``odoo/http.py``
     - A merge conflict at every upgrade, for a twenty-line wrapper.

What remains is ``post_load`` plus ``server_wide_modules``: the one pair of
mechanisms Odoo offers that runs at process start, with no database and no
registry. The manifest's ``post_load`` key alone is **not** enough — it fires on
a registry load too, which is too late to be useful, and that is the single
thing about this addon that is easy to get wrong.

Why a separate addon
^^^^^^^^^^^^^^^^^^^^

The obvious alternative is for ``dms_certify_portal`` to carry this code itself.
It cannot, usefully: the portal is a database-installed module with a long
dependency list, and ``server_wide_modules`` imports a package before anything
exists for it to depend on. Splitting them means the entry in ``odoo.conf``
names a module whose ``depends`` is ``["base"]`` and whose import surface is
``logging`` and ``odoo.http``.

The split also puts the vocabulary in one place and the policy in the other.
|addon| answers *"is this a check host, and what is its parent?"*. Everything
about what a check host is allowed to serve belongs to the portal. Conflating
them is how you end up with two definitions of a check host that disagree — see
:doc:`../limits`.

Reusing ``is_check_host`` from your own addon
---------------------------------------------

``is_check_host`` is the addon's public surface, and the reason to import it
rather than writing ``host.startswith("check.")`` is that the prefix, the
lowercasing and the bare-``check.`` guard then cannot drift apart between your
module and the database routing.

Declare the dependency in your manifest:

.. code-block:: python

   {
       "name": "My verification extras",
       "depends": ["dms_certify_host"],
   }

Then import from the runtime package name:

.. code-block:: python

   from odoo import models
   from odoo.http import request

   from odoo.addons.dms_certify_host.hosts import is_check_host


   class IrHttp(models.AbstractModel):
       _inherit = "ir.http"

       @classmethod
       def _match(cls, path_info):
           if request and is_check_host():
               # Only reached on check.<host>. Narrow, rewrite, or refuse here.
               ...
           return super()._match(path_info)

``dms_certify_portal/models/ir_http.py`` is the worked example — twenty-nine
lines that rewrite every path on the check host under ``/_check`` and refuse that
prefix everywhere else.

Four things to know before you do this:

* **Depending on it does not load it.** The ``depends`` entry makes the package
  importable and installs a database record; it does **not** add the module to
  ``server_wide_modules``, and the database routing is not in force without
  that line. Say so in your own installation instructions, as
  :doc:`../installation` does.
* **``is_check_host()`` with no argument needs a request.** It reads
  ``request.httprequest.host`` and returns ``False`` outside a request rather
  than raising, but writing ``if request and is_check_host():`` states the
  precondition where the reader is. Pass ``host=`` explicitly anywhere a request
  is not guaranteed.
* **Use ``parent_of_check_host`` if you need the name**, not a second
  ``[len("check."):]`` slice of your own.
* **Importing ``hosts`` is always safe.** It has no module-level imports, so it
  cannot deadlock on load order or drag ``odoo.http`` into a module that runs
  before the HTTP application exists.

You are maintaining somebody's API
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

Both functions in ``hosts.py`` are imported by another addon at module level, so
renaming either one, or changing what ``parent_of_check_host`` returns for an
edge case, is a breaking change — including the ones that look like
housekeeping. Changing ``CHECK_PREFIX`` changes the DNS name, the certificate
and the proxy block at the same time. If you touch any of it, say so in
:doc:`../changelog`.

Conventions
-----------

Five house rules, each of which has a reason on another page:

#. **``hosts.py`` keeps zero module-level imports.** Three consequences depend
   on it — see :doc:`../reference/hosts`. If you need something from Odoo, import
   it inside the function, as ``is_check_host`` does.
#. **The patch is a strict no-op off the check host.** It is installed
   process-wide, for every database and every hostname the server answers for,
   so a non-check host must reach ``db_filter`` byte for byte: not lowercased,
   port intact. That is what the ``or host`` fallback is for
   (:doc:`../reference/post_load`).
#. **Keep the idempotency marker.** ``post_load`` runs again on every registry
   load, and two stacked wrappers strip two prefixes — which is a behaviour
   change, not just waste.
#. **One prefix, one place.** ``CHECK_PREFIX`` is read once and measured once.
   Resist making it configurable; :doc:`../limits` argues why, and what to do
   instead if you genuinely need a second prefix.
#. **The log line is the only observable.** There is no model to inspect and no
   setting to read back, and a ``server_wide_modules`` entry that fails to
   import does not stop the server. Anything you add that can silently not
   happen needs to say so at ``INFO`` on the same terms.

Adding a dependency is a decision, not a detail: this module is imported before
Odoo has a database, and an ``ImportError`` here is logged and skipped rather
than fatal. The failure mode of a heavier import surface is a server that starts
cleanly with the feature missing.

.. _development-testing:

Testing
-------

**There are none.** No ``tests/`` directory, nothing tagged for
``--test-tags``. :ref:`limits-no-tests` states the case against that at length;
this section is what to do about it.

Where they would go
^^^^^^^^^^^^^^^^^^^

The manifest declares ``installable: True`` and ``dms_certify_portal`` depends on
the module, so it is a real installed module in any database that has the
portal. A ``tests/__init__.py`` importing your test modules is all the wiring
Odoo needs:

.. code-block:: bash

   odoo-bin -c odoo.conf -d <scratch-database> -i dms_certify_host \
       --test-enable --test-tags /dms_certify_host --stop-after-init

Use a scratch database. Pass the production name explicitly and deliberately,
never by default.

The easy half
^^^^^^^^^^^^^

``parent_of_check_host`` is a pure function from a string to a string or
``None``, importing nothing. The cases are already enumerated as a table on
:doc:`../reference/hosts` — a check host with and without a port, mixed case, a
bare ``check.``, ``check.check.``, a non-check host, the empty string, ``None``
— and every row is one ``assertEqual``. There is no excuse for this half being
untested; there is only the fact that it is.

The half that is actually interesting
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

The patch. A test has to observe that the **inner** ``db_filter`` was handed the
parent host, which means installing a stand-in it can watch:

.. code-block:: python

   from odoo import http
   from odoo.addons.dms_certify_host import post_load
   from odoo.tests.common import TransactionCase


   class TestCheckHostPatch(TransactionCase):
       def setUp(self):
           super().setUp()
           self.seen = []
           self.addCleanup(setattr, http, "db_filter", http.db_filter)
           # A stand-in carrying no `_dms_check_host` marker, so post_load()
           # has something to wrap.
           http.db_filter = lambda dbs, host=None: self.seen.append(host) or dbs
           post_load()

       def test_check_host_resolves_through_its_parent(self):
           http.db_filter(["anything"], host="check.erp.example.com")
           self.assertEqual(self.seen, ["erp.example.com"])

       def test_other_hosts_arrive_untouched(self):
           http.db_filter(["anything"], host="ERP.Example.com:8069")
           self.assertEqual(self.seen, ["ERP.Example.com:8069"])

Three traps are visible in that sketch, and they are why the suite does not
exist yet rather than reasons it cannot:

* **Calling ``post_load()`` against the live ``db_filter`` does nothing.** On a
  server that loads this module, the marker is already set and the function
  returns immediately — correctly. A test must install its own unmarked
  stand-in first, which is what the ``setUp`` above does.
* **The patch is process-global**, so a test that forgets to restore
  ``http.db_filter`` corrupts every test that runs after it, in any module. The
  ``addCleanup`` is not optional.
* **The ``host is None`` branch needs a fake request** —
  ``http.request.httprequest.environ`` returning ``{"HTTP_HOST":
  "check.erp.example.com"}``. It is the branch no caller in ``odoo/http.py``
  takes, so it is also the branch most likely to rot. :ref:`limits-no-tests` has
  the full list of what a complete test would assert.

None of this needs a database, which is the other reason the gap is hard to
defend.

Building these docs
-------------------

From the addon root, any environment with Sphinx:

.. code-block:: bash

   # an existing venv that already has Sphinx
   ~/venvs/odoo3.12/bin/sphinx-build -b html -W docs docs/_build/html

   # or a clean one, with no Odoo anywhere
   python3 -m venv .venv && . .venv/bin/activate
   pip install -r docs/requirements.txt
   sphinx-build -b html -W docs docs/_build/html

``-W`` turns warnings into errors, so a broken cross-reference fails the build
instead of scrolling past. The tree builds clean under it; keep it that way.

``conf.py`` mocks ``odoo`` **unconditionally**, even where a real Odoo is
installed, because Odoo 19's ``MetaModel`` asserts that every model class is
imported under ``odoo.addons.*`` — and ``sys.path`` here makes the package plain
``dms_certify_host``. The useful consequence is that these docs build with no
Odoo and no database at all. ``hosts.py`` is the one module in the repository
that needs no mock to be read, which is why :doc:`../reference/hosts` is
generated and :doc:`../reference/post_load` is hand-written.

Point the ``[source]`` links at a tag instead of ``main``:

.. code-block:: bash

   DMS_CERTIFY_DOCS_GIT_REF=19.0.1.0.0 sphinx-build -b html -W docs docs/_build/html

Before you commit
-----------------

* **Restart, do not upgrade.** ``-u dms_certify_host`` does not replace a patch
  that a running process installed at import. Nothing short of a restart tests
  what you changed.
* **Confirm the startup line**, then run the two-host comparison in
  :ref:`administration-confirm`. A green log line only proves the wrapper is
  installed, not that it resolves the database you think it does.
* **Check a non-check host is still untouched.** It is the property with the
  widest blast radius and the one no test guards.
* Build the docs with ``-W`` if you touched them, and update
  :doc:`../reference/hosts` or :doc:`../reference/post_load` for anything you
  added or renamed — a stale reference page is worse than a missing one.
* Add a line to :doc:`../changelog`, and bump the manifest version if the
  behaviour changed.

See also
--------

* :doc:`../reference/hosts` — the two functions, their edge cases, and why
  ``hosts.py`` imports nothing.
* :doc:`../reference/post_load` — the patch, the closure, the guard and the two
  fallbacks, decision by decision.
* :doc:`../handbook/concepts` — the before/after diagram, which is the shortest
  path to understanding what you are changing.
* :doc:`../installation` — ``server_wide_modules``, and why an Apps-list install
  is not a substitute for it.
* :doc:`../limits` — the untested surface, the hard-coded prefix, and the
  deployments on which none of this does anything.
* :doc:`../changelog` — where a behaviour change has to end up.
