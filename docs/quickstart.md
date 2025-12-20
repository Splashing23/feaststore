# Quickstart

## 1. Bring up the stores

```bash
make up            # postgres + redis via docker compose
pip install -e ".[dev]"
```

## 2. Seed synthetic data + register features

```bash
make seed          # loads the fraud example source tables into Postgres
make apply         # registers the feature views from examples/fraud/feature_repo.py
feaststore list
```

## 3. Materialize online

```bash
make materialize
```

## 4. Serve

```bash
make serve         # uvicorn on :8000
```

```bash
curl -s localhost:8000/get-online-features \
  -H 'content-type: application/json' \
  -d '{
        "features": ["card_velocity:txn_count_1h", "card_account:issuer_country"],
        "entities": [{"card_id": 1}, {"card_id": 2}]
      }' | jq
```

## 5. Build a training set (point-in-time correct)

```python
import pandas as pd
from feaststore.store import FeatureStore

store = FeatureStore()

# your labels, each with the timestamp the label was observed
entities = pd.DataFrame({
    "card_id": [1, 2, 3],
    "event_timestamp": pd.to_datetime(["2025-05-01", "2025-05-02", "2025-05-03"]),
})

training_df = store.get_historical_features(
    entity_df=entities,
    features=["card_velocity:txn_count_1h", "card_account:account_age_days"],
)
print(training_df)
```
