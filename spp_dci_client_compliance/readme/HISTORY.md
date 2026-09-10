### 19.0.1.0.2

- fix(security): remove compliance data sources that still hold the old shared
  bearer token on upgrade, refuse to serve any such record from the trigger
  controller, and reject the well-known default token when configured, so
  upgraded or freshly configured databases cannot use the shared credential
  over the unauthenticated trigger routes.
