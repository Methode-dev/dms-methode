Development
===========

For working on the code rather than using the feature.

Two different jobs, and they want different pages:

:doc:`extending`
   **Building the module that produces the documents.** The integration surface:
   ``issue()``, the three documented override points, how to add a fact, a second
   factor or a disclosure mode, which external ids are safe to ``xpath`` against,
   and what is stable versus what is not.

:doc:`contributing`
   **Changing this addon.** Layout, the conventions it enforces, the security
   invariants that must not be broken casually, and what to do before you commit.

Background for both:

:doc:`architecture`
   How the pieces fit: the issuing path, the lookup path, the trust boundary between
   them, and why ``tools/seal.py`` holds no ORM at all. Read this first — most of
   :doc:`extending` only makes sense once you know why the public templates receive a
   dict rather than a record.

:doc:`testing`
   Running the suite, what each module covers, and an audited list of the gaps. The
   portal tests fake the check host on every request, which is worth understanding
   before you add one.

.. toctree::
   :maxdepth: 2
   :hidden:

   architecture
   extending
   contributing
   testing
