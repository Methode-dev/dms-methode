DMS Certify — ``check.*`` host routing
======================================

|addon| makes ``check.erp.example.com`` serve the same Odoo database as
``erp.example.com``.

That is the whole addon. Three files, fifty-seven lines, no models, no views, no
data — one monkey-patch of ``odoo.http.db_filter`` and two helper functions.

Why it has to exist
-------------------

Odoo resolves which database a request belongs to from the **hostname**, through
``dbfilter`` and its ``%h`` / ``%d`` substitutions. A deployment that uses
``dbfilter = %d`` or ``%h`` is therefore saying *"the database is named after the
host"*.

``dms_certify_portal`` — the only addon that depends on this one, documented in its
own ``docs/`` folder beside this one — wants a hostname of its own,
``check.<your-host>``, so that the URL printed on a certified document exposes a
handful of public routes rather than the whole of Odoo, and does not advertise the
hostname of your ERP. But ``check.erp.example.com`` under ``%d`` would look for a
database called ``check``, which does not exist, and every request to the
verification portal would 404 before any addon saw it.

This module hands ``db_filter`` the **parent** host instead:

.. code-block:: text

   request for  check.erp.example.com
        │
        ▼
   db_filter(host="check.erp.example.com")
        │  ← patched by this addon
        ▼
   original db_filter(host="erp.example.com")
        │
        ▼
   the same database erp.example.com resolves to

.. important::

   The patch must be in place **before any request picks a database**, which a
   normal addon installation is too late for. |addon| is loaded with
   ``server_wide_modules``, not installed from the Apps list. See
   :doc:`installation` — this is the one thing about this addon that is easy to get
   wrong.

At a glance
-----------

.. list-table::
   :widths: 30 70

   * - Odoo version
     - 19.0 (``base`` only)
   * - Module version
     - |release|
   * - Technical name
     - |addon|
   * - Licence
     - LGPL-3
   * - Loaded via
     - ``server_wide_modules`` **and** ``post_load``, not an ordinary install
   * - Defines
     - no models, no views, no data, no security rules
   * - Python packages
     - none
   * - Tests
     - none — see :ref:`limits-no-tests`
   * - Source
     - :ghsrc:`__manifest__.py`

Where to start
--------------

* **Setting this up?** :doc:`installation` is the only page you need, and the
  ``server_wide_modules`` requirement is the part to read twice.
* **Want to know what it actually does?** :doc:`handbook/concepts` — it is short,
  because the addon is short.
* **Configuring DNS, TLS and the proxy?** :doc:`handbook/administration`.
* **The check host is serving the wrong thing, or nothing?**
  :doc:`handbook/troubleshooting`.
* **Changing it, or reusing** ``is_check_host`` **in your own addon?**
  :doc:`development/index`.

.. toctree::
   :maxdepth: 2
   :caption: Getting started

   installation

.. toctree::
   :maxdepth: 2
   :caption: Handbook

   handbook/index

.. toctree::
   :maxdepth: 2
   :caption: Reference

   reference/index

.. toctree::
   :maxdepth: 2
   :caption: Development

   development/index

.. toctree::
   :maxdepth: 1
   :caption: About

   changelog
   limits

Indices and tables
------------------

* :ref:`genindex`
* :ref:`modindex`
* :ref:`search`
