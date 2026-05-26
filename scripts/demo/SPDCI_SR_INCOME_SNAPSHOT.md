# SR + DR + CRVS — Federated Snapshot

Live snapshot of the 10 demo identifiers shared by the OpenG2P + OpenCRVS teams for the
post-event recording, with the OpenSPP-DR disability status pulled from the remote demo
DR for cross-registry context.

Sources, fetched via DCI search-sync on 2026-05-26:

- **SR** — OpenG2P playground at `partner-nsr.play.openg2p.org` (no auth)
- **DR** — OpenSPP-DR demo at `openspp-dci-demo-dr.genete.acn.fr` (bearer)
- **CRVS** — OpenCRVS Farajaland at `dci-crvs-api.farajaland-integration.opencrvs.dev`
  (OAuth2)

Note: OpenG2P moved its demo UINs from the synthetic `IND-NSR-XXXX` format to 10-digit
numeric identifiers aligned with OpenCRVS, so the same UIN resolves to the same person
across all three registries.

| #   | UIN          | Name           | income_level | has_disability (DR) | In CRVS death? |
| --- | ------------ | -------------- | ------------ | ------------------- | -------------- |
| 1   | `8579520716` | Tomasz Novak   | low          | **True**            | ✅ yes         |
| 2   | `3253492082` | Sofia Petrovic | low          | **True**            | —              |
| 3   | `9475380352` | Daniel Kauri   | low          | **True**            | ✅ yes         |
| 4   | `9726938790` | Leila Haddar   | low          | False               | —              |
| 5   | `6985017629` | Malik Adeyemi  | medium       | False               | —              |
| 6   | `2140239450` | Priya Menon    | medium       | False               | —              |
| 7   | `2195415820` | Omar El-Hadi   | low          | **True**            | —              |
| 8   | `4364503413` | Aiko Tanabe    | high         | False               | —              |
| 9   | `3184198562` | Rafael Duarte  | low          | False               | ✅ yes         |
| 10  | `8794017267` | Elna Voss      | low          | **True**            | —              |

## Expected eligibility outcomes

**SR + CRVS rule** (`is_poor == "low" && is_deceased == false`): 4 of 10 enroll — Sofia
Petrovic, Leila Haddar, Omar El-Hadi, Elna Voss. The other 6 fail on at least one
predicate (3 deceased per CRVS, 3 with income not equal to `"low"` per SR).

**Full SR + DR + CRVS rule**
(`has_disability == true && is_poor == "low" && is_deceased == false`): 3 of 10 enroll —
Sofia Petrovic, Omar El-Hadi, Elna Voss. Tomasz Novak and Daniel Kauri are disabled and
poor but registered as deceased in CRVS; the other 5 fail on disability or income.

**DR-only sanity** (`has_disability == true`): 5 of 10 — Tomasz Novak, Sofia Petrovic,
Daniel Kauri, Omar El-Hadi, Elna Voss.
