Troubleshooting
===============

The addon has one job, so it has a small number of ways to fail. Every symptom
below is one of them.

.. admonition:: Do this first, every time
   :class: important

   **Try the parent host.** If ``erp.example.com`` is also broken, nothing on
   this page applies — the problem is your ``dbfilter``, your proxy or your Odoo,
   and |addon| is not involved. If the parent host works and
   ``check.erp.example.com`` does not, the fault is in one of the four things
   listed under :doc:`administration`, and this page tells you which.

   **Then look for the startup line.** One ``grep`` separates "the patch is not
   installed" from everything else:

   .. code-block:: bash

      docker compose logs odoo | grep dms_certify_host

.. contents::
   :local:
   :depth: 2

The check host serves nothing
-----------------------------

404, or "Database not found"
^^^^^^^^^^^^^^^^^^^^^^^^^^^^

The request reached Odoo, Odoo could not decide which database it was for, and
no addon ever saw it. In order of likelihood:

.. list-table::
   :header-rows: 1
   :widths: 34 66

   * - Cause
     - How to tell, and the fix
   * - **Not in**
       ``server_wide_modules``
     - The startup line is absent. This is the answer most of the time. Add
       ``dms_certify_host`` to the list and **restart** —
       :ref:`installation-server-wide`.
   * - Installed from the Apps
       list instead
     - Also no startup line on the server that matters. An ordinary install is
       not wrong, it is *too late*: resolving the database is what has to happen
       before a database can load a module. :ref:`installation-server-wide` has
       the loop drawn out.
   * - The module could not be
       imported
     - ``grep 'Failed to load server-wide module' <log>``. A name in
       ``server_wide_modules`` that Odoo cannot find is logged and skipped —
       **the server starts normally**. Usually a typo, or an ``addons_path``
       that points at ``dms-methode/dms_certify_host`` instead of at
       ``dms-methode``.
   * - The server was not
       restarted
     - ``-u dms_certify_host`` does not replace the patch. The wrapper is
       installed by an import at process start; a running worker keeps the
       function it was handed. Restart.
   * - The proxy rewrote ``Host``
     - See :ref:`troubleshooting-proxy-host` below. Discriminator: the
       hand-made request in step 1 of :ref:`administration-confirm` succeeds
       while the same request through the proxy 404s.
   * - The printed URL is not
       the host you configured
     - Read the URL on the document character by character. ``check-erp``,
       ``check.www.erp`` and a second ``check.`` prefix are all not the host
       this addon recognises. :doc:`../reference/hosts` has the exact set.

The startup log line is missing
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

Expected, at ``INFO``, once per server process:

.. code-block:: text

   ... INFO ? odoo.addons.dms_certify_host: dms_certify_host: check.* hosts use their parent host's database

If it is not there:

#. **The module is not in** ``server_wide_modules`` — the common case, above.
#. **It failed to import** — grep for ``Failed to load server-wide module``,
   which is logged instead.
#. **You are reading the wrong log.** In a multi-container or multi-instance
   deployment, the line is emitted by whichever process serves the request. The
   database field reads ``?`` because no database is bound yet, which is also
   how you recognise it as a startup line rather than a request line.
#. **``INFO`` is suppressed.** ``log_level = warn``, or a ``log_handler``
   entry that raises the threshold for ``odoo.addons``, hides the line while the
   patch works perfectly. Raise the level once to check, rather than concluding
   the patch is missing.

The line appears **once** per process even though ``post_load`` runs again on
every registry load — the idempotency guard returns before the log statement.
That is normal and is explained on :doc:`../reference/post_load`.

The check host serves the wrong thing
-------------------------------------

It serves a *different* database
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

The patch is working — a database resolved — but not the one the parent host
resolves to. Four causes, and the first two are not this addon:

.. list-table::
   :header-rows: 1
   :widths: 34 66

   * - Cause
     - How to tell, and the fix
   * - A stale session cookie
     - ``dbfilter`` is also used to validate the database already in the
       session cookie. Under a loose filter, a browser holding a session for
       another database keeps it. **Retry in a private window.** If that fixes
       it, it was always the cookie.
   * - ``dbfilter`` is ambiguous
     - ``%d`` takes only the first label, so ``erp`` matches ``erp_prod``,
       ``erp_test`` and ``erp_old`` alike. Odoo proceeds only when exactly one
       database survives, so the real symptom is usually a 404 — but with a
       regex of your own, ambiguity can resolve to the wrong one. Tighten the
       filter; the fix is the same for the parent host.
   * - Two ``A`` records that
       drifted
     - ``check.`` and the parent name resolve to different servers, each with
       its own databases. ``dig +short`` both names and compare. This is the
       failure a ``CNAME`` cannot have — see :doc:`administration`.
   * - A doubly-prefixed host
     - ``check.check.erp.example.com`` has exactly one prefix stripped and
       should 404. If it instead serves the live database, two wrappers are
       stacked on ``db_filter`` and the idempotency guard is not holding —
       that is a bug, not a configuration error. Report it with the startup
       log. :doc:`../reference/post_load` explains the arithmetic.

Run step 2 of :ref:`administration-confirm` either way: it compares the database
that answered for each host, which is the only statement that settles this.

It serves the whole back office
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

|addon| resolves a database and stops. It does **not** narrow what the host
serves, and never did — so the back office appearing on a check host is this
addon working and ``dms_certify_portal``'s routing not being in play. See
:doc:`../limits`.

.. warning::

   Until this is fixed, ``check.<host>`` is a second, probably unmonitored,
   front door to your ERP's login page. Take the proxy's ``check.*`` block down
   rather than leaving it up while you investigate.

Three causes, in order:

#. **``dms_certify_portal`` is not installed.** The expected state in the window
   between restarting with ``server_wide_modules`` and installing the portal.
   Install it.
#. **The portal is installed in a different database than the one the check host
   resolved to.** The override is a per-database install; the host routing is
   per process. Run step 2 of :ref:`administration-confirm`, then check the Apps
   list *in the database that actually answered*.
#. **The proxy normalised ``Host`` to the parent name.** This one is nasty,
   because the database resolves perfectly and only the confinement disappears:
   ``is_check_host()`` reads the host Odoo was given, so if the proxy forwarded
   ``Host: erp.example.com``, Odoo is — correctly — serving the parent host.
   Look for a ``proxy_set_header Host`` with a literal name or a ``$server_name``
   rather than ``$host``.

Before the request reaches Odoo
-------------------------------

.. _troubleshooting-proxy-host:

The proxy is rewriting ``Host``
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

**Symptom.** The hand-made request to ``127.0.0.1:8069`` with
``-H 'Host: check.erp.example.com'`` succeeds; the same URL through the proxy
404s, or serves the back office.

**Cause.** The hostname is the only input this addon has. nginx's default is
``Host: $proxy_host`` — the upstream's own name — so a block that does not set
the header explicitly deletes the mechanism. Two inheritance rules do most of
the damage:

* ``proxy_set_header`` is not inherited **between** ``server`` blocks, so a new
  ``check.*`` block starts from nothing;
* within a block, a ``location`` that sets **any** ``proxy_set_header`` replaces
  the inherited set rather than adding to it — one ``proxy_set_header Upgrade``
  in a websocket location drops ``Host`` for that location alone.

**Fix.** ``proxy_set_header Host $host;`` in the block that serves ``check.*``,
and in every ``location`` inside it that declares headers of its own.
:ref:`administration-proxy` has a working block.

.. note::

   ``$host`` is lowercased and carries no port; ``$http_host`` is the header
   verbatim. Either works here — ``parent_of_check_host`` lowercases the name
   itself and reattaches whatever port it was given untouched. Pick one and use
   it for both ``Host`` and ``X-Forwarded-Host`` so the two cannot disagree.

TLS complains about the name
^^^^^^^^^^^^^^^^^^^^^^^^^^^^

**Symptom.** ``curl: (60) SSL: no alternative certificate subject name matches
target host name``, or a browser interstitial naming the certificate's host
instead of yours. Nothing has reached Odoo, so no amount of Odoo configuration
will help.

**Cause.** The certificate does not cover ``check.<host>``. Most often a
wildcard at the wrong level: ``*.example.com`` matches ``erp.example.com`` but
not ``check.erp.example.com``. A wildcard label covers exactly one hostname
label.

**Diagnosis.** Ask the server what it is actually presenting:

.. code-block:: bash

   openssl s_client -connect erp.example.com:443 \
       -servername check.erp.example.com </dev/null 2>/dev/null \
     | openssl x509 -noout -text | grep -A1 'Subject Alternative Name'

**Fix.** Add the name — ``certbot certonly --expand -d erp.example.com -d
check.erp.example.com`` — and reload the proxy. Then make the name list part of
your renewal, because a renewal that silently drops it breaks only the check
host and leaves the back office looking fine. :doc:`administration` says more
about that particular trap.

The name does not resolve
^^^^^^^^^^^^^^^^^^^^^^^^^

**Symptom.** ``Could not resolve host``, and ``dig +short check.erp.example.com``
returns nothing.

**Cause.** No DNS record. A zone wildcard you were counting on is probably at
the wrong level, for the same arithmetic as the certificate above.

**Fix.** :doc:`administration`. To test the proxy and the certificate before
propagation, resolve the name yourself with ``curl --resolve``.

It works in production and not in development
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

``check.localhost`` is a valid check host — ``parent_of_check_host`` returns
``localhost`` — so the code is not the problem. The usual suspects are below it:

* the name does not resolve locally (add it to ``/etc/hosts``, or use
  ``curl -H 'Host: check.localhost'``);
* a self-signed certificate (``curl -k``, or trust it);
* a single database, where Odoo's monodb rule resolves everything regardless of
  hostname — so development can be *passing for the wrong reason*. See
  :ref:`limits-inert`.

Everything looks right and nothing changed
------------------------------------------

Two cases where the addon is genuinely doing nothing, and that is correct:

* **Your ``dbfilter`` does not use the host.** With a literal ``dbfilter``, with
  ``db_name`` and no filter, or with no filter at all, the host is never read and
  the patch changes no outcome. It still loads and still logs. The table in
  :ref:`limits-inert` lists each case.
* **There is one database.** Monodb resolves it from anything. The check host
  works, but not because of this module; add a second database and it stops.

Both are worth knowing before you spend an afternoon on a patch that has nothing
to do.

Getting more detail
-------------------

**The startup line**, which is the whole of this addon's instrumentation:

.. code-block:: bash

   docker compose logs odoo | grep dms_certify_host
   grep -E 'dms_certify_host|Failed to load server-wide module' /var/log/odoo/odoo.log

**The two requests**, side by side — the comparison in
:ref:`administration-confirm` is the single most informative thing you can run.

**The functions, directly.** Settle what counts as a check host by asking,
rather than by reasoning about the prefix:

.. code-block:: python

   >>> from odoo.addons.dms_certify_host.hosts import parent_of_check_host, is_check_host
   >>> parent_of_check_host("check.erp.example.com:8069")
   'erp.example.com:8069'
   >>> is_check_host("checkout.example.com")
   False

Both are pure string functions with an explicit ``host`` argument, so this is
safe to run in an ``odoo-bin shell`` against production: nothing is read and
nothing is written.

The table on :doc:`../reference/hosts` lists every case this way round.

See also
--------

* :doc:`administration` — DNS, TLS, the proxy, and the three-step confirmation
  most of this page refers back to.
* :doc:`concepts` — what ``dbfilter`` does, so a 404 stops being mysterious.
* :doc:`../installation` — ``server_wide_modules``, which is the answer to the
  largest share of the symptoms above.
* :doc:`../limits` — behaviour that looks like a fault and is not: the inert
  deployments, ``check.check.``, and the absence of any isolation.
* :doc:`../reference/post_load` — the patch itself, for when a symptom looks
  like the wrapper rather than the configuration.
