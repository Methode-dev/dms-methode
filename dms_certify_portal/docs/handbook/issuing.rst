Issuing
=======

For the module that produces the documents. |addon| does not produce any: it has
no upload screen and no "certify this file" wizard, because the people listed on
a document have to come from somewhere, and a hand-typed crew that disagrees with
the page is worse than no entry screen at all (:doc:`../limits`).

So registering a document is a few lines of Python in **your** module, called at
the moment you generate the file.

.. contents::
   :local:
   :depth: 2

Depend on it
------------

.. code-block:: python

   # my_module/__manifest__.py
   'depends': ['dms_certify_portal', 'my_other_dependency'],

That is the whole integration surface. You do not need ``dms_certify_host``
yourself — it is already a hard dependency of |addon|.

Declare the kinds of document you produce
-----------------------------------------

``dms.certificate.type`` is a **record, not a Selection**, and this addon ships
none of its own. What a document *is* belongs to whoever produces it, and a
generic fallback would only fill the registry — and the public page — with
*"Other"*. Version 19.0.5.0.0 went as far as deleting the four generic types the
module used to carry.

.. code-block:: xml

   <record id="certificate_type_visa_letter" model="dms.certificate.type">
       <field name="name">Visa letter</field>
       <field name="code">visa_letter</field>
       <field name="sequence">10</field>
       <!-- register one automatically the moment it is generated -->
       <field name="auto_stamp" eval="True"/>
   </record>

:guilabel:`Name` is translatable and an administrator may rename it freely.
:guilabel:`Code` is the stable key your module refers to and is unique across
the database — pick something namespaced enough that another producing module
will not collide with it.

:guilabel:`Stamp on generation` (``auto_stamp``) is a *hint from you* that an
administrator then owns: it appears in :menuselection:`Settings --> General
Settings --> Certified documents: defaults --> Stamp on generation` and they can
untick it. Ask for it rather than assuming it:

.. code-block:: python

   Type = self.env['dms.certificate.type']
   if 'visa_letter' in Type._auto_stamp_codes():
       ...  # register this one
   kind = Type._get_by_code('visa_letter')   # empty recordset if unknown

``_get_by_code`` searches with ``active_test=False``, so an archived type still
resolves — a document already in circulation has to keep being able to say what
it is.

.. tip::

   If the list of document kinds already exists somewhere in your module as
   Python, declaring the records from a ``post_init_hook`` instead of XML keeps
   one source of truth. ``_get_by_code`` is then the only thing you need at
   runtime. :doc:`../development/extending` has a worked recipe.

Register and seal in one call
-----------------------------

``issue()`` is the integration entry point. It creates the entry, measures where
everyone sits on the page, and seals it.

.. code-block:: python

   @api.model
   def issue(self, vals, holders=None, source=None, redaction_secrets=None)

.. code-block:: python

   import json

   entry = self.env['dms.certificate'].sudo().issue(
       {
           'type_id': self.env.ref(
               'my_module.certificate_type_visa_letter').id,
           'movement_date': self.travel_date,
           'company_id': self.company_id.id,
           'facts_json': json.dumps([
               # a label may be a plain string, or a mapping of language
               # to string — the portal is read in French by people this
               # module has never heard of
               {'label': {'en': "Vessel", 'fr': "Navire"},
                'value': self.vessel_id.name},
               {'label': {'en': "Port of call", 'fr': "Port d'escale"},
                'value': self.port_id.name},
           ]),
       },
       holders=[
           {
               'name': traveller.last_name,          # Surname, required
               'first_name': traveller.first_name,
               'date_of_birth': traveller.date_of_birth,
               'rank': traveller.function,
               'passport_number': traveller.passport_number,
           }
           for traveller in self.traveller_ids
       ],
       source=self,
       redaction_secrets={
           index: [traveller.seamans_book_number]
           for index, traveller in enumerate(self.traveller_ids)
           if traveller.seamans_book_number
       },
   )

   entry.reference     # print this beside the QR code
   entry.verify_url    # what the QR code encodes

Four arguments, and three of them have a catch.

``vals``
   Ordinary ``create`` values. ``type_id`` is **required** and has no default.
   Everything else — the second factor, the disclosure mode, the validity window,
   the reference prefix — defaults from the system parameters an administrator
   set, so leave them out unless this particular document genuinely differs.

``holders``
   A list of ``dms.certificate.holder`` value dicts. Only ``name`` (the surname)
   is required, but a holder with no ``passport_number`` and no ``date_of_birth``
   has **no hash and therefore cannot open the document**, and a certificate with
   no holders at all cannot be sealed — ``certify()`` refuses it, because nobody
   could open it.

   The passport fields are restricted to *Certification: Registrar*, which is why
   the call above goes through ``sudo()``. A producing module running as an
   ordinary user cannot write them.

``source``
   The recordset this entry stands for. Its ``_name`` and ``id`` are written with
   ``setdefault``, so an explicit ``res_model``/``res_id`` in ``vals`` still
   wins. This is what lets the back office navigate from the entry back to your
   record, and it is a loose reference rather than a ``Many2one`` because this
   addon must not know your models exist.

``redaction_secrets``
   ``{index: [strings]}``, **keyed by position in** ``holders`` — not by holder
   id, which you cannot know for records you are asking to be created. It is
   translated to ``{holder_id: [...]}`` internally.

.. warning::

   ``redaction_secrets`` is for strings printed on the page for that person that
   the **holder record does not already carry**. Surname, first name, rank,
   passport number and the date of birth in two formats are measured from the
   holder row automatically, so passing the passport numbers here as well is
   redundant.

   It is not a flat list, and it is not keyed by holder. A flat list gets you a
   ``TypeError`` at best and silently wrong redaction at worst.

.. todo::

   ``README.md``'s integration example calls
   ``issue(..., redaction_needles=self.traveller_ids.mapped('passport_number'))``
   and ``entry.stash_redaction(passport_numbers)``. **Neither keyword nor shape
   matches the code**: the keyword is ``redaction_secrets`` and takes
   ``{index: [strings]}``, and ``stash_redaction`` takes
   ``{holder_id: [strings]}``. Correct the README against this page, which was
   written from the signature.

Register now, seal later
------------------------

``issue()`` **seals**. For most workflows that is the wrong moment: the marking
is a judgement an operator makes by looking at the stamped page, and the form's
preview panel exists precisely so they can. So the usual shape is to create the
entry as a draft and let somebody press :guilabel:`Certify and watermark`.

.. code-block:: python

   Certificate = self.env['dms.certificate'].sudo()
   entry = Certificate.create({
       'type_id': kind.id,
       'movement_date': self.travel_date,
       'res_model': self._name,
       'res_id': self.id,
       'holders_locked': True,
       'holder_ids': [
           (0, 0, {
               'name': traveller.last_name,
               'first_name': traveller.first_name,
               'date_of_birth': traveller.date_of_birth,
               'rank': traveller.function,
               'passport_number': traveller.passport_number,
           })
           for traveller in self.traveller_ids
       ],
   })
   entry.stash_redaction()

**Do not skip the** ``stash_redaction()`` **call.** It is what measures where
each listed person appears on the source document, and it has to happen while
the document is the one those measurements describe. Without it, every
confirm-only lookup falls back to searching the page for the stored values —
which is weaker in a specific way (a surname that is also a word in the letter
body gets blanked too) and logs an ``INFO`` line nobody reads. The reasoning in
full is :ref:`sealing-redaction`.

``stash_redaction()`` returns ``False`` when there is nothing to measure, which
is the signal that ``_certify_source()`` found no bytes.

Two further flags worth setting from a producing module:

:guilabel:`Listed people fixed` (``holders_locked``)
   Set it when you read the crew **off the document itself**. The list is then
   the document's rather than the operator's, and the form stops offering
   :guilabel:`Add a line` or the delete handle. Without it the portal could
   answer for people the page does not name, or refuse somebody it does. Note it
   is a UI lock, not an ORM one — your own code can still write ``holder_ids``,
   which is exactly what it has to be able to do.

``facts_json``
   A JSON list of ``{label, value}``, printed under *Voyage*. JSON rather than a
   child model because the vocabulary of a port call belongs to you; a child
   model here would mean this addon having opinions about ships. Parsed
   defensively, so a malformed value yields no facts rather than a 500 on a
   public page.

.. _issuing-override-points:

The override points
-------------------

.. list-table::
   :header-rows: 1
   :widths: 26 36 38

   * - Method
     - Why you would override it
     - What to keep true
   * - ``_certify_source()``
     - **The main one.** Point the seal at your own storage instead of an
       attachment — the operations bridge returns the ``dms.file`` its
       generation wizard produced.
     - Return ``(filename, bytes)``, or ``(None, None)``. It is called from the
       seal, the measurement, **every confirm-only lookup** and the form
       preview, so it must be cheap and free of side effects.
   * - ``_generate_reference(place_code=None)``
     - Change the shape of the printed reference.
     - Keep at least thirty bits of entropy, keep the alphabet transcribable,
       and keep it non-sequential. If you change the alphabet you must change
       the public page's sentence about ``I``, ``L``, ``O`` and ``U``.
   * - ``_get_public_values(holder=None)``
     - Add a fact to the result page that does not fit ``facts_json``.
     - Call ``super()`` and update the dict. **Return plain data** — strings,
       booleans, dates, and lists of dicts of those. Never a recordset.
   * - ``_hide_expired()``
     - — **this method does not exist.**
     - ``README.md`` lists it as a fourth override point. There is no such
       method anywhere in the addon, and the ``hide_expired`` parameter it would
       have read is shipped but never consulted. See :doc:`../limits`.

.. admonition:: ``_get_public_values`` is the security boundary
   :class: important

   The public templates receive that dict and nothing else. Hand a QWeb template
   a record and every relation on it becomes a one-dot walk —
   ``doc.issuer_id.partner_id.email``, ``doc.company_id.vat``,
   ``doc.message_ids`` and the whole thread with whatever an operator typed into
   it. Nothing stops that walk, because QWeb is not a sandbox; the only defence
   is that there is nothing to walk.

   It is a *whitelist* rather than a blacklist for the same reason: a field added
   to the model next year is invisible to the portal until somebody deliberately
   adds it here.

Other methods you could technically reach — ``_seal_spec()``,
``_store_artifact()``, ``_public_bytes()`` — are not on this list. They are
internal, and overriding them is how a redaction bug gets introduced.
:doc:`../development/extending` tiers them explicitly.

Revocation
----------

.. code-block:: python

   entry.action_revoke(reason="Superseded by %s" % new_entry.reference)

Irreversible, and a pure state change — no re-stamp. Re-sealing with a ``VOID``
watermark would be pointless: the portal already refuses to show the page or
offer the download once the state is ``revoked``, so there is no public copy left
for a watermark to protect, and the paper already in somebody's hand cannot be
changed either way. What changes is what a lookup *says* now.

The reason is not paperwork. It is printed under the public refusal notice, so
the agent reading it learns why a genuine-looking paper must be turned away;
that is why the back-office wizard insists on one and defaults it to something
plausible rather than leaving it blank. Called from Python with no reason at all
you get *"No reason recorded."*, which is what a refusal notice will then say.

.. note::

   Prefer revoking to deleting, always. An ``@api.ondelete`` guard refuses to
   delete an entry in a live state precisely because deleting one makes a genuine
   document read as **forged** to the next embassy that checks it, and erases the
   trail that would explain why.

What you get back
-----------------

.. list-table::
   :widths: 30 70

   * - ``entry.reference``
     - Print this beside the QR code. Immutable once issued.
   * - ``entry.verify_url``
     - ``{public base}/d/{reference}`` — what the QR encodes. Note the path:
       ``/d/…``, never ``/_check/d/…``. The ``/_check`` prefix is internal and
       must never be emitted.
   * - ``entry.source_hash``
     - The fingerprint printed on the page, of the document **before** sealing.
   * - ``entry.sealed_attachment_id``
     - The sealed copy, owned by the entry. Deliberately **not** filed back into
       your DMS folder — the folder shows the document as produced, and a folder
       filling with near-identical sealed variants is a folder nobody can read.

.. important::

   ``verify_url`` is built from
   ``dms_certify_portal.public_base_url``, or derived from ``web.base.url`` with
   ``check.`` prefixed when that parameter is empty. **It goes on paper.** Set it
   before you issue anything in anger — a document already in an embassy's file
   cannot be re-pointed. See :ref:`deployment-check-host`.

See also
--------

* :doc:`concepts` — what a reference, a second factor and a disclosure mode are
* :doc:`sealing` — what the stamp draws, and :ref:`sealing-redaction`
* :doc:`administration` — the defaults your ``vals`` inherit
* :doc:`../reference/models/dms_certificate` — :ref:```issue()`` <dms_certificate-issue>`,
  :ref:```stash_redaction()`` <dms_certificate-stash_redaction>`,
  :ref:```_certify_source()`` <dms_certificate-certify_source>` and
  :ref:```_get_public_values()`` <dms_certificate-get_public_values>` in full
* :doc:`../reference/models/dms_certificate_holder` — the three hashes and the
  measured boxes
* :doc:`../reference/models/dms_certificate_type` — why the type is a record
* :doc:`../development/extending` — stability tiers and more recipes
