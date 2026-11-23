"""Tests for mapping CEDA market names onto our (canonical) market rows."""

from __future__ import annotations

import pandas as pd

from backend.ingestion.market_crosswalk import (
    build_crosswalk,
    norm_name,
    norm_state,
)


def _ours() -> pd.DataFrame:
    return pd.DataFrame(
        [
            (1, "Telangana", "Hyderabad", "Kukatpally,RBZ"),
            (2, "Telangana", "Hyderabad", "RYTHU BAZAR MEHDIPATNAM"),
            (3, "Telangana", "Hyderabad", "L B Nagar APMC"),
            (4, "Telangana", "Rangareddy", "Gudimalkapur"),
            (5, "Karnataka", "Bangalore", "Bangalore"),
            (6, "Karnataka", "Kolar", "Kolar"),
        ],
        columns=["market_id", "state", "district", "name"],
    )


def _ceda(*rows) -> pd.DataFrame:
    return pd.DataFrame(
        list(rows),
        columns=["ceda_market_id", "ceda_market_name", "ceda_state", "ceda_district"],
    )


def _one(ceda_row, ours=None, overrides=None) -> pd.Series:
    cw = build_crosswalk(_ceda(ceda_row), _ours() if ours is None else ours, overrides)
    assert len(cw) == 1
    return cw.iloc[0]


def test_noise_words_and_spelling_groups_match_exactly():
    r = _one((10, "L B Nagar", "Telangana", "Hyderabad"))
    assert r["method"] == "exact" and r["market_id"] == 3

    r = _one((11, "Kukatpally(Rythu Bazar)", "Telangana", "Hyderabad"))
    assert r["method"] == "exact" and r["market_id"] == 1


def test_spelling_variant_matches_fuzzily():
    r = _one((12, "Mehndipatnam(Rythu Bazar)", "Telangana", "Hyderabad"))
    assert r["method"] == "fuzzy"
    assert r["market_id"] == 2
    assert r["score"] >= 0.88


def test_our_names_are_never_changed():
    """CEDA's spelling must never leak into the stored name."""
    r = _one((11, "Kukatpally(Rythu Bazar)", "Telangana", "Hyderabad"))
    assert r["our_name"] == "Kukatpally,RBZ"
    assert r["our_district"] == "Hyderabad"
    assert r["our_state"] == "Telangana"


def test_unrelated_market_is_left_unmatched():
    r = _one((13, "Bowenpally", "Telangana", "Hyderabad"))
    assert r["method"] == "unmatched"
    assert pd.isna(r["market_id"])


def test_other_states_are_never_candidates():
    # Exists in Karnataka only; a Telangana CEDA row must not grab it.
    r = _one((14, "Kolar", "Telangana", "Kolar"))
    assert pd.isna(r["market_id"])


def test_district_breaks_ties_between_same_name_markets():
    ours = pd.DataFrame(
        [(1, "Karnataka", "Bangalore", "Main Market"), (2, "Karnataka", "Mysore", "Main Market")],
        columns=["market_id", "state", "district", "name"],
    )
    r = _one((15, "Main Market APMC", "Karnataka", "Mysore"), ours=ours)
    assert r["method"] == "exact" and r["market_id"] == 2


def test_same_name_in_unknown_district_is_ambiguous_not_guessed():
    ours = pd.DataFrame(
        [(1, "Karnataka", "Bangalore", "Main Market"), (2, "Karnataka", "Mysore", "Main Market")],
        columns=["market_id", "state", "district", "name"],
    )
    r = _one((16, "Main Market", "Karnataka", "Hassan"), ours=ours)
    assert r["method"] == "ambiguous"
    assert pd.isna(r["market_id"])


def test_manual_override_wins_and_uses_our_name():
    overrides = pd.DataFrame(
        [("17", "Telangana", "Hyderabad", "Kukatpally,RBZ", "", "BWP-style abbreviation")],
        columns=["ceda_market_id", "state", "district", "market", "ignore", "notes"],
    )
    r = _one((17, "Hyderabad_Bowenpally", "Telangana", "Hyderabad"), overrides=overrides)
    assert r["method"] == "override"
    assert r["market_id"] == 1
    assert r["our_name"] == "Kukatpally,RBZ"


def test_override_can_ignore_a_market():
    overrides = pd.DataFrame(
        [("18", "", "", "", "true", "closed mandi")],
        columns=["ceda_market_id", "state", "district", "market", "ignore", "notes"],
    )
    r = _one((18, "Kolar", "Karnataka", "Kolar"), overrides=overrides)
    assert r["method"] == "ignored"
    assert pd.isna(r["market_id"])


def test_override_pointing_at_missing_market_is_reported():
    overrides = pd.DataFrame(
        [("19", "Telangana", "Hyderabad", "Does Not Exist", "", "")],
        columns=["ceda_market_id", "state", "district", "market", "ignore", "notes"],
    )
    r = _one((19, "Whatever", "Telangana", "Hyderabad"), overrides=overrides)
    assert r["method"] == "override_not_found"
    assert pd.isna(r["market_id"])


def _hp() -> pd.DataFrame:
    """Himachal live-feed names as they really appear (yard-type prefixes)."""
    return pd.DataFrame(
        [
            (1, "Himachal Pradesh", "Bilaspur", "PMY Bilaspur"),
            (2, "Himachal Pradesh", "Kangra", "PMY Kangra"),
            (3, "Himachal Pradesh", "Kangra", "SMY Baijnath"),
            (4, "Himachal Pradesh", "Mandi", "SMY Dhanotu"),
            (5, "Himachal Pradesh", "Kangra", "SMY Dharamshala"),
        ],
        columns=["market_id", "state", "district", "name"],
    )


def test_yard_type_prefixes_are_ignored_when_matching():
    r = _one((20, "Bilaspur", "Himachal Pradesh", "Bilaspur"), ours=_hp())
    assert r["method"] == "exact" and r["our_name"] == "PMY Bilaspur"

    r = _one((21, "Dhanotu (Mandi)", "Himachal Pradesh", "Mandi"), ours=_hp())
    assert r["method"] == "exact" and r["our_name"] == "SMY Dhanotu"


def test_bracketed_submarket_matches_only_with_the_same_district():
    r = _one((22, "Kangra(Baijnath)", "Himachal Pradesh", "Kangra"), ours=_hp())
    assert r["method"] == "exact_paren"
    assert r["our_name"] == "SMY Baijnath" and r["score"] == 0.99

    # same text, but CEDA says a different district: not accepted
    r = _one((23, "Kangra(Baijnath)", "Himachal Pradesh", "Chamba"), ours=_hp())
    assert pd.isna(r["market_id"])


def test_a_bracketed_submarket_is_never_mistaken_for_the_main_market():
    # 'Kangra(Jassour)' is a different yard from 'PMY Kangra'; mixing them would blend two
    # mandis' price histories.
    r = _one((24, "Kangra(Jassour)", "Himachal Pradesh", "Kangra"), ours=_hp())
    assert pd.isna(r["market_id"])
    assert r["method"] in {"unmatched", "ambiguous"}


def test_a_bracket_that_names_the_district_is_not_treated_as_the_market():
    # Real Himachal name: Namhol is a sub-market OF Bilaspur district, not the main Bilaspur
    # market. Matching on the bracket would silently merge two mandis' histories.
    r = _one((26, "Namhol(Bilaspur)", "Himachal Pradesh", "Bilaspur"), ours=_hp())
    assert pd.isna(r["market_id"])


def test_similar_town_names_are_not_merged():
    ours = pd.DataFrame(
        [(1, "Maharashtra", "Pune", "APMC Shirur")],
        columns=["market_id", "state", "district", "name"],
    )
    r = _one((25, "Shirpur", "Maharashtra", "Dhule"), ours=ours)   # Shirpur != Shirur
    assert pd.isna(r["market_id"])


def test_state_spellings_are_unified():
    assert norm_state("Keralam") == norm_state("Kerala")
    assert norm_state("Orissa") == norm_state("Odisha")


def test_norm_name_ignores_case_order_punctuation_and_noise():
    assert norm_name("RYTHU BAZAR MEHDIPATNAM") == norm_name("mehdipatnam (Rythu Bazaar)")
    assert norm_name("L B Nagar APMC") == norm_name("l.b. nagar")
