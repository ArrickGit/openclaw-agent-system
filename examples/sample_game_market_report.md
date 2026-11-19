# Game-Market Monitor Report (SIMULATED)

> **SIMULATED EXAMPLE.** All items, players, channels, prices, and listings below are fictional.
> No real messages are quoted. "Example Player" names are placeholders.

**Source:** Game Market Channel (fictional, read-only)
**Filters:** item = `Example Item A`, direction = `sell`, currency = `credits`
**Rolling window:** last 24 hours
**Previous recorded low:** 1,000 credits

---

## Result: new low observed

| Field | Value |
|---|---|
| Item | Example Item A |
| Direction | sell |
| Price | **950 credits** |
| Seller | Example Player 2 |
| Observed at | 2030-01-15 10:05 UTC (fictional) |
| Observation ID | `sha256:d06ffec6…89cdaf` (from the simulated demo) |
| Change vs. previous low | -50 credits (-5.0%) |

## Observations in window

| # | Item | Direction | Price | Currency | Player | Outcome |
|---:|---|---|---:|---|---|---|
| 1 | Example Item A | sell | 1,200 | credits | Example Player 1 | accepted |
| 2 | Example Item A | sell | 950 | credits | Example Player 2 | accepted, **lowest** |
| 3 | Example Item A | sell | 950 | credits | Example Player 2 | duplicate (same ID as #2), suppressed |
| 4 | Example Item A | sell | 500 | tokens | Example Player 3 | rejected: currency mismatch |
| 5 | Example Item A | buy | 400 | credits | Example Player 4 | rejected: direction mismatch |
| 6 | Example Item A | sell | 700 | credits | Example Player 5 | rejected: outside 24h window |
| 7 | Example Item A | sell | n/a | credits | Example Player 6 | rejected: price could not be parsed |

## Run summary

```json
{
  "label": "SIMULATED",
  "status": "alert",
  "completed": true,
  "observations_seen": 7,
  "accepted": 2,
  "duplicates_suppressed": 1,
  "rejected": 4,
  "stages": ["normalized_and_identified", "deduplicated", "filtered", "classified", "completed"],
  "messages_sent_to_market": 0,
  "purchases_made": 0
}
```

The monitor is read-only. It sends no messages to the market or to players and makes no
purchases. This report is the only output.
