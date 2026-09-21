### 19.0.2.0.1

- test(metric): make the tests hold on a database that has `spp_indicator` installed, the only place they run at all (they skip without `spp.indicator`, so they had never executed before the full-stack CI). The base-model tests create their `spp.cel.variable` with the fields the model has — `cel_expression` and the required `cel_accessor`, no `label`, which only `spp_studio` adds — and the category test uses a code no data file claims, since `spp_indicator` seeds `demographics`. No behaviour change (#443)

### 19.0.2.0.0

- Initial migration to OpenSPP2
