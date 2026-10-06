Verification
============

The public half, from the side that matters: an agent at a consular counter with
a piece of paper in one hand and a passport in the other.

There is no account, no portal invitation and no shared password. There is also
no website builder behind the page — see :ref:`limits-no-website` for what that
costs.

.. contents::
   :local:
   :depth: 2

The page an agent reaches
-------------------------

Either by scanning the QR code in the seal block, or by typing the address
printed beside it. Both land on the same form; scanning only saves the agent
retyping the reference.

.. code-block:: text

   https://check.erp.example/              the form, empty
   https://check.erp.example/d/ICS-2026-DKK-4KQ7-9B
                                           the form, reference prefilled

The address is a host of its own — ``check.`` in front of your ordinary Odoo
name — and nothing else of Odoo answers on it. See
:ref:`deployment-check-host`.

.. important::

   The prefilled landing page **looks nothing up**. The scanned value is echoed
   straight back into the form and that is all, so the QR landing page is
   exactly as silent about whether a reference exists as the empty form is. This
   is not an oversight to be optimised away.

Above the form sits a short explanation of what this organisation issues and the
one sentence that does most of the work: *"A reference on its own opens nothing:
a listed passport is needed too."* Below every page — including every refusal —
sits the same explainer, because an agent who has just been turned away is
exactly the person who needs to read it.

The two inputs
--------------

.. list-table::
   :header-rows: 1
   :widths: 28 72

   * - Field
     - What the agent does
   * - :guilabel:`Document reference`
     - Types what is printed in bold beside the QR code. A browser mask
       re-groups it as they type, from group sizes the **server** supplies, so
       the input formats the way that instance's documents actually print.
       Spacing, dashes and capitals are stripped before anything is matched.
   * - :guilabel:`Passport of a person listed on the paper`
     - Types what the passport in hand shows. The help text underneath covers
       all three modes without the page having to disclose which one *this*
       document uses: *"Some documents ask for the whole number, others for just
       the last 4 characters … If the document carries no passport number, type
       a listed date of birth instead (DDMMYYYY)."*

That the second field cannot be labelled precisely is deliberate. Naming the
mode would tell a guesser the shape of the secret before they have found a valid
reference. See :ref:`concepts-second-factor`.

If ``google_recaptcha`` is installed and configured, an invisible v3 widget is
rendered into the same form and its token travels with the submission. If it is
not, nothing appears and nothing is checked — silently. See :doc:`deployment`.

What happens on submit
----------------------

The passport arrives in a ``POST`` body, is matched, and is then **dropped**.
What the browser is redirected to is an opaque, session-bound token.

.. code-block:: text

   POST /          reference + second factor
     │
     ├── refused ──► redirect to / #result           ── a reason code only
     │
     └── matched ──► redirect to /r/<token> #result   ── the result page

So the second factor never reaches a URL: not browser history, not a ``Referer``
header, not an nginx access log. The token on its own is worthless — it only
resolves against the session that minted it, so pasting ``/r/<token>`` into
another browser gets the *expired* refusal. It lasts fifteen minutes by default.

The ``#result`` fragment is not decoration. The verdict renders *below* the
lookup form on the same page, and a plain redirect would land the browser at the
top and leave the agent to scroll for the answer.

.. _verification-refusals:

Every refusal, and what it does not say
---------------------------------------

.. list-table::
   :header-rows: 1
   :widths: 17 24 33 13 13

   * - Situation
     - Heading the agent sees
     - What they are told
     - Logged as
     - Desk told
   * - **Unknown reference**, *or* a reference that exists with the wrong second
       factor
     - *Those two details do not open a document*
     - That both have to come from the same document, that **we will not say
       which of the two failed**, and to check ``0`` against ``O`` and ``1``
       against ``I``. Plus the reference as they typed it, re-grouped, and how
       many tries are left on it.
     - ``no_match``
     - yes, when the reference exists
   * - **A box left empty**
     - *Both details are needed*
     - To fill both, and that the reference on its own never opens a document.
     - ``no_match``
     - no
   * - **Captcha not satisfied**
     - *We could not confirm this came from a browser*
     - To reload and try again, and to call the operations desk if it keeps
       happening.
     - ``captcha``
     - no
   * - **Too many failures from this address**
     - *Checks from here are paused*
     - That checks resume in about N minutes. A full page, not a banner.
     - ``throttled``
     - no
   * - **Too many failures on this reference**
     - *Reference locked*
     - That it is locked for about N minutes, **that the operations desk has
       been told**, and to call if the document is needed now.
     - ``locked``
     - yes, plus an activity
   * - **Result token expired, or opened in another browser**
     - *That result has expired*
     - That a result stays readable only for a short while, and to enter the
       details again.
     - *not logged*
     - no

The things the page never discloses:

* **Whether a reference exists.** The first row above covers both failures with
  one wording. Separating them would hand anyone an oracle: walk the reference
  space with an arbitrary passport value and keep the hits.
* **Which of the two inputs was wrong.** Said out loud on the page, which is
  better than leaving an agent to wonder whether the system is broken.
* **That a document is registered but not yet sealed.** A draft is not in the
  states the portal speaks about, so it refuses exactly like an unknown
  reference — truthfully enough, since nothing has been printed yet.
* **Anything through timing.** A reference that does not exist still costs one
  throwaway HMAC before the refusal, so a miss and a wrong passport take about
  the same wall time. Identical wording with a measurable difference underneath
  would be no better than two messages.

The one thing a refusal *does* give away is **how many attempts are left on that
reference**. An agent who mistyped needs it badly; somebody guessing can count
their own failures anyway.

.. note::

   Two sub-resources refuse with a plain **404** rather than a page: a page
   image past the end of the document, and the download when
   :guilabel:`Allow downloading the sealed document` is off. Both are
   sub-resources of a page the caller is already looking at, so there is no
   refusal worth rendering — and the download check is made in the route as well
   as in the template, so turning the setting off actually closes the route
   rather than only hiding the button.

A note on the two limits
^^^^^^^^^^^^^^^^^^^^^^^^

They behave differently in a way worth knowing when you are watching a lockout:

* The **address** limit counts only ``no_match`` and ``captcha`` rows, so being
  throttled does not deepen the hole you are in.
* The **reference** lock counts ``locked`` rows too — but its clock runs from
  the failure that *tripped* the lock, so a caller who keeps hammering does not
  keep pushing their own release back.

Both are configured in :doc:`administration`.

The result page
---------------

Three verdicts, each a whole sentence rather than a status word.

.. list-table::
   :header-rows: 1
   :widths: 24 76

   * - Verdict
     - Wording, and what else changes
   * - **Authentic**
     - *"Document is authentic — issued by us and unchanged since. Compare the
       page below, line for line, with the paper presented to you."* The wax
       seal graphic is shown.
   * - **Authentic, but out of date**
     - *"We did issue this document, and its validity has now ended. Ask the
       operations desk for a current one."* Far more useful to an embassy than
       silence, which is why expiry is reported rather than hidden.
   * - **Document revoked — do not accept**
     - *"This reference was issued by us and then cancelled. The paper in front
       of you is no longer valid, even if it looks intact."* The cancellation
       date and **the reason the operator typed** are printed, the page images
       are not shown, and the download button is gone.

Under the verdict runs a band of facts: the verification number (how many times
this document has been checked), that the second check passed, when it was
issued, what it is valid until — or *"Valid until revoked"* — and whether the
issuer is notified of this lookup.

Then, side by side:

**Who was checked.** Under ``confirm`` disclosure: *"confirmed — 1 of the 23
listed"*, the matched person's name and rank, and a box explaining that the
other lines stay redacted and that the operations desk can open full disclosure
on a reasoned request. Under ``full``: the whole crew table, with a note that
full disclosure was switched on by the issuer and that this lookup is
timestamped and notified. **Neither mode ever prints a passport number.**

**Voyage.** Whatever facts the producing module supplied, label and value. If it
supplied none, the document's type is printed instead so the panel is never
empty.

**The document as issued.** One image per page, each linking to itself at full
resolution.

At the foot: the reference, the issuer and company, and the full SHA-256
fingerprint of the issued file.

The page images, and why they are images
----------------------------------------

Each page is rasterised to PNG and streamed through the same gate as everything
else. A PDF viewer would carry its own save, print and text-extraction, none of
which pass back through that gate — and comparing a screen against a sheet of
paper needs no more than a picture.

They are rendered at 200 dpi, which is **measured, not chosen for comfort**: the
stamp's QR is 18 mm square and a code of that density needs roughly three pixels
per module to decode. PyMuPDF's default 110 dpi gave about two, and the QR on
the screen was unscannable.

.. tip::

   Fitted to its column the page is right for reading line by line, but the QR
   comes out around 40 pixels across and no reader will decode it. **Clicking a
   page opens it full size**, where the QR can be scanned off the screen — which
   is how an agent confirms that the code on the paper and the code in the
   register point to the same place. The page says so.

The download
------------

:guilabel:`Download the sealed PDF` streams the bytes through this controller —
never a link to ``/web/content/<id>``, which would be readable by anyone who
knew the attachment id and would detach the file from the second check
altogether.

Under ``confirm`` disclosure the download is the **same redacted copy** the page
images came from, not the full sealed document. Under a revoked verdict the
button is not rendered at all.

Turn it off globally with :guilabel:`Allow downloading the sealed document`.

Reporting a mismatch
--------------------

:guilabel:`The paper does not match` — the most valuable thing this portal
collects.

A document that verifies while the paper in front of the agent differs from it
is either a forgery built on a real reference or a stale copy, and either way
somebody at the issuing desk needs to know within minutes. So the button:

* writes an attempt row with outcome ``mismatch``;
* posts to the certificate's chatter **regardless of the per-document
  notification setting**, and raises a warning activity on the issuer;
* shows the agent *"Thank you. The issuing desk has been told and will look at
  this document straight away."*

It takes no free text. Asking an agent at a counter to write a description is
asking for an empty field; what the desk needs is the certificate and the
timestamp, and they can telephone.

:guilabel:`Print this result` prints the verdict page itself — the agent's own
record that they checked, dated by their own machine.

The language switcher
---------------------

Top right, and it offers **only the languages the portal copy actually exists
in**. A database with six back-office languages installed should not show an
embassy six buttons, five of which lead to an English page, so the list is
filtered against the ``i18n/*.po`` files this addon ships.

There are no ``/fr/`` URLs — those come from ``website``, which this addon
deliberately does not depend on. The choice rides a ``lang`` query parameter and
then sticks to the session. Two consequences worth telling an embassy about:

* a French result page cannot be bookmarked or shared *as French*;
* a shared workstation keeps whatever language the previous agent chose until
  the session ends.

Switching language from a result page returns to the form, because the switcher
links to the form. The session's language survives an expiry — somebody whose
fifteen minutes ran out is still reading French.

Every page says no
------------------

Every response carries ``Cache-Control: no-store``, ``Pragma: no-cache``,
``X-Robots-Tag: noindex, nofollow, noarchive`` and
``Referrer-Policy: no-referrer``. A result page names a person and shows their
document; it must not survive in a shared browser's cache or in an intermediate
proxy, and the reference must not leak to whatever a link on the page points at.

The result page also tells the agent, in words, that it closes on its own and to
shut the tab — *"this workstation may be shared."*

See also
--------

* :doc:`concepts` — :ref:`concepts-second-factor` and
  :ref:`concepts-disclosure`
* :doc:`sealing` — :ref:`sealing-redaction`, which is what makes the images
  under ``confirm`` disclosure safe to serve
* :doc:`administration` — both rate limits, the result lifetime, the portal
  company
* :doc:`deployment` — ``--proxy-mode``, without which the per-address limit
  becomes one global limit
* :doc:`troubleshooting` — a verdict with no page, a lookup throttled for
  everybody at once
* :doc:`../reference/controllers/verify` — all seven routes, the session keys
  and the order of the checks
* :doc:`../reference/templates` — where every sentence quoted above lives
