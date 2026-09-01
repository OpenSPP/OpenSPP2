# OpenSPP Child Benefit

Birth-order based child benefit programme support:

- **Family birth order**: computes each child's rank within the mother's
  sibling sequence from family-group membership (citizenship-by-descent only,
  individual ranks for multiple births, officer determination queue when a
  multiple-birth sequence is not recorded).
- **Scheduled entitlements**: generates the full benefit schedule up front
  (entry/exit month proration around a configurable day-of-month cut-off) and
  materializes installments into standard entitlements each cycle.
- **Bank file export**: renders each payment batch as a CSV disbursement file
  attached to the batch, with payments issued to the family's registered payee.
