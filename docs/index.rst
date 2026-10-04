PhotoChart and Unified Photo Organizer
======================================

PhotoChart is a photo and video catalog with a storage-independent organizer.
It can discover uploaded media, determine capture dates, classify files into
configurable paths, resolve collisions, verify transfers, and retain an audit
history through its Django application.

The organizer supports local filesystems, NAS mounts, pCloud Drive, the pCloud
API, WebDAV, Nextcloud, SFTP, and S3-compatible object storage.

.. warning::

   Start with dry-run and copy mode against test data. Do not enable destructive
   move processing for a remote provider until its acceptance tests have passed.

.. toctree::
   :maxdepth: 2
   :caption: User guide

   getting_started
   configuration
   cli
   adapters
   operations

.. toctree::
   :maxdepth: 2
   :caption: Architecture and integration

   architecture
   django_api
   compose_host_postgres
   deployment
   development
   reference

Indices
-------

* :ref:`genindex`
* :ref:`modindex`
* :ref:`search`
