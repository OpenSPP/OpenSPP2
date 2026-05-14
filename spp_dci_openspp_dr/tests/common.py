"""Test helpers shared across spp_dci_openspp_dr test cases."""


def get_or_create_uin_code(env):
    """Return the UIN vocabulary code, creating it if absent.

    The system ``urn:openspp:vocab:id-type`` vocabulary has
    UNIQUE(vocabulary_id, code), so only one preset can seed UIN via
    data XML. Tests need access to the code (to tag partner reg_ids)
    regardless of which preset installed it — or whether any did.

    Uses ``get_or_create_local`` which is the supported runtime path
    for adding codes to system vocabularies (ADR-016 country-extension
    pattern). Returns whatever record matches first, marking newly
    created ones with ``is_local=True``.
    """
    return env["spp.vocabulary.code"].get_or_create_local(
        namespace_uri="urn:openspp:vocab:id-type",
        code="UIN",
        display="UIN (Universal Identification Number)",
    )
