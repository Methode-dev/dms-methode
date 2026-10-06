res_config_settings_views
=========================

**Model:** :doc:`res.config.settings <../models/res_config_settings>`

Source: :ghsrc:`views/res_config_settings_views.xml`. One inherited form view
injecting **three** blocks.

.. contents::
   :local:
   :depth: 2

.. _res_config_settings_view_form_certify:

``res_config_settings_view_form``
---------------------------------

Inherits ``base_setup.res_config_settings_view_form`` and inserts three
``<block>`` elements before ``//block[@name='integration']``:

.. code-block:: xml

   <xpath expr="//block[@name='integration']" position="before">
     <block title="Document verification portal"       name="dms_certify"/>
     <block title="Certified documents: defaults"      name="dms_certify_defaults"/>
     <block title="Certified documents: the seal"      name="dms_certify_seal"/>
   </xpath>

Three blocks rather than one. That is the module's own division of labour made
visible: the first block is **how the public door behaves**, the second is **what
a new document starts out as**, and the third is **house style for the stamp**.
They are edited by different people on different days, and a reader looking for
the watermark angle should not have to scroll past the rate limiter.

Inheriting ``base_setup`` rather than ``website`` is a consequence of
:ref:`not depending on the website module <limits-no-website>` — see also
:doc:`../../limits`.

.. note::

   None of the three blocks carries a ``groups`` attribute, so visibility is
   whatever :menuselection:`Settings --> General Settings` already requires. The
   groups this module defines gate the :doc:`menus`, not this page.

Block 1 — ``dms_certify``: the public door
------------------------------------------

Throttling
^^^^^^^^^^

.. list-table::
   :header-rows: 1
   :widths: 24 34 42

   * - ``<setting>``
     - Fields
     - Why it is its own setting
   * - :guilabel:`Rate limiting`
     - ``certify_max_failures``,
       ``certify_window_minutes``
     - Per IP address. The ``help`` says what it does **not** cover: *"Put a
       second limit in your reverse proxy: this one only catches what already
       reached Odoo."*
   * - :guilabel:`Reference lockout`
     - ``certify_max_reference_failures``,
       ``certify_reference_lock_minutes``
     - Counted across **every** address. *"With a four-character second check,
       this is the limit that actually protects a document."*

Two limits, and the help strings carry the reason they are not one. Someone
guessing at a single document will change address; an agent mistyping will not.
A per-address limit alone therefore protects the server and not the document,
which is why the second one exists and is the one the help string calls out.

The nginx half of the same story is in :ref:`deployment-nginx`.

Portal behaviour
^^^^^^^^^^^^^^^^

.. list-table::
   :header-rows: 1
   :widths: 26 32 42

   * - ``<setting>``
     - Field
     - Notes
   * - :guilabel:`Result lifetime`
     - ``certify_session_minutes``
     - *"How long a result stays readable after a successful lookup."* The field
       help adds the reason to keep it short: embassy workstations are shared.
   * - :guilabel:`Log retention`
     - ``certify_retention_days``
     - *"Attempt logs hold IP addresses. Agree this figure with whoever signs off
       your processing record."* Drives the purge cron.
   * - ``certify_hide_expired_setting``
     - ``certify_hide_expired``
     - No ``string``; the field label carries it. See the warning below.
   * - ``certify_allow_download_setting``
     - ``certify_allow_download``
     - *"Streamed through the verification gate, never through /web/content."*
   * - :guilabel:`Portal company`
     - ``certify_portal_company_id``
     - ``options="{'no_create': True}"``. *"An embassy is looking at one
       organisation, whichever company issued the document they are checking."*
   * - :guilabel:`Public verification URL`
     - ``certify_public_base_url``
     - *"Printed on every document and encoded in its QR code, so it stays in
       circulation for months."*

Two of these are one-way doors and the help strings say so rather than leaving it
to a runbook:

**The public verification URL goes on paper.** It is printed beside the QR code
and encoded inside it, on documents that circulate for months, and a document
already in an embassy's file cannot be re-pointed. Set it before issuing
anything.

**The portal company is a decision, not a fallback.** A public request resolves
to whatever company the public user happens to default to, which is nobody's
choice. ``no_create`` is there because creating a company from the settings page
of another module is never what was meant.

.. warning::

   ``certify_allow_download`` only governs the gated route. Turning it off
   removes the :guilabel:`Download the sealed PDF` button and makes
   ``/r/<token>/file`` return *not found*; it does nothing about
   ``/web/content/<id>``, which this module never links and which the
   :doc:`../security/ir_rule` and the absence of a public ACL are what keep shut.

.. todo::

   ``certify_hide_expired`` writes ``dms_certify_portal.hide_expired``, the
   parameter ships with a default of ``False`` in :doc:`../data/ir_config_parameter`,
   and the field's help describes a real behavioural difference — *"When on it
   reads as 'no match', which shrinks the searchable set but can make an agent
   reject a real holder."* **Nothing in the addon reads the parameter.** A grep
   for ``hide_expired`` across ``models/``, ``controllers/``, ``tools/``,
   ``wizards/`` and ``hooks.py`` finds only the field declaration itself.

   The README lists ``_hide_expired()`` as an extension point, and no method of
   that name exists either.

   So: was the hook removed in a refactor, or never written? Either the controller
   should consult the parameter when ``public_state == 'expired'``, or the setting
   and its parameter should come out of the UI — a switch that does nothing is
   worse than an absent feature, because somebody will tick it and believe it.

Block 2 — ``dms_certify_defaults``: what a new document starts as
-----------------------------------------------------------------

.. list-table::
   :header-rows: 1
   :widths: 28 32 40

   * - ``<setting>``
     - Fields
     - Notes
   * - :guilabel:`Stamp on generation`
     - ``certify_auto_stamp_type_ids``
     - ``widget="many2many_checkboxes"``, ``nolabel="1"``
   * - :guilabel:`How a document opens`
     - ``certify_second_factor``,
       ``certify_disclosure``,
       ``certify_validity_days``
     - *"Set per document when it is issued; these are the values a new one
       starts with. The second check can never be switched off."*
   * - :guilabel:`Reference`
     - ``certify_reference_prefix``
     - *"References read PREFIX-YEAR-PORT-XXXX-XX and carry no counter, so two of
       them tell nobody how many were issued in between."*
   * - ``certify_notify_setting``
     - ``certify_notify_on_lookup``
     - *"Off means only failures, lockouts and mismatch reports reach the desk."*

.. admonition:: :guilabel:`Stamp on generation` is not a config parameter
   :class: important

   ``certify_auto_stamp_type_ids`` is a plain ``Many2many`` over
   :doc:`dms.certificate.type <../models/dms_certificate_type>`, filled by
   ``get_values()`` and written back onto the ``auto_stamp`` flag of each type by
   ``set_values()``. The flag lives on the type itself, so a producing module
   ships a sensible default with its data record and an administrator changes it
   here, neither side knowing about the other. The same tick is editable from
   :doc:`dms_certificate_type_views`.

   It is deliberately **not** a computed field. A non-stored compute recomputes
   when the cache is invalidated — which happens between the client saving the
   record and ``set_values()`` reading it back, so an unticked box was recomputed
   straight back to ticked before anything was written. There are regression tests
   for both directions (``test_unticking_a_kind_survives_the_save``,
   ``test_ticking_a_kind_survives_the_save``).

The help on :guilabel:`How a document opens` carries the one invariant worth
repeating in every surface that touches it: **the second check can never be
switched off.** There is no selection value for "reference only" — see
:ref:`concepts-second-factor`.

Note what changing ``certify_reference_prefix`` moves besides the prefix. The
controller derives the input mask's group sizes from its length
(``[len(prefix), 4, 3, 4, 2]``), so a four-letter prefix reformats both the
browser mask and the server-side regrouping of a refused reference. See
:doc:`../static/verify`.

Block 3 — ``dms_certify_seal``: house style
-------------------------------------------

.. list-table::
   :header-rows: 1
   :widths: 26 34 40

   * - ``<setting>``
     - Fields
     - Notes
   * - :guilabel:`Watermark`
     - ``certify_seal_opacity``,
       ``certify_seal_size``,
       ``certify_seal_angle``,
       ``certify_seal_mode``,
       ``certify_seal_color``
     - *"The marking itself is chosen per document. This is the house style it is
       drawn in."*
   * - :guilabel:`Stamp block`
     - ``certify_seal_qr_corner``,
       ``certify_seal_band``
     - *"Where the QR code, the reference and the fingerprint are printed."*
   * - ``certify_guilloche_setting``
     - ``certify_seal_guilloche``
     - *"Engraved line pattern around the page. It moirés on a photocopy."*
   * - ``certify_microtext_setting``
     - ``certify_seal_microtext``
     - *"Repeats the reference at 1 pt along the foot. Legible under a loupe, a
       grey smear once scanned."*

**The division between this block and the certificate form is the point.** What
the watermark *says* (``seal_marking``, ``seal_text``) is per document and is
chosen on :doc:`dms_certificate_views` by looking at the preview panel. How it is
*drawn* — ink, angle, opacity, coverage, border, microtext, stamp corner — is
agreed once and set here. Putting the angle on every document would invite a
house style that drifts, and a document whose stamp looks unlike the others is a
document an agent has to think about.

The two anti-copying features carry their own justification in the ``help``
rather than in a wiki: both are there because they **degrade on reproduction**,
which is what makes them worth printing at all.

:guilabel:`Make room for the stamp` (``certify_seal_band``) is the one setting
here with a real trade-off, and its help states it: *"Sealing cannot reflow a
page. When the stamp's corner is already occupied, the page can be shrunk
slightly to free a strip for it."* The default, ``auto``, keeps most documents at
their exact size and only shrinks the ones that would otherwise be overprinted.

Layout convention
-----------------

Every multi-field setting follows the same pattern:

.. code-block:: xml

   <setting string="…" help="…">
       <div class="content-group mt-2">
           <div class="row">
               <label for="certify_window_minutes" class="col-lg-6 o_light_label"/>
               <field name="certify_window_minutes"/>
           </div>
       </div>
   </setting>

An explicit ``<label for="…">`` with ``o_light_label`` per row, because a
``<setting>`` renders a single field with its own label and stacking several
without this gives them inconsistent widths. Single-boolean settings skip it
entirely and carry an ``id`` instead of a ``string`` — the field's own label is
the sentence, and a title above it would say it twice.

See also
--------

* :doc:`../models/res_config_settings` — every field, its parameter key and its
  default
* :doc:`../data/ir_config_parameter` — the parameters shipped at install, which
  are what these fields read on a fresh database
* :doc:`dms_certificate_type_views` — the other place ``auto_stamp`` is edited
* :doc:`dms_certificate_views` — where the per-document half of the seal is chosen
* :doc:`../../handbook/administration` — the same page, in the order you would
  set it up
* :doc:`../../handbook/deployment` — the settings that have to be right before the
  first document is issued
