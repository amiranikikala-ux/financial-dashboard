"""Lock-in: normalize_name handles HTML-escaped quotes from BOG SOAP feed.

BOG's SOAP API returns recipient names with `&apos;` instead of `'`.
Without html.unescape, normalize_name leaves the literal `&apos;` in the
string, breaking name-based supplier matching.

Concrete case (verified 2026-05-08): 4 BOG payments to შპს კომპანია ორბიტა
(840 + 1000 + small fees) failed to match because the BOG cache stored
"შპს &apos;კომპანია ორბიტა&apos;" instead of "შპს 'კომპანია ორბიტა'".
"""
from dashboard_pipeline.supplier_matching import normalize_name


def test_normalize_name_unescapes_apos():
    raw = "შპს &apos;კომპანია ორბიტა&apos;"
    assert normalize_name(raw) == "კომპანია ორბიტა"


def test_normalize_name_unescapes_double_apos():
    raw = "სს ''კოკა-კოლა ბოთლერს ჯორჯია''"
    assert normalize_name(raw) == "კოკა-კოლა ბოთლერს ჯორჯია"


def test_normalize_name_unescapes_amp():
    raw = "სს თ &amp; რ დისტრიბუშენ"
    assert normalize_name(raw) == "თ & რ დისტრიბუშენ"


def test_normalize_name_strips_legacy_quote_punctuation():
    assert normalize_name("შპს „პარტნიორი 2010\"") == "პარტნიორი 2010"


def test_normalize_name_collapses_double_space():
    assert normalize_name("შპს  'გაგრა პლუსი '") == "გაგრა პლუსი"
