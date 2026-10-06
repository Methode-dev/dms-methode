Quickstart
==========

From a freshly installed module to one sealed document that an embassy can
actually check, on one database. About thirty minutes, most of it configuration
you only do once.

This page is the happy path with no explanation. Every step links to the page
that explains it.

.. contents::
   :local:
   :depth: 1

Before you start
----------------

* |addon| installed — see :doc:`../installation`.
* You are logged in as a user with :guilabel:`Settings` access **and**
  *Certification: Registrar*. The administrator gets the latter at install.
* Odoo running with ``proxy_mode = True``. Not optional once this is in front of
  real embassies — see :doc:`deployment`.
* One PDF on disk to pretend is a letter of invitation.
* Shell access. There is no screen in this addon that creates a verification
  entry, by design (:doc:`../limits`), so the one you check will be created from
  the shell.

Step 1 — Prove the check host answers
-------------------------------------

**Do this first.** Without it the portal has no address and every public URL
404s, and you will spend the rest of this page wondering why.

``dms_certify_host`` must be in ``server_wide_modules``, because it patches
Odoo's database resolution at import time and that has to be in place before any
request has to pick a database:

.. code-block:: ini

   [options]
   server_wide_modules = base,web,dms_certify_host

.. important::

   ``server_wide_modules`` **replaces** Odoo's default (``base,web``) rather than
   adding to it. Repeat both, or the web client stops loading.

Restart, then check the log for the line the patch writes, and the routing from
both sides:

.. code-block:: bash

   grep 'check.\* hosts use their parent' /var/log/odoo/odoo.log

   # on the check host, the portal answers at the bare path
   curl -sI -H 'Host: check.localhost' http://127.0.0.1:8069/ | head -1

   # on the ordinary host, the same path is the back office and
   # the internal prefix is a 404
   curl -sI -H 'Host: localhost' http://127.0.0.1:8069/_check | head -1

You want ``200`` and ``404`` in that order. If you get the back office on the
check host, see :doc:`troubleshooting`; the DNS, TLS and nginx side is
:ref:`deployment-check-host`.

Step 2 — Set the address that goes on paper
-------------------------------------------

:menuselection:`Settings --> General Settings --> Document verification portal`.

.. list-table::
   :header-rows: 1
   :widths: 32 68

   * - Setting
     - What to put in it
   * - :guilabel:`Public verification URL`
     - The address an embassy will type, scheme included —
       ``https://check.erp.example``. Leave it empty in development and it is
       derived from ``web.base.url`` with ``check.`` prefixed.
   * - :guilabel:`Portal company`
     - Whose name, address, email and phone the public page carries. An embassy
       is looking at one organisation whichever of your companies issued the
       document. Leave it empty and a public request resolves to whatever
       company the public user happens to default to, which is nobody's
       decision.

.. warning::

   :guilabel:`Public verification URL` is **printed on every document and
   encoded in its QR code**, on paper that circulates for months. A document
   already in an embassy's file cannot be re-pointed. Get it right before you
   issue anything in anger.

Confirm what Odoo will actually print:

.. code-block:: bash

   odoo-bin shell -c odoo.conf -d <database>

.. code-block:: python

   >>> env["dms.certificate"]._public_base_url()
   'https://check.erp.example'

Leave the rest of this block at its defaults for now. They are
:doc:`administration`.

Step 3 — Declare one document type
----------------------------------

:menuselection:`Consular --> Configuration --> Document types --> New`.

The list is **empty** on a fresh install, and that is correct: what a document
*is* belongs to whoever produces it (:doc:`issuing`).

.. list-table::
   :header-rows: 1
   :widths: 30 70

   * - Field
     - Value
   * - :guilabel:`Name`
     - ``Letter of invitation``
   * - :guilabel:`Code`
     - ``loi`` — the stable key a producing module refers to. Unique, and not
       renameable in practice once documents carry it.
   * - :guilabel:`Stamp on generation`
     - Leave it **off** for this walkthrough. It only means anything once a
       producing module is asking.

Step 4 — Agree the seal house style
-----------------------------------

:menuselection:`Settings --> General Settings --> Certified documents: the
seal`.

You can take all of it as shipped. Look at two:

* :guilabel:`Stamp position` — bottom right by default, which is next to where a
  signature usually sits. Move it if your letterhead already uses that corner.
* :guilabel:`Make room for the stamp` — leave on :guilabel:`Only when the corner
  is taken`. It keeps most documents at their exact size and shrinks only the
  ones that would otherwise be stamped over.

Everything here is a *house style*: set once, applied to every document. The
per-document choice is the :guilabel:`Marking`, which you will see in the next
step. :doc:`sealing` says what each layer is for.

Step 5 — Register and seal one document
---------------------------------------

In the shell. This stands in for what your producing module will do
(:doc:`issuing`).

.. code-block:: python

   >>> import base64
   >>> raw = open("/tmp/letter.pdf", "rb").read()
   >>> attachment = env["ir.attachment"].create({
   ...     "name": "letter.pdf",
   ...     "datas": base64.b64encode(raw),
   ...     "mimetype": "application/pdf",
   ... })
   >>> entry = env["dms.certificate"].create({
   ...     "type_id": env["dms.certificate.type"]._get_by_code("loi").id,
   ...     "movement_date": "2026-11-04",
   ...     "source_attachment_id": attachment.id,
   ...     "holder_ids": [(0, 0, {
   ...         "name": "KOWALSKI",
   ...         "first_name": "Jan",
   ...         "date_of_birth": "1985-03-14",
   ...         "rank": "Master",
   ...         "passport_number": "ZS1234567",
   ...     })],
   ... })
   >>> entry.stash_redaction()
   True
   >>> entry.certify()
   True
   >>> entry.reference, entry.verify_url
   ('ICS-2026-FRA-7MQ2-4B', 'https://check.erp.example/d/ICS-2026-FRA-7MQ2-4B')
   >>> env.cr.commit()

.. important::

   ``odoo shell`` **rolls back when you exit.** Without the ``commit()`` the
   entry you just sealed does not exist by the time you open a browser, and the
   lookup will refuse — correctly, and confusingly.

Three things to notice:

* ``stash_redaction()`` before ``certify()``. That ordering is the contract:
  measuring before sealing is what makes the measurements be of the source, and
  what every later confirm-only lookup re-derives. See :ref:`sealing-redaction`.
* ``certify()`` would have refused outright with no ``holder_ids`` — nobody
  could open it.
* The reference's place component is ``FRA``, the default, because nothing told
  it which port this is about.

Now open the entry in the back office
(:menuselection:`Consular --> Verification entries`) and look at the right-hand
panel: that is the stamped PDF in a real viewer, so you can zoom into the
microtext and check where the block landed. Try switching :guilabel:`Marking` to
:guilabel:`For embassy submission` and watch the watermark change before you
commit to anything.

Also look at the chatter. The issue note restates, in words, what opening this
document needs and what the portal will disclose — because those are Selection
fields an operator may never have looked at, and the moment they care is the
moment an embassy says it cannot get in.

Step 6 — Check it as an embassy would
-------------------------------------

Open the URL the shell printed. You get the lookup form with the reference
already filled in, exactly as scanning the QR code would. (The back office has
an :guilabel:`Open as embassy` button that does the same thing.)

#. Leave the reference as it is.
#. In :guilabel:`Passport of a person listed on the paper`, type **4567** — the
   last four characters, because ``ppt4`` is the shipped default second factor.
#. :guilabel:`Verify document`.

You should get **Document is authentic**, the person you checked named as *"1 of
the 1 listed"*, the voyage panel falling back to the document type because you
supplied no facts, one page image per page of your PDF, and the full SHA-256
fingerprint at the foot.

Click a page image. It opens full size, which is the size at which the QR code
in the stamp can be scanned off the screen — scan it with a phone and you should
land back on the same prefilled form.

Then try the failures, which are the more instructive half:

.. list-table::
   :header-rows: 1
   :widths: 44 56

   * - Do this
     - Expect
   * - The right reference, the wrong four characters
     - *Those two details do not open a document* — and **not** a hint that the
       reference was fine
   * - A reference that does not exist at all
     - The identical refusal. That is the point; see
       :ref:`verification-refusals`
   * - Leave the passport box empty
     - *Both details are needed*
   * - Get it wrong five times on the same reference
     - *Reference locked*, a note and a warning activity on the entry, and the
       page telling the agent the desk has been told
   * - Wait out :guilabel:`Result lifetime` and reload the result page
     - *That result has expired*, back at the form

Finally, press :guilabel:`The paper does not match` on a good result and look at
the entry's chatter again. That report arrives **even with notifications off**,
and it is the single most valuable thing this portal collects.

What next
---------

* :doc:`issuing` — do step 5 from your own module, properly, with ``issue()``
  and the override points. **Read it before you wire anything up.**
* :doc:`deployment` — the checklist before anything goes on paper: DNS, TLS,
  ``--proxy-mode``, nginx's two rate-limit zones, and backing up the pepper.
  Read it *before* you issue real documents, not after.
* :doc:`administration` — both rate limits, retention, and who gets which group.
* :doc:`security-and-privacy` — what personal data this holds, and what to
  settle before going live.
* :doc:`concepts` — if any of the above felt like it was referring to something
  you had not been told.
