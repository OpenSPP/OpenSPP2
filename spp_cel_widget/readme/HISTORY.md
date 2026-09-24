### 19.0.2.0.1

- fix: import the tours' stepUtils from the Odoo 19 path @web_tour/tour_utils and drop the pre-18
  `test` tour key that Odoo 19 rejects, so web.assets_tests loads without module loader errors and
  no longer fails every backend tour (#551)

### 19.0.2.0.0

- Initial migration to OpenSPP2
