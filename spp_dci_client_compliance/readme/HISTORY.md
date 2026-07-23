### 19.0.1.0.2

- fix(security): remove compliance data sources that still hold the old shared
  bearer token on upgrade, and refuse to serve any such record from the trigger
  controller, so upgraded databases cannot re-use the well-known credential over
  the unauthenticated trigger routes.
