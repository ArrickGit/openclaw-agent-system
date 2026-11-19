"""Simulated game-market monitor (sanitized showcase).

SIMULATED: every observation in this module is fictional. This file does not
connect to any chat platform, browser, marketplace, or external service. It
exists to demonstrate the data-handling pattern used by the game-market monitor
in my OpenClaw environment:

    normalize -> assign deterministic ID -> validate ID -> deduplicate
              -> filter (item, direction, currency, rolling window)
              -> classify alert -> structured result + completion record

The key invariant: every observation entering alert classification must have a
non-empty, valid SHA-256 observation ID.
"""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import asdict, dataclass, field, replace
from datetime import datetime, timedelta, timezone
from typing import Any, Callable, Iterable

ID_PATTERN = re.compile(r"^[0-9a-f]{64}$")
VALID_DIRECTIONS = frozenset({"buy", "sell"})


class InvariantViolation(Exception):
    """Raised when data reaches a pipeline stage it is not allowed to reach."""


class NormalizationError(ValueError):
    """Raised when a raw observation cannot be normalized."""


@dataclass(frozen=True)
class Observation:
    item: str
    direction: str
    price: int
    currency: str
    timestamp: datetime
    source_text: str
    observation_id: str = ""


@dataclass(frozen=True)
class MonitorConfig:
    item: str
    direction: str
    currency: str
    window: timedelta = timedelta(hours=24)

    def normalized(self) -> "MonitorConfig":
        return MonitorConfig(
            item=_clean(self.item),
            direction=_clean(self.direction),
            currency=_clean(self.currency),
            window=self.window,
        )


@dataclass
class MonitorResult:
    status: str  # "alert" | "no_alert" | "no_valid_observations" | "failed"
    completed: bool
    lowest: Observation | None = None
    is_new_low: bool = False
    accepted: list[Observation] = field(default_factory=list)
    rejected: list[dict[str, Any]] = field(default_factory=list)
    duplicates_suppressed: int = 0
    stages: list[str] = field(default_factory=list)
    error: str | None = None

    def to_dict(self) -> dict[str, Any]:
        def obs_dict(o: Observation) -> dict[str, Any]:
            d = asdict(o)
            d["timestamp"] = o.timestamp.isoformat()
            return d

        return {
            "status": self.status,
            "completed": self.completed,
            "lowest": obs_dict(self.lowest) if self.lowest else None,
            "is_new_low": self.is_new_low,
            "accepted_count": len(self.accepted),
            "rejected": self.rejected,
            "duplicates_suppressed": self.duplicates_suppressed,
            "stages": self.stages,
            "error": self.error,
        }


# --------------------------------------------------------------------------- #
# Normalization and identifiers
# --------------------------------------------------------------------------- #

def _clean(text: Any) -> str:
    """Collapse whitespace and casefold so equivalent text compares equal."""
    return " ".join(str(text).split()).casefold()


def _parse_timestamp(value: Any) -> datetime:
    if isinstance(value, datetime):
        ts = value
    elif isinstance(value, str):
        ts = datetime.fromisoformat(value)
    else:
        raise NormalizationError("timestamp must be a datetime or ISO-8601 string")
    if ts.tzinfo is None:
        raise NormalizationError("timestamp must be timezone-aware")
    return ts.astimezone(timezone.utc).replace(microsecond=0)


def _parse_price(value: Any) -> int:
    if isinstance(value, bool):
        raise NormalizationError("price must be numeric")
    if isinstance(value, str):
        value = value.replace(",", "").strip()
    try:
        price = int(value)
    except (TypeError, ValueError) as exc:
        raise NormalizationError("price must be an integer") from exc
    if price <= 0:
        raise NormalizationError("price must be positive")
    return price


def normalize(raw: dict[str, Any]) -> Observation:
    """Turn a raw (simulated) observation into a canonical Observation."""
    try:
        direction = _clean(raw["direction"])
        if direction not in VALID_DIRECTIONS:
            raise NormalizationError(f"unknown direction: {direction!r}")
        item = _clean(raw["item"])
        currency = _clean(raw["currency"])
        if not item or not currency:
            raise NormalizationError("item and currency are required")
        return Observation(
            item=item,
            direction=direction,
            price=_parse_price(raw["price"]),
            currency=currency,
            timestamp=_parse_timestamp(raw["timestamp"]),
            source_text=" ".join(str(raw.get("source_text", "")).split()),
        )
    except KeyError as exc:
        raise NormalizationError(f"missing field: {exc.args[0]}") from exc


def compute_observation_id(obs: Observation) -> str:
    """Deterministic SHA-256 over normalized fields.

    The same logical observation seen on two different scans produces the same
    ID, which makes deduplication and re-runs idempotent.
    """
    canonical = "|".join(
        [
            obs.item,
            obs.direction,
            str(obs.price),
            obs.currency,
            obs.timestamp.isoformat(),
            _clean(obs.source_text),
        ]
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def is_valid_id(observation_id: str | None) -> bool:
    return bool(observation_id) and bool(ID_PATTERN.match(observation_id))


# --------------------------------------------------------------------------- #
# Pipeline stages
# --------------------------------------------------------------------------- #

def deduplicate(observations: Iterable[Observation]) -> tuple[list[Observation], int]:
    seen: set[str] = set()
    unique: list[Observation] = []
    duplicates = 0
    for obs in observations:
        if obs.observation_id in seen:
            duplicates += 1
            continue
        seen.add(obs.observation_id)
        unique.append(obs)
    return unique, duplicates


def matches_filters(obs: Observation, config: MonitorConfig, now: datetime) -> str | None:
    """Return a rejection reason, or None if the observation passes every filter."""
    if obs.item != config.item:
        return "item_mismatch"
    if obs.direction != config.direction:
        return "direction_mismatch"
    if obs.currency != config.currency:
        return "currency_mismatch"
    if obs.timestamp > now:
        return "timestamp_in_future"
    if obs.timestamp < now - config.window:
        return "outside_window"
    return None


def classify_alert(
    candidates: list[Observation], previous_low_price: int | None
) -> tuple[Observation | None, bool]:
    """Select the lowest observation and decide whether it is a new low.

    Enforces the invariant that every candidate has a valid ID. Callers must
    never be able to classify (and later deliver) an unidentified observation.
    """
    for obs in candidates:
        if not is_valid_id(obs.observation_id):
            raise InvariantViolation(
                "observation entered alert classification without a valid ID"
            )
    if not candidates:
        return None, False
    lowest = min(candidates, key=lambda o: (o.price, o.timestamp, o.observation_id))
    is_new_low = previous_low_price is None or lowest.price < previous_low_price
    return lowest, is_new_low


def run_monitor(
    raw_observations: Iterable[dict[str, Any]],
    config: MonitorConfig,
    now: datetime,
    previous_low_price: int | None = None,
    id_fn: Callable[[Observation], str] = compute_observation_id,
) -> MonitorResult:
    """Run one simulated monitor pass and return a structured result.

    `id_fn` is injectable so tests can simulate a faulty ID generator.
    """
    config = config.normalized()
    now = _parse_timestamp(now)
    result = MonitorResult(status="failed", completed=False)

    try:
        # 1. Normalize, then assign and validate IDs immediately.
        identified: list[Observation] = []
        for index, raw in enumerate(raw_observations):
            try:
                obs = normalize(raw)
            except NormalizationError as exc:
                result.rejected.append({"index": index, "reason": f"normalization: {exc}"})
                continue
            obs = replace(obs, observation_id=id_fn(obs))
            if not is_valid_id(obs.observation_id):
                result.rejected.append({"index": index, "reason": "missing_or_invalid_id"})
                continue
            identified.append(obs)
        result.stages.append("normalized_and_identified")

        # 2. Deduplicate by deterministic ID.
        unique, result.duplicates_suppressed = deduplicate(identified)
        result.stages.append("deduplicated")

        # 3. Apply explicit filters.
        for obs in unique:
            reason = matches_filters(obs, config, now)
            if reason:
                result.rejected.append({"observation_id": obs.observation_id, "reason": reason})
            else:
                result.accepted.append(obs)
        result.stages.append("filtered")

        # 4. Classify (invariant enforced inside).
        lowest, is_new_low = classify_alert(result.accepted, previous_low_price)
        result.stages.append("classified")

    except InvariantViolation as exc:
        # Safe failure: do not mark the run complete, do not produce an alert.
        result.status = "failed"
        result.completed = False
        result.error = str(exc)
        return result

    result.lowest = lowest
    result.is_new_low = is_new_low
    if lowest is None:
        result.status = "no_valid_observations"
    else:
        result.status = "alert" if is_new_low else "no_alert"
    result.completed = True
    result.stages.append("completed")  # completion sentinel
    return result


# --------------------------------------------------------------------------- #
# SIMULATED demo data
# --------------------------------------------------------------------------- #

SIMULATED_NOW = datetime(2030, 1, 15, 12, 0, tzinfo=timezone.utc)

SIMULATED_OBSERVATIONS: list[dict[str, Any]] = [
    {"item": "Example Item A", "direction": "sell", "price": "1,200", "currency": "credits",
     "timestamp": "2030-01-15T09:30:00+00:00", "source_text": "[simulated] selling Example Item A 1,200 credits"},
    {"item": "Example Item A", "direction": "sell", "price": 950, "currency": "credits",
     "timestamp": "2030-01-15T10:05:00+00:00", "source_text": "[simulated] Example Item A for 950 credits"},
    # Same listing captured again on a later scan -> duplicate.
    {"item": "example item a", "direction": "SELL", "price": 950, "currency": "Credits",
     "timestamp": "2030-01-15T10:05:00+00:00", "source_text": "[simulated]  Example Item A for 950 credits"},
    # Cheaper, but wrong currency.
    {"item": "Example Item A", "direction": "sell", "price": 500, "currency": "tokens",
     "timestamp": "2030-01-15T11:00:00+00:00", "source_text": "[simulated] Example Item A 500 tokens"},
    # Buy request, not a sell listing.
    {"item": "Example Item A", "direction": "buy", "price": 400, "currency": "credits",
     "timestamp": "2030-01-15T11:10:00+00:00", "source_text": "[simulated] buying Example Item A 400 credits"},
    # Outside the 24h window.
    {"item": "Example Item A", "direction": "sell", "price": 700, "currency": "credits",
     "timestamp": "2030-01-13T08:00:00+00:00", "source_text": "[simulated] old listing Example Item A 700"},
    # Malformed price.
    {"item": "Example Item A", "direction": "sell", "price": "cheap", "currency": "credits",
     "timestamp": "2030-01-15T11:20:00+00:00", "source_text": "[simulated] Example Item A cheap"},
]


def main() -> None:
    config = MonitorConfig(item="Example Item A", direction="sell", currency="credits")
    result = run_monitor(
        SIMULATED_OBSERVATIONS, config, now=SIMULATED_NOW, previous_low_price=1000
    )
    print("SIMULATED RUN - fictional data only")
    print(json.dumps(result.to_dict(), indent=2))


if __name__ == "__main__":
    main()
