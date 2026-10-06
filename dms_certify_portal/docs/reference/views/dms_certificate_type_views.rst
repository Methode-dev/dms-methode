dms_certificate_type_views
==========================

**Model:** :doc:`dms.certificate.type <../models/dms_certificate_type>`

Source: :ghsrc:`views/dms_certificate_type_views.xml`. Two views and one action.
Loaded **first** of the view files, because the certificate form references the
type and the revoke action references the certificate.

This module ships **no types of its own**. What a document *is* belongs to
whichever module produces it, so these screens are almost always looking at
records somebody else's data file created.

Structure
---------

.. code-block:: text

   list "Document types"  editable="bottom"
     sequence (handle) · name · code · auto_stamp "Stamp on generation"
     certificate_count "Documents" (readonly)

   form "Document type"
     ribbon  "Archived"            invisible active
     oe_title  name   placeholder "Letter of Invitation"
     group
       code  placeholder "loi"    │  auto_stamp
       sequence                   │  certificate_count (readonly)
       active (invisible="1")     │
     note  "The code is what a producing module refers to … The name can be
            renamed and translated freely — it is what the verification page
            shows."

Record ids
----------

.. list-table::
   :header-rows: 1
   :widths: 42 20 38

   * - External id
     - Kind
     - Notes
   * - ``view_dms_certificate_type_list``
     - ``ir.ui.view``
     - ``editable="bottom"`` — the whole taxonomy is maintainable inline
   * - ``view_dms_certificate_type_form``
     - ``ir.ui.view``
     - Reached only by clicking through from the list
   * - ``action_dms_certificate_type``
     - ``ir.actions.act_window``
     - :menuselection:`Consular --> Configuration --> Document types`

Decisions worth naming
----------------------

**The list is editable, and that is where the work happens.** A document type is
a name, a code, an order and one tick. Opening a form to change a tick is a worse
experience than ticking it in place, so the list carries every field the form
does except ``active``.

**The code cannot change once documents exist, and the name always can.** The
note under the form is the only place this is stated in the interface. A
producing module refers to a type by ``code`` when it registers a document, so
renaming the code breaks that call; the ``name`` is what the public verification
page prints, so it is free to be renamed and translated. ``certificate_count``
next to it is what tells you whether you are past that point.

**Nothing offers to delete a type in use.** The model raises on it — a type with
documents behind it cannot be unlinked, because deleting it would leave issued
documents unable to say what they are on a page whose whole job is to say so.
Archiving is the way out, which is what the ``active`` field and the
:guilabel:`Archived` ribbon are for; ``active`` itself is ``invisible="1"``
because archiving is done from the list's action menu, as it is everywhere else
in Odoo.

**The** :guilabel:`Stamp on generation` **tick appears twice.** Here, on the type,
and in :doc:`res_config_settings_views` as a checkbox list over every type. Same
field, two audiences: a producing module ships its own default alongside its
type, and an administrator changes it from Settings without either side knowing
about the other. The settings page writes ``auto_stamp`` back onto these records
rather than into a system parameter.

The action's ``help`` block says the same thing in the empty state, which is the
one moment the reader is certain to be looking for it.

See also
--------

* :doc:`../models/dms_certificate_type` — the ``code`` uniqueness constraint and
  the unlink guard
* :doc:`res_config_settings_views` — the other place ``auto_stamp`` is edited
* :doc:`menus` — where this action hangs
* :doc:`../../handbook/administration` — setting up the taxonomy
