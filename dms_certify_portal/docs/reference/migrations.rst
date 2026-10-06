migrations
==========

Source: :ghsrc:`migrations`

Three upgrade scripts, all of them ``post-migrate``. Each one exists because
something it needs — a loaded data file, a model that only comes into being with
that version — is not available to a data file or to a hook.

.. list-table::
   :header-rows: 1
   :widths: 16 12 72

   * - Version
     - Phase
     - What it does
   * - ``19.0.3.0.0``
     - post
     - Runs ``activate_portal_languages()`` on a database that already had the
       module, because ``post_init_hook`` only fires on install
   * - ``19.0.4.0.0``
     - post
     - Maps the retired ``document_type`` selection column onto
       :doc:`models/dms_certificate_type` records, and logs the codes it could
       not resolve
   * - ``19.0.5.0.0``
     - post
     - Deletes the four generic document types this module used to ship, where
       nothing uses them; keeps and logs any that are still referenced

There is no ``pre-migrate`` and no ``end-`` script in this addon. The manifest
is at ``19.0.5.0.0``, so a database on 2.x or earlier crosses all three in
order.

.. note::

   The repository's history begins with a single commit that already contains
   all three scripts, so what changed in versions before ``19.0.3.0.0`` is not
   recorded anywhere in the repository. :doc:`../changelog` says the same thing
   rather than reconstructing it.

Why all three are post-migrate
------------------------------

Worth stating once, because it is the transferable part. An Odoo upgrade runs, in
order:

.. code-block:: text

   pre-migrate       the old schema, the old data, nothing new loaded yet
   schema update     columns added/altered; new stored fields computed
   data files        the manifest's `data` list is re-read and loaded
   post-migrate      everything new exists and is loaded

``19.0.4.0.0`` has to resolve a ``dms.certificate.type`` record per old
selection value. Those records come from a data file — a producing module's, or
this module's own at the time — so they do not exist until the loader has run.
A ``pre-migrate`` script would find none of them and map nothing.

``19.0.3.0.0`` needs the installed-modules state to be current before it decides
which ``res.lang`` variants to activate, and ``19.0.5.0.0`` has to look at the
types *after* the loader has had its last chance to re-create them. Nothing here
wants the old schema, so nothing here is a pre-migrate.

19.0.3.0.0 — the language step, again
-------------------------------------

.. code-block:: python

   from odoo.addons.dms_certify_portal.hooks import activate_portal_languages

   def migrate(cr, version):
       activate_portal_languages(api.Environment(cr, SUPERUSER_ID, {}))

Six lines of substance, and the whole reason for them is that Odoo has
``pre_init`` / ``post_init`` / ``uninstall`` manifest hooks and **no
post-migrate hook**. ``post_init_hook`` fires on install and never again, so a
database that had this module before the portal was translated never ran the
step: the switcher on the public page lists only active languages the portal has
copy for, so it would show one button and the French catalogue would sit in the
file unused.

The function is imported from :doc:`hooks` rather than copied, so there is one
definition of *"which languages does the portal offer"* and the install path and
the upgrade path cannot drift apart. It is safe to re-run — it skips any
language already active — which is what makes calling it from a migration
reasonable at all.

The pepper half of ``post_init_hook`` is deliberately **not** re-run here. A
database that already has the module either has the key, or never had it and
needs a reinstall or a restore;
:py:meth:`_keyed_hash() <odoo.addons.dms_certify_portal.models.dms_certificate_holder.DmsCertificateHolder._keyed_hash>`
says so explicitly rather than minting a new one and invalidating every stored
hash. See
:ref:`PASSPORT_KEY_PARAM <dms_certificate_holder-PASSPORT_KEY_PARAM>`.

19.0.4.0.0 — a selection becomes a model
----------------------------------------

``document_type`` used to be a ``Selection`` on the certificate. It became
:doc:`models/dms_certificate_type`, a model, so that a producing module could
add its own kinds of document as data instead of patching a selection list, and
so that per-kind choices — :guilabel:`Stamp on generation` first among them —
had a record to live on.

The script has three parts, and each is a decision.

**It guards on the column still existing.**

.. code-block:: python

   SELECT 1 FROM information_schema.columns
    WHERE table_name = 'dms_certificate' AND column_name = 'document_type'

Odoo leaves a retired field's column in place rather than dropping it, which is
what makes the old values still available to read. The guard is what lets the
script be a silent no-op on a database that never had the column — a fresh
install that crosses the version, for instance.

**It reads the old column, not the new one.**

   *Not "where type_id is null": adding a required column makes Odoo fill every
   existing row with the field's default* **before** *this script runs, so by now
   they all say "Other". The old column is the only record of what they actually
   were.*

This is the part worth remembering. The schema-update phase has already run by
the time a post-migrate script starts, so a newly added required column is not
empty and waiting to be filled — it is uniformly wrong. Selecting on
``type_id IS NULL`` would find nothing and the script would appear to succeed.

**An unresolvable code is logged, not guessed.** ``_get_by_code()`` returns an
empty recordset for a code this module knows nothing about, and those rows are
counted as ``orphaned`` and left alone:

   *A code this module knows nothing about. The producing module that owns that
   vocabulary declares its types when it loads, which happens after this, and
   picks these up then.*

So the script maps what it can, and the ``INFO`` line tells the reader how many
rows are waiting on somebody else's data file rather than silently filing them
under a placeholder type.

.. note::

   The update is raw SQL —
   ``UPDATE dms_certificate SET type_id = %s WHERE id = %s`` — rather than an
   ORM ``write()``. Raw SQL on a few thousand rows avoids the ORM's per-record
   overhead and, more to the point, avoids re-triggering constraints and
   tracking on records that are only being repaired.

.. todo::

   :py:attr:`type_code <odoo.addons.dms_certify_portal.models.dms_certificate.DmsCertificate.type_code>`
   is ``related="type_id.code", store=True``. A raw SQL ``UPDATE`` of
   ``type_id`` does not recompute it, and the schema-update phase has already
   computed it from whatever ``type_id`` held at that point. Does a database
   that crossed ``19.0.4.0.0`` end up with ``type_code`` out of step with
   ``type_id``, and if so should this script finish with an explicit
   ``_recompute_field`` or ``flush`` on ``type_code``? The repository has a
   single initial commit, so it is not possible to tell from history whether
   ``type_code`` even existed at that version.

.. note::

   The script reflects the module as it was at ``19.0.4.0.0``, when generic
   types were shipped and a certificate could fall back to *Other*. Today
   :py:attr:`type_id <odoo.addons.dms_certify_portal.models.dms_certificate.DmsCertificate.type_id>`
   has **no default** and this module ships no types at all — which is what
   ``19.0.5.0.0`` cleaned up. The script is unchanged and does not need to be:
   the ``information_schema`` guard makes it inert on any database that is past
   that point.

19.0.5.0.0 — removing the generic types
---------------------------------------

``RETIRED_CODES = ('visa', 'certificate', 'attestation', 'other')``.

These four were carried straight across from the selection that preceded the
model, and they were never documents anybody issues — they were *categories*.
Their only visible effect was to fill the :guilabel:`Stamp on generation` list
in :menuselection:`Settings --> General Settings` with entries corresponding to
nothing, sitting next to the real documents a producing module had declared.
Deleting them is what makes
:py:attr:`type_id <odoo.addons.dms_certify_portal.models.dms_certificate.DmsCertificate.type_id>`
able to have no default: there is no longer a generic answer to fall back on, so
what a document *is* has to come from whoever produced it.

**A type in use is kept, and said so out loud.**

.. code-block:: text

   for each retired code, searched with active_test=False:
       any certificate pointing at it?   ->  kept,    log the code
       none?                             ->  dropped, log the code

The docstring says why:

   *A type that is actually in use is left alone: whatever it labels is on a page
   somewhere, and the verification page has to keep being able to say what it
   is.*

Two details follow from that:

* The ``kept`` branch logs *"rename or archive them by hand"* rather than
  attempting it. Renaming a type changes what the public page prints for every
  document already carrying it, which is a judgement call about documents in an
  embassy's file, not something a migration should decide.
* The check is the same one
  :py:meth:`_unlink_except_used() <odoo.addons.dms_certify_portal.models.dms_certificate_type.DmsCertificateType._unlink_except_used>`
  makes, so the migration never fights the model's own guard — it just never
  calls ``unlink()`` on anything the guard would refuse. Duplicating the
  condition is cheaper than catching the ``UserError`` and having to work out
  which record raised it.

``active_test=False`` on both searches, because an archived generic type is
exactly as much clutter in the settings list as an active one, and an archived
type that is still referenced still has to be kept.

Conventions for a new script
----------------------------

* Decide pre- versus post-migrate by what the script needs to *read*: the old
  schema and old data means pre, anything the data loader creates means post.
* Guard on the thing you are migrating still existing, as ``19.0.4.0.0`` does
  with ``information_schema``. A migration that assumes its starting state runs
  exactly once, in one direction, on one database.
* Log counts at ``INFO``, with the module name as a prefix, and name what a
  human has to finish by hand. All three scripts do.
* Return early when there is nothing to do, so an upgrade log that says nothing
  means nothing happened.
* Import shared logic from :doc:`hooks` or from a model rather than copying it,
  as ``19.0.3.0.0`` does.

See also
--------

* :doc:`hooks` — ``activate_portal_languages()``, and why install and upgrade
  have to share it
* :doc:`models/dms_certificate_type` — the model the 4.0.0 step maps onto, and
  the unlink guard the 5.0.0 step respects
* :doc:`models/dms_certificate` — ``type_id`` with no default, and ``type_code``
* :doc:`data/ir_config_parameter` — ``noupdate="1"``, and why a migration is the
  only way to change a shipped parameter on a live database
* :doc:`../changelog` — the same three versions, read as release notes
* :doc:`../installation` — upgrading, and that an upgrade runs these scripts
