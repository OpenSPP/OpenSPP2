OpenSPP Notary Evidence Demo
============================

This addon seeds a runnable Registry Notary demonstration against the hosted
Registry Lab demo environment. It creates:

* two Notary data providers:

  * ``Registry Lab Civil Notary`` at
    ``https://civil-notary.lab.registrystack.org``
  * ``Registry Lab Shared Eligibility Notary`` at
    ``https://shared-eligibility-notary.lab.registrystack.org``

* four Notary claims and CEL variables
* ten individual registrants with national IDs ``NID-1001`` through
  ``NID-1010``
* three CEL-driven programs
* a one-click demo runner under ``Registry Notary Demo``

The expected happy-path demo result is ``30 passed, 0 failed, 0 errors,
0 skipped``.

The seeded program eligibility expressions use the explicit Notary evidence
syntax:

::

   r.evidence.registry_lab_civil_notary.person_is_alive == true
   r.evidence.registry_lab_shared_eligibility_notary.eligible_for_combined_support == true
   r.evidence.registry_lab_shared_eligibility_notary.health_service_available == true

Prerequisites
-------------

The hosted Registry Lab at ``https://lab.registrystack.org`` must be reachable.
The addon seeds public demo credentials for the hosted lab by default. Those
credentials only reach synthetic demo data, never a real or production system.

Install the OpenSPP Demo Addon
-------------------------------

In the OpenSPP developer environment, start or update Odoo as usual, then
install ``spp_notary_evidence_demo`` from Apps:

1. Open OpenSPP.
2. Go to ``Apps``.
3. Update the apps list if the module is new in the checkout.
4. Search for ``OpenSPP Notary Evidence Demo``.
5. Click ``Install``.

If local override values are present in Odoo system parameters or in the
OpenSPP process environment during installation, the addon uses those values
instead of the hosted defaults.

For local ``registry-lab`` development, one practical pattern is to export the
lab credentials and URLs before starting the OpenSPP container or before running
a module install command:

::

   cd /Users/jeremi/Projects/204-programs-delivery-commons/apps/registry-lab
   set -a
   source .env
   export REGISTRY_LAB_CIVIL_NOTARY_URL=http://host.docker.internal:4321
   export REGISTRY_LAB_SHARED_NOTARY_URL=http://host.docker.internal:4323
   set +a

Then start or install OpenSPP from the same shell environment.

Configure Provider Credentials
------------------------------

Fresh installs are configured automatically. To override them in the UI:

1. Go to ``Notary Evidence > Configuration > Data Providers``.
2. Open ``Registry Lab Civil Notary``.
3. Confirm:

   * URL: ``https://civil-notary.lab.registrystack.org``
   * Auth Type: ``API Key``
   * API Key Header: ``x-api-key``
   * API Key: hosted demo key from ``https://lab.registrystack.org``, or local
     ``CIVIL_EVIDENCE_CLIENT_TOKEN`` when overriding to a local lab
   * Subject ID Type: ``National ID``

4. Open ``Registry Lab Shared Eligibility Notary``.
5. Confirm:

   * URL: ``https://shared-eligibility-notary.lab.registrystack.org``
   * Auth Type: ``Bearer``
   * Bearer Token: hosted demo token from ``https://lab.registrystack.org``, or
     local ``SHARED_EVIDENCE_CLIENT_BEARER`` when overriding to a local lab
   * Subject ID Type: ``National ID``

Keep the default purpose URL unless the lab fixture changes:
``https://demo.example.gov/purpose/decentralized-evidence-demo``.

Run the Demo
------------

1. Go to ``Notary Evidence > Registry Notary Demo > Run Demo``.
2. Open the generated run if it does not open automatically.
3. Check the counters and result lines.

A healthy lab-backed run shows:

* ``30 passed``
* ``0 failed``
* ``0 errors``
* ``0 skipped``

The seeded matrix is:

* ``Registry Lab Living Person Grant``:

  * ``NID-1001``, ``NID-1002``, ``NID-1004``, ``NID-1005``,
    ``NID-1006``, ``NID-1007``, ``NID-1008``, ``NID-1009``, and
    ``NID-1010`` eligible
  * ``NID-1003`` ineligible

* ``Registry Lab Combined Support``:

  * ``NID-1001``, ``NID-1004``, ``NID-1006``, and ``NID-1008`` eligible
  * ``NID-1002``, ``NID-1003``, ``NID-1005``, ``NID-1007``,
    ``NID-1009``, and ``NID-1010`` ineligible

* ``Registry Lab Health Access Support``:

  * ``NID-1001``, ``NID-1003``, ``NID-1004``, ``NID-1006``,
    ``NID-1007``, ``NID-1008``, and ``NID-1009`` eligible
  * ``NID-1002``, ``NID-1005``, and ``NID-1010`` ineligible

What to Show in a Demo
----------------------

Use this short flow when presenting:

1. Show ``Notary Evidence > Claims`` and the generated CEL evidence path, for
   example ``r.evidence.registry_lab_civil_notary.person_is_alive``.
2. Open one seeded program and show that eligibility is a normal CEL expression
   backed by a Notary claim.
3. Click ``Test Expression`` on the eligibility manager. A healthy lab shows a
   success notification, for example ``7 beneficiaries match this
   expression`` for the health access program.
4. Run ``Registry Notary Demo > Run Demo``.
5. Open a result row and show:

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

Hosted lab connection errors
~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Check ``https://lab.registrystack.org`` first. If the lab is being redeployed,
the Notary hosts can temporarily return HTTP 503. Retry once the lab status page
shows the Notary services are up.

Errors connecting to a local lab
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

If you override to local URLs, ``host.docker.internal`` assumes OpenSPP runs in
Docker on the host machine. If OpenSPP is not running in Docker, change the
provider URLs to ``http://127.0.0.1:4321`` and ``http://127.0.0.1:4323``.

Batch evaluation returns HTTP 501
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Some lab Notary claims intentionally do not support batch evaluation yet.
OpenSPP falls back to single-subject ``/v1/evaluations`` for those claims. This
is expected when the final demo result still has no failures or errors.

Notary subject was not found
~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Some local registrants may have a National ID that the current lab fixtures do
not expose through a specific Notary source. OpenSPP treats upstream
subject-not-found as no evidence for that registrant and continues evaluating
the rest of the preview or demo run.

Wrong result counts
~~~~~~~~~~~~~~~~~~~

For hosted-lab demos, check ``https://lab.registrystack.org`` first. For local
lab overrides, run:

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

For a live smoke, run the demo from the UI. The run record is persisted in
``spp.notary.demo.run`` with one
``spp.notary.demo.result`` row per program/persona decision.
