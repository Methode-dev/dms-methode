form_renderer_patch
===================

Source: :ghsrc:`static/src/js/form_renderer_patch.js`

**Patches:** ``FormRenderer.prototype`` (``@web/views/form/form_renderer``), via
``patch()`` from ``@web/core/utils/patch``.

A twenty-two-line comment above a fourteen-line patch, which is the right ratio:
what it does is obvious and what it avoids is not. It is the delivery mechanism
for
:doc:`certificate_chatter` — that page carries *why* the certificate's chatter
has no composer; this one carries *how* it gets onto the form, and why the
obvious implementation does not work from here.

Not a registry entry
--------------------

``patch()`` on the prototype, not ``registry.category(...)``. So there is no
widget name to look up and nothing to add to a view's arch: every form view in
the database runs this code, and the model check inside it is what narrows the
effect to one.

The patch
---------

.. code-block:: javascript

   patch(FormRenderer.prototype, {
       setup() {
           super.setup();
           onWillRender(() => {
               if (
                   this.mailComponents &&
                   this.mailComponents.Chatter !== CertificateChatter &&
                   this.props.record?.resModel === "dms.certificate"
               ) {
                   this.mailComponents = { ...this.mailComponents, Chatter: CertificateChatter };
               }
           });
       },
   });

``mailComponents`` is the map the compiled form template reads its chatter
component out of, as ``__comp__.mailComponents.Chatter``. Swapping the entry is
the whole operation.

The three guards, in the order they are written:

.. list-table::
   :widths: 40 60

   * - ``this.mailComponents``
     - A form view with no chatter has no map. Cheapest check, so it is first.
   * - ``.Chatter !== CertificateChatter``
     - Idempotency. ``onWillRender`` fires on every render; without this the
       object would be rebuilt each time for no gain.
   * - ``props.record?.resModel === "dms.certificate"``
     - The narrowing. Optional chaining because a renderer can be set up before
       a record is attached.

.. _form_renderer_patch-race:

Why ``onWillRender`` and not ``setup``
--------------------------------------

The obvious implementation is to assign ``this.mailComponents.Chatter`` inside
the ``setup()`` patch and stop. That is how ``outlook_chatter_theme`` and
``sh_helpdesk_relation`` do it, and it is what the file's comment block exists to
explain the rejection of.

It would not work from here, for a reason that is pure arithmetic:

.. code-block:: text

   patches apply in asset order
     asset order follows module load order
       dms_certify_portal   → position #414 in web.assets_backend
       outlook_chatter_theme → position #446
                                    (measured, not assumed)

   so:  our setup() runs first
        the theme's setup() runs second and overwrites the choice
        → the stock themed chatter renders on the certificate form,
          composer and all

Winning that race in ``setup()`` means loading after the theme, which means
depending on the theme. This module is generic, ships in a different repository,
and must not acquire a dependency on a chatter skin to keep its own audit trail
read-only.

So the choice is re-asserted at **render** time instead. ``onWillRender`` runs
after every ``setup()``, whoever patched it, and immediately before the compiled
template reads ``mailComponents.Chatter``. Asset order stops mattering: the last
writer before the read is always this one.

.. important::

   Two properties make the re-assertion safe rather than a hack.

   **It triggers no further render.** ``mailComponents`` is a plain property, not
   reactive state, so assigning to it inside ``onWillRender`` does not schedule
   another render. The same line against a reactive field would loop.

   **There is nothing to restore.** A renderer instance belongs to one form view
   and therefore to one model, so only certificates ever reach the assignment —
   no other model's renderer can inherit a swapped map from a previous record.

This is the kind of decision nobody rediscovers cheaply. Moving the assignment
back into ``setup()`` looks like a simplification, passes on any database without
a chatter theme installed, and breaks silently on the one production database
that has one.

How it is tested
----------------

Only in a browser. No Python test can see this: the component choice happens
client-side, after the server has shipped both templates untouched.

* ``dms_certify_portal_chatter_tour`` asserts the rendered chatter has no
  :guilabel:`Send message`, no :guilabel:`Log note` and no composer, and that it
  is still a chatter — see :doc:`certificate_chatter`.
* The race itself has been run, both ways. The docstring of
  :ghsrc:`tests/test_chatter_tour.py` records the command:

  .. code-block:: bash

     make test m=dms_certify_portal,outlook_chatter_theme \
         t=/dms_certify_portal:TestCertificateChatterTour

  It passes as written and fails — *"A Send message button … is on the
  certificate chatter"* — the moment the override is moved back into
  ``setup()``. ``outlook_chatter_theme`` is not a dependency, so it is absent
  from the ordinary test database and the combination has to be asked for.

.. note::

   The ``#414`` and ``#446`` positions in ``web.assets_backend`` are a
   measurement of one database at one time, not a guarantee. They are recorded
   because they are the evidence for the decision, not because the fix depends
   on them — ``onWillRender`` is correct for any ordering, which is the point of
   choosing it.

See also
--------

* :doc:`certificate_chatter` — the component this installs, and why the
  certificate's thread is read-only
* :doc:`../views/dms_certificate_views` — the form, and the rest of its geometry
* :doc:`../assets` — ``web.assets_backend``, where load order comes from
* :doc:`../../development/testing` — running the tour, including against the
  theme
