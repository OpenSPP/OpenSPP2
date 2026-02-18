def get_param(env, key, default=None):
    return env["ir.config_parameter"].sudo().get_param(key, default)  # nosemgrep: odoo-sudo-without-context


def get_branding_config(env):
    return {
        "spp_system_name": get_param(env, "spp.system.name", "OpenSPP Platform"),
        "spp_documentation_url": get_param(env, "spp.documentation.url", "https://docs.openspp.org"),
        "spp_support_url": get_param(env, "spp.support.url", "https://openspp.org"),
        "is_spp_show_powered_by": get_param(env, "spp.show.powered_by", "True") == "True",
        "is_spp_telemetry_enabled": get_param(env, "spp.telemetry.enabled", "True") == "True",
        "spp_telemetry_endpoint": get_param(env, "spp.telemetry.endpoint", "https://telemetry.openspp.org"),
    }


def version_info_payload(env):
    system_name = get_param(env, "spp.system.name", "OpenSPP Platform")
    return {
        "server_version": system_name,
        "server_serie": "19.0",
        "protocol_version": 1,
    }


def telemetry_payload(env):
    enabled = get_param(env, "spp.telemetry.enabled", "True") == "True"
    if not enabled:
        return {"status": "disabled", "message": "Telemetry disabled"}
    endpoint = get_param(env, "spp.telemetry.endpoint", "https://telemetry.openspp.org")
    return {
        "status": "redirected",
        "endpoint": endpoint,
        "message": "Telemetry redirected to OpenSPP",
    }
