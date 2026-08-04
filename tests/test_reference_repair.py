"""Tests for truncated reference ID repair."""

import pytest

from open_notebook.utils.reference_repair import repair_reference_ids

KNOWN = [
    "source:lh9mbuyd1m9g4bh56u36",
    "source:bpqgzxbzzdhwwf9u93up",
    "note:avltbmair9c52tetrqst",
    "source_insight:7wj145os5nqfsfwsalhe",
]


class TestRepairReferenceIds:
    def test_prefix_truncation_is_repaired(self):
        text = "依据 [source:lh9mbu] 的研究。"
        assert repair_reference_ids(text, KNOWN) == (
            "依据 [source:lh9mbuyd1m9g4bh56u36] 的研究。"
        )

    def test_suffix_truncation_is_repaired(self):
        text = "参考 [source:dhwwf9u93up] 报告。"
        assert repair_reference_ids(text, KNOWN) == (
            "参考 [source:bpqgzxbzzdhwwf9u93up] 报告。"
        )

    def test_middle_substring_unique_match_is_repaired(self):
        text = "见 [source:yd1m9g4] 数据。"
        assert repair_reference_ids(text, KNOWN) == (
            "见 [source:lh9mbuyd1m9g4bh56u36] 数据。"
        )

    def test_full_id_is_untouched(self):
        text = "见 [source:lh9mbuyd1m9g4bh56u36]。"
        assert repair_reference_ids(text, KNOWN) == text

    def test_ambiguous_match_is_left_untouched(self):
        # Both source ids share the 'u93up' suffix
        ambiguous = KNOWN + ["source:anotherprefixdhwwf9u93up"]
        text = "见 [source:u93up]。"
        assert repair_reference_ids(text, ambiguous) == "见 [source:u93up]。"

    def test_no_match_is_left_untouched(self):
        text = "见 [source:zzzzz] 与 [note:qwqwq]。"
        assert repair_reference_ids(text, KNOWN) == text

    def test_type_mismatch_is_not_repaired(self):
        # 'lh9mbu' exists as source: prefix only; a note: reference must not
        # be rewritten to the source id
        text = "见 [note:lh9mbu]。"
        assert repair_reference_ids(text, KNOWN) == "见 [note:lh9mbu]。"

    def test_insight_alias_matches_canonical_type(self):
        text = "见 [insight:7wj145os5]。"
        assert repair_reference_ids(text, KNOWN) == (
            "见 [source_insight:7wj145os5nqfsfwsalhe]。"
        )

    def test_multiple_references_repaired_independently(self):
        text = "A [source:lh9mbu] B [source:dhwwf9u93up] C [note:avltbmair9c52tetrqst]"
        assert repair_reference_ids(text, KNOWN) == (
            "A [source:lh9mbuyd1m9g4bh56u36] "
            "B [source:bpqgzxbzzdhwwf9u93up] "
            "C [note:avltbmair9c52tetrqst]"
        )

    def test_empty_input_and_known_ids(self):
        assert repair_reference_ids("", KNOWN) == ""
        assert repair_reference_ids("见 [source:lh9mbu]。", []) == "见 [source:lh9mbu]。"

    def test_non_string_known_ids_ignored(self):
        text = "见 [source:lh9mbu]。"
        assert repair_reference_ids(text, [None, 123, "source:lh9mbuyd1m9g4bh56u36"]) == (
            "见 [source:lh9mbuyd1m9g4bh56u36]。"
        )
