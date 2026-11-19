"""Tests for the simulated internship tracker.

Run from the demo directory with:  python -m unittest -v
"""

from __future__ import annotations

import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from internship_tracker import (  # noqa: E402
    InternshipTracker,
    Posting,
    SearchConfig,
    SourceScan,
    save_and_verify,
)

CONFIG = SearchConfig(locations=frozenset({"Example City"}))
BOARD, LIST = "Example Job Board", "Example Internship List"


def post(source=BOARD, company="Example Startup A", title="Software Engineering Intern",
         location="Example City", board_job_id="board-001"):
    return Posting(source, company, title, location, board_job_id)


def scan(source, *postings, ok=True):
    return SourceScan(source, ok, tuple(postings))


class IdentityTests(unittest.TestCase):
    def test_same_role_from_two_sources_is_one_row(self):
        t = InternshipTracker(CONFIG)
        diff = t.apply_scan([scan(BOARD, post()),
                             scan(LIST, post(source=LIST, board_job_id=None))])
        self.assertEqual(len(t.roles), 1)
        self.assertEqual(len(diff.new), 1)
        self.assertEqual(next(iter(t.roles.values())).sources, {BOARD, LIST})

    def test_board_id_match_survives_title_edit(self):
        t = InternshipTracker(CONFIG)
        t.apply_scan([scan(BOARD, post())])
        diff = t.apply_scan([scan(BOARD, post(title="Software Engineering Intern (Summer)"))])
        self.assertEqual(diff.new, [])
        self.assertEqual(len(t.roles), 1)

    def test_rescan_is_idempotent(self):
        t = InternshipTracker(CONFIG)
        t.apply_scan([scan(BOARD, post())])
        before = t.snapshot()
        diff = t.apply_scan([scan(BOARD, post())])
        self.assertFalse(diff.has_changes())
        self.assertEqual(t.snapshot(), before)


class FilterTests(unittest.TestCase):
    def test_non_internship_and_wrong_location_hidden_with_reason(self):
        t = InternshipTracker(CONFIG)
        diff = t.apply_scan([scan(BOARD, post(title="Senior Engineer", board_job_id="b2"),
                                  post(location="Other City", board_job_id="b3"))])
        self.assertEqual(t.roles, {})
        self.assertEqual(sorted(h["reason"] for h in diff.hidden),
                         ["location_mismatch", "not_an_internship"])


class ClosingTests(unittest.TestCase):
    def test_closes_only_after_two_consecutive_misses(self):
        t = InternshipTracker(CONFIG)
        t.apply_scan([scan(BOARD, post())])
        self.assertEqual(t.apply_scan([scan(BOARD)]).closed, [])
        role_id = next(iter(t.roles))
        self.assertEqual(t.apply_scan([scan(BOARD)]).closed, [role_id])
        self.assertEqual(t.roles[role_id].state, "closed")

    def test_failed_source_never_closes_anything(self):
        t = InternshipTracker(CONFIG)
        t.apply_scan([scan(BOARD, post())])
        for _ in range(5):
            diff = t.apply_scan([scan(BOARD, ok=False)])
            self.assertEqual(diff.closed, [])
            self.assertEqual(diff.skipped_sources, [BOARD])
        self.assertEqual(next(iter(t.roles.values())).state, "open")

    def test_miss_counter_resets_when_role_reappears(self):
        t = InternshipTracker(CONFIG)
        t.apply_scan([scan(BOARD, post())])
        t.apply_scan([scan(BOARD)])           # miss 1
        t.apply_scan([scan(BOARD, post())])   # seen again, reset
        self.assertEqual(t.apply_scan([scan(BOARD)]).closed, [])  # miss 1 again

    def test_closed_role_reopens_if_listed_again(self):
        t = InternshipTracker(CONFIG)
        t.apply_scan([scan(BOARD, post())])
        t.apply_scan([scan(BOARD)])
        t.apply_scan([scan(BOARD)])
        diff = t.apply_scan([scan(BOARD, post())])
        self.assertEqual(len(diff.reopened), 1)


class HumanOwnedFieldTests(unittest.TestCase):
    def test_scan_never_overwrites_user_status(self):
        t = InternshipTracker(CONFIG)
        t.apply_scan([scan(BOARD, post())])
        role_id = next(iter(t.roles))
        t.mark(role_id, "Applied")
        t.apply_scan([scan(BOARD, post())])
        t.apply_scan([scan(BOARD)])
        t.apply_scan([scan(BOARD)])  # role closes
        self.assertEqual(t.roles[role_id].user_status, "Applied")

    def test_unknown_status_rejected(self):
        t = InternshipTracker(CONFIG)
        t.apply_scan([scan(BOARD, post())])
        with self.assertRaises(ValueError):
            t.mark(next(iter(t.roles)), "Auto-applied")


class PersistenceTests(unittest.TestCase):
    def test_save_and_verify(self):
        t = InternshipTracker(CONFIG)
        t.apply_scan([scan(BOARD, post())])
        self.assertTrue(save_and_verify(t, {}))

    def test_verify_fails_on_bad_store(self):
        class BrokenStore(dict):
            def __setitem__(self, key, value):  # silently drops writes
                pass

        t = InternshipTracker(CONFIG)
        t.apply_scan([scan(BOARD, post())])
        self.assertFalse(save_and_verify(t, BrokenStore()))


if __name__ == "__main__":
    unittest.main()
