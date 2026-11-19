# Daily Stock Observation Report (SIMULATED)

> **SIMULATED EXAMPLE.** Every ticker, price, percentage, and headline below is fictional and
> was made up to show the report format. `FICT-*` symbols and the `BENCH` index do not exist.

**Session date:** 2030-01-15 (fictional)
**Data freshness check:** passed (session date matches expected trading day)
**Benchmark:** BENCH (fictional broad-market index): **+0.40%**

---

## Watchlist movement

| Symbol | Close | Day % | vs. BENCH | Rel. volume | 5-day % | Day range % |
|---|---:|---:|---:|---:|---:|---:|
| FICT-A | 48.20 | +3.10% | +2.70 pp | 2.4× | +6.8% | 4.1% |
| FICT-B | 112.55 | -1.80% | -2.20 pp | 1.1× | -0.9% | 2.6% |
| FICT-C | 23.07 | +0.35% | -0.05 pp | 0.8× | +1.2% | 1.4% |
| FICT-D | 301.40 | -0.10% | -0.50 pp | 0.9× | +2.3% | 1.1% |

**Notes**

- **FICT-A** beat the benchmark by 2.7 percentage points on 2.4× its 20-day average volume and
  is up 6.8% over five sessions. Fictional context: *"FICT-A announces sample product update"*.
- **FICT-B** lagged the benchmark on roughly normal volume. No unusual activity flagged.
- FICT-C and FICT-D moved roughly in line with the benchmark.

## Volume context

| Symbol | Today volume | 20-day avg volume | Ratio |
|---|---:|---:|---:|
| FICT-A | 9.6M | 4.0M | 2.4× |
| FICT-B | 3.3M | 3.0M | 1.1× |
| FICT-C | 1.2M | 1.5M | 0.8× |
| FICT-D | 5.4M | 6.0M | 0.9× |

## Research candidates (dynamic discovery)

Found by scanning a broad (fictional) market universe for unusual benchmark-relative movement,
volume, five-day momentum, and range. **These are candidates for further research, not trading
recommendations.**

| Symbol | Day % | vs. BENCH | Rel. volume | 5-day % | Day range % | Why it was flagged |
|---|---:|---:|---:|---:|---:|---|
| FICT-X | +8.90% | +8.50 pp | 5.1× | +14.2% | 11.3% | Large relative move on very high volume |
| FICT-Y | -6.40% | -6.80 pp | 3.7× | -9.5% | 8.0% | Sharp decline with elevated volume; fictional headline about guidance |
| FICT-Z | +4.20% | +3.80 pp | 2.9× | +4.0% | 5.6% | Breakout from a quiet five-day range |

## Run metadata

```json
{
  "label": "SIMULATED",
  "session_date": "2030-01-15",
  "benchmark": "BENCH",
  "watchlist_count": 4,
  "candidates_count": 3,
  "validation": "passed",
  "trades_executed": 0
}
```

---

**Disclaimer:** This is a simulated example with fictional data. It is not financial advice and
not a recommendation to buy or sell any security. The stock observer does not execute trades.
