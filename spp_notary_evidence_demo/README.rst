OpenSPP Notary Evidence Demo
============================

This addon seeds a runnable Registry Notary demonstration for the local
``registry-lab`` stack. It creates:

* two Notary data providers:

  * ``Registry Lab Civil Notary`` at ``http://host.docker.internal:4321``
  * ``Registry Lab Shared Eligibility Notary`` at
    ``http://host.docker.internal:4323``

* four Notary claims and CEL variables
* three individual registrants with national IDs ``NID-1001`` through
  ``NID-1003``
* three CEL-driven programs
* a one-click demo runner under ``Registry Notary Demo``

The expected happy-path demo result is ``9 passed, 0 failed, 0 errors,
0 skipped``.

Prerequisites
-------------

Start ``registry-lab`` first:

::

   cd /Users/jeremi/Projects/204-programs-delivery-commons/apps/registry-lab
   just setup
   just generate
   just build
   just up
   just smoke
   just notary-client

``just generate`` writes the local ``.env`` file used by the lab. The demo
addon needs these values from that file:

* ``CIVIL_EVIDENCE_CLIENT_TOKEN`` for the civil Notary API-key provider
* ``SHARED_EVIDENCE_CLIENT_BEARER`` for the shared eligibility bearer provider
* ``REGISTRY_NOTARY_AUDIT_HASH_SECRET`` for keyed subject hashes, optional
  because the addon has a demo default

Install the OpenSPP Demo Addon
-------------------------------

In the OpenSPP developer environment, start or update Odoo as usual, then
install ``spp_notary_evidence_demo`` from Apps:

1. Open OpenSPP.
2. Go to ``Apps``.
3. Update the apps list if the module is new in the checkout.
4. Search for ``OpenSPP Notary Evidence Demo``.
5. Click ``Install``.

If the lab tokens are present in the OpenSPP process environment during
installation, the addon copies them into the seeded provider records. If they
are not present, the provider, claim, variable, registrant, and program records
are still created, but live evaluation is skipped until credentials are added.

For local developer installs, one practical pattern is to export the lab
credentials before starting the OpenSPP container or before running a module
install command:

::

   cd /Users/jeremi/Projects/204-programs-delivery-commons/apps/registry-lab
   set -a
   source .env
   set +a

Then start or install OpenSPP from the same shell environment.

Configure Provider Credentials
------------------------------

If the credentials were not copied during install, configure them in the UI:

1. Go to ``Notary Evidence > Configuration > Data Providers``.
2. Open ``Registry Lab Civil Notary``.
3. Confirm:

   * URL: ``http://host.docker.internal:4321``
   * Auth Type: ``API Key``
   * API Key Header: ``x-api-key``
   * API Key: value of ``CIVIL_EVIDENCE_CLIENT_TOKEN``
   * Subject ID Type: ``National ID``

4. Open ``Registry Lab Shared Eligibility Notary``.
5. Confirm:

   * URL: ``http://host.docker.internal:4323``
   * Auth Type: ``Bearer``
   * Bearer Token: value of ``SHARED_EVIDENCE_CLIENT_BEARER``
   * Subject ID Type: ``National ID``

Keep the default purpose URL unless the lab fixture changes:
``https://demo.example.gov/purpose/decentralized-evidence-demo``.

Run the Demo
------------

1. Go to ``Notary Evidence > Registry Notary Demo > Run Demo``.
2. Open the generated run if it does not open automatically.
3. Check the counters and result lines.

A healthy lab-backed run shows:

* ``9 passed``
* ``0 failed``
* ``0 errors``
* ``0 skipped``

The seeded matrix is:

* ``Registry Lab Living Person Grant``:

  * ``NID-1001`` eligible
  * ``NID-1002`` eligible
  * ``NID-1003`` ineligible

* ``Registry Lab Combined Support``:

  * ``NID-1001`` eligible
  * ``NID-1002`` ineligible
  * ``NID-1003`` ineligible

* ``Registry Lab Health Access Support``:

  * ``NID-1001`` eligible
  * ``NID-1002`` ineligible
  * ``NID-1003`` eligible

What to Show in a Demo
----------------------

Use this short flow when presenting:

1. Show ``Notary Evidence > Claims`` and the generated CEL accessors, for
   example ``notary_registry_lab_civil_notary_person_is_alive``.
2. Open one seeded program and show that eligibility is a normal CEL expression
   backed by a Notary claim.
3. Run ``Registry Notary Demo > Run Demo``.
4. Open a result row and show:

   * persona and national ID
   * program
   * expected vs actual eligibility
   * CEL expression used for the decision

This demonstrates that OpenSPP evaluates ordinary program eligibility while the
facts come from Registry Notary services instead of local registry columns.

Troubleshooting
---------------

Skipped results
~~~~~~~~~~~~~~~

``Skipped`` usually means the provider credential is missing. Add the missing
API key or bearer token on the provider record and run the demo again.

Errors connecting to ``host.docker.internal``
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

The seeded URLs assume OpenSPP runs in Docker on the host machine. If OpenSPP is
not running in Docker, change the provider URLs to ``http://127.0.0.1:4321`` and
``http://127.0.0.1:4323``.

Batch evaluation returns HTTP 501
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Some lab Notary claims intentionally do not support batch evaluation yet.
OpenSPP falls back to single-subject ``/v1/evaluations`` for those claims. This
is expected when the final demo result still has no failures or errors.

Wrong result counts
~~~~~~~~~~~~~~~~~~~

Run the lab checks first:

::

   cd /Users/jeremi/Projects/204-programs-delivery-commons/apps/registry-lab
   just ps
   just smoke
   just notary-client

Then confirm the two provider URLs and credentials in OpenSPP.

Useful Developer Checks
-----------------------

From the OpenSPP checkout:

::

   ./spp test spp_notary_client
   ./spp test spp_notary_evidence
   ./spp test spp_notary_evidence_demo

For a live smoke, start ``registry-lab`` and run the demo from the UI. The run
record is persisted in ``spp.notary.demo.run`` with one
``spp.notary.demo.result`` row per program/persona decision.
