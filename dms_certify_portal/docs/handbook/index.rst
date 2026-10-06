Handbook
========

The reference section answers *"what is this symbol?"*. This one answers *"how do I
do the thing?"*.

Read :doc:`concepts` first if you are new. Most of what is confusing about this addon
comes from not having separated the four things it keeps separate — the document, the
entry about it, the second factor and the disclosure mode — and that takes one page to
fix.

Start here
----------

:doc:`quickstart`
   One document type, sealed and then checked from a browser, end to end. About
   thirty minutes, most of it configuration you only do once.

:doc:`concepts`
   The ideas the rest of the addon is built out of: the two halves, the reference,
   the second factor, disclosure, and what *verifiable* means here.

Day to day
----------

:doc:`sealing`
   What the stamp puts on the page and why, what a re-stamp does, the markings, and
   the redaction that makes confirm-only disclosure safe.

:doc:`verification`
   The public page as the embassy sees it: the two inputs, every refusal and what it
   deliberately does not tell them, the result, and reporting a mismatch.

:doc:`issuing`
   For the module that produces the documents: ``issue()``, registering without
   sealing, the three override points, and revocation.

Administration
--------------

:doc:`administration`
   Document types, the seal house style, the second factor and disclosure defaults,
   the two rate limits, retention, and who gets which group.

:doc:`deployment`
   The checklist before anything goes on paper: the check host, ``--proxy-mode``,
   the public URL, nginx, reCAPTCHA, and backing up the pepper.

:doc:`security-and-privacy`
   What personal data this holds, what the design refuses to do and why — the
   absence of a public ACL, one error message for every failure, constant-time
   comparison, non-sequential references — and what to settle before going live.

:doc:`troubleshooting`
   The failures that actually happen, with the fix for each.

.. toctree::
   :maxdepth: 2
   :hidden:

   quickstart
   concepts
   sealing
   verification
   issuing
   administration
   deployment
   security-and-privacy
   troubleshooting
