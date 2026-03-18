import jwt

from .oauth_exception import OpenSPPOAuthJWTException

JWT_ALGORITHM = "RS256"


def get_private_key(env):
    """
    Retrieves the OAuth private key from Odoo's system parameters.

    :param env: The Odoo environment.
    :return: The private key as a string.
    :raises OpenSPPOAuthJWTException: If the private key is not configured.
    """
    # nosemgrep: odoo-sudo-without-context - system parameter access requires sudo
    private_key = env["ir.config_parameter"].sudo().get_param("spp_oauth.oauth_private_key")
    if not private_key:
        raise OpenSPPOAuthJWTException("OAuth private key not configured in settings.")
    return private_key


def get_public_key(env):
    """
    Retrieves the OAuth public key from Odoo's system parameters.

    :param env: The Odoo environment.
    :return: The public key as a string.
    :raises OpenSPPOAuthJWTException: If the public key is not configured.
    """
    # nosemgrep: odoo-sudo-without-context - system parameter access requires sudo
    public_key = env["ir.config_parameter"].sudo().get_param("spp_oauth.oauth_public_key")
    if not public_key:
        raise OpenSPPOAuthJWTException("OAuth public key not configured in settings.")
    return public_key


def calculate_signature(env, header, payload):
    """
    Calculates a JWT signature.

    :param env: The Odoo environment.
    :param header: The JWT header.
    :param payload: The JWT payload.
    :return: The encoded JWT.
    """

    private_key = get_private_key(env)
    return jwt.encode(headers=header, payload=payload, key=private_key, algorithm=JWT_ALGORITHM)


def verify_and_decode_signature(env, access_token):
    """
    Verifies and decodes a JWT access token.

    :param env: The Odoo environment.
    :param access_token: The JWT to verify and decode.
    :return: The decoded payload.
    :raises OpenSPPOAuthJWTException: If verification fails or for any other JWT error.
    """
    public_key = get_public_key(env)
    try:
        return jwt.decode(access_token, key=public_key, algorithms=[JWT_ALGORITHM])
    except jwt.exceptions.PyJWTError as e:
        raise OpenSPPOAuthJWTException(str(e)) from e
