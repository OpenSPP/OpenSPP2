# Part of OpenSPP. See LICENSE file for full copyright and licensing details.

# Storage key for the registry access-control setting.
#
# The toggle itself moved to the consolidated Registry Settings section in
# spp_registry (OP#1009), which is why the field and its set_values override are
# gone from here. The key stays: res_partner imports it for enforcement, and the
# central toggle writes this key and spp_farmer_registry's in step, so this
# module's controller reads exactly what it always did (OP#1009 review).
REGISTRY_ADMIN_ONLY_CRUD_PARAM = "spp_starter.registry_admin_only_crud"
