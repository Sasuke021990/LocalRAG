"""Unit tests for the RediSearch TAG-value escaping in vector_index.

Pure string logic — no Redis needed, so this runs everywhere (unlike the
KNN integration tests, which require redis-stack). Guards the regression
where an unescaped '-' in a user_id produced 'Syntax error ... near user'
and made KNN search silently return [].
"""

from retrieval import vector_index


def test_hyphenated_id_is_escaped():
    # 'user-aaa' -> 'user\-aaa' so the TAG filter parses as one value.
    assert vector_index.escape_tag_value("user-aaa") == r"user\-aaa"


def test_hex_uuid_is_unchanged():
    # Production ids are uuid4 hex — no special chars, nothing to escape.
    uid = "0b626ed531394601b6f4d064c7c68ca9"
    assert vector_index.escape_tag_value(uid) == uid


def test_various_specials_escaped():
    for ch in ["-", ".", ":", " ", "@", "{", "}", "|", "/"]:
        assert vector_index.escape_tag_value(f"a{ch}b") == f"a\\{ch}b"
