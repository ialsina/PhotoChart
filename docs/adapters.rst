Storage adapters
================

All adapters implement :class:`photochart.organizer.storage.StorageAdapter`.
Capabilities are descriptive; callers must not infer atomic behavior merely
because an adapter exposes ``move``.

Local filesystem, NAS, and pCloud Drive
---------------------------------------

Use ``local`` for local disks and mounted SMB, NFS, or NAS paths:

.. code-block:: yaml

   adapter:
     type: local

For pCloud Drive, restrict operations to its mount:

.. code-block:: yaml

   adapter:
     type: pcloud_drive
     mount_root: /mnt/pCloud

The pCloud Drive adapter checks mount readability and rejects paths outside the
configured root. It conservatively reports moves as non-atomic because a
virtual filesystem may translate them into remote operations.

pCloud API
----------

.. code-block:: yaml

   adapter:
     type: pcloud_api
     endpoint: https://api.pcloud.com
     access_token_env: PCLOUD_ACCESS_TOKEN

The adapter uses recursive folder listing, object ``stat``, server-side copy or
rename, and temporary downloads for metadata. Select the API endpoint matching
the account's data region.

WebDAV
------

.. code-block:: yaml

   adapter:
     type: webdav
     endpoint: https://dav.example.test
     username_env: WEBDAV_USERNAME
     password_env: WEBDAV_PASSWORD

Discovery uses recursive depth-one ``PROPFIND`` requests. Directories use
``MKCOL``; transfers use ``COPY`` and ``MOVE``. A 404 is distinct from
authentication, permission, and backend availability errors.

Nextcloud
---------

.. code-block:: yaml

   adapter:
     type: nextcloud
     endpoint: https://cloud.example.test
     username_env: NEXTCLOUD_USERNAME
     password_env: NEXTCLOUD_PASSWORD

Nextcloud shares WebDAV behavior and constructs the standard
``/remote.php/dav/files/USERNAME`` endpoint.

SFTP
----

.. code-block:: yaml

   adapter:
     type: sftp
     host: photos.example.test
     port: 22
     username_env: SFTP_USERNAME
     key_filename: /etc/photochart/id_ed25519
     known_hosts: /etc/ssh/ssh_known_hosts

Password authentication can use ``password_env``. Unknown host keys are
rejected; provide system or explicit known-host data. Rename is server-side,
while copy streams through a ``.partial`` object before final rename.

S3-compatible storage
---------------------

.. code-block:: yaml

   adapter:
     type: s3
     bucket: photo-archive
     region_name: eu-west-1

For another S3-compatible service, add ``endpoint_url``. Standard AWS
credential resolution is preferred. Explicit environment references are also
available:

.. code-block:: yaml

   adapter:
     type: s3
     bucket: photo-archive
     endpoint_url: https://objects.example.test
     access_key_id_env: PHOTO_S3_ACCESS_KEY
     secret_access_key_env: PHOTO_S3_SECRET_KEY

S3 has prefixes rather than directories, so directory creation is a no-op. A
move performs managed copy, checks object size, verifies a provider checksum
when available or streams SHA-256 otherwise, and deletes the source only after
successful verification.

Capability summary
------------------

================= =========== ================== ============== ==============
Adapter           Local path  Server-side move   Object storage Optional extra
================= =========== ================== ============== ==============
local             yes         filesystem         no             none
pcloud_drive      yes         conservative/no    no             none
pcloud_api        no          yes                no             none
webdav/nextcloud  no          yes                no             none
sftp              no          yes                no             ``remote``
s3                no          copy/delete        yes            ``s3``
================= =========== ================== ============== ==============

Provider acceptance tests
-------------------------

For every production adapter:

#. create a dedicated test prefix;
#. upload one image with known metadata;
#. run dry-run and verify the proposed path;
#. copy and compare content independently;
#. test an identical collision and a different-content collision;
#. test a large video and interrupted connectivity;
#. run the same command twice to verify idempotency;
#. enable move mode only after confirming source deletion semantics.

The executable contract suite is opt-in:

.. code-block:: console

   export PHOTOCHART_ACCEPTANCE_PROVIDER=s3
   export PHOTOCHART_ACCEPTANCE_CONFIG=/secure/s3-acceptance.yaml
   export PHOTOCHART_ACCEPTANCE_SOURCE_OBJECT=/acceptance/fixture.jpg
   export PHOTOCHART_ACCEPTANCE_PREFIX=/acceptance/photochart
   python -m pytest tests/acceptance -m integration --no-cov

The configured source object is never deleted. The suite copies it into a
unique run prefix, byte-verifies it, exercises verified move semantics, and
requires cleanup to succeed. The manual/scheduled provider workflow uses the
same contract. Unattended move mode must remain disabled for a provider until
its credentialed workflow is green.
