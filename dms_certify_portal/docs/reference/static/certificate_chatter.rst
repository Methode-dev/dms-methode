certificate_chatter
===================

Source: :ghsrc:`static/src/js/certificate_chatter.js` and
:ghsrc:`static/src/js/certificate_chatter.xml`

**Defines:** ``CertificateChatter``, an OWL component extending ``Chatter``
(``@mail/chatter/web_portal/chatter``), and the primary-inherit template
``dms_certify_portal.CertificateChatter``.

Two files, one decision: **the chatter on a certificate cannot be written
into.** This page is why; :doc:`form_renderer_patch` is how it reaches the form,
and the two should be read together.

The decision
------------

A certificate's thread is not a conversation. It accumulates lookups, access
requests and their verdicts, state changes, and the planned activities that hang
off them — all of it written by the module itself, most of it by the public
controller through ``sudo()``.

So the two topbar buttons and the composer they open are removed. A note typed by
hand would land in that thread looking exactly like a machine-written one: same
avatar position, same timestamp, same formatting. An auditor reading the thread
six months later would have no way to tell "the system recorded a lookup from
81.x.x.x" from "a colleague typed that a lookup happened". An audit trail whose
entries cannot be told apart by origin is not an audit trail.

Everything else stays. Activities, followers, the attachment box, the search and
the message list are the stock components, untouched — this is a chatter with the
composer taken out, not a bespoke log widget. Logging a *planned activity*
remains possible precisely because an activity is a structured record with its
own fields, not free prose in the stream.

.. note::

   The operator is not left without a way to annotate. Revocation takes a
   mandatory reason through its own wizard, and that reason is a stored field on
   the certificate — a place where a human sentence is wanted, labelled, and
   distinguishable. See :doc:`../views/dms_certificate_revoke_views`.

The component
-------------

.. code-block:: javascript

   import { Chatter } from "@mail/chatter/web_portal/chatter";

   export class CertificateChatter extends Chatter {
       static template = "dms_certify_portal.CertificateChatter";
   }

The entire class. No overridden method, no extra prop, no state — the behaviour
difference is in the template, and the only reason a subclass exists at all is
that ``static template`` is how an OWL component points at one.

.. important::

   It extends the **stock** ``Chatter``, deliberately, and not whatever chatter
   happens to be installed on the other forms in the database. A theme that
   restyles or extends the chatter everywhere else does not get a say in what the
   certificate form shows, and this module does not have to depend on any such
   theme to say so. The cost of that independence is paid in
   :doc:`form_renderer_patch`.

The template
------------

``certificate_chatter.xml`` inherits ``mail.Chatter`` in **primary** mode and
carries exactly three operations:

.. list-table::
   :header-rows: 1
   :widths: 56 44

   * - XPath
     - Removes
   * - ``//button[hasclass('o-mail-Chatter-sendMessage')]``
     - the :guilabel:`Send message` button
   * - ``//button[hasclass('o-mail-Chatter-logNote')]``
     - the :guilabel:`Log note` button
   * - ``//t[@t-if='state.composerType']``
     - the composer itself, and the "To:" recipients row inside it

All three are ``position="replace"`` with an empty body, which is QWeb's delete.

Removing the buttons without the third xpath would leave the composer in the
markup, openable by anything else that sets ``state.composerType``; removing the
composer without the buttons would leave two controls that do nothing. The block
is one change expressed in three places because that is where the markup puts it.

.. warning::

   These three expressions are the module's tightest coupling to Odoo's own
   source. A class rename or a restructure in ``mail/static/src/chatter/web/``
   turns any one of them into an xpath that matches nothing — and
   ``apply_inheritance_specs`` raises on that, which in the browser means the
   certificate form renders with **no chatter at all** and no error a user would
   report.

   That is the specific failure the tests below exist to catch, and it is why
   there are two of them rather than one.

Why ``t-inherit-mode="primary"``
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

A secondary (default) inherit *modifies* ``mail.Chatter`` in place, for everyone.
A primary inherit produces a **new, separately named** template that leaves the
parent alone. Since the goal is a different chatter on one model's form and the
stock one everywhere else, primary is the only mode that expresses it.

It is also what makes the component subclass necessary: a primary inherit has a
name, and something has to point at that name.

How it is tested
----------------

The inheritance is applied **in the browser**. The server ships
``mail.Chatter`` and ``dms_certify_portal.CertificateChatter`` side by side and
never evaluates the xpaths, so neither half can be checked the usual way. The
suite therefore attacks it from two directions.

.. list-table::
   :widths: 34 66

   * - ``TestChatterTemplate``
     - :ghsrc:`tests/test_certificate.py`. Parses ``mail.Chatter`` out of Odoo's
       own source with ``file_path()``, parses our template, and runs the
       children of the ``t-inherit`` element through Odoo's
       ``apply_inheritance_specs`` — the same machinery, in Python. It raises if
       an xpath locates nothing, which is the point. Two assertions:
       ``sendMessage``, ``logNote``, ``<Composer`` and ``RecipientsInput`` are
       gone; ``mail.ActivityList``, ``o-mail-Chatter-activity``,
       ``o-mail-Followers``, ``o-mail-Chatter-fileUploader`` and ``<Thread`` are
       still there.
   * - ``dms_certify_portal_chatter_tour``
     - :ghsrc:`static/tests/tours/certificate_chatter_tour.js`. Opens a real
       certificate in a real browser and asserts the same two halves against the
       rendered DOM. This is the only test that can prove the form picked up
       ``CertificateChatter`` at all.

The second assertion in each — *it is still the chatter, not an empty box where
one used to be* — is the one that catches a broken xpath, because a chatter that
failed to render passes the "nothing can be posted" check trivially.

The tour's helper throws a message naming what it found rather than failing on a
bare selector, so a regression report says *"A Send message button
(.o-mail-Chatter-sendMessage) is on the certificate chatter: the thread records
what happened, it is not written into"* instead of a selector timeout.

See also
--------

* :doc:`form_renderer_patch` — how this component replaces the stock one on the
  certificate form, and the asset-ordering race that decided where
* :doc:`../views/dms_certificate_views` — the form, and
  :ref:`why the chatter sits inside the sheet <certificate-form-geometry>`
* :doc:`../models/dms_certificate` — ``_notify_verification()``, which writes
  most of what ends up in this thread
* :doc:`../assets` — the bundle this pair is loaded through, and the tour
* :doc:`../../development/testing` — running the Python test and the tour, and
  the ``outlook_chatter_theme`` combination
