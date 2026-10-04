Getting started
===============

Requirements
------------

PhotoChart requires Python 3.9 or newer. Node.js is needed for the React
frontend. ExifTool is strongly recommended because Pillow cannot read all RAW
and video metadata. PDF documentation additionally requires a TeX distribution
with ``latexmk`` and ``pdflatex``.

Installation
------------

Create an isolated environment and install the project:

.. code-block:: console

   python -m venv .venv
   source .venv/bin/activate
   pip install -e ".[nef,remote,s3,dev,docs]"

The extras are:

``nef``
   RAW/NEF image support.

``remote``
   SFTP support through Paramiko. pCloud API and WebDAV use the standard
   library.

``s3``
   AWS S3 and S3-compatible storage support through Boto3.

``docs``
   Sphinx, the Read the Docs theme, and type-hint rendering.

First local dry-run
-------------------

Copy the supplied example from ``examples/organizer/``:

.. code-block:: console

   cp examples/organizer/organizer.example.yaml organizer.yaml

Set the source and destination to disposable test directories. Then preview:

.. code-block:: console

   pchart organize once organizer.yaml --dry-run

Each output line is JSON and records status, source, proposed destination,
capture-date source, and verification state. If the result is correct, run in
copy mode before enabling move mode:

.. code-block:: console

   pchart organize once organizer.yaml --copy

Database and web application
----------------------------

Create the Django schema and start the backend:

.. code-block:: console

   cp .env.example .env
   python backend/manage.py migrate
   python backend/manage.py runserver

In another terminal:

.. code-block:: console

   npm --prefix frontend install
   npm --prefix frontend run dev

Open the UI at ``http://localhost:5173``. Vite proxies ``/api`` and ``/media`` to
``http://127.0.0.1:8000`` so login uses same-origin session cookies. Keep
``python backend/manage.py runserver`` running on port 8000. Create a user with
``python backend/manage.py createsuperuser`` before signing in.

The Organizer tab displays configurations, dry-run controls, recent jobs, and
operation details. The readiness endpoint is
``http://localhost:8000/api/organizer-health/``.

Recommended rollout
-------------------

#. Test path patterns and metadata selection with ``--dry-run``.
#. Use copy mode on representative images, RAW files, and large videos.
#. Verify destination files independently.
#. Test collisions, missing metadata, network loss, and restart behavior.
#. Enable move mode with one worker.
#. Increase concurrency only if the provider and application both support it.
