"""Example feature repo: card-fraud detection.

Run `feaststore apply examples/fraud/feature_repo.py` to register these, then
`feaststore materialize` to push them online. The features here are the sort you'd
actually build for a real-time fraud model: trailing transaction velocity per
card, and slowly-changing account attributes.
"""

from datetime import timedelta

from feaststore import Entity, Feature, FeatureView, ValueType

card = Entity(
    name="card",
    join_key="card_id",
    description="A payment card (hashed PAN).",
)

merchant = Entity(
    name="merchant",
    join_key="merchant_id",
    description="A merchant accepting payments.",
)

# Fast-moving behavioural features -- short ttl, materialized frequently.
card_velocity = FeatureView(
    name="card_velocity",
    entities=[card],
    features=[
        Feature("txn_count_1h", ValueType.INT64, "Transactions in the trailing hour"),
        Feature("txn_amount_1h", ValueType.FLOAT, "Total amount in the trailing hour"),
        Feature("txn_count_24h", ValueType.INT64, "Transactions in the trailing day"),
        Feature("distinct_merchants_24h", ValueType.INT64, "Distinct merchants, 24h"),
    ],
    source_table="card_velocity_source",
    ttl=timedelta(hours=2),
)

# Slowly-changing account attributes -- long ttl.
card_account = FeatureView(
    name="card_account",
    entities=[card],
    features=[
        Feature("account_age_days", ValueType.INT64),
        Feature("is_prepaid", ValueType.BOOL),
        Feature("issuer_country", ValueType.STRING),
    ],
    source_table="card_account_source",
    ttl=timedelta(days=7),
    tags={"team": "risk", "owner": "dev"},
)

# Cross-entity features keyed on (card, merchant).
card_merchant = FeatureView(
    name="card_merchant",
    entities=[card, merchant],
    features=[
        Feature("prior_txns", ValueType.INT64, "Historical txns between this card+merchant"),
        Feature("avg_ticket", ValueType.FLOAT),
    ],
    source_table="card_merchant_source",
    ttl=timedelta(days=30),
)
