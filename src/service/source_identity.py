"""Content identities used to transport and apply model-selected source edits."""

import hashlib
import json


def source_hash(source: str) -> str:
    return hashlib.sha256(source.encode("utf-8")).hexdigest()


def sources_fingerprint(sources: dict[str, str]) -> str:
    return source_hash(json.dumps(sources, sort_keys=True))
