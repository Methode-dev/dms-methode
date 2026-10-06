Handbook
========

Three pages, because there are fifty-seven lines of code.

:doc:`concepts`
   What ``dbfilter`` does, what this addon changes about it, and what
   ``is_check_host`` is for. The one page worth reading before you touch the
   deployment.

:doc:`administration`
   DNS, the TLS certificate, the reverse proxy, and how to confirm the check host
   resolves to the right database.

:doc:`troubleshooting`
   The check host 404s, serves the wrong database, or serves the whole back office.
   One cause each.

.. toctree::
   :maxdepth: 2
   :hidden:

   concepts
   administration
   troubleshooting
