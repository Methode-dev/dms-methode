dms_certificate_views
=====================

**Model:** :doc:`dms.certificate <../models/dms_certificate>`

Source: :ghsrc:`views/dms_certificate_views.xml`. Three views and one action, all
defined from scratch — nothing here inherits.

This is the issuing screen. Its shape carries one argument: the settings are on
the left and **the page they produce is on the right**, because the marking is
the one thing chosen per document, and it is chosen by looking at the result
rather than at a description of it. Everything else about the seal is house
style and lives in :doc:`res_config_settings_views`.

.. contents::
   :local:
   :depth: 2

.. _view_dms_certificate_form:

``view_dms_certificate_form``
-----------------------------

.. code-block:: text

   form "Certified document"
   │
   ├── header ──────────────────────────────────────────────────────────────
   │     [Certify and watermark]   btn-primary    state == 'draft'
   │     [Re-stamp document]                      state in certified/delivered
   │     [Send to embassy]         btn-primary    state == 'certified'
   │     [Download stamped PDF]                   state != 'draft'
   │     [Open as embassy]                        state != 'draft'
   │     [Revoke certificate]      btn-secondary  state in certified/delivered
   │     state                     statusbar      draft · certified · delivered
   │
   ├── sheet ───────────────────────────────────────────────────────────────
   │     oe_button_box
   │       (fa-search) Lookups   verify_count   statinfo, disabled="1"
   │       (fa-users)  Listed    holder_count   statinfo, disabled="1"
   │
   │     oe_title
   │       reference  (h1, readonly)
   │       public_state  (badge: valid / expired / revoked / unpublished)
   │
   │     group  "Document"            │  group  "Marking"
   │       type_id                    │    seal_marking
   │       movement_date              │    seal_text  (readonly unless custom)
   │       validity_days              │
   │       valid_until   (readonly)   │
   │       company_id    (multi-co)   │
   │
   │     group  "How it opens"
   │       second_factor · disclosure │  notify_on_lookup
   │     note  "The reference on its own never opens a document…"
   │
   │     notebook
   │       ├── "Listed people"        name="holders"
   │       ├── "Issued certificate"   name="issued"   invisible state == 'draft'
   │       ├── "Verification log"     name="lookups"
   │       ├── "Files"                name="files"    groups="base.group_no_one"
   │       └── "Source record"        name="source"   invisible not res_model
   │
   │     group  "Revocation"          invisible state != 'revoked'
   │
   │     <chatter/>                   ←  inside the sheet, at its foot
   │
   └── div.o_certify_preview.o_certify_preview_aside   ←  OUTSIDE the sheet
         h3 "Stamped output"
         preview_pdf   widget="pdf_viewer"  readonly
         div.o_certify_preview_empty        invisible preview_pdf
         caption  "Rendered from the document itself with the marking
                   currently selected. What you see is what the QR resolves to."

Header
^^^^^^

``action_certify`` is bound twice, under two labels: :guilabel:`Certify and
watermark` on a draft and :guilabel:`Re-stamp document` once there is something
to re-stamp. Same method, different sentence — the second one has to say that it
is overwriting a file, and a ``string`` attribute cannot be made conditional.

:guilabel:`Revoke certificate` is the only ``type="action"`` button, bound to
``%(action_dms_certificate_revoke)d`` with an explicit
``context="{'active_model': 'dms.certificate', 'active_id': id}"``. This is why
the manifest loads :doc:`dms_certificate_revoke_views` **before** this file: the
xmlid has to resolve at load time.

The status bar shows ``draft,certified,delivered`` and deliberately omits
``revoked`` — a revoked document is a dead end, not a further stage, and showing
it as the fourth step would read as a progression.

Notebook pages
^^^^^^^^^^^^^^

:guilabel:`Listed people`
"""""""""""""""""""""""""

An editable (``editable="bottom"``) inline list of ``holder_ids``, with
``sequence`` as a ``handle``. Two decisions sit on it.

**Conditional create and delete, expressed as domains.** The ``<list>`` tag's own
``create`` and ``delete`` attributes are static, so a list that may be appended
to today and frozen tomorrow cannot say so there. The ``options`` on the
``<field>`` can:

.. code-block:: xml

   <field name="holders_locked" invisible="1"/>
   <field name="holder_ids" options="{
           'create': [('holders_locked', '=', False)],
           'delete': [('holders_locked', '=', False)]}">

Those are domains the web client evaluates against *this* record, which is what
``holders_locked`` is on the form for at all — a field not on the form is not in
``record.data``, and the domain would have nothing to read.

**The passport number is not masked.** This screen is reachable only by internal
users, who are typing a number off the document in front of them, and dots make
that impossible to proofread. The placeholder — *"Typed once, kept only as a
hash"* — is what tells them what happens to it.

Two muted notes sit under the list. The first appears only when
``holders_locked`` is set and explains that the list is the document's rather
than the operator's; the second is unconditional and says that any one of these
people opens the document.

:guilabel:`Issued certificate`
""""""""""""""""""""""""""""""

``issued_on``, ``issuer_id``, ``verify_url`` (widget ``CopyClipboardChar`` —
this value gets pasted into messages), and both fingerprints side by side,
labelled :guilabel:`SHA-256 (printed)` and :guilabel:`SHA-256 (sealed file)`.

The note underneath is the only place in the interface that explains why there
are two: *a file cannot carry its own hash*, so the printed value is the hash of
the document as produced, and re-stamping changes the sealed file while leaving
the printed value alone. Copies already in an embassy's file keep verifying.
Hidden entirely on a draft, where none of it exists yet.

:guilabel:`Verification log`
""""""""""""""""""""""""""""

``attempt_ids``, ``readonly="1"``, three columns: when, ``requester_label``, and
``outcome`` as a decorated badge. The log on the certificate shows
``requester_label`` and **not** ``ip_address`` — the asymmetry is deliberate and
is documented on :doc:`../models/dms_certificate_attempt`. The address is still
on the row, and :doc:`dms_certificate_attempt_views` shows it.

The ``invisible="verify_count > 0"`` note turns an empty list into a sentence
("a row appears here the moment someone types the reference"), which an empty
x2many does not say on its own.

:guilabel:`Files`
"""""""""""""""""

``groups="base.group_no_one"`` — the developer-mode group. Nothing an issuer does
goes through this page: the source is normally supplied by whichever module
produced the document through ``_certify_source()``, and the sealed copy is
written by ``action_certify``. It is on the form for the case where that wiring
is what you are debugging, and off it for everyone else so that pointing a
certificate at a different file is not a thing one does by mistake.

.. admonition:: The source picker will not offer you a seal
   :class: important

   ``source_attachment_id`` carries its domain on the **field**, not on the view,
   so every picker in every module inherits it:

   .. code-block:: python

      domain=[('res_field', '=', False),
              ('res_model', '!=', 'dms.certificate')]

   ``res_field = False`` drops the internal attachments Odoo keeps behind binary
   fields — including the ones holding a ``dms.file``'s own content.
   ``res_model != 'dms.certificate'`` drops the sealed copies **this module
   produces**. Without the second clause you could pick a sealed output as a new
   source and seal a seal: a page with two watermarks, two QR codes and a printed
   fingerprint that no longer matches anything.

   There is a regression test for exactly this —
   ``test_the_source_picker_ignores_the_copies_we_generate`` reads the domain off
   ``_fields`` and asserts the sealed attachment is not among the candidates.

:guilabel:`Source record`
"""""""""""""""""""""""""

``res_model`` and ``res_id``, both readonly, ``invisible="not res_model"``. The
back-link to whatever produced the document. Hidden when there is nothing to link
to, which is the case for an entry created by hand.

Stat buttons
^^^^^^^^^^^^

Both carry ``disabled="1"``, which is unusual enough to be worth saying out loud:
they are **figures, not destinations**.

* :guilabel:`Lookups` shows ``verify_count``, a plain integer. There is no
  recordset behind it to open.
* :guilabel:`Listed` shows ``holder_count``, and the rows it counts are on the
  first notebook page a few pixels below. A button that scrolls you somewhere you
  can already see is noise.

Leaving them enabled would have meant inventing two actions to satisfy the
affordance.

.. _view_dms_certificate_list:

``view_dms_certificate_list``
-----------------------------

``sample="1"``, so a fresh database shows a plausible-looking list rather than an
empty grid. ``reference`` carries ``decoration-bf="1"`` — it is the identifier
people read off paper and search for.

``public_state`` is the badge, decorated four ways (success / warning / danger /
muted), while ``state`` is present but ``column_invisible="1"``. Two state fields
and only one of them shown: ``state`` is the lifecycle an operator drives,
``public_state`` is what an embassy is told, and on a list the second is the
question being asked.

``verify_count`` is ``optional="show"`` under the label :guilabel:`Lookups`;
``last_verified_on`` and ``company_id`` are ``optional="hide"``.

.. _view_dms_certificate_search:

``view_dms_certificate_search``
-------------------------------

.. list-table::
   :header-rows: 1
   :widths: 30 70

   * - Element
     - Domain / context
   * - ``reference``
     - searchable field
   * - ``holder_ids``
     - searchable field, relabelled :guilabel:`Listed person` — searching by the
       name of somebody on the document, which is how a desk enquiry arrives
   * - :guilabel:`Certified`
     - ``[('state', 'in', ('certified', 'delivered'))]``
   * - :guilabel:`Revoked`
     - ``[('state', '=', 'revoked')]``
   * - :guilabel:`Expired`
     - ``[('valid_until', '<', context_today().strftime('%Y-%m-%d'))]``
   * - :guilabel:`Never looked up`
     - ``[('verify_count', '=', 0)]``
   * - :guilabel:`Type`
     - ``{'group_by': 'type_id'}``
   * - :guilabel:`Status`
     - ``{'group_by': 'state'}``
   * - :guilabel:`Movement date`
     - ``{'group_by': 'movement_date'}``

:guilabel:`Expired` filters on ``valid_until`` rather than on ``public_state``,
because ``public_state`` is a non-stored compute and cannot be searched. The
same split explains why :guilabel:`Status` groups by ``state``.

.. _action_dms_certificate:

``action_dms_certificate``
--------------------------

``list,form``, with ``view_dms_certificate_search`` bound explicitly and an
``help`` block whose second paragraph states the access rule in one sentence:
*anyone holding the document, plus the passport of someone listed on it, can
check its status without an account.*

Record ids
----------

.. list-table::
   :header-rows: 1
   :widths: 40 18 42

   * - External id
     - Kind
     - Notes
   * - ``view_dms_certificate_list``
     - ``ir.ui.view``
     - ``sample="1"``, ``public_state`` as the badge
   * - ``view_dms_certificate_form``
     - ``ir.ui.view``
     - The issuing screen
   * - ``view_dms_certificate_search``
     - ``ir.ui.view``
     - Four filters, three groupings
   * - ``action_dms_certificate``
     - ``ir.actions.act_window``
     - Reached from :doc:`menus` as :guilabel:`Verification entries`

Decisions worth naming
----------------------

.. _certificate-form-geometry:

The chatter is inside the sheet; the preview is outside it
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

Both placements are deliberate, and they are the same decision read from two
sides: **there is one right-hand slot on this form, and the stamped page gets
it.**

A ``<chatter/>`` that sits *outside* the sheet is moved by Odoo's form compiler
into the right-hand aside. That is precisely where the page goes, so the chatter
is left **inside** the sheet, where it stays at the foot of the settings.

``div.o_certify_preview_aside`` is then a sibling of the sheet's background. At
XXL the form view is already laid out as a flex row (``o_xxl_form_view``, added
by ``FormController`` on screen size alone), so the panel lands to the right of
the sheet and claims two fifths of the width — and neither the fields nor the
page are capped by the sheet's maximum width any more. Below XXL the form is a
column and the panel stacks underneath, exactly as an aside chatter does.

.. important::

   **The arch and the stylesheet each look right on their own.** Only the
   rendered box says which side of the sheet the panel ended up on, which is why
   this geometry is asserted by browser tours rather than by reading XML:

   * ``test_the_chatter_sits_under_the_form_not_beside_it`` — Python, parses the
     arch and asserts ``//sheet/chatter`` matches and ``/form/chatter`` does not.
     Cheap, and catches someone moving the tag.
   * ``dms_certify_portal_preview_aside_tour`` — browser at 1920×1080. Asserts
     the panel starts at or after the sheet's right edge, and that its width is
     two fifths of the form's to within one percent.
   * ``dms_certify_portal_preview_below_tour`` — browser at 1366×768. Asserts the
     panel's top is at or below the sheet's bottom, i.e. that it stacked rather
     than being squeezed beside the sheet.

   The two layout tours set ``browser_size`` before ``start_tour``, because which
   branch of the layout you get is decided by the viewport. See
   :doc:`../../development/testing`.

The preview re-seals rather than reading the stored copy
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

``preview_pdf`` is computed on ``seal_marking``, ``seal_text``,
``source_attachment_id`` and ``state`` — so the panel shows what the marking
*currently selected* would produce, including before anything has been certified.
That is the whole point of putting it on screen: you are choosing the marking by
looking at it.

It is served through the stock ``pdf_viewer`` widget, so zoom, paging and fit
belong to pdf.js and the page stays sharp at any magnification. That is the
**opposite** choice to the public page, which rasterises each page to PNG on
purpose — there the reader must not get a viewer with its own save, print and
text extraction. Here the reader is the operator, and the viewer is what they
need. See :doc:`../controllers/verify`.

See also
--------

* :doc:`../models/dms_certificate` — every field on this form, and why
  ``public_state`` is not stored
* :doc:`dms_certificate_revoke_views` — the wizard the header button opens, and
  why it loads first
* :doc:`res_config_settings_views` — the house style this form does *not* carry
* :doc:`../assets` — ``certificate_form.scss``, which is the panel's geometry
* :doc:`../static/certificate_chatter` — why the chatter here has no composer
* :doc:`../../handbook/issuing` — the same screen, told as a task
