"""File-signature cache for incremental pipeline ingest.

Sprint 1 shipped v1 (signature-only). Sprint 2 bumps the schema to v2 so
each cache entry now carries a JSON-serializable per-file payload
alongside the signature. That lets callers (starting with
retail_sales.collect_retail_sales_bundle) skip the Excel re-read for
unchanged files and merge cached per-file aggregates straight into the
final bundle.

The scale problem the Tier 2 fix addresses:
  The pipeline today re-reads every Excel source on every run. At
  current scale (~131 MB data.json from ~200+ Excel files), the pipeline
  takes 2-5 minutes on a healthy machine; with the user's planned
  daily-add trajectory it will grow linearly with history forever.

The Tier 2 approach:
  Before reading a source file, compute a cheap signature (mtime + size).
  Compare against the previous run's cached signature. If the signature
  is unchanged, reuse the cached payload; if changed, re-read and update
  the entry. The merge step assembles per-file payloads into the full
  bundle shape that callers expected before caching existed.

This module owns signature + payload plumbing only. Per-file payload
schema and merge semantics are the caller's concern — the cache is
payload-agnostic.

v1 → v2:
  - Cache file schema bumped. A v1 cache on disk is treated as empty on
    load (safe — we never crash on a stale cache).
  - Each entry in ``cache["files"][path]`` is now
    ``{"signature": <sig_dict>, "payload": <any JSON>}`` instead of the
    flat signature dict.

Design choices:
  - mtime+size default: ~microsecond per file; sufficient when the only
    source of edits is the user re-exporting Excel from their POS.
  - Optional sha256: opt-in for higher confidence; adds ~file-size-bound
    I/O but is the only defense against clock skew or file-copy tricks.
    Callers can pass `include_hash=True` on paths they do not fully
    trust.
  - Cache file is JSON at the project root (gitignored). Malformed /
    missing cache degrades gracefully to "everything changed" — we never
    suppress a re-read based on a broken cache.
  - Optional ``content_fingerprint`` header: callers that want cache
    invalidation when non-file inputs change (e.g. object_mapping,
    duplicate-file policy) can pin a fingerprint. A mismatch on load
    drops the whole cache to empty.
"""

from __future__ import annotations

import hashlib
import json
import os
from dataclasses import asdict, dataclass
from typing import Any, Iterable, Mapping, Optional


CACHE_VERSION = 2
DEFAULT_CACHE_FILENAME = ".pipeline_cache.json"
_HASH_CHUNK_SIZE = 1024 * 1024  # 1 MB


@dataclass(frozen=True)
class FileSignature:
    """Cheap fingerprint for a source file.

    `sha256` is None when the signature was computed in fast mode
    (mtime+size only). Two signatures compare equal only on fields that
    are populated in both — a fast-mode signature can therefore match a
    full-mode signature that has the same mtime+size. Callers that
    require hash-level confidence must pass `include_hash=True` on both
    ends of the comparison.
    """

    path: str
    mtime_ns: int
    size: int
    sha256: Optional[str] = None

    def matches(self, other: "FileSignature") -> bool:
        if self.size != other.size or self.mtime_ns != other.mtime_ns:
            return False
        if self.sha256 is not None and other.sha256 is not None:
            return self.sha256 == other.sha256
        return True

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, payload: Mapping) -> "FileSignature":
        return cls(
            path=str(payload.get("path") or ""),
            mtime_ns=int(payload.get("mtime_ns") or 0),
            size=int(payload.get("size") or 0),
            sha256=(
                str(payload["sha256"])
                if payload.get("sha256") is not None
                else None
            ),
        )


def _sha256_of_file(path: str) -> str:
    hasher = hashlib.sha256()
    with open(path, "rb") as handle:
        while True:
            chunk = handle.read(_HASH_CHUNK_SIZE)
            if not chunk:
                break
            hasher.update(chunk)
    return hasher.hexdigest()


def compute_file_signature(
    path: str, *, include_hash: bool = False
) -> FileSignature:
    """Return a FileSignature for `path`.

    Raises FileNotFoundError if the path does not exist (caller decides
    whether that means "deleted" or "not a tracked source yet").
    """
    stat = os.stat(path)
    sha = _sha256_of_file(path) if include_hash else None
    return FileSignature(
        path=os.path.normpath(path),
        mtime_ns=int(stat.st_mtime_ns),
        size=int(stat.st_size),
        sha256=sha,
    )


def empty_cache(content_fingerprint: Optional[str] = None) -> dict:
    """Return a fresh empty cache scaffold."""
    cache: dict = {"version": CACHE_VERSION, "files": {}}
    if content_fingerprint is not None:
        cache["content_fingerprint"] = str(content_fingerprint)
    return cache


def load_cache(
    cache_path: str, *, content_fingerprint: Optional[str] = None
) -> dict:
    """Load the on-disk cache or return an empty scaffold.

    Never raises for a missing / unreadable / malformed cache. The whole
    point of a cache is to be disposable — a bad cache means "treat every
    file as changed", never "crash the pipeline".

    When ``content_fingerprint`` is passed and does not match the stored
    fingerprint, the cache is dropped (treated as empty). This is how
    callers invalidate when non-file inputs change.
    """
    empty = empty_cache(content_fingerprint=content_fingerprint)
    if not os.path.exists(cache_path):
        return empty
    try:
        with open(cache_path, "r", encoding="utf-8") as handle:
            payload = json.load(handle)
    except (OSError, json.JSONDecodeError):
        return empty
    if not isinstance(payload, dict):
        return empty
    version = payload.get("version")
    files = payload.get("files")
    if version != CACHE_VERSION or not isinstance(files, dict):
        return empty
    if content_fingerprint is not None:
        stored_fp = payload.get("content_fingerprint")
        if stored_fp != content_fingerprint:
            return empty
    result: dict = {"version": CACHE_VERSION, "files": {}}
    for key, raw_entry in files.items():
        if not isinstance(raw_entry, Mapping):
            continue
        signature_payload = raw_entry.get("signature")
        if not isinstance(signature_payload, Mapping):
            continue
        result["files"][key] = {
            "signature": dict(signature_payload),
            "payload": raw_entry.get("payload"),
        }
    if content_fingerprint is not None:
        result["content_fingerprint"] = str(content_fingerprint)
    elif "content_fingerprint" in payload:
        result["content_fingerprint"] = str(payload["content_fingerprint"])
    return result


def save_cache(cache_path: str, cache: Mapping) -> None:
    """Atomically write the cache to disk (temp + rename)."""
    tmp_path = cache_path + ".tmp"
    os.makedirs(os.path.dirname(cache_path) or ".", exist_ok=True)
    with open(tmp_path, "w", encoding="utf-8") as handle:
        json.dump(cache, handle, ensure_ascii=False, indent=2, sort_keys=True)
    os.replace(tmp_path, cache_path)


def _entry_signature(cache: Mapping, key: str) -> Optional[dict]:
    files = cache.get("files") if isinstance(cache, Mapping) else None
    if not isinstance(files, Mapping):
        return None
    entry = files.get(key)
    if not isinstance(entry, Mapping):
        return None
    sig = entry.get("signature")
    if isinstance(sig, Mapping):
        return dict(sig)
    return None


def file_has_changed(
    path: str, cache: Mapping, *, include_hash: bool = False
) -> bool:
    """True if the file on disk differs from the cached signature.

    Treats any of {missing from cache, missing on disk, signature
    mismatch, IO error} as "changed" — the safe default is always
    "re-read".
    """
    key = os.path.normpath(path)
    cached_sig_payload = _entry_signature(cache, key)
    if cached_sig_payload is None:
        return True
    try:
        current = compute_file_signature(path, include_hash=include_hash)
    except OSError:
        return True
    try:
        cached = FileSignature.from_dict(cached_sig_payload)
    except (TypeError, ValueError):
        return True
    return not current.matches(cached)


def get_payload(cache: Mapping, path: str) -> Any:
    """Return the cached payload for ``path`` or None if absent."""
    key = os.path.normpath(path)
    files = cache.get("files") if isinstance(cache, Mapping) else None
    if not isinstance(files, Mapping):
        return None
    entry = files.get(key)
    if not isinstance(entry, Mapping):
        return None
    return entry.get("payload")


def put_entry(
    cache: dict, path: str, signature: FileSignature, payload: Any
) -> None:
    """Write a {signature, payload} entry into the mutable cache dict."""
    if not isinstance(cache, dict):
        raise TypeError("cache must be a mutable dict")
    files = cache.setdefault("files", {})
    if not isinstance(files, dict):
        cache["files"] = files = {}
    key = os.path.normpath(path)
    files[key] = {"signature": signature.to_dict(), "payload": payload}


def drop_entry(cache: dict, path: str) -> None:
    """Remove an entry (e.g. when the file no longer exists on disk)."""
    files = cache.get("files") if isinstance(cache, dict) else None
    if not isinstance(files, dict):
        return
    files.pop(os.path.normpath(path), None)


def build_new_cache(
    paths: Iterable[str],
    *,
    include_hash: bool = False,
    content_fingerprint: Optional[str] = None,
) -> dict:
    """Build a fresh cache payload (signatures only, no payloads).

    Paths that fail to stat are silently skipped — they will be treated
    as "changed" on the next run (since they will be absent from the
    cache). This is the right behavior: a file we could not read cannot
    be "unchanged".
    """
    files: dict = {}
    for path in paths:
        try:
            sig = compute_file_signature(path, include_hash=include_hash)
        except OSError:
            continue
        files[sig.path] = {"signature": sig.to_dict(), "payload": None}
    cache: dict = {"version": CACHE_VERSION, "files": files}
    if content_fingerprint is not None:
        cache["content_fingerprint"] = str(content_fingerprint)
    return cache
