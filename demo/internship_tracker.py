"""Simulated daily internship search tracker (sanitized showcase).

SIMULATED: every company, role, and source below is fictional. This module makes
no network calls. It never applies to a job, submits a form, or contacts anyone.
It only finds, filters, and tracks roles.

It shows the reconciliation rules used by the internship search in my OpenClaw
environment:

  * One tracked role per real posting, however many sources list it
    (match on the board's job ID first, then normalized company + title)
  * A role closes only after it is missing from a successfully read source on
    two scans in a row, so a failed or blocked source never closes anything
  * Statuses I set by hand (for example "Applied") are never overwritten by a scan
  * A run is complete only after the saved state reads back identically
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from typing import Any

MISSES_TO_CLOSE = 2
USER_STATUSES = frozenset({"Interested", "Applied", "Interviewing", "Rejected", "Offer"})


@dataclass(frozen=True)
class Posting:
    source: str
    company: str
    title: str
    location: str
    board_job_id: str | None = None


@dataclass(frozen=True)
class SourceScan:
    source: str
    ok: bool  # False when the source failed, timed out, or refused the request
    postings: tuple[Posting, ...] = ()


@dataclass
class TrackedRole:
    role_id: str
    company: str
    title: str
    location: str
    state: str = "open"  # "open" | "closed" (owned by the scanner)
    misses: int = 0
    sources: set[str] = field(default_factory=set)
    board_job_ids: set[str] = field(default_factory=set)
    user_status: str | None = None  # owned by the human, never set by a scan


@dataclass
class ScanDiff:
    new: list[str] = field(default_factory=list)
    closed: list[str] = field(default_factory=list)
    reopened: list[str] = field(default_factory=list)
    hidden: list[dict[str, str]] = field(default_factory=list)
    skipped_sources: list[str] = field(default_factory=list)

    def has_changes(self) -> bool:
        return bool(self.new or self.closed or self.reopened)


@dataclass(frozen=True)
class SearchConfig:
    locations: frozenset[str]
    role_keywords: frozenset[str] = frozenset({"intern", "internship"})


def _norm(text: str) -> str:
    return " ".join(text.split()).casefold()


def _name_key(company: str, title: str) -> str:
    return f"{_norm(company)}|{_norm(title)}"


def _role_id(company: str, title: str) -> str:
    return hashlib.sha256(_name_key(company, title).encode("utf-8")).hexdigest()[:16]


def hide_reason(posting: Posting, config: SearchConfig) -> str | None:
    title = _norm(posting.title)
    if not any(k in title.split() for k in config.role_keywords):
        return "not_an_internship"
    if _norm(posting.location) not in {_norm(loc) for loc in config.locations}:
        return "location_mismatch"
    return None


class InternshipTracker:
    def __init__(self, config: SearchConfig) -> None:
        self.config = config
        self.roles: dict[str, TrackedRole] = {}
        self._by_board_id: dict[str, str] = {}
        self._by_name: dict[str, str] = {}

    # -- identity ----------------------------------------------------------- #
    def _match(self, posting: Posting) -> TrackedRole | None:
        if posting.board_job_id and posting.board_job_id in self._by_board_id:
            return self.roles[self._by_board_id[posting.board_job_id]]
        role_id = self._by_name.get(_name_key(posting.company, posting.title))
        return self.roles.get(role_id) if role_id else None

    def _index(self, role: TrackedRole, posting: Posting) -> None:
        role.sources.add(posting.source)
        if posting.board_job_id:
            role.board_job_ids.add(posting.board_job_id)
            self._by_board_id[posting.board_job_id] = role.role_id
        self._by_name[_name_key(posting.company, posting.title)] = role.role_id

    # -- scanning ----------------------------------------------------------- #
    def apply_scan(self, scans: list[SourceScan]) -> ScanDiff:
        diff = ScanDiff()
        ok_sources = {s.source for s in scans if s.ok}
        failed_sources = {s.source for s in scans if not s.ok}
        diff.skipped_sources = sorted(failed_sources)
        seen: set[str] = set()

        for scan in scans:
            if not scan.ok:
                continue
            for posting in scan.postings:
                reason = hide_reason(posting, self.config)
                if reason:
                    diff.hidden.append({"company": posting.company, "title": posting.title,
                                        "reason": reason})
                    continue
                role = self._match(posting)
                if role is None:
                    role = TrackedRole(role_id=_role_id(posting.company, posting.title),
                                       company=posting.company, title=posting.title,
                                       location=posting.location)
                    self.roles[role.role_id] = role
                    diff.new.append(role.role_id)
                self._index(role, posting)
                seen.add(role.role_id)

        for role in self.roles.values():
            if role.role_id in seen:
                if role.state == "closed":
                    role.state = "open"
                    diff.reopened.append(role.role_id)
                role.misses = 0
                continue
            # Only count a miss when we can prove absence: every source that has
            # listed this role was read successfully this scan.
            if role.state == "open" and role.sources and role.sources <= ok_sources:
                role.misses += 1
                if role.misses >= MISSES_TO_CLOSE:
                    role.state = "closed"
                    diff.closed.append(role.role_id)
        return diff

    # -- human-owned fields ------------------------------------------------- #
    def mark(self, role_id: str, user_status: str) -> None:
        if user_status not in USER_STATUSES:
            raise ValueError(f"unknown status: {user_status!r}")
        self.roles[role_id].user_status = user_status

    # -- persistence -------------------------------------------------------- #
    def snapshot(self) -> dict[str, Any]:
        return {
            rid: {"company": r.company, "title": r.title, "location": r.location,
                  "state": r.state, "misses": r.misses, "sources": sorted(r.sources),
                  "board_job_ids": sorted(r.board_job_ids), "user_status": r.user_status}
            for rid, r in sorted(self.roles.items())
        }


def save_and_verify(tracker: InternshipTracker, store: dict[str, str]) -> bool:
    """Write state to a (simulated) store, then read it back and compare.

    The daily run is only marked complete when this returns True.
    """
    expected = tracker.snapshot()
    store["tracker"] = json.dumps(expected, sort_keys=True)
    try:
        return json.loads(store["tracker"]) == expected
    except (KeyError, json.JSONDecodeError):
        return False


# --------------------------------------------------------------------------- #
# SIMULATED demo
# --------------------------------------------------------------------------- #

CONFIG = SearchConfig(locations=frozenset({"Example City"}))


def _day(list_ok: bool, board_ok: bool, include_role_b: bool) -> list[SourceScan]:
    board = [Posting("Example Job Board", "Example Startup A", "Software Engineering Intern",
                     "Example City", board_job_id="board-001")]
    if include_role_b:
        board.append(Posting("Example Job Board", "Example Startup B", "Data Intern",
                             "Example City", board_job_id="board-002"))
    listing = [
        Posting("Example Internship List", "Example Startup A", "Software Engineering Intern",
                "Example City"),
        Posting("Example Internship List", "Example Startup C", "Senior Engineer",
                "Example City"),
        Posting("Example Internship List", "Example Startup D", "Backend Intern",
                "Other City"),
    ]
    return [SourceScan("Example Job Board", board_ok, tuple(board)),
            SourceScan("Example Internship List", list_ok, tuple(listing))]


def main() -> None:
    tracker = InternshipTracker(CONFIG)
    store: dict[str, str] = {}
    days = [
        ("Day 1: both sources read", _day(True, True, True)),
        ("Day 2: job board fails; Data Intern absent but NOT counted as a miss",
         _day(True, False, False)),
        ("Day 3: Data Intern missing from a good read (miss 1 of 2)", _day(True, True, False)),
        ("Day 4: still missing (miss 2 of 2) -> closed", _day(True, True, False)),
    ]
    print("SIMULATED RUN - fictional data only; never applies or contacts anyone")
    for label, scans in days:
        diff = tracker.apply_scan(scans)
        if label.startswith("Day 1"):
            first = next(iter(tracker.roles))
            tracker.mark(first, "Applied")  # human decision, preserved by later scans
        saved = save_and_verify(tracker, store)
        print(f"\n{label}")
        print(json.dumps({"new": diff.new, "closed": diff.closed, "reopened": diff.reopened,
                          "hidden": [h["reason"] for h in diff.hidden],
                          "skipped_sources": diff.skipped_sources,
                          "saved_and_verified": saved}, indent=2))
    print("\nFinal tracker state")
    print(json.dumps(tracker.snapshot(), indent=2))


if __name__ == "__main__":
    main()
