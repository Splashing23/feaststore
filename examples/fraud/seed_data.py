"""Generate synthetic source tables for the fraud example and load them into Postgres.

Usage:
    python examples/fraud/seed_data.py

Reads FEASTSTORE_OFFLINE_DSN from the environment (falls back to the local
docker-compose default). Deterministic given --seed so the example is reproducible.
"""

from __future__ import annotations

import argparse
import random
from datetime import datetime, timedelta

import pandas as pd
from sqlalchemy import create_engine

from feaststore.config import get_settings


def _build_velocity(n_cards: int, rng: random.Random, now: datetime) -> pd.DataFrame:
    rows = []
    for card_id in range(1, n_cards + 1):
        # a handful of hourly snapshots per card
        for h in range(rng.randint(1, 6)):
            ts = now - timedelta(hours=h)
            rows.append(
                {
                    "card_id": card_id,
                    "txn_count_1h": rng.randint(0, 8),
                    "txn_amount_1h": round(rng.uniform(0, 900), 2),
                    "txn_count_24h": rng.randint(0, 60),
                    "distinct_merchants_24h": rng.randint(0, 20),
                    "event_timestamp": ts,
                }
            )
    return pd.DataFrame(rows)


def _build_account(n_cards: int, rng: random.Random, now: datetime) -> pd.DataFrame:
    countries = ["US", "GB", "DE", "IN", "BR", "NG"]
    return pd.DataFrame(
        [
            {
                "card_id": card_id,
                "account_age_days": rng.randint(1, 3000),
                "is_prepaid": rng.random() < 0.15,
                "issuer_country": rng.choice(countries),
                "event_timestamp": now - timedelta(days=rng.randint(0, 5)),
            }
            for card_id in range(1, n_cards + 1)
        ]
    )


def _build_card_merchant(n_cards: int, rng: random.Random, now: datetime) -> pd.DataFrame:
    rows = []
    for card_id in range(1, n_cards + 1):
        for merchant_id in rng.sample(range(1, 51), rng.randint(1, 5)):
            rows.append(
                {
                    "card_id": card_id,
                    "merchant_id": merchant_id,
                    "prior_txns": rng.randint(0, 200),
                    "avg_ticket": round(rng.uniform(5, 300), 2),
                    "event_timestamp": now - timedelta(days=rng.randint(0, 20)),
                }
            )
    return pd.DataFrame(rows)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--cards", type=int, default=200)
    parser.add_argument("--seed", type=int, default=7)
    # fixed reference time keeps the generated data stable across runs
    parser.add_argument("--now", default="2025-06-01T12:00:00")
    args = parser.parse_args()

    rng = random.Random(args.seed)
    now = datetime.fromisoformat(args.now)
    engine = create_engine(get_settings().offline_dsn, future=True)

    tables = {
        "card_velocity_source": _build_velocity(args.cards, rng, now),
        "card_account_source": _build_account(args.cards, rng, now),
        "card_merchant_source": _build_card_merchant(args.cards, rng, now),
    }
    with engine.begin() as conn:
        for name, df in tables.items():
            df.to_sql(name, conn, index=False, if_exists="replace")
            print(f"loaded {len(df):>5} rows -> {name}")


if __name__ == "__main__":
    main()
