"""Canonical identifier helper."""


def split_canonical_id(canonical_id: str) -> tuple[str, str, str]:
    parts = canonical_id.split(":", 2)
    if len(parts) != 3:
        raise ValueError(f"invalid canonical id: {canonical_id}")
    return parts[0], parts[1], parts[2]
