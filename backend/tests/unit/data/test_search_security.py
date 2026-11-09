
import pytest

from data.accent import (
    SEARCH_MAX_LENGTH,
    SearchQueryError,
    build_search_pattern,
    escape_like,
    validate_search_term,
)




class TestValidateSearchTerm:
    def test_strips_whitespace(self):
        assert validate_search_term("  harina  ") == "harina"

    @pytest.mark.parametrize("bad", ["", "   ", "\t\n"])
    def test_empty_or_blank_rejected(self, bad):
        with pytest.raises(SearchQueryError, match="must not be empty"):
            validate_search_term(bad)

    @pytest.mark.parametrize(
        "bad",
        [
            "harina\x00",
            "a\x07b",
            "del\x7fe",
            "zero\u200bwidth",
            "\u202ebidi",
            "\ue000priv",
            "surro\u0000gate",
        ],
    )
    def test_control_and_invisible_rejected(self, bad):
        with pytest.raises(SearchQueryError, match="invalid characters"):
            validate_search_term(bad)

    def test_too_long_rejected(self):
        with pytest.raises(SearchQueryError, match="at most"):
            validate_search_term("a" * (SEARCH_MAX_LENGTH + 1))

    def test_max_length_is_accepted(self):
        assert validate_search_term("a" * SEARCH_MAX_LENGTH) == "a" * SEARCH_MAX_LENGTH

    def test_accents_and_spaces_are_fine(self):
        assert validate_search_term("Café con leche") == "Café con leche"

    def test_like_metacharacters_are_allowed_but_neutralized(self):
        assert validate_search_term("50% off_2") == "50% off_2"




class TestEscapeLike:
    def test_plain_text_unchanged(self):
        assert escape_like("harina") == "harina"

    def test_percent_escaped(self):
        assert list(escape_like("50%")) == ["5", "0", "\\", "%"]

    def test_underscore_escaped(self):
        assert list(escape_like("a_b")) == ["a", "\\", "_", "b"]

    def test_backslash_first_then_others(self):
        assert list(escape_like("a\\%_b")) == [
            "a", "\\", "\\", "\\", "%", "\\", "_", "b",
        ]

    def test_double_escaped_percent_stays_literal(self):
        assert list(escape_like("\\%")) == ["\\", "\\", "\\", "%"]




class TestBuildSearchPattern:
    def test_accent_folded_and_wrapped(self):
        assert build_search_pattern("Café") == "%cafe%"

    def test_percent_is_literal(self):
        assert build_search_pattern("100%") == "%100\\%%"

    def test_underscore_is_literal(self):
        assert build_search_pattern("a_b") == "%a\\_b%"

    def test_input_is_stripped(self):
        assert build_search_pattern("  harina  ") == "%harina%"

    @pytest.mark.parametrize("bad", ["", "   ", "x\x00", "\u202e", "a" * (SEARCH_MAX_LENGTH + 1)])
    def test_invalid_term_rejected(self, bad):
        with pytest.raises(SearchQueryError):
            build_search_pattern(bad)
