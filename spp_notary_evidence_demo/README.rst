OpenSPP Notary Evidence Demo
============================

Seeds demo Registry Notary providers, sample registrants, and CEL-driven
programs aligned with the local ``registry-lab`` stack.

The module uses these defaults from inside OpenSPP Docker containers:

* Civil Notary: ``http://host.docker.internal:4321``
* Shared Eligibility Notary: ``http://host.docker.internal:4323``

If the lab tokens are present in the OpenSPP environment during install, they
are copied into the demo provider records:

* ``CIVIL_EVIDENCE_CLIENT_TOKEN``
* ``SHARED_EVIDENCE_CLIENT_BEARER``

Without those values, the providers, claims, variables, registrants, and
programs are still created; add the credentials on the provider records before
running live evaluation.
