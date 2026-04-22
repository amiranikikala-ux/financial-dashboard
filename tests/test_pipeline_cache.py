"""Unit tests for dashboard_pipeline.pipeline_cache.

Sprint 1 of Tier 2 (incremental ingest): pins the file-signature +
cache-load/save + file_has_changed contract so Sprint 2 (retail_sales
integration) can build on a tested foundation. No pipeline integration
is exercised here — that comes in the next sprint.
"""

from __future__ import annotations

import json
import os

import pytest

from dashboard_pipeline.pipeline_cache import (
    CACHE_VERSION,
    FileSignature,
    build_new_cache,
    compute_file_signature,
    file_has_changed,
    load_cache,
    save_cache,
)


# ---------------------------------------------------------------------------
# compute_file_signature
# ---------------------------------------------------------------------------

def test_compute_signature_populates_mtime_size_path(tmp_path):
    f = tmp_path / "sample.txt"
    f.write_text("hello")
    sig = compute_file_signature(str(f))
    assert sig.path == os.path.normpath(str(f))
    assert sig.size == 5
    assert sig.mtime_ns > 0
    assert sig.sha256 is None


def test_compute_signature_fills_hash_when_requested(tmp_path):
    f = tmp_path / "sample.txt"
    f.write_text("hello")
    sig = compute_file_signature(str(f), include_hash=True)
    # sha256("hello") = 2cf24dba5fb0a30e26e83b2ac5b9e29e1b161e5c1fa7425e73043362938b9824
    assert sig.sha256 == (
        "2cf24dba5fb0a30e26e83b2ac5b9e29e1b161e5c1fa7425e73043362938b9824"
    )


def test_compute_signature_raises_on_missing_path(tmp_path):
    with pytest.raises(FileNotFoundError):
        compute_file_signature(str(tmp_path / "does_not_exist.txt"))


# ---------------------------------------------------------------------------
# FileSignature.matches
# ---------------------------------------------------------------------------

def test_signature_matches_exact():
    a = FileSignature(path="f", mtime_ns=1, size=10, sha256="aaa")
    b = FileSignature(path="f", mtime_ns=1, size=10, sha256="aaa")
    assert a.matches(b)


def test_signature_mismatch_on_size():
    a = FileSignature(path="f", mtime_ns=1, size=10, sha256=None)
    b = FileSignature(path="f", mtime_ns=1, size=11, sha256=None)
    assert not a.matches(b)


def test_signature_mismatch_on_mtime():
    a = FileSignature(path="f", mtime_ns=1, size=10, sha256=None)
    b = FileSignature(path="f", mtime_ns=2, size=10, sha256=None)
    assert not a.matches(b)


def test_signature_mismatch_on_hash_when_both_present():
    a = FileSignature(path="f", mtime_ns=1, size=10, sha256="aaa")
    b = FileSignature(path="f", mtime_ns=1, size=10, sha256="bbb")
    assert not a.matches(b)


def test_signature_matches_when_hash_missing_on_one_side():
    # Fast-mode (no hash) should compare-equal to a full-mode signature
    # with the same mtime+size. Callers wanting hash-level confidence
    # must compute both signatures in include_hash=True mode.
    fast = FileSignature(path="f", mtime_ns=1, size=10, sha256=None)
    full = FileSignature(path="f", mtime_ns=1, size=10, sha256="aaa")
    assert fast.matches(full)
    assert full.matches(fast)


# ---------------------------------------------------------------------------
# load_cache / save_cache roundtrip
# ---------------------------------------------------------------------------

def test_load_returns_empty_scaffold_when_missing(tmp_path):
    cache = load_cache(str(tmp_path / "does_not_exist.json"))
    assert cache == {"version": CACHE_VERSION, "files": {}}


def test_load_returns_empty_on_malformed_json(tmp_path):
    p = tmp_path / "cache.json"
    p.write_text("this is not json{")
    cache = load_cache(str(p))
    assert cache == {"version": CACHE_VERSION, "files": {}}


def test_load_returns_empty_on_version_mismatch(tmp_path):
    p = tmp_path / "cache.json"
    p.write_text(json.dumps({"version": 999, "files": {"f": {}}}))
    cache = load_cache(str(p))
    assert cache == {"version": CACHE_VERSION, "files": {}}


def test_load_returns_empty_when_files_key_wrong_type(tmp_path):
    p = tmp_path / "cache.json"
    p.write_text(json.dumps({"version": CACHE_VERSION, "files": "not a dict"}))
    cache = load_cache(str(p))
    assert cache == {"version": CACHE_VERSION, "files": {}}


def test_save_then_load_roundtrip(tmp_path):
    p = str(tmp_path / "cache.json")
    payload = {
        "version": CACHE_VERSION,
        "files": {
            "some/path.xlsx": {
                "path": "some/path.xlsx",
                "mtime_ns": 123,
                "size": 456,
                "sha256": None,
            }
        },
    }
    save_cache(p, payload)
    reloaded = load_cache(p)
    assert reloaded == payload


def test_save_is_atomic(tmp_path):
    p = str(tmp_path / "cache.json")
    save_cache(p, {"version": CACHE_VERSION, "files": {}})
    # After save, tmp file must not remain
    assert not os.path.exists(p + ".tmp")
    assert os.path.exists(p)


# ---------------------------------------------------------------------------
# file_has_changed
# ---------------------------------------------------------------------------

def test_file_has_changed_true_when_cache_empty(tmp_path):
    f = tmp_path / "x.txt"
    f.write_text("hi")
    assert file_has_changed(str(f), {"version": CACHE_VERSION, "files": {}})


def test_file_has_changed_true_when_cache_shape_wrong(tmp_path):
    f = tmp_path / "x.txt"
    f.write_text("hi")
    assert file_has_changed(str(f), {})
    assert file_has_changed(str(f), {"version": CACHE_VERSION})


def test_file_has_changed_false_when_signature_matches(tmp_path):
    f = tmp_path / "x.txt"
    f.write_text("hi")
    sig = compute_file_signature(str(f))
    cache = {
        "version": CACHE_VERSION,
        "files": {sig.path: sig.to_dict()},
    }
    assert not file_has_changed(str(f), cache)


def test_file_has_changed_true_after_write(tmp_path):
    f = tmp_path / "x.txt"
    f.write_text("hi")
    sig = compute_file_signature(str(f))
    cache = {"version": CACHE_VERSION, "files": {sig.path: sig.to_dict()}}
    # Rewrite to change size + mtime
    f.write_text("hi there, much longer content now")
    assert file_has_changed(str(f), cache)


def test_file_has_changed_true_when_file_missing_on_disk(tmp_path):
    cache = {
        "version": CACHE_VERSION,
        "files": {
            os.path.normpath(str(tmp_path / "gone.txt")): {
                "path": os.path.normpath(str(tmp_path / "gone.txt")),
                "mtime_ns": 1,
                "size": 1,
                "sha256": None,
            }
        },
    }
    assert file_has_changed(str(tmp_path / "gone.txt"), cache)


def test_file_has_changed_true_on_corrupt_cache_entry(tmp_path):
    f = tmp_path / "x.txt"
    f.write_text("hi")
    cache = {
        "version": CACHE_VERSION,
        "files": {os.path.normpath(str(f)): "not a dict"},
    }
    assert file_has_changed(str(f), cache)


# ---------------------------------------------------------------------------
# build_new_cache
# ---------------------------------------------------------------------------

def test_build_new_cache_indexes_by_normalized_path(tmp_path):
    f1 = tmp_path / "a.txt"
    f1.write_text("A")
    f2 = tmp_path / "b.txt"
    f2.write_text("BB")
    cache = build_new_cache([str(f1), str(f2)])
    assert cache["version"] == CACHE_VERSION
    assert set(cache["files"].keys()) == {
        os.path.normpath(str(f1)),
        os.path.normpath(str(f2)),
    }
    assert cache["files"][os.path.normpath(str(f1))]["size"] == 1
    assert cache["files"][os.path.normpath(str(f2))]["size"] == 2


def test_build_new_cache_skips_missing_paths(tmp_path):
    f = tmp_path / "exists.txt"
    f.write_text("x")
    cache = build_new_cache([str(f), str(tmp_path / "missing.txt")])
    assert list(cache["files"].keys()) == [os.path.normpath(str(f))]


def test_build_new_cache_populates_hash_when_requested(tmp_path):
    f = tmp_path / "x.txt"
    f.write_text("hello")
    cache = build_new_cache([str(f)], include_hash=True)
    entry = cache["files"][os.path.normpath(str(f))]
    assert entry["sha256"] == (
        "2cf24dba5fb0a30e26e83b2ac5b9e29e1b161e5c1fa7425e73043362938b9824"
    )
