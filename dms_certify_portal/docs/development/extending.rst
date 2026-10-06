Extending it
============

For building the **module that produces the documents** — a separate addon that
depends on this one — rather than changing this one. If you are working inside
this repository, see :doc:`contributing`.

The short version: there is no plugin registry and no event bus. Extension is
ordinary Odoo — ``_inherit`` a model, override a method, ship a data record — and
the useful part of this page is *which* methods are worth overriding, which are
not what they look like, and which of this addon's shapes you must not break from
the outside.

Read :doc:`architecture` first. Most of what follows only makes sense once you
know why the public templates receive a dict rather than a record.

.. contents::
   :local:
   :depth: 2

Depending on it
---------------

.. code-block:: python

   # my_addon/__manifest__.py
   {
       "name": "My Documents",
       "version": "19.0.1.0.0",
       "depends": ["dms_certify_portal"],
       ...
   }

That transitively gives you ``base_setup``, ``web``, ``mail`` and
``dms_certify_host``, so you do not need to list them again. It does **not** give
you ``website``, and you should think twice before adding it — see
:ref:`limits-no-website` for what this addon gains by going without.

Both addons must be on the same addons path, and |addon| needs its prerequisite
reachable at server start. See :doc:`../limits` and
:ref:`deployment-check-host` — a producing module that works perfectly in
development and prints QR codes that 404 in production has almost always skipped
that step.

.. _extending-stability:

What is safe to rely on
-----------------------

Nothing here is versioned independently of the addon, but the three tiers differ
a lot in how likely they are to move under you.

.. list-table::
   :header-rows: 1
   :widths: 18 40 42

   * - Tier
     - What
     - Notes
   * - **Stable**
     - The model names (``dms.certificate``, ``dms.certificate.holder``,
       ``dms.certificate.type``, ``dms.certificate.attempt``); the field names
       on them; ``issue()`` and ``stash_redaction()``; the two security groups
       ``group_certify_user`` / ``group_certify_manager``; the
       ``dms_certify_portal.*`` parameter keys; the ``dms.certificate.type``
       ``code`` as a lookup key via ``_get_by_code()``
     - Renaming any of these would break this addon's own views, data and
       migrations, so they do not move casually. The reference *shape* is
       separate — see the warning below
   * - **Semi-stable**
     - ``_certify_source()``, ``_generate_reference()``,
       ``_get_public_values()`` — the three documented override points —
       plus ``_seal_spec()`` and ``_store_artifact()``
     - Designed to be overridden and documented as such, but their
       **signatures** may gain arguments. ``super()`` with ``*args, **kwargs``
       where the base allows it, and never change the *return shape*
   * - **Internal**
     - ``_match()``, ``_public_bytes()``, ``_apply_seal()``,
       ``_survives()``, ``_boxes()``, ``_keyed_hash()``, every ``_compute_*``,
       the controller's ``_fail`` / ``_session_document`` / ``_chrome``, and
       everything in ``tools/seal.py`` except the public functions
     - These are the security path. Override only if you are prepared to
       re-read them on every upgrade, and read :doc:`contributing` first for
       what each of them is holding up

.. warning::

   The **printed reference shape** is not an API, it is paper. Documents stay in
   circulation for months and an embassy's file keeps whatever was printed on
   it. Changing ``_generate_reference`` changes only what *new* documents look
   like; old references still have to match, which they will, because matching
   normalises both sides. What you cannot do is change what the alphabet *is*
   without also changing the sentence on the public page that tells an agent
   which four letters are never used.

The three override points
-------------------------

There are three. The README lists four; the fourth does not exist — see
`What is not extensible`_.

.. _extending-certify-source:

``_certify_source()`` — where the bytes come from
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

**The main one.** Returns ``(filename, bytes)`` of the document to seal, or
``(None, None)``. The default reads ``source_attachment_id`` under ``sudo``,
which is what lets this addon stand alone with no producing module installed.

.. code-block:: python

   class DmsCertificate(models.Model):
       _inherit = "dms.certificate"

       def _certify_source(self):
           self.ensure_one()
           if self.res_model == "my.document":
               document = self.env["my.document"].sudo().browse(self.res_id)
               if document.exists() and document.pdf_file:
                   return document.display_name + ".pdf", document.pdf_file
           return super()._certify_source()

Three constraints on an override, all of which come from where it is called
from:

* **It must be cheap and side-effect free.** It is called from
  ``_apply_seal()``, ``stash_redaction()``, ``_public_bytes()`` *and*
  ``_compute_preview_pdf()`` — and the last of those runs on every read of the
  certificate form. An override that re-renders a report here turns opening a
  record into a render.
* **It must be stable.** ``stash_redaction()`` measures positions against what
  this returns and stores the fingerprint it measured against. If a later call
  returns different bytes — a report re-rendered with today's date in a footer,
  say — every measurement goes stale at once and the portal falls back to
  redacting by value on every lookup, logging at ``INFO`` where nobody will see
  it. See :doc:`../limits`.
* **It must never modify the source.** The printed fingerprint is of these
  bytes. Change them and the value on the paper stops describing the document.

``super()`` on the way out rather than guarding the whole method, so a
certificate created from the back office with a plain attachment still works.

.. _extending-generate-reference:

``_generate_reference(place_code=None)`` — what gets printed
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

``@api.model``. The default is ``PREFIX-YYYY-PPP-XXXX-XX`` — the configured
prefix, the year, three characters of place code, then thirty random bits.

The *place code* is the reason this is an override point at all: this addon has
no idea what a port is. A producing module that knows the UN/LOCODE can pass it
straight through.

.. code-block:: python

   @api.model
   def _generate_reference(self, place_code=None):
       return super()._generate_reference(
           place_code=place_code or self.env.context.get("my_port_code"))

Or, more usefully, set it at create time without overriding anything:

.. code-block:: python

   Certificate = self.env["dms.certificate"]
   entry = Certificate.issue({
       "type_id": doc_type.id,
       "reference": Certificate._generate_reference(place_code="DKK"),
       ...
   }, holders=[...])

.. important::

   If you replace the body rather than delegating, keep **at least thirty bits
   of entropy** and keep the alphabet transcribable. A sequential component
   leaks volume — anyone holding two documents can read off how many were issued
   between them — and makes the space walkable, which reduces the second check
   to the only secret standing between a guesser and a document. ``secrets``,
   not ``random``: this is a credential.

.. _extending-public-values:

``_get_public_values(holder=None)`` — what the page says
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

Call ``super()`` and update the dict.

.. code-block:: python

   def _get_public_values(self, holder=None):
       values = super()._get_public_values(holder=holder)
       values["port_of_call"] = self.my_document_id.port_id.name or ""
       values["vessel"] = self.my_document_id.vessel_id.name or ""
       return values

.. admonition:: Keep returning plain data
   :class: important

   Strings, booleans, dates, integers, and lists of dicts of those. Never a
   record, never a recordset, never an id you expect the template to browse.

   This is the one invariant in the addon that an *outside* module can break on
   its own, and it will not fail loudly when you do. ``values["vessel"] =
   self.my_document_id.vessel_id`` renders something plausible on the page and
   hands the template a record to walk from. The next person to edit a template
   has ``vessel.message_ids`` within reach, on a page an anonymous caller is
   looking at. See :doc:`architecture`.

   ``''`` rather than ``False`` for an absent string, because the templates
   print what they are given.

Note what ``super()`` already did with the two conditional keys, and do not undo
it: ``revoke_reason`` is ``False`` unless the public state is ``revoked``, and
``crew`` is ``[]`` under confirm-only disclosure. Adding your own copy of either
reinstates the leak those lines exist to close.

Adding a fact without overriding anything
-----------------------------------------

For the common case — vessel, berth, ETA, a flight number — there is no override
point, because there does not need to be one. ``facts_json`` is a JSON list of
``{"label": …, "value": …}`` that the public page prints under *Voyage*, and
``issue()`` takes it like any other value.

.. code-block:: python

   import json

   entry = self.env["dms.certificate"].issue({
       "type_id": doc_type.id,
       "movement_date": call.date,
       "facts_json": json.dumps([
           {"label": {"en": "Vessel", "fr": "Navire"}, "value": call.vessel_name},
           {"label": {"en": "Port", "fr": "Port"}, "value": call.port_name},
           {"label": "IMO", "value": call.imo},
       ]),
   }, holders=[...], source=call)

A label may be a plain string or a ``{lang: string}`` mapping, resolved against
the reader's language with a chain of fallbacks that never raises. That shape is
the point: the vocabulary of a port call belongs to your module, but the page is
read in French by people your module knows about and this one does not, so the
vocabulary has to be able to arrive in more than one language.

A malformed ``facts_json`` yields no facts rather than a 500 on a public page.
That is defensive, not permissive — your module should not be shipping invalid
JSON, and nothing will tell you if it does.

Issuing, with the real signature
--------------------------------

.. code-block:: python

   @api.model
   def issue(self, vals, holders=None, source=None, redaction_secrets=None)

.. code-block:: python

   entry = self.env["dms.certificate"].issue(
       {
           "type_id": self.env.ref("my_addon.certify_type_loi").id,
           "movement_date": self.call_date,
           "second_factor": "ppt4",
           "disclosure": "confirm",
       },
       holders=[
           {
               "name": member.surname,
               "first_name": member.first_name,
               "rank": member.rank,
               "date_of_birth": member.birthday,
               "passport_number": member.passport_number,
           }
           for member in self.crew_ids
       ],
       source=self,
       redaction_secrets={
           index: [member.passport_number]
           for index, member in enumerate(self.crew_ids)
       },
   )

Two things about ``redaction_secrets`` that are easy to get wrong:

* It is keyed **by position in** *holders*, not by id — the caller cannot know
  the ids of records it is asking to be created. ``issue()`` translates it to
  ``{holder_id: [...]}`` before calling ``stash_redaction()``.
* It is for strings printed on the page **on top of** what the holder record
  itself carries. The surname, first name, rank, passport number and date of
  birth already come from the holder values. Pass the passport number here as
  well when your module does *not* store it on the holder — that is the case the
  parameter exists for, and the hashed leak check is what later lets the page be
  searched for a number nobody kept.

.. warning::

   ``issue()`` **seals**. For the usual desk flow — register now, look at the
   stamped page, then choose the marking — create the record directly and call
   ``stash_redaction()`` yourself:

   .. code-block:: python

      entry = self.env["dms.certificate"].create({..., "holder_ids": [...]})
      entry.stash_redaction({
          holder.id: [holder_passport[holder.id]]
          for holder in entry.holder_ids
      })
      # ... later, from the form's Certify button, or:
      entry.certify()

   **Do not skip ``stash_redaction()``.** Without it no holder has measured
   positions, so every confirm-only lookup falls back to searching the page for
   the stored values — which matches a surname wherever it appears, including in
   the body of the letter, and cannot find a passport number that was never
   stored at all. See :ref:`sealing-redaction` and :doc:`../handbook/issuing`.

Registering your document types
-------------------------------

As data, with a predictable external id:

.. code-block:: xml

   <record id="certify_type_loi" model="dms.certificate.type">
       <field name="name">Letter of Invitation</field>
       <field name="code">loi</field>
       <field name="sequence">10</field>
   </record>

``code`` is the stable key your module refers to; ``name`` is translatable and an
administrator may rename it freely. Resolve a code rather than an external id
when the record may have been archived:

.. code-block:: python

   doc_type = self.env["dms.certificate.type"]._get_by_code("loi")

``_get_by_code`` searches with ``active_test=False``, so an archived type still
resolves — which is deliberate: a type withdrawn from the picker must not break
the lookup of documents already issued under it.

When the list already exists in your module
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

If your addon already enumerates its documents somewhere — a ``_DOCUMENT_DEFS``
table, a Selection — do not hand-maintain a parallel XML file. Create them from
your own ``post_init_hook``, idempotently:

.. code-block:: python

   def post_init_hook(env):
       Type = env["dms.certificate.type"]
       for sequence, (code, label) in enumerate(MY_DOCUMENTS.items(), start=1):
           if not Type._get_by_code(code):
               Type.create({"code": code, "name": label,
                            "sequence": sequence * 10})

Guard on ``_get_by_code`` rather than on a bare ``search``, and never ``write``
over an existing record: ``code`` is ``UNIQUE``, ``auto_stamp`` is an
administrator's choice, and ``name`` may have been renamed on purpose.

.. note::

   ``auto_stamp`` on a type means *"when a producing module generates a document
   of this kind, register it straight away, as a draft"*. Nothing in this addon
   acts on it — reading ``_auto_stamp_codes()`` and deciding what to do about it
   is **your** module's job. Shipping a type with ``auto_stamp`` set and then
   never reading the flag is a settings box that does nothing, which is the one
   failure mode this addon has already made once (see :doc:`../limits`).

Reusing the stamp on its own
----------------------------

``tools/seal.py`` imports no Odoo. Nothing stops you using it directly for
something that is not a certificate at all:

.. code-block:: python

   from odoo.addons.dms_certify_portal.tools import seal

   digest = seal.fingerprint(pdf_bytes)
   png = seal.render_page(pdf_bytes, page_number=0, dpi=200)
   clean = seal.redact(pdf_bytes, ["MB1234567", "Shwe Moung"])
   words = seal.text_tokens(clean)

``redact`` / ``redact_boxes`` are a real redaction — ``apply_redactions`` drops
the glyphs out of the content stream rather than drawing a rectangle over them.
``render_page`` defaults to 110 dpi, which is *not* enough to decode an 18 mm QR
code; pass 200 if the output has to be scannable.

.. tip::

   If you are rasterising for a public page, copy the pattern rather than the
   call: do the redaction, then ``text_tokens`` the result and assert that what
   should be gone is gone, and refuse to serve anything when it is not. The
   geometry is the easy half. See :doc:`../reference/tools/seal`.

What is not extensible
----------------------

``_hide_expired()`` does not exist
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

.. warning::

   The README's extension-points table lists a fourth row,
   ``_hide_expired()`` — *"decide whether an expired document reads as expired or
   as not found"*. **There is no such method anywhere in this addon.** Overriding
   it does nothing at all, silently, and leaves you believing an expired document
   is being hidden when it is not.

   The ``dms_certify_portal.hide_expired`` parameter and the
   ``certify_hide_expired`` settings field exist and are stored; nothing reads
   either. An expired document always reads as "authentic but out of date". See
   :doc:`../limits` for the whole shape of it.

   If you need the other behaviour today, the honest route is to revoke the
   document with a reason, which the portal does act on.

.. todo::

   ``docs/index.rst`` and ``docs/development/index.rst`` both say "four
   documented override points", following the README. There are three. Which
   way should it be resolved — implement ``_hide_expired()`` and make the count
   right, or correct the README and the two index pages?

Adding a second-factor mode
^^^^^^^^^^^^^^^^^^^^^^^^^^^

Not from the outside. ``second_factor`` is a Selection, so ``selection_add``
works, and the result is a document **nobody can open** — quietly.

``_stored_factor_hash`` maps the three known values onto the three stored hash
columns and returns ``''`` for anything else; ``_match`` requires a non-empty
stored hash before it will compare, so every lookup falls through to "no match"
and the agent is told the same thing they would be told about a wrong passport.

A fourth mode is a fourth hash column, a branch in ``_recompute_credentials``, a
branch in ``_submitted_factor_hash``, a line in ``_stored_factor_hash``, a field
on the holder with the same ``groups=``, and copy on the public form explaining
what to type. That is a change to this addon, not an extension of it — see
:doc:`contributing`.

It fails closed, which is the correct direction for a mistake of this kind.

Adding a disclosure mode
^^^^^^^^^^^^^^^^^^^^^^^^

.. warning::

   This one fails **open**, and that is why it has its own warning.

   ``_public_bytes`` branches on ``if self.disclosure != 'confirm'`` and serves
   the stored sealed copy — the whole document, every crew line on it.
   ``_get_public_values`` computes ``confirm_only = self.disclosure ==
   'confirm'`` and lists the full crew when it is false.

   So a ``selection_add`` of, say, ``redacted_plus`` produces a document that
   behaves exactly like ``full``: the complete page and the complete crew list
   handed to whoever opened it. Nothing warns you, no test covers your new
   value, and the page looks like it is working.

   If a third mode is genuinely needed, it belongs in this addon, with the
   branches turned into an explicit mapping so that an unknown value cannot
   mean *full*.

The public ACL
^^^^^^^^^^^^^^

There is none, and adding one from your own module is the single most damaging
thing this page could tell you to do. The comment in ``security/ir_rule.xml``
says why: an ``ir.model.access`` row for ``base.group_public`` also opens
``/web/dataset/call_kw``, which bypasses both rate limits, the session token and
the second check entirely.

If something you are building seems to need one, the fix is in a controller —
yours or this one's. See :doc:`contributing`.

The refusal wording
^^^^^^^^^^^^^^^^^^^

All of it lives in the ``verify_form`` template, keyed off ``error_code``, so
there is exactly one place it can diverge. You can inherit the template and
change the words. What you must not do is make the refusals **differ by cause** —
``no_match`` deliberately covers both "no such reference" and "that reference
exists but the second check is wrong", and splitting them turns the form into an
enumeration oracle. See :ref:`verification-refusals`.

Testing against it
------------------

There is no shared fixture module to import — this addon's tests build their own
in each class. What is importable and worth reusing is the PDF builder and the
crew, out of ``tests/test_certificate.py``:

.. code-block:: python

   from odoo.addons.dms_certify_portal.tests.test_certificate import CREW, build_pdf

``build_pdf()`` returns a one-page PDF with the crew lines on it, which is what
makes the redaction assertions possible: seal it, redact it, re-open the result
and read its text.

.. important::

   If you test anything through the portal's own routes, **every request has to
   carry the check host as its** ``Host`` **header**, or the route does not
   exist. This is the most common way a new portal test fails for a reason that
   has nothing to do with what it was testing. See :doc:`testing`.

See also
--------

* :doc:`architecture` — why the pieces are shaped this way
* :doc:`contributing` — changing this addon rather than extending it, and the
  invariants an override must not break
* :doc:`testing` — the suite, and the check-host trap
* :doc:`../handbook/issuing` — the same ground as a procedure, and
  :ref:`issuing-override-points`
* :doc:`../reference/models/dms_certificate` — every field and method, with the
  reasoning
* :doc:`../reference/tools/seal` — the stamp, function by function
* :doc:`../reference/index` — everything else
* :doc:`../limits` — what the addon deliberately does not do
