verify
======

Source: :ghsrc:`static/src/js/verify.js`

**Registers:** nothing. No component, no registry entry, no module import.

Ninety-four lines in ``web.assets_frontend``, and the first thing to say about
them is what they are not.

Framework-free, on purpose
--------------------------

This is a plain IIFE — ``(function () { "use strict"; … })()`` — with one
``DOMContentLoaded`` listener and two helper functions. **It is not OWL.** There
is no ``import``, no ``@odoo/owl``, no ``@web/core`` anything, and that is the
decision the file exists to record.

The public verification page's whole argument is that it carries as little as
possible: no ``website`` module, no builder, no theme, no account. Pulling in the
Odoo JavaScript framework to format an input would contradict that at the only
point where an anonymous visitor's browser is executing the module's code.

The consequence is the test of whether the decision is real: **everything here
degrades to nothing.** With scripting off or blocked, the form still posts, the
server still formats the reference it echoes back, and the verdict page still
renders. Nothing in the file is load-bearing — which is why none of it is
checked for presence anywhere.

.. code-block:: text

   DOMContentLoaded
   │
   ├── form = document.querySelector(".dc-portal form.dc-lookup-form")
   │     ├── maskReference(form)      group the reference as it is printed
   │     └── wireCaptcha(form)        reCAPTCHA v3, only if a site key is set
   │
   └── print = document.getElementById("dc_print")
         └── click → window.print()

Both lookups are guarded, because all three pages load the same bundle and none
of them carries both elements: ``verify_throttled`` has no form, and the print
button exists only on ``verify_result``.

``maskReference(form)``
-----------------------

Rewrites ``#dc_reference`` on every ``input`` event into the hyphenated grouping
the reference is printed in, so what the agent types looks like what they are
copying from.

**The group sizes come from the server.** They are read off
``form.dataset.groups`` — the ``data-groups`` attribute
:doc:`../templates` renders from ``reference_groups``, which the controller
computes as ``[len(prefix), 4, 3, 4, 2]`` from the configured reference prefix.

.. admonition:: One grouping, one place
   :class: important

   A hard-coded mask would fight the configuration. The prefix is a system
   parameter; change it from ``ICS`` to something four characters long and a
   JavaScript ``3,4,3,4,2`` would start inserting hyphens in the wrong places on
   a page whose entire purpose is helping somebody transcribe a string
   accurately.

   The same grouping is implemented a second time, in Python, as
   ``_format_reference()`` — and for the same reason, from the same source: the
   refusal page has to give back what the agent typed rather than the stripped
   form the lookup used. The server copy is what makes the page right **without**
   this file; this file is what makes it right live.

   The ``"3,4,3,4,2"`` literal in the ``||`` fallback is the only duplication of
   the default, and it is reached only if the attribute is missing entirely.

The normalisation inside ``format()`` is ``toUpperCase()`` then
``replace(/[^A-Z0-9]/g, "")`` — it strips the hyphens it is about to re-insert,
so the mask is idempotent and survives a paste. Note what it does **not** do: it
does not reject ``I``, ``L``, ``O`` or ``U``. The alphabet is not duplicated here
either; the server matches, and the page's copy tells the reader which characters
are never used. An input that silently ate a typed ``O`` would hide the very
mistake the page is trying to surface.

The caret handling is the detail that makes it usable:

.. code-block:: javascript

   var atEnd = input.selectionStart === input.value.length;
   input.value = format(input.value);
   if (atEnd) {
       input.setSelectionRange(input.value.length, input.value.length);
   }

Assigning to ``value`` collapses the caret to the end in every browser. Restoring
it only when the user was *already* typing at the end means an agent correcting a
character in the middle keeps their position, and an agent typing straight
through does not have the caret jump out from under them. Mid-string edits are
left alone rather than approximated.

The final two lines format a value that is already in the box on load — the
pre-filled QR landing route and the reference echoed back after a refusal both
arrive server-formatted, so this is the belt to that braces.

``wireCaptcha(form)``
---------------------

The browser half of the soft dependency on ``google_recaptcha``.

.. code-block:: text

   no data-sitekey, or no #dc_recaptcha_token  → return, do nothing
   submit
     ├── token already present, or grecaptcha undefined → let it through
     └── otherwise
           preventDefault
           grecaptcha.ready → execute(key, {action: "dms_certify"})
                            → field.value = token
                            → form.submit()

Three independent ways for this to be inert, which is what "soft dependency"
has to mean in practice: no site key configured, the ``<script>`` tag absent
from the page (the template emits it under the same ``t-if``), or ``grecaptcha``
failing to load from a blocked CDN. In all three the submit proceeds unchanged —
and the server agrees, because ``_captcha_ok()`` returns ``True`` when there is
no verifier to call.

``action: "dms_certify"`` is the string the controller passes to
``_verify_recaptcha_token``; the two have to stay in step.

.. note::

   ``form.submit()`` rather than re-dispatching the event, so the handler is not
   re-entered. The ``field.value`` check at the top is the matching guard for the
   case where it is.

The print button
----------------

.. code-block:: javascript

   print.addEventListener("click", function () { window.print(); });

``#dc_print`` is the one control on the result page that needs script at all —
there is no markup-only way to open the print dialog. It is a ``<button
type="button">`` in a page whose other actions are a link and a form, so it
cannot be mistaken for a submit.

What it prints is governed by the ``@media print`` block at the foot of
``verify.scss``: the hero, the explainer, the masthead, the footer and the action
row are hidden, the verdict card loses its shadow and gains a plain border, and
``.docframe`` drops its ``max-height`` so every page image prints rather than
only the first scrollful. What an agent files is the verdict, not the furniture
around it. See :doc:`../assets`.

Because the result page is session-bound and expires, the printed sheet is the
only durable artefact of a lookup on the embassy's side — which is the argument
for the button existing rather than leaving it to the browser's own menu.

No test
-------

There is no JavaScript test for this file, and no Python test asserts any of its
effects. That is a consequence of the degradation property rather than a gap:
there is no behaviour here whose absence breaks a page, so there is nothing a
test could usefully guard that is not already covered server-side —
``_format_reference()`` produces the same grouping, and ``_captcha_ok()`` decides
the captcha.

.. todo::

   Worth confirming against :doc:`../../development/testing`: is the absence of a
   browser tour over the public page a deliberate omission, or simply not done
   yet? A tour asserting that the mask produces the printed grouping would be
   cheap and would pin ``reference_groups`` to the JavaScript that consumes it.

See also
--------

* :doc:`../templates` — the markup this file attaches to, including
  ``data-groups`` and ``data-sitekey``
* :doc:`../controllers/verify` — ``_format_reference()`` and ``_captcha_ok()``,
  the server halves of two of the three functions here
* :doc:`../assets` — ``verify.scss``, the ``@media print`` block, and the
  frontend bundle
* :doc:`../../handbook/verification` — the page as the agent uses it
