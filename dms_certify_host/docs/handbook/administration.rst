Administration
==============

There is nothing to administer **inside** Odoo. |addon| has no settings page, no
groups, no scheduled job and no records of any kind — once the
``server_wide_modules`` line is in place (:doc:`../installation`), the addon
needs no further attention for as long as the hostname stays the same.

Everything on this page is therefore outside Odoo: a DNS name, a TLS
certificate, and a reverse proxy that does not meddle. Those three plus one
restart are the whole job, and the last section is how to prove it worked.

.. contents::
   :local:
   :depth: 2

What has to agree
-----------------

``check.`` appears in four places, and they all have to say the same thing:

.. list-table::
   :header-rows: 1
   :widths: 22 78

   * - Where
     - What it is
   * - DNS
     - An ``A`` or ``CNAME`` record for ``check.<your-host>``, so the name
       resolves at all.
   * - TLS
     - A certificate whose subject names cover ``check.<your-host>``.
   * - The proxy
     - A server block that answers for the name and forwards ``Host``
       **unchanged**.
   * - The code
     - ``CHECK_PREFIX`` in :doc:`../reference/hosts`.

The fourth is a constant rather than a setting on purpose — the value has to be
known before any database exists, so a configuration option would only be a
fifth place to disagree. See :doc:`../limits`.

DNS
---

One record, for the host ``check.`` + your existing Odoo hostname:

.. code-block:: text

   check.erp.example.com.    CNAME    erp.example.com.

A ``CNAME`` pointing at the parent name is the better of the two options, and
not only for brevity. The addon's entire premise is that ``check.<host>`` and
``<host>`` are *the same Odoo serving the same database*; a ``CNAME`` states that
relationship once, and a later change of address follows automatically. Two
``A`` records state it twice and can drift apart silently — and when they do, the
symptom is a check host that intermittently reaches a different server, which is
an unpleasant thing to diagnose.

.. tip::

   If your zone already carries a wildcard — ``*.example.com`` — and your Odoo
   host is ``erp.example.com``, note that the wildcard does **not** cover
   ``check.erp.example.com``: a DNS wildcard matches one label, and that is one
   label too few. The record above is still needed. The same arithmetic catches
   people out with certificates, below, and for the same reason.

TLS
---

The certificate has to cover the new name. Two ways, with different blast
radii:

.. list-table::
   :header-rows: 1
   :widths: 26 74

   * - Approach
     - Notes
   * - A SAN entry
     - Add ``check.erp.example.com`` to the certificate alongside
       ``erp.example.com``. Explicit, auditable, and the renewal has to keep
       remembering it — see the warning below.
   * - A wildcard
     - ``*.erp.example.com`` covers it, and so does any future
       ``something.erp.example.com``. Note the level: a certificate for
       ``*.example.com`` matches ``erp.example.com`` but **not**
       ``check.erp.example.com``. One wildcard label, one hostname label.

With certbot, the name joins the existing certificate rather than getting one of
its own, so the proxy keeps loading a single file:

.. code-block:: bash

   certbot certonly --expand -d erp.example.com -d check.erp.example.com

.. warning::

   A renewal that drops the extra name breaks the check host **while the parent
   host keeps working perfectly**. Nobody notices from the inside: the back
   office is fine, and the only people who meet the failure are the embassies
   holding a printed URL. If your renewal is scripted, make the name list part of
   the script rather than something that was typed once by hand.

.. _administration-proxy:

The reverse proxy
-----------------

The proxy has one obligation: forward the ``Host`` header the client sent,
untouched.

This is load-bearing in a way that is easy to underestimate. The hostname is the
**only** input the addon has. There is no path, no cookie, no header and no
parameter that distinguishes a verification request from any other — the whole
mechanism is ``Host: check.erp.example.com`` reaching ``db_filter``. A proxy that
rewrites ``Host`` does not degrade the feature; it deletes it.

.. code-block:: nginx

   server {
       listen 443 ssl;
       server_name check.erp.example.com;     # or: check.*

       ssl_certificate     /etc/letsencrypt/live/erp.example.com/fullchain.pem;
       ssl_certificate_key /etc/letsencrypt/live/erp.example.com/privkey.pem;

       proxy_set_header Host             $host;
       proxy_set_header X-Forwarded-Host $host;
       proxy_set_header X-Forwarded-For  $proxy_add_x_forwarded_for;
       proxy_set_header X-Forwarded-Proto $scheme;

       location / {
           proxy_pass http://127.0.0.1:8069;
       }
   }

``server_name check.*;`` is worth knowing about if you run the same
configuration across several environments: it matches ``check.localhost``,
``check.staging.example.com`` and ``check.erp.example.com`` from one block,
which is exactly the set of names this addon handles.

.. important::

   **nginx's default is wrong for this**, and the mistake is invisible. With no
   ``proxy_set_header Host``, nginx sends ``Host: $proxy_host`` — the name of the
   upstream, ``127.0.0.1:8069``. ``db_filter`` then sees a host that is neither a
   check host nor the parent, and the addon has nothing to work with.

   Two inheritance rules make this a real trap rather than a theoretical one:

   * ``proxy_set_header`` is **not** inherited between ``server`` blocks. If you
     add a separate block for ``check.*``, every header the main block sets has
     to be set again there. Copying the ``server_name`` and ``proxy_pass`` and
     forgetting the headers produces a check host that reaches Odoo and 404s.
   * Within a block, a ``location`` that declares **any** ``proxy_set_header``
     replaces the whole inherited set rather than adding to it. One
     ``proxy_set_header Upgrade`` in a websocket location silently drops
     ``Host``.

If your parent host already works under a host-derived ``dbfilter``, then
``Host`` is already being forwarded correctly — so the only place this can go
wrong is a *new* server block. That is also the usual place it does.

.. note::

   With ``proxy_mode = True`` in ``odoo.conf``, send ``X-Forwarded-Host`` as
   well, carrying the same value. The addon reads the host from the WSGI environ
   and ``is_check_host`` reads it from the request object; keeping the two headers
   in agreement means the question of which one wins never arises. See the
   ``.. todo::`` on :doc:`../reference/post_load`.

What the proxy cannot do for you
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

Adding a ``check.*`` block does not narrow what the check host serves. The
moment the proxy forwards ``/``, it is Odoo deciding what to answer with — and
with |addon| alone, Odoo answers with the whole back office. The narrowing is
``dms_certify_portal``'s, and the rate limits, the ``robots.txt`` and the
asset-only exemptions that belong in that block are documented in that addon's
own ``docs/`` folder beside this one. Read :doc:`../limits` before you put a
check host in front of a production database with only this module loaded.

.. _administration-confirm:

Confirming the check host reaches the right database
----------------------------------------------------

Three steps, in increasing order of how much infrastructure they need. Do them
in order; each one eliminates a layer.

1. Odoo, with no DNS and no TLS
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

Send the ``Host`` header by hand, straight at Odoo, bypassing the proxy
entirely:

.. code-block:: bash

   curl -s -o /dev/null -w '%{http_code}\n' \
        -H 'Host: check.erp.example.com' http://127.0.0.1:8069/

   curl -s -o /dev/null -w '%{http_code}\n' \
        -H 'Host: erp.example.com'       http://127.0.0.1:8069/

A ``404`` on the first and a ``200`` or ``303`` on the second means the patch is
not in force — go back to :ref:`installation-server-wide`. Identical status
codes mean Odoo resolved a database for both.

2. The comparison that actually proves it
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

A status code only says *a* database answered, not *which*. The database name is
the fourth field of every Odoo log line for the request, so run the two requests
above and read it back:

.. code-block:: bash

   docker compose logs --tail=50 odoo | grep ' INFO '
   # or
   tail -n 50 /var/log/odoo/odoo.log

The two requests must name the **same** database. This comparison is the whole
verification, and it is not optional busywork: on a server with exactly one
database, Odoo's monodb rule resolves everything regardless of hostname, so a
check host can appear to work on a deployment where this addon is doing nothing
at all. Adding a second database is then the moment it breaks. See
:ref:`limits-inert`.

.. note::

   With ``dms_certify_portal`` installed you cannot ask Odoo over HTTP which
   database it chose, because every path on a check host is rewritten into the
   portal's own namespace — there is no back-office endpoint left to interrogate.
   The log is the instrument. If you want to see it in the UI instead, do it in
   the window between restarting with ``server_wide_modules`` and installing the
   portal, when the check host still serves the back office; log in through it
   once and read the database name off the user menu, then install the portal.

3. End to end, through the proxy
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

Once the certificate exists, you can test the proxy before the DNS record has
propagated by resolving the name yourself:

.. code-block:: bash

   curl -sS -o /dev/null -w '%{http_code}\n' \
        --resolve check.erp.example.com:443:203.0.113.10 \
        https://check.erp.example.com/

Then, with DNS in place, drop ``--resolve``. A TLS error here and a success at
step 1 narrows the problem to the certificate; a ``404`` here and a success at
step 1 narrows it to the proxy rewriting ``Host``. :doc:`troubleshooting` takes
each of those from the symptom.

When the hostname changes
-------------------------

The check name is derived from the parent name, so renaming the parent host
renames the check host too — and nothing in Odoo knows that happened.

.. warning::

   Verification URLs printed on documents already in circulation are not
   recoverable. An embassy holding a sealed PDF has ``check.<old-host>`` on
   paper, in a file, possibly for years. Before retiring a hostname, keep the old
   name resolving — DNS record, certificate name and proxy block — for as long as
   those documents are in use, or accept that they stop being checkable.

Routine maintenance
-------------------

Honestly: none, apart from the certificate.

* **No cron, no logs to review, no data to purge.** The addon writes nothing.
* **Certificate renewal** is the one recurring task, and the one failure mode
  that hides — see the warning above.
* **An Odoo upgrade** is worth a look: the patch wraps ``db_filter(dbs,
  host=None)``, and a change to that signature in a future series would be the
  thing to check. :doc:`../installation` says so under requirements.
* **After any restart**, the startup log line is the one-command confirmation
  that the patch came back. :ref:`installation-verify`.

See also
--------

* :doc:`concepts` — what ``dbfilter`` does with the hostname you are configuring
  here. Read it first if any of the above felt arbitrary.
* :doc:`troubleshooting` — symptom by symptom, for when the three steps above do
  not come out the way this page says.
* :doc:`../installation` — the ``server_wide_modules`` line, which has to be in
  place before any of this is observable.
* :doc:`../limits` — why a check host is not an isolation boundary, and the
  deployments on which the addon is inert.
* :doc:`../reference/hosts` — the prefix, the port handling and the exact set of
  hostnames that count as a check host.
