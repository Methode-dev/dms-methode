Troubleshooting
===============

The failures that actually happen, and the fix for each. Things that are
confusing but *correct* are here too, flagged as such; genuine limitations are
in :doc:`../limits`.

.. contents::
   :local:
   :depth: 2

The portal is unreachable
-------------------------

Every public URL 404s
^^^^^^^^^^^^^^^^^^^^^

**This is the first thing to check, every time, and it is the answer most of
the time.**

|addon| declares all seven of its routes under the internal prefix ``/_check``,
and nothing is ever served at that path. An ``ir.http`` override rewrites ``/``
to ``/_check`` — **but only on a host whose name begins** ``check.``. So in
order of likelihood:

#. **``dms_certify_host`` is not in** ``server_wide_modules``. Its patch to
   Odoo's database resolution runs at import time, and without it ``check.``
   hosts cannot pick a database at all. The startup log line is the test:

   .. code-block:: bash

      grep 'check.\* hosts use their parent' /var/log/odoo/odoo.log

   Nothing? Add it — and remember it **replaces** the default:
   ``server_wide_modules = base,web,dms_certify_host``.

#. **There is no DNS record** for ``check.<host>``, or TLS does not cover the
   name. A browser refusing the certificate looks exactly like an outage from
   the counter.

#. **You are testing the wrong path.** On the check host the portal is at
   ``/``. ``https://check.<host>/_check`` is a 404 and is *supposed* to be.

Confirm the routing from both sides in one go:

.. code-block:: bash

   curl -sI -H 'Host: check.erp.example' http://127.0.0.1:8069/     | head -1
   curl -sI -H 'Host: erp.example'       http://127.0.0.1:8069/_check | head -1

``200`` then ``404``. Full procedure in :ref:`deployment-check-host`.

The check host serves the whole back office
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

The host test is a string comparison on the request's host, so something is
telling Odoo the request arrived somewhere else.

#. **The proxy is rewriting** ``Host``. ``proxy_set_header Host $host;`` — not
   ``$proxy_host``, not a literal upstream name. This is the usual cause.
#. **|addon| is not installed** on the database that host resolves to. The
   rewrite lives in this addon's ``ir.http`` override; ``dms_certify_host``
   alone only fixes database selection.
#. **The check host resolved to a different database.** Two databases, the
   portal installed on one of them. ``check.erp.example`` should land on exactly
   the same database as ``erp.example``.

Either way: do not "fix" it with an nginx ``location`` block that proxies only
the portal paths. The isolation is Odoo's job here, and a path allowlist in
nginx would have to be maintained in step with the routes.

The language switcher offers only English
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

The switcher lists only the languages the **portal copy** exists in *and* that
are active in the database. A fresh database has only English active, which is
why the install hook activates the rest.

.. code-block:: python

   >>> env["res.lang"].search([("active", "=", True)]).mapped("code")
   ['en_US', 'fr_FR']

If ``fr_FR`` is missing, the hook could not find an installable variant — it
logs ``no installable language found for 'fr'``. Activate it by hand from
:menuselection:`Settings --> Translations --> Languages`. On a database that
predates the module's language step, upgrading re-runs it
(:doc:`../reference/migrations`).

Lookups are refused
-------------------

Every lookup is throttled, for everybody, at once
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

Agents who have made no mistake at all get *"Checks from here are paused"*.

**Odoo is not running with** ``--proxy-mode``. The portal reads the client
address from ``remote_addr``, which Werkzeug only resolves from
``X-Forwarded-For`` when proxy mode is on. Without it every request appears to
come from your reverse proxy, so the per-address limit becomes **one global
limit**: ten failures from anyone in the world pauses the form for every embassy.

Nothing fails loudly, which is why this is worth checking before anything else.
The evidence is in the log:

.. code-block:: text

   Consular --> Reporting --> Verification attempts

Every row showing the *same* address — your proxy's — is the confirmation. Fix
it with ``proxy_mode = True`` in ``odoo.conf`` and
``proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;`` on the vhost,
then wait out the window or delete the offending rows.

See :doc:`deployment`.

A correct passport is refused on every document
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

**The pepper changed, or was lost.** Every stored second-factor hash is an HMAC
under ``dms_certify_portal.passport_key``. Change it and the hashes it produced
are no longer reproducible, so the form refuses every correct passport with the
same message it gives a wrong one.

.. code-block:: python

   >>> bool(env["ir.config_parameter"].sudo().get_param(
   ...     "dms_certify_portal.passport_key"))
   True

If the parameter is **missing entirely**, you get a loud error instead of a
silent refusal — *"The verification hashing key is missing. Reinstall the module
or restore the … system parameter from backup."* — which is the better failure
of the two.

If it is present but *different* from the one in force when the documents were
issued, there is no way to tell from the data. Restore it from backup. There is
no key history and no re-derivation path; the only repair without the original
key is a script that re-hashes from the stored passport numbers, and a holder
whose number was never stored cannot be recovered at all. See
:doc:`../limits`.

A document that should open is reported as not existing
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

In order of likelihood:

#. **It is still a draft.** The portal only speaks about ``certified``,
   ``delivered`` and ``revoked`` entries, so a registered-but-unsealed document
   refuses exactly like an unknown reference. Press :guilabel:`Certify and
   watermark`.
#. **The holder has no hash for this document's second factor.** A holder
   created with no passport number has no passport hash and cannot open a
   document set to ``ppt4`` or ``pptfull``; one with no date of birth cannot
   open one set to ``dob``. Check the second factor on the entry against what
   the holder rows actually carry.
#. **The agent is typing the wrong thing.** Under ``ppt4`` it is the *last four
   characters* of the number, not the first four, and not four digits of
   something else. Separators and case do not matter; what is typed is
   normalised the same way the stored side was.
#. **The reference is right but belongs to another document.** References are
   matched on the normalised form, so this is rarer than it sounds —
   ``UNIQUE(reference_key)`` makes punctuation-only collisions impossible to
   create.

.. note::

   **By design:** the refusal wording is identical for all of the above and for
   a reference that genuinely does not exist. That is not the portal being
   unhelpful; see :ref:`verification-refusals`.

A reference keeps re-locking
^^^^^^^^^^^^^^^^^^^^^^^^^^^^

**Working as intended, and somebody should look at it.** Five failures against
one reference, counted from *any* address, lock it for thirty minutes — and the
lock is counted across addresses precisely so that changing address does not
help a guesser.

The lock's clock runs from the failure that tripped it, so continued attempts do
not extend it. If an agent is genuinely stuck, the fastest route is the
operations desk opening the entry and reading them the answer; the lockout page
tells them to call.

Repeated lockouts on a document that nobody is expecting to be checked is a
signal, not a nuisance. Every lockout posts to the certificate's chatter **and**
raises a warning activity on the issuer, whatever the notification setting says.

The result page is wrong
------------------------

The verdict is right but there is no page
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

The agent gets *"Document is authentic"*, the reference, the fingerprint — and
*"The page cannot be shown here"* where the images should be. The download 404s.

**The redaction leak check failed closed.** Under ``confirm`` disclosure the
page is rebuilt per lookup with everyone else's lines removed, and the result is
then checked for what should have gone. If anything survived, nothing is served
at all: an empty page is a nuisance, a page carrying somebody else's passport
number is a breach (:ref:`sealing-redaction`).

Confirm it from the log — this is the only trace:

.. code-block:: bash

   grep 'refusing to serve it' /var/log/odoo/odoo.log

.. code-block:: text

   ERROR … dms_certify_portal: redacting ICS-2026-DKK-4KQ7-9B left
   KOWALSKI, <passport> behind; refusing to serve it

Then narrow it down in the shell. ``_public_bytes`` with *every* holder passed
in has nobody to redact, so it exercises the sealing path without the redaction
path:

.. code-block:: python

   >>> doc = env["dms.certificate"].search(
   ...     [("reference", "=", "ICS-2026-DKK-4KQ7-9B")])
   >>> doc.disclosure
   'confirm'
   >>> len(doc._public_bytes(doc.holder_ids))      # no redaction at all
   184203
   >>> len(doc._public_bytes(doc.holder_ids[0]))   # the real path
   0

Bytes from the first and nothing from the second confirms redaction is the
problem rather than the document or the seal. The usual cause is that the
document changed after it was registered, so re-measure and try again:

.. code-block:: python

   >>> doc.stash_redaction()
   True

If it still returns nothing, the leaked tokens named in the log tell you what
survived. A surname that also appears in the letter body as ordinary prose is
the classic — the by-value fallback cannot distinguish them.

As a stopgap, switching that one document to ``full`` disclosure serves the
sealed copy as issued and bypasses the whole path. Do that knowing it publishes
the crew list.

A fallback line appears on every single lookup
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

.. code-block:: text

   INFO … dms_certify_portal: ICS-2026-DKK-4KQ7-9B has no current positions
   for Jan Kowalski; redacting by value instead

The measured positions no longer match the document, so the portal is searching
the page for stored values instead. It still works, and it is weaker: searching
blanks a string wherever it appears, and a value that was never stored cannot be
searched for at all.

This logs at ``INFO`` and nobody is watching for it. Call ``stash_redaction()``
again, or re-register the document. If the source keeps changing after
registration, fix that — the measurement is only meaningful against a document
that has settled.

The printed URL points at the wrong host
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

**The public base URL was set after those documents were issued.** The seal
block prints the address, and the QR encodes it, at the moment the document is
sealed — on paper that is now in somebody's filing cabinet.

``verify_url`` is a computed field, so the back office and
:guilabel:`Open as embassy` will show the *new* address. The paper will not.

.. code-block:: python

   >>> env["dms.certificate"]._public_base_url()
   'https://check.erp.example'

What you can do:

* **Re-stamp** the affected documents. The reference and the printed
  fingerprint do not change, so copies already out keep verifying — but the
  copies already out keep the old address, so this only helps for documents that
  have not been sent.
* **Serve the old name too**, if it still exists: a ``check.`` vhost on the old
  host name proxying to the same Odoo. The references are unchanged, so lookups
  resolve.
* Nothing else. This is why :doc:`deployment` puts the URL above the fold.

Nothing reaches the desk
------------------------

No chatter message after a successful lookup
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

**Working as intended** if :guilabel:`Notify on every lookup` is off on that
entry. A successful check by an embassy is routine and goes quiet.

What still comes through with notifications off: a **lockout** and a **reported
mismatch**. Both also raise a warning activity on the issuer. If *those* are
missing, check that the entry has an issuer at all — the activity falls back to
``create_uid``, and a database with no ``mail.mail_activity_data_warning`` type
logs ``no warning activity type available`` and posts the note only.

A failed lookup against an unknown reference reaches nobody
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

Correct: there is no document to post onto. The case that *is* notified is the
reference being right and the second check wrong — which is exactly the one an
operator at the issuing desk wants to know about. The row is in the attempt log
either way.

The back office
---------------

An agent cannot see passport numbers
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

**By design.** ``passport_number`` and its three hashes are restricted at the
field level to *Certification: Registrar*. For an Agent the field is not greyed
out — it is absent.

If somebody needs to read or correct a passport number, they need the Registrar
group, and that is a data-protection decision rather than a convenience one
(:doc:`security-and-privacy`). An Agent can still see who is listed, by name,
and can run a lookup for an embassy on the telephone.

The stamped-output panel is empty
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

The panel re-seals the source on every read, and it swallows every failure on
purpose — an unreadable source must leave the form **openable**, because that
form is where somebody fixes it.

So an empty panel means the source could not be read or could not be sealed:

#. **There is no source.** No :guilabel:`Source document`, and no producing
   module overriding ``_certify_source()``.
#. **It is not a PDF.** A ``.docx`` or an image dropped into the attachment
   field. The source has to be a PDF; sealing is a PDF operation.
#. **It is a truncated or encrypted PDF.**

The traceback is in the log:

.. code-block:: bash

   grep 'preview failed for' /var/log/odoo/odoo.log

Certifying the same document raises *"There is no document to seal on …"*, which
is the loud version of the same problem.

.. note::

   The :guilabel:`Source document` picker deliberately hides two things, so a
   missing attachment may be hidden rather than absent: attachments with a
   ``res_field`` set (Odoo's internal storage behind every binary field,
   including a ``dms.file``'s own content) and this module's own sealed copies.
   A producing module should override ``_certify_source()`` rather than fight
   the picker.

"Revoke an issued entry instead of deleting it"
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

**Working as intended.** Deleting an entry in a live state makes a genuine
document read as *forged* to the next embassy that checks it, and erases the
trail that would explain why. Revoke instead — that answers the lookup with a
reason the agent can read.

The same applies to duplicating: :guilabel:`Duplicate` always refuses. A clone
would inherit the holders, the fingerprints and the sealed attachment of a
different document while carrying a fresh reference, and the unique constraint
would not notice. Issue a new document.

"%s is revoked. Issue a new document rather than re-sealing this one"
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

Also intended. A withdrawn reference that suddenly carries a fresh marking is a
reference whose meaning changed after it left the building.

"Add at least one listed person to %s, otherwise nobody can open it"
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

``certify()`` refuses an entry with no holders, because the reference alone
never opens a document and there would be nothing to match against.

If the :guilabel:`Listed people` tab offers no :guilabel:`Add a line`, the entry
has :guilabel:`Listed people fixed` set — the producing module read the crew off
the document itself, and the list is the document's rather than the operator's.
Fix it in the producing module, or clear the flag in the shell if you know what
you are doing.

A document type cannot be deleted
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

*"This type is on N certified documents. Archive it instead, so those documents
keep saying what they are."*

Intended, and the message names the count. **Archive** it: the type disappears
from the pickers and from the :guilabel:`Stamp on generation` list, while the
documents already carrying it keep resolving — ``_get_by_code`` searches with
``active_test=False`` for exactly this reason.

The settings
------------

Ticking "Hide expired documents" changes nothing
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

Correct, and it is a bug in the settings page rather than in your
understanding. The parameter is shipped, the box saves, and **nothing in the
codebase reads it**. An expired document always reads as *authentic but out of
date*. See :doc:`../limits`.

The captcha never triggers
^^^^^^^^^^^^^^^^^^^^^^^^^^

``google_recaptcha`` is a soft dependency and is **silent twice over**: the
controller passes when the module is absent, and Odoo's own verifier passes when
no site key is configured. So an installed-but-unkeyed instance is
indistinguishable from one that never installed it.

Check for the key, not for the module:

.. code-block:: python

   >>> env["ir.config_parameter"].sudo().get_param("recaptcha_public_key")
   False

Empty means no widget is rendered and nothing is checked. Set the keys in
:menuselection:`Settings --> General Settings --> Integrations`.

If instead **every** lookup suddenly fails the captcha after an Odoo upgrade,
the verifier's signature has moved again — the controller handles two shapes and
would need a third. The log will carry ``captcha verification failed`` with a
traceback.

The attempt log has grown enormous
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

The daily cron *Verification: purge old attempt logs* is disabled, or the server
runs with ``max_cron_threads = 0``. Nothing warns you.

.. code-block:: python

   >>> env["dms.certificate.attempt"]._gc_attempts()
   148302

It deletes everything older than :guilabel:`Keep attempt logs for (days)` and
returns the count. Re-enable the cron afterwards, and remember the log is the
rate limit's counter as well as the audit trail — pruning inside the throttle
window resets somebody's budget.

Getting more detail
-------------------

**The server log.** Everything this addon wants you to know goes there with the
``dms_certify_portal:`` prefix:

.. code-block:: bash

   grep 'dms_certify_portal' /var/log/odoo/odoo.log

.. list-table::
   :header-rows: 1
   :widths: 14 86

   * - Level
     - What it means
   * - ``ERROR``
     - A redaction left something behind and the page was **not** served, or an
       unreadable sealed copy
   * - ``WARNING``
     - An address was throttled; or a portal language could not be activated
   * - ``INFO``
     - A document was issued; redaction fell back to searching by value; the
       attempt log was vacuumed; the pepper was generated

**The attempt log.** :menuselection:`Consular --> Reporting --> Verification
attempts` has the reference tried, the address, the user agent, the outcome and
the matched document — every hit, including the ones that never reached the
registry.

**The shell.**

.. code-block:: python

   >>> doc = env["dms.certificate"].search(
   ...     [("reference", "=", "ICS-2026-DKK-4KQ7-9B")])
   >>> doc.state, doc.public_state, doc.valid_until
   >>> doc.second_factor, doc.disclosure
   >>> doc.verify_url
   >>> doc.holder_ids.read(["name", "first_name", "date_of_birth"])
   >>> env["dms.certificate"]._match("ICS2026DKK4KQ79B", "4567")
   >>> Attempt = env["dms.certificate.attempt"]
   >>> Attempt.reference_attempts_left("ICS2026DKK4KQ79B")
   >>> Attempt.reference_lock_left("ICS2026DKK4KQ79B")
   >>> Attempt.is_throttled("203.0.113.9")

``_match`` returning two empty recordsets is the whole of what the public form
would have decided, without the rate limits in the way — the quickest way to
separate "the lookup is wrong" from "the lookup is being refused".

**The tests.** :doc:`../development/testing` lists what is covered and, just as
usefully, what is not.

See also
--------

* :doc:`deployment` — the check host, ``--proxy-mode``, nginx, the pepper
* :doc:`administration` — both limits, retention, the two groups
* :doc:`verification` — :ref:`verification-refusals`, with what each refusal
  deliberately withholds
* :doc:`sealing` — :ref:`sealing-redaction`, for the blank-page case
* :doc:`../limits` — the genuine limitations, as opposed to the surprises
