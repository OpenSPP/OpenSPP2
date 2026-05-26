# SR + CRVS — Federated Snapshot

Live snapshot of the 10 demo identifiers shared by the OpenG2P + OpenCRVS teams for the
post-event recording. SR data fetched via DCI search-sync from OpenG2P's playground
(`partner-nsr.play.openg2p.org`); CRVS death column fetched via DCI from OpenCRVS's
playground (`dci-crvs-api.farajaland-integration.opencrvs.dev`).

Captured on 2026-05-26.

Note: OpenG2P moved its demo UINs from the synthetic `IND-NSR-XXXX` format to 10-digit
numeric identifiers aligned with OpenCRVS, so the same UIN resolves to the same person
across both registries. See the cross-registry matrix in `SPDCI_DEMO_BRIEFING.md` for
the SR↔CRVS overlap.

| #   | UIN          | Name           | income_level | In CRVS death? |
| --- | ------------ | -------------- | ------------ | -------------- |
| 1   | `8579520716` | Tomasz Novak   | low          | ✅ yes         |
| 2   | `3253492082` | Sofia Petrovic | low          | —              |
| 3   | `9475380352` | Daniel Kauri   | low          | ✅ yes         |
| 4   | `9726938790` | Leila Haddar   | low          | —              |
| 5   | `6985017629` | Malik Adeyemi  | medium       | —              |
| 6   | `2140239450` | Priya Menon    | medium       | —              |
| 7   | `2195415820` | Omar El-Hadi   | low          | —              |
| 8   | `4364503413` | Aiko Tanabe    | high         | —              |
| 9   | `3184198562` | Rafael Duarte  | low          | ✅ yes         |
| 10  | `8794017267` | Elna Voss      | low          | —              |

## Expected eligibility outcomes

For a rule like `is_poor == "low" && is_deceased == false` (SR + CRVS, no DR), 4 of 10
registrants enroll: Sofia Petrovic, Leila Haddar, Omar El-Hadi, Elna Voss. The other 6
fail on at least one predicate (3 deceased per CRVS, 3 with income not equal to `"low"`
per SR).
