from enum import StrEnum


class OAuthIdentityProviderType(StrEnum):
    KEYCLOAK = "keycloak"
    GOOGLE = "google"