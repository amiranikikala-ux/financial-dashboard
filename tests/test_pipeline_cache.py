"""Unit tests for dashboard_pipeline.pipeline_cache.

Sprint 1 of Tier 2 shipped v1 (signature-only). Sprint 2 bumped the
schema to v2: each entry is now ``{signature, payload}`` so per-file
aggregates can travel with the signature. Tests here pin the v2
contract (schema shape, helpers, fingerprint invalidation) so the
retail_sales incremental integration can build on a tested foundation.
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
    drop_entry,
    empty_cache,
    file_has_changed,
    get_payload,
    load_cache,
    put_entry,
    save_cache,
)


def _make_entry(sig: FileSignature, payload=None):
    return {"signature": sig.to_dict(), "payload": payload}


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
# empty_cache
# ---------------------------------------------------------------------------

def test_empty_cache_returns_v2_scaffold():
    assert empty_cache() == {"version": CACHE_VERSION, "files": {}}


def test_empty_cache_carries_content_fingerprint_when_given():
    cache = empty_cache(content_fingerprint="abc")
    assert cache == {
        "version": CACHE_VERSION,
        "files": {},
        "content_fingerprint": "abc",
    }


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
    # v1 flat shape — must be treated as empty under v2
    p.write_text(json.dumps({"version": 1, "files": {"f": {"path": "f", "mtime_ns": 1, "size": 2}}}))
    cache = load_cache(str(p))
    assert cache == {"version": CACHE_VERSION, "files": {}}


def test_load_returns_empty_when_files_key_wrong_type(tmp_path):
    p = tmp_path / "cache.json"
    p.write_text(json.dumps({"version": CACHE_VERSION, "files": "not a dict"}))
    cache = load_cache(str(p))
    assert cache == {"version": CACHE_VERSION, "files": {}}


def test_load_skips_entries_without_signature(tmp_path):
    p = tmp_path / "cache.json"
    p.write_text(json.dumps({
        "version": CACHE_VERSION,
        "files": {
            "legit": {"signature": {"path": "legit", "mtime_ns": 1, "size": 2}, "payload": 7},
            "broken": {"payload": 7},  # no signature → dropped
            "also_broken": "not a dict",  # not a mapping → dropped
        },
    }))
    cache = load_cache(str(p))
    assert set(cache["files"].keys()) == {"legit"}
    assert cache["files"]["legit"]["payload"] == 7


def test_save_then_load_roundtrip_with_payload(tmp_path):
    p = str(tmp_path / "cache.json")
    payload = {
        "version": CACHE_VERSION,
        "files": {
            "some/path.xlsx": {
                "signature": {
                    "path": "some/path.xlsx",
                    "mtime_ns": 123,
                    "size": 456,
                    "sha256": None,
                },
                "payload": {"row_count": 42, "revenue_ge": 100.5},
            }
        },
    }
    save_cache(p, payload)
    reloaded = load_cache(p)
    assert reloaded == payload


def test_save_is_atomic(tmp_path):
    p = str(tmp_path / "cache.json")
    save_cache(p, {"version": CACHE_VERSION, "files": {}})
    assert not os.path.exists(p + ".tmp")
    assert os.path.exists(p)


def test_load_with_matching_content_fingerprint_preserves_entries(tmp_path):
    p = str(tmp_path / "cache.json")
    payload = {
        "version": CACHE_VERSION,
        "content_fingerprint": "abc",
        "files": {
            "f": {"signature": {"path": "f", "mtime_ns": 1, "size": 2}, "payload": 7}
        },
    }
    save_cache(p, payload)
    reloaded = load_cache(p, content_fingerprint="abc")
    assert reloaded["files"]["f"]["payload"] == 7
    assert reloaded["content_fingerprint"] == "abc"


def test_load_with_mismatched_content_fingerprint_returns_empty(tmp_path):
    p = str(tmp_path / "cache.json")
    payload = {
        "version": CACHE_VERSION,
        "content_fingerprint": "abc",
        "files": {
            "f": {"signature": {"path": "f", "mtime_ns": 1, "size": 2}, "payload": 7}
        },
    }
    save_cache(p, payload)
    reloaded = load_cache(p, content_fingerprint="different")
    assert reloaded["files"] == {}
    assert reloaded["content_fingerprint"] == "different"


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
        "files": {sig.path: _make_entry(sig, payload=None)},
    }
    assert not file_has_changed(str(f), cache)


def test_file_has_changed_true_after_write(tmp_path):
    f = tmp_path / "x.txt"
    f.write_text("hi")
    sig = compute_file_signature(str(f))
    cache = {
        "version": CACHE_VERSION,
        "files": {sig.path: _make_entry(sig, payload=None)},
    }
    f.write_text("hi there, much longer content now")
    assert file_has_changed(str(f), cache)


def test_file_has_changed_true_when_file_missing_on_disk(tmp_path):
    gone = os.path.normpath(str(tmp_path / "gone.txt"))
    cache = {
        "version": CACHE_VERSION,
        "files": {
            gone: {
                "signature": {
                    "path": gone,
                    "mtime_ns": 1,
                    "size": 1,
                    "sha256": None,
                },
                "payload": None,
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


def test_file_has_changed_true_when_entry_missing_signature(tmp_path):
    f = tmp_path / "x.txt"
    f.write_text("hi")
    cache = {
        "version": CACHE_VERSION,
        "files": {os.path.normpath(str(f)): {"payload": 1}},  # no signature
    }
    assert file_has_changed(str(f), cache)


# ---------------------------------------------------------------------------
# get_payload / put_entry / drop_entry
# ---------------------------------------------------------------------------

def test_get_payload_returns_none_when_missing(tmp_path):
    assert get_payload({"version": CACHE_VERSION, "files": {}}, "anything") is None


def test_put_entry_then_get_payload_roundtrip(tmp_path):
    f = tmp_path / "x.txt"
    f.write_text("hi")
    sig = compute_file_signature(str(f))
    cache = empty_cache()
    put_entry(cache, str(f), sig, payload={"row_count": 3})
    assert get_payload(cache, str(f)) == {"row_count": 3}
    # Same file should now report unchanged.
    assert not file_has_changed(str(f), cache)


def test_put_entry_overwrites_previous_payload(tmp_path):
    f = tmp_path / "x.txt"
    f.write_text("hi")
    sig = compute_file_signature(str(f))
    cache = empty_cache()
    put_entry(cache, str(f), sig, payload={"v": 1})
    put_entry(cache, str(f), sig, payload={"v": 2})
    assert get_payload(cache, str(f)) == {"v": 2}


def test_put_entry_rejects_non_dict_cache():
    with pytest.raises(TypeError):
        put_entry("not a dict", "p", FileSignature("p", 1, 1), None)


def test_drop_entry_removes_entry(tmp_path):
    f = tmp_path / "x.txt"
    f.write_text("hi")
    sig = compute_file_signature(str(f))
    cache = empty_cache()
    put_entry(cache, str(f), sig, payload=1)
    drop_entry(cache, str(f))
    assert get_payload(cache, str(f)) is None
    assert cache["files"] == {}


def test_drop_entry_is_noop_when_missing():
    cache = empty_cache()
    drop_entry(cache, "never_added")
    assert cache == empty_cache()


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
    assert cache["files"][os.path.normpath(str(f1))]["signature"]["size"] == 1
    assert cache["files"][os.path.normpath(str(f1))]["payload"] is None
    assert cache["files"][os.path.normpath(str(f2))]["signature"]["size"] == 2


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
    assert entry["signature"]["sha256"] == (
        "2cf24dba5fb0a30e26e83b2ac5b9e29e1b161e5c1fa7425e73043362938b9824"
    )


def test_build_new_cache_embeds_content_fingerprint(tmp_path):
    f = tmp_path / "x.txt"
    f.write_text("hello")
    cache = build_new_cache([str(f)], content_fingerprint="fp1")
    assert cache["content_fingerprint"] == "fp1"
