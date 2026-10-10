"""Unit tests for the rules every number rests on: name matching, holding periods, scoring, JSON checks, escalation.

Run: python3 -m unittest -v      (from demo/; standard library only, no model needed)
"""
import unittest
from unittest import mock

import cascade
import extract
import score as s

KEYS, RX = s.load_keys(s.REDFLAG)


def ev(owner, year, span_ok=True, role="dealer"):
    return {"owner": owner, "year": year, "span_ok": span_ok, "role": role, "source_span": owner}


def status(events, i=0):
    return s.holding_status(events, i, KEYS, RX)


class OwnerNames(unittest.TestCase):
    def test_reordered_name_is_same_owner(self):
        self.assertTrue(s.same_owner("Goering, Hermann, Reichsmarschall", "Hermann Goering"))

    def test_different_people_are_not_same_owner(self):
        self.assertFalse(s.same_owner("Samuel H. Kress", "Alessandro Contini Bonacossi"))

    def test_sharing_one_name_is_not_enough(self):
        self.assertFalse(s.same_owner("Samuel H. Kress", "Rush H. Kress"))  # brothers

    def test_empty_or_stopword_names_never_match(self):
        self.assertFalse(s.same_owner("", "Kress"))
        self.assertFalse(s.same_owner("The Gallery", "Kress"))

    def test_person_and_foundation_count_as_same_owner(self):
        # ponytail: known approximation of token-subset matching, stated in the write-up's limits
        self.assertTrue(s.same_owner("Samuel H. Kress Foundation", "Samuel H. Kress"))

    def test_forward_puts_forename_first(self):
        self.assertEqual(s.forward("Haberstock, Karl"), "Karl Haberstock")
        self.assertEqual(s.forward("Karl Haberstock"), "Karl Haberstock")


class RedFlagMatching(unittest.TestCase):
    def test_tiers_get_stricter(self):
        text = "sold to Karl Haberstock, Berlin"
        for tier in ("naive", "cased", "fullname"):
            self.assertIn("haberstock", s.match(text, RX, KEYS, tier=tier), tier)

    def test_lowercase_word_only_matches_naive_tier(self):
        self.assertTrue(s.match("haberstock", RX, KEYS, tier="naive"))
        self.assertFalse(s.match("haberstock", RX, KEYS, tier="cased"))

    def test_surname_without_forename_fails_fullname_tier(self):
        self.assertTrue(s.match("sold to Haberstock", RX, KEYS, tier="cased"))
        self.assertFalse(s.match("sold to Haberstock", RX, KEYS, tier="fullname"))

    def test_unlisted_dealer_is_not_matched(self):
        self.assertFalse(s.match("sold to Joseph Duveen, London", RX, KEYS, tier="fullname"))

    def test_hyphenated_list_name_matches_spaced_text(self):
        self.assertTrue(s.match("(Count Alessandro Contini Bonacossi, Florence)", RX, KEYS, tier="fullname"))


class HoldingPeriod(unittest.TestCase):
    def test_held_across_1933_is_flagged(self):
        self.assertEqual(status([ev("Karl Haberstock", 1928), ev("Someone Else", 1936)]), "flagged")

    def test_period_boundaries_are_inclusive(self):
        self.assertEqual(status([ev("Karl Haberstock", 1945), ev("Someone Else", 1950)]), "flagged")
        self.assertEqual(status([ev("Karl Haberstock", 1920), ev("Someone Else", 1933)]), "flagged")
        self.assertIsNone(status([ev("Karl Haberstock", 1946), ev("Someone Else", 1950)]))
        self.assertIsNone(status([ev("Karl Haberstock", 1900), ev("Someone Else", 1932)]))

    def test_silver_label_uses_the_museums_owner_list(self):
        doc = lambda name, b, e: {"gold_owners": [{"name": name, "beginyear": b, "endyear": e}]}
        self.assertEqual(s.silver_label(doc("Haberstock, Karl", 1938, None), KEYS, RX), "flagged")
        self.assertEqual(s.silver_label(doc("Haberstock, Karl", None, None), KEYS, RX), "flagged")  # undated counts
        self.assertEqual(s.silver_label(doc("Haberstock, Karl", 1950, 1955), KEYS, RX), "not flagged")
        self.assertEqual(s.silver_label(doc("Duveen, Joseph", 1938, None), KEYS, RX), "not flagged")

    def test_held_only_before_1933_is_not_flagged(self):
        self.assertIsNone(status([ev("Karl Haberstock", 1920), ev("Someone Else", 1925)]))

    def test_held_only_after_1945_is_not_flagged(self):
        self.assertIsNone(status([ev("Karl Haberstock", 1950), ev("Someone Else", 1955)]))

    def test_no_dates_is_not_decided(self):
        self.assertEqual(status([ev("Karl Haberstock", None), ev("Someone Else", None)]), "not decided")

    def test_undated_owner_dated_by_next_event(self):
        self.assertEqual(status([ev("Karl Haberstock", None), ev("Someone Else", 1937)]), "flagged")

    def test_quote_not_in_text_never_counts(self):
        self.assertIsNone(status([ev("Karl Haberstock", 1938, span_ok=False)]))

    def test_unverified_step_does_not_end_a_holding(self):
        events = [ev("Karl Haberstock", 1920), ev("Invented Owner", 1930, span_ok=False), ev("Someone Else", 1950)]
        self.assertEqual(status(events), "flagged")

    def test_unlisted_owner_never_counts(self):
        self.assertIsNone(status([ev("Joseph Duveen", 1938)]))

    def test_verdict_prefers_flagged_over_not_decided(self):
        events = [ev("Karl Haberstock", None), ev("Gustav Rochlitz", 1938), ev("Someone Else", 1940)]
        self.assertEqual(s.plan_verdict(events, KEYS, RX), "flagged")

    def test_custom_period_is_respected(self):
        events = [ev("Karl Haberstock", 1928), ev("Someone Else", 1936)]
        self.assertEqual(s.plan_verdict(events, KEYS, RX, years=range(1928, 1931)), "flagged")
        self.assertEqual(s.plan_verdict(events, KEYS, RX, years=range(1940, 1946)), "not flagged")

    def test_evidence_is_only_the_flagging_events(self):
        events = [ev("Joseph Duveen", 1920), ev("Karl Haberstock", 1938), ev("Someone Else", 1941)]
        self.assertEqual([e["owner"] for e in s.flag_events(events, KEYS, RX)], ["Karl Haberstock"])

    @unittest.expectedFailure
    def test_known_issue_auction_sale_is_not_a_holding(self):
        # NGA 52183: a 1910 sale at Hotel Drouot (on the list) is read as holding the work until 1955.
        # This is P1's only false positive; the write-up reports it. Remove the decorator when fixed.
        events = [ev("Hôtel Drouot", 1910, role="auction"), ev("Druet", None), ev("Ailsa Mellon Bruce", 1955)]
        self.assertEqual(s.plan_verdict(events, KEYS, RX), "not flagged")


class Scoring(unittest.TestCase):
    def test_prf_known_values_and_zero_division(self):
        self.assertEqual(s.prf(8, 2, 2), {"P": 0.8, "R": 0.8, "F1": 0.8})
        self.assertEqual(s.prf(0, 0, 0), {"P": 0.0, "R": 0.0, "F1": 0.0})

    def test_screening_leaves_out_uncertain_and_counts_lenient_recall(self):
        docs = [{"id": i} for i in "abcd"]
        labels = {"a": "flagged", "b": "flagged", "c": "not flagged", "d": "uncertain"}
        verdicts = {"a": "flagged", "b": "not decided", "c": "not flagged", "d": "flagged"}
        out = s.screening(docs, verdicts, labels)
        self.assertEqual((out["P"], out["R"], out["R_lenient"]), (1.0, 0.5, 1.0))

    def test_owner_scores_match_each_gold_owner_once(self):
        docs = [{"id": "x", "gold_owners": [{"name": "Kress, Samuel H."}]}]
        events = [{"owner": "Samuel H. Kress", "span_ok": True}, {"owner": "Kress", "span_ok": True}]
        self.assertEqual(s.owner_scores(docs, {"x": {"events": events}}), {"P": 0.5, "R": 1.0, "F1": 0.667})

    def test_owner_scores_ignore_unsupported_events(self):
        docs = [{"id": "x", "gold_owners": [{"name": "Kress, Samuel H."}]}]
        events = [{"owner": "Samuel H. Kress", "span_ok": False}]
        self.assertEqual(s.owner_scores(docs, {"x": {"events": events}})["R"], 0.0)

    def test_prepare_drops_receiving_museum_and_ignores_whitespace(self):
        docs = [{"id": "x", "provenance_text": "sold to   Karl Haberstock,\nBerlin; gift to NGA."}]
        results = {"x": {"id": "x", "events": [
            {"owner": "Karl Haberstock", "source_span": "Karl Haberstock, Berlin"},
            {"owner": "National Gallery of Art", "source_span": "NGA"},
            {"owner": "Invented Owner", "source_span": "not in the text"}]}}
        events = s.prepare(docs, results)["x"]["events"]
        self.assertEqual([(e["owner"], e["span_ok"]) for e in events],
                         [("Karl Haberstock", True), ("Invented Owner", False)])


class ModelOutputChecks(unittest.TestCase):
    EVENT = '{"owner": "A", "role": "%s", "date": "1937", "year": %s, "place": null, "source_span": "A"}'

    def test_code_fence_is_tolerated(self):
        self.assertEqual(len(extract.validate('```json\n{"events": [%s]}\n```' % (self.EVENT % ("dealer", 1937)))), 1)

    def test_missing_field_is_an_error(self):
        with self.assertRaises(ValueError):
            extract.validate('{"events": [{"owner": "A", "role": "dealer"}]}')

    def test_unknown_role_becomes_other_and_text_year_is_parsed(self):
        e = extract.validate('{"events": [%s]}' % (self.EVENT % ("broker", '"1937-06"')))[0]
        self.assertEqual((e["role"], e["year"]), ("other", 1937))

    def test_not_json_is_an_error(self):
        with self.assertRaises(ValueError):
            extract.validate("I could not find any owners.")

    def test_failed_request_is_a_counted_error_not_a_crash(self):
        with mock.patch.object(extract, "call", side_effect=OSError("connection refused")):
            r = extract.extract("m", {"id": "x", "provenance_text": "t"})
        self.assertEqual((r["events"], r["error"]), ([], "request failed: connection refused"))


class CascadeRule(unittest.TestCase):
    DOC = {"id": "x", "provenance_text": "sold 1938 to Karl Haberstock"}

    def result(self, events, error=None):
        return {"id": "x", "events": events, "error": error, "in_tok": 10, "out_tok": 20, "seconds": 1.0}

    def test_escalation_reasons(self):
        ok = dict(ev("Karl Haberstock", 1938))
        self.assertEqual(cascade.needs_escalation(self.DOC, self.result([], "bad json")), "error or empty")
        self.assertEqual(cascade.needs_escalation(self.DOC, self.result([dict(ok, span_ok=False)])), "span not in text")
        self.assertEqual(cascade.needs_escalation(self.DOC, self.result([dict(ok, year=1950)])), "no dated 1933-45 event")
        self.assertIsNone(cascade.needs_escalation(self.DOC, self.result([ok])))

    def test_failed_large_model_keeps_small_answer_and_sums_cost(self):
        small = self.result([dict(ev("Karl Haberstock", 1938), span_ok=False)])
        with mock.patch.object(cascade, "extract", side_effect=[small, self.result([], "request failed")]):
            r = cascade.cascade("small", "large", self.DOC)
        self.assertEqual(r["events"], small["events"])
        self.assertIn("large model failed", r["escalated"])
        self.assertEqual((r["out_tok"], r["seconds"]), (40, 2.0))

    def test_good_small_answer_is_not_escalated(self):
        small = self.result([ev("Karl Haberstock", 1938)])
        with mock.patch.object(cascade, "extract", side_effect=[small]) as m:
            r = cascade.cascade("small", "large", self.DOC)
        self.assertEqual((m.call_count, r["escalated"]), (1, None))


if __name__ == "__main__":
    unittest.main()
