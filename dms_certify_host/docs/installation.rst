Installation
============

Three files and no database footprint, so almost all of this page is about one
line in ``odoo.conf``. If you read only one section, read
:ref:`installation-server-wide`.

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
     - Declared in the manifest as |release|. The addon wraps
       ``odoo.http.db_filter``, whose signature is ``db_filter(dbs, host=None)``
       in 19.0. It is small enough to port, but do not assume it loads unchanged
       on another series without checking that signature.
   * - Odoo addons
     - —
     - ``base`` only. No ``web``, no ``website``, no Enterprise.
   * - Python
     - whatever your Odoo 19 server runs
     - ``hosts.py`` imports nothing at all and ``__init__.py`` imports only
       ``logging`` and ``odoo.http``. There are no third-party packages to
       install, and nothing to check with ``pip``.

Deployment
^^^^^^^^^^

The addon changes how a hostname is turned into a database name. For that to be
worth anything you also need the hostname to exist and to arrive intact:

* a DNS record for ``check.<your-host>``,
* a TLS certificate that covers it,
* a reverse proxy that passes ``Host`` through unchanged.

All three are :doc:`handbook/administration`. None of them are a prerequisite
for *loading* the module, so you can do this page first and that one second.

.. note::

   The addon is only ever observable on a deployment whose ``dbfilter``
   contains ``%h`` or ``%d``. Under an explicit ``dbfilter = mydb``, or with no
   ``dbfilter`` at all, Odoo never looks at the host and the patch has nothing
   to do. See :ref:`limits-inert`.

Getting the code
----------------

|addon| is a top-level folder inside the ``dms-methode`` repository, which is a
flat collection of addons — ``dms_certify_host``, ``dms_certify_portal`` and the
rest sit side by side in the repository root.

As a git submodule (recommended)
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

This is how the addon is deployed: the repository is a submodule under the
deployment's ``addons/`` folder, so the stack pins an exact commit and an
upgrade is an explicit ``git`` operation rather than a surprise.

.. code-block:: bash

   cd /path/to/your/odoo-deployment
   git submodule add https://github.com/Methode-dev/dms-methode.git \
       addons/dms-methode
   git submodule update --init --recursive
   git commit -m "Add dms-methode submodule"

Cloning a deployment that already declares the submodule:

.. code-block:: bash

   git clone --recurse-submodules <your-deployment>

   # or, if you already cloned without it:
   git submodule update --init --recursive

Pulling a newer version later:

.. code-block:: bash

   cd addons/dms-methode
   git fetch origin && git checkout main && git pull
   cd - && git add addons/dms-methode
   git commit -m "Bump dms-methode"

.. important::

   The addons path must point at the **repository**, not at |addon| itself.
   Odoo scans a directory for addon folders, so it needs the parent:

   .. code-block:: text

      addons/dms-methode/          ← this goes on addons_path
        dms_certify_host/          ← the addon Odoo will find
          __manifest__.py
        dms_certify_portal/
          __manifest__.py

As a plain clone
^^^^^^^^^^^^^^^^

.. code-block:: bash

   cd /path/to/addons
   git clone https://github.com/Methode-dev/dms-methode.git

Putting it on the addons path
-----------------------------

In ``odoo.conf``:

.. code-block:: ini

   [options]
   addons_path = /odoo/odoo/addons,/odoo/addons/dms-methode

Or on the command line:

.. code-block:: bash

   odoo-bin --addons-path=/odoo/odoo/addons,/odoo/addons/dms-methode

The addons path has to be right **before** the next section will work:
``server_wide_modules`` names a module, and Odoo can only find it by scanning
the path. Getting this wrong produces the silent failure described in
:ref:`installation-verify`.

.. _installation-server-wide:

Loading it: ``server_wide_modules``
-----------------------------------

.. code-block:: ini

   [options]
   server_wide_modules = base,web,dms_certify_host

Or, equivalently, on the command line:

.. code-block:: bash

   odoo-bin --load=base,web,dms_certify_host

Restart the server. There is no ``-i``, no ``-u`` and no database name in that
command, because nothing is being written anywhere.

.. note::

   Odoo 19's default list is ``base,rpc,web``, and it force-adds only ``base``
   and ``web`` back if you leave them out (``REQUIRED_SERVER_WIDE_MODULES`` in
   ``odoo/tools/config.py``). ``rpc`` is **not** force-added, so writing
   ``base,web,dms_certify_host`` drops it relative to the stock configuration.
   If anything on your deployment talks to Odoo over the external API, write
   ``base,rpc,web,dms_certify_host`` instead.

Why an Apps-list install is not enough
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

A module's ``post_load`` hook does run when a database's registry loads it —
``odoo/modules/loading.py`` calls ``load_openerp_module()`` for every package in
the graph, and that is what invokes ``post_load``. So an ordinary install is not
*ignored*. It is **circular**:

.. code-block:: text

   request for check.erp.example.com
        │
        ▼
   which database?  ──► db_filter()      ← the patch belongs HERE
        │                   │
        │                   └─ unpatched, with dbfilter = %h: no match
        ▼
   404, no registry loaded
        │
        ▼
   dms_certify_host's post_load never runs, because loading it
   requires the database that could not be resolved

``server_wide_modules`` breaks the loop. ``odoo.http.Application.initialize()``
calls ``load_server_wide_modules()``, which imports each named package and calls
its ``post_load``, **before the WSGI application serves anything at all** — no
database, no registry, no request. That is the only point early enough to be
useful.

.. tip::

   ``dms_certify_portal`` declares ``dms_certify_host`` in its ``depends``, so
   installing the portal also installs this module as an ordinary database
   record. That is correct and harmless — it is how ``is_check_host`` becomes
   importable as ``odoo.addons.dms_certify_host.hosts`` — but it is **not** a
   substitute for the ``server_wide_modules`` line. Both, always.

.. _installation-verify:

Verifying the patch is live
---------------------------

The addon logs one line, at ``INFO``, from ``post_load``:

.. code-block:: text

   2026-10-01 09:12:44,017 1 INFO ? odoo.addons.dms_certify_host: dms_certify_host: check.* hosts use their parent host's database

That line is the whole verification. It is emitted once per server process, at
startup, before any request — which is why the database field reads ``?``:
there is no database bound yet. Seeing it means the wrapper is installed on
``odoo.http.db_filter``; not seeing it means it is not, whatever the Apps list
says.

.. code-block:: bash

   # in Docker
   docker compose logs odoo | grep dms_certify_host

   # from a log file
   grep dms_certify_host /var/log/odoo/odoo.log

.. warning::

   A module named in ``server_wide_modules`` that cannot be imported does
   **not** stop the server. ``load_server_wide_modules()`` catches the
   exception and logs *"Failed to load server-wide module
   `dms_certify_host`."* — so the symptom of a typo or a wrong addons path is a
   server that starts perfectly and a check host that 404s. Grep for both
   strings, not just the success one.

Then confirm the routing itself, without needing DNS or TLS, by sending the
``Host`` header by hand:

.. code-block:: bash

   curl -s -o /dev/null -w '%{http_code}\n' \
        -H 'Host: check.erp.example.com' http://127.0.0.1:8069/

With ``dms_certify_portal`` installed this reaches the verification form. The
database that answered is the fourth field of every Odoo log line for that
request, and it should be the same name as a request to ``erp.example.com``
produces. :doc:`handbook/administration` works that comparison through
end to end.

Upgrading
---------

Pull the submodule and **restart the server**:

.. code-block:: bash

   cd addons/dms-methode && git pull && cd -
   docker compose restart odoo     # or your service manager's equivalent

``-u dms_certify_host`` is not wrong, but it is not what applies the new code
either: the patch is installed by an import at process start, so nothing short
of a restart replaces it. A running worker keeps the wrapper it was handed.

Uninstalling
------------

Remove |addon| from ``server_wide_modules`` and restart. That is the removal
that matters; the patch exists only in the process's memory.

.. code-block:: ini

   [options]
   server_wide_modules = base,rpc,web

.. warning::

   While the module is listed in ``server_wide_modules``, Odoo refuses to
   uninstall it from the Apps list at all — ``ir.module.module.button_uninstall``
   raises *"Those modules cannot be uninstalled: dms_certify_host"*. Edit
   ``odoo.conf`` and restart **first**, then uninstall if you also want the
   database record gone.

What uninstalling does not undo
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

Nothing in this addon's own footprint, because it has none: no tables, no
views, no data, no settings, no cron, no groups. Removing it changes exactly one
thing — ``check.<host>`` stops resolving to a database.

Everything *around* it survives and is yours to clean up:

* **DNS.** The ``check.<host>`` record keeps resolving, now to a 404.
* **TLS.** The certificate keeps covering a name that no longer serves
  anything. A wildcard is harmless; a SAN entry you added for this is dead
  weight.
* **The reverse proxy.** Any ``check.*`` server block keeps forwarding. Remove
  it, or it is an open door to a 404.
* **``dms_certify_portal``.** It imports ``is_check_host`` from this package at
  module level. Removing |addon| from the addons path entirely while the portal
  is installed breaks the portal's import, not just its routing. Uninstall the
  portal first.
* **Certificate URLs already printed on paper.** Every sealed document carries
  a ``check.<host>`` URL. Those are not recoverable, and they are the reason to
  think twice before doing any of this.

See also
--------

* :doc:`handbook/concepts` — what ``dbfilter`` does and what the patch changes
  about it. Worth reading before the restart, not after.
* :doc:`handbook/administration` — DNS, TLS and the proxy, which is the other
  half of making the check host work.
* :doc:`handbook/troubleshooting` — the check host 404s, serves the wrong
  database, or serves the whole back office. One cause each.
* :doc:`limits` — what the addon deliberately does not do, including the
  deployments on which it is inert.
* :doc:`reference/post_load` — the patch itself, line by line.
