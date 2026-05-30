"""
simulator/generators.py
========================
Semua fungsi generator untuk retail dataset.

Fungsi yang tersedia:
  generate_dim_customers_scd2(fake, config)  -> DataFrame  (SCD Type 2)
  generate_dim_products_scd2(fake, config)   -> DataFrame  (SCD Type 2, price history)
  generate_dim_stores(config)                -> DataFrame  (static)
  generate_fact_orders_and_items(customers, products, stores, config) -> (orders_df, items_df)
  generate_fact_payments(orders, config)     -> DataFrame
  generate_fact_events(customers, products, config) -> DataFrame
  generate_raw_returns(orders, fake, config) -> DataFrame
  generate_raw_inventory_feed(products, fake, config) -> DataFrame
  generate_snapshot_sources(batch, fake, config) -> (customers_df, products_df)
    batch: 1 = initial state, 2 = upgrades, 3 = churn
"""

import json
import random
import uuid
from datetime import timedelta

import pandas as pd

from utils import rand_ts, to_ts


# ─────────────────────────────────────────────────────────────────
# 1. DIM_CUSTOMERS  (SCD Type 2)
# ─────────────────────────────────────────────────────────────────

def generate_dim_customers_scd2(fake, config):
    """
    Customer dimension dengan SCD Type 2.
    ~30% customer punya 2 versi (pindah kota / naik segmen).
    ~2% versi pertama punya date overlap (edge case untuk stg_customers).
    """
    rows = []
    surrogate = 1

    for cust_id in range(1, config.N_CUSTOMERS + 1):
        name   = fake.name()
        email  = fake.email()
        phone  = fake.phone_number() if random.random() > 0.08 else None
        gender = random.choice(["M", "F", "prefer_not_to_say"])
        dob    = fake.date_of_birth(minimum_age=18, maximum_age=65)

        city_v1    = random.choice(config.CITIES)
        segment_v1 = random.choice(["new", "occasional"])
        start_v1   = config.START_DATE - timedelta(days=random.randint(0, 365))
        has_change = random.random() < 0.30

        end_v1 = rand_ts(
            start_v1 + timedelta(days=60),
            config.END_DATE - timedelta(days=30)
        ) if has_change else None

        # ~2% intentional date overlap untuk data quality showcase
        overlap = (end_v1 is not None) and (random.random() < 0.02)
        valid_to_v1 = to_ts(end_v1 + timedelta(hours=2)) if overlap and end_v1 else \
                      to_ts(end_v1) if end_v1 else None

        rows.append({
            "customer_key":  surrogate,
            "customer_id":   cust_id,
            "full_name":     name,
            "email":         email,
            "phone":         phone,
            "gender":        gender,
            "date_of_birth": str(dob),
            "city":          city_v1,
            "segment":       segment_v1,
            "referral_code": fake.bothify("REF-????##") if random.random() > 0.6 else None,
            "is_active":     True,
            "valid_from":    to_ts(start_v1),
            "valid_to":      valid_to_v1,
            "is_current":    not has_change,
            "updated_at":    to_ts(start_v1),
            "ingested_at":   to_ts(start_v1),
            "batch_id":      config.BATCH_ID,
        })
        surrogate += 1

        if has_change and end_v1:
            rows.append({
                "customer_key":  surrogate,
                "customer_id":   cust_id,
                "full_name":     name,
                "email":         email,
                "phone":         phone,
                "gender":        gender,
                "date_of_birth": str(dob),
                "city":          random.choice([c for c in config.CITIES if c != city_v1]),
                "segment":       random.choice(["loyal", "vip"]),
                "referral_code": fake.bothify("REF-????##") if random.random() > 0.6 else None,
                "is_active":     True,
                "valid_from":    to_ts(end_v1),
                "valid_to":      None,
                "is_current":    True,
                "updated_at":    to_ts(end_v1),
                "ingested_at":   to_ts(end_v1),
                "batch_id":      config.BATCH_ID,
            })
            surrogate += 1

    return pd.DataFrame(rows)


# ─────────────────────────────────────────────────────────────────
# 2. DIM_PRODUCTS  (SCD Type 2, price history)
# ─────────────────────────────────────────────────────────────────

def generate_dim_products_scd2(fake, config):
    """
    Product dimension dengan SCD Type 2.
    ~35% produk pernah reprice (naik atau turun).
    Kolom: product_key, product_id, sku, product_name, category,
           brand, cost_price, selling_price, weight_gram, is_active,
           valid_from, valid_to, is_current, updated_at
    """
    rows = []
    surrogate = 1

    for pid in range(1, config.N_PRODUCTS + 1):
        category = random.choice(config.CATEGORIES)
        brand    = fake.company().split()[0]
        name     = f"{brand} {fake.word().capitalize()} {random.choice(['Pro', 'Max', 'Lite', 'Plus', ''])}".strip()
        sku      = f"SKU-{str(pid).zfill(5)}"
        cost_v1  = round(random.uniform(20_000, 2_000_000), -3)
        price_v1 = round(cost_v1 * random.uniform(1.3, 2.5), -3)
        start_v1 = config.START_DATE - timedelta(days=random.randint(0, 180))

        has_reprice = random.random() < 0.35
        end_v1 = rand_ts(
            start_v1 + timedelta(days=30),
            config.END_DATE - timedelta(days=30)
        ) if has_reprice else None

        rows.append({
            "product_key":   surrogate,
            "product_id":    pid,
            "sku":           sku,
            "product_name":  name,
            "category":      category,
            "brand":         brand,
            "cost_price":    cost_v1,
            "selling_price": price_v1,
            "weight_gram":   random.randint(50, 5_000),
            "is_active":     True,
            "valid_from":    to_ts(start_v1),
            "valid_to":      to_ts(end_v1) if end_v1 else None,
            "is_current":    not has_reprice,
            "updated_at":    to_ts(start_v1),
        })
        surrogate += 1

        if has_reprice and end_v1:
            multiplier = random.choice([0.80, 0.85, 1.10, 1.20, 1.15])
            price_v2   = round(price_v1 * multiplier, -3)
            start_v2   = end_v1 + timedelta(seconds=1)
            rows.append({
                "product_key":   surrogate,
                "product_id":    pid,
                "sku":           sku,
                "product_name":  name,
                "category":      category,
                "brand":         brand,
                "cost_price":    cost_v1,
                "selling_price": price_v2,
                "weight_gram":   random.randint(50, 5_000),
                "is_active":     True,
                "valid_from":    to_ts(start_v2),
                "valid_to":      None,
                "is_current":    True,
                "updated_at":    to_ts(start_v2),
            })
            surrogate += 1

    return pd.DataFrame(rows)


# ─────────────────────────────────────────────────────────────────
# 3. DIM_STORES  (static dimension)
# ─────────────────────────────────────────────────────────────────

def generate_dim_stores(config):
    """
    Store dimension — statis, satu baris per channel.
    Kolom: store_id, store_name, channel_type, platform, city,
           region, opened_date, is_active
    """
    rows = []
    for i, ch in enumerate(config.CHANNELS, 1):
        is_online = "offline" not in ch
        rows.append({
            "store_id":     i,
            "store_name":   ch.replace("_", " ").title(),
            "channel_type": "online" if is_online else "offline",
            "platform":     ch,
            "city":         None if is_online else random.choice(config.CITIES),
            "region":       random.choice(["Jawa", "Sumatera", "Kalimantan", "Sulawesi"]),
            "opened_date":  str((config.START_DATE - timedelta(days=random.randint(365, 1825))).date()),
            "is_active":    True,
        })
    return pd.DataFrame(rows)


# ─────────────────────────────────────────────────────────────────
# 4. FACT_ORDERS + FACT_ORDER_ITEMS
# ─────────────────────────────────────────────────────────────────

def generate_fact_orders_and_items(customers, products, stores, config):
    """
    Generate fact_orders dan fact_order_items sekaligus.

    Data quality yang disimulasikan:
    - ~25 orphan items (item_id tanpa order header yang valid)
    - Diskon berbeda berdasarkan channel

    Kolom orders: order_id, customer_id, store_id, order_date, status,
                  gross_amount, discount_total, net_amount, channel,
                  shipping_city, updated_at, ingested_at, batch_id, source
    Kolom items:  item_id, order_id, product_id, quantity, unit_price,
                  discount, subtotal, ingested_at, batch_id
    """
    products_current  = products[products["is_current"]].copy()
    customers_current = customers[customers["is_current"]].copy()
    store_list        = stores.to_dict("records")

    # Lookup: store_id -> channel/platform string
    store_channel = {s["store_id"]: s["platform"] for s in store_list}

    orders = []
    items  = []

    orphan_order_ids = set(
        random.sample(range(config.N_ORDERS + 1, config.N_ORDERS + 200), 25)
    )

    for oid in range(1, config.N_ORDERS + 1):
        cust     = customers_current.sample(1).iloc[0]
        ts       = rand_ts()
        store    = random.choice(store_list)
        store_id = store["store_id"]
        channel  = store_channel[store_id]

        n_items = (
            random.randint(3, 6) if cust["segment"] == "vip"    else
            random.randint(2, 4) if cust["segment"] == "loyal"  else
            random.randint(1, 2)
        )

        status = random.choices(
            ["completed", "cancelled", "returned", "processing", "shipped"],
            weights=[55, 15, 10, 10, 10]
        )[0]

        gross = 0.0
        discount_total = 0.0
        selected = products_current.sample(min(n_items, len(products_current)))

        for _, prod in selected.iterrows():
            qty   = random.randint(1, 3)
            price = float(prod["selling_price"])

            discount = (
                price * random.choice([0, 0.10, 0.15])
                if store_id in [1, 2] else
                price * random.choice([0, 0.05])
            )

            subtotal = (price - discount) * qty
            gross    += price * qty
            discount_total += discount * qty

            items.append({
                "item_id":    str(uuid.uuid4()),
                "order_id":   oid,
                "product_id": int(prod["product_id"]),
                "quantity":   qty,
                "unit_price": price,
                "discount":   round(discount, 2),
                "subtotal":   round(subtotal, 2),
                "ingested_at": to_ts(ts),
                "batch_id":   config.BATCH_ID,
            })

        orders.append({
            "order_id":      oid,
            "customer_id":   int(cust["customer_id"]),
            "store_id":      store_id,
            "order_date":    to_ts(ts),
            "status":        status,
            "gross_amount":  round(gross, 2),
            "discount_total": round(discount_total, 2),
            "net_amount":    round(gross - discount_total, 2),
            "channel":       channel,
            "shipping_city": random.choice(config.CITIES),
            "updated_at":    to_ts(ts + timedelta(minutes=random.randint(0, 60))),
            "ingested_at":   to_ts(ts),
            "batch_id":      config.BATCH_ID,
            "source":        config.SOURCE_SYSTEM,
        })

    # Inject orphan items
    for oid in orphan_order_ids:
        prod = products_current.sample(1).iloc[0]
        ts   = rand_ts()
        items.append({
            "item_id":    str(uuid.uuid4()),
            "order_id":   oid,
            "product_id": int(prod["product_id"]),
            "quantity":   1,
            "unit_price": float(prod["selling_price"]),
            "discount":   0.0,
            "subtotal":   float(prod["selling_price"]),
            "ingested_at": to_ts(ts),
            "batch_id":   config.BATCH_ID,
        })

    return pd.DataFrame(orders), pd.DataFrame(items)


# ─────────────────────────────────────────────────────────────────
# 5. FACT_PAYMENTS
# ─────────────────────────────────────────────────────────────────

def generate_fact_payments(orders, config):
    """
    Payment transactions — bisa 1 order = 2 payments (split).
    Data quality: ~3% late-arriving (payment_date < order_date).

    Kolom: payment_id, order_id, amount, payment_method,
           payment_date, ingested_at, batch_id
    """
    payments   = []
    payment_id = 1

    for _, order in orders.iterrows():
        order_ts = pd.to_datetime(order["order_date"])
        net      = order["net_amount"]
        n_split  = random.choices([1, 2], weights=[85, 15])[0]

        splits = (
            [net] if n_split == 1 else
            [round(net * 0.6, 2), round(net * 0.4, 2)]
        )

        for amt in splits:
            is_late = random.random() < 0.03
            lag     = timedelta(minutes=random.randint(5, 1_440))
            pay_ts  = order_ts + (-lag if is_late else lag)

            payments.append({
                "payment_id":     payment_id,
                "order_id":       order["order_id"],
                "amount":         amt,
                "payment_method": random.choice(config.PAYMENT_METHODS),
                "payment_date":   to_ts(pay_ts),
                "ingested_at":    to_ts(pay_ts),
                "batch_id":       config.BATCH_ID,
            })
            payment_id += 1

    return pd.DataFrame(payments)


# ─────────────────────────────────────────────────────────────────
# 6. FACT_EVENTS  (clickstream)
# ─────────────────────────────────────────────────────────────────

def generate_fact_events(customers, products, config):
    """
    Clickstream events dengan full purchase funnel.
    Data quality: ~1% duplicate events (ROW_NUMBER() di stg_events).

    Kolom: event_id, session_id, customer_id, product_id, event_type,
           event_ts, channel, device, funnel_stage, ingested_at, batch_id
    """
    EVENT_FLOW = [
        "page_view",
        "product_view",
        "add_to_cart",
        "checkout_start",
        "checkout_complete",
    ]

    FUNNEL_MAP = {e: i + 1 for i, e in enumerate(EVENT_FLOW)}

    customers_active = customers[customers["is_current"]].copy()
    products_current = products[products["is_current"]].copy()

    events = []

    for _ in range(config.N_EVENTS):
        ts         = rand_ts()
        session_id = str(uuid.uuid4())
        cust       = customers_active.sample(1).iloc[0] if random.random() > 0.15 else None
        prod       = products_current.sample(1).iloc[0] if random.random() > 0.30 else None
        event_type = random.choice(EVENT_FLOW)

        events.append({
            "event_id":    str(uuid.uuid4()),
            "session_id":  session_id,
            "customer_id": int(cust["customer_id"]) if cust is not None else None,
            "product_id":  int(prod["product_id"]) if prod is not None else None,
            "event_type":  event_type,
            "event_ts":    to_ts(ts),
            "channel":     random.choice(config.CHANNELS),
            "device":      random.choice(["mobile", "desktop"]),
            "funnel_stage": FUNNEL_MAP.get(event_type, 0),
            "ingested_at": to_ts(ts),
            "batch_id":    config.BATCH_ID,
        })

    df = pd.DataFrame(events)

    # Inject ~1% duplicates
    dupes = df.sample(int(len(df) * 0.01)).copy()
    df    = pd.concat([df, dupes], ignore_index=True)

    return df.sample(frac=1).reset_index(drop=True)


# ─────────────────────────────────────────────────────────────────
# 7. RAW_RETURNS  (messy format — perlu cleaning di staging)
# ─────────────────────────────────────────────────────────────────

def generate_raw_returns(orders, fake, config):
    """
    Return requests dari order yang statusnya 'returned'.
    Data quality yang disimulasikan:
    - Inconsistent casing pada kolom reason
    - 10% dalam USD (currency mismatch)
    - NULL pada kolom opsional

    Kolom: return_ref, order_id, return_date, reason, refund_amount,
           currency, refund_method, ingested_at
    """
    REASONS = [
        "Produk rusak",
        "PRODUK TIDAK SESUAI DESKRIPSI",
        "salah kirim",
        "barang cacat",
        "Tidak suka",
        "ukuran tidak pas",
        None,
    ]

    rows = []
    returned_orders = orders[orders["status"] == "returned"]["order_id"].tolist()

    for oid in returned_orders:
        refund_idr = round(random.uniform(50_000, 1_000_000), -3)

        if random.random() < 0.10:  # currency mismatch anomaly
            currency   = "USD"
            refund_amt = round(refund_idr / 15_500, 2)
        else:
            currency   = "IDR"
            refund_amt = refund_idr

        order_ts = pd.to_datetime(
            orders.loc[orders["order_id"] == oid, "order_date"].iloc[0]
        )
        start_ts = order_ts.to_pydatetime() + timedelta(days=1)
        end_ts   = config.END_DATE

        if start_ts >= end_ts:
            continue  # skip return ini (invalid timeline)

        return_ts = rand_ts(start=start_ts, end=end_ts)

        rows.append({
            "return_ref":    f"RET-{str(uuid.uuid4())[:8].upper()}",
            "order_id":      oid,
            "return_date":   str(return_ts.date()),
            "reason":        random.choice(REASONS),
            "refund_amount": refund_amt,
            "currency":      currency,
            "refund_method": random.choice(["original", "store_credit", "bank_transfer"]),
            "ingested_at":   to_ts(return_ts),
        })

    return pd.DataFrame(rows)


# ─────────────────────────────────────────────────────────────────
# 8. RAW_INVENTORY_FEED  (semi-structured — nested JSON metadata)
# ─────────────────────────────────────────────────────────────────

def generate_raw_inventory_feed(products, fake, config):
    """
    Weekly inventory snapshot dengan nested JSON metadata.
    Kolom: snapshot_date, warehouse_id, product_id, sku,
           qty_on_hand, qty_reserved, reorder_point, metadata (JSON)
    """
    WAREHOUSES = ["WH-JKT", "WH-SBY", "WH-BDG", "WH-MDN"]
    products_current = products[products["is_current"]].copy()
    dates = pd.date_range(config.START_DATE, config.END_DATE, freq="W")

    rows = []
    for dt in dates:
        for _, prod in products_current.iterrows():
            rows.append({
                "snapshot_date": str(dt.date()),
                "warehouse_id":  random.choice(WAREHOUSES),
                "product_id":    int(prod["product_id"]),
                "sku":           prod["sku"],
                "qty_on_hand":   random.randint(0, 500),
                "qty_reserved":  random.randint(0, 50),
                "reorder_point": random.choice([10, 20, 50]),
                "metadata": json.dumps({
                    "last_restock":  str(fake.date_between(start_date="-90d", end_date="today")),
                    "storage_zone":  random.choice(["A", "B", "C"]),
                    "temp_sensitive": random.choice([True, False]),
                }),
            })

    return pd.DataFrame(rows)


# ─────────────────────────────────────────────────────────────────
# 9. SNAPSHOT SOURCES  (flat current-state — untuk dbt snapshot)
# ─────────────────────────────────────────────────────────────────

def generate_snapshot_sources(batch, fake, config):
    """
    Generate raw_customers_current dan raw_products_current.
    Ini adalah tabel FLAT (tidak ada histori) yang mensimulasikan
    sistem sumber yang hanya menyimpan state terbaru.

    dbt snapshot akan track perubahannya menjadi SCD Type 2.

    batch=1 : initial state (semua new/occasional, harga awal)
    batch=2 : segment upgrades (~30% naik ke loyal/vip) + repricing (~20%)
    batch=3 : churn events (~10% jadi churned) + price adjustments

    Returns: (customers_df, products_df)
    """
    batch_ts = config.SNAPSHOT_BATCH_TIMESTAMPS[batch]

    # ── Customers ──────────────────────────────────────────────
    customers = []
    rng_cust = random.Random(batch * 100)  # deterministik per batch

    for cid in range(1, config.N_CUSTOMERS + 1):
        if batch == 1:
            segment = rng_cust.choice(["new", "occasional"])
            city    = rng_cust.choice(config.CITIES)
        elif batch == 2:
            if rng_cust.random() < 0.30:
                segment = rng_cust.choice(["loyal", "vip"])
                city    = rng_cust.choice(config.CITIES)
            else:
                segment = rng_cust.choice(["new", "occasional"])
                city    = rng_cust.choice(config.CITIES)
        else:  # batch 3
            roll = rng_cust.random()
            if roll < 0.10:
                segment = "churned"
            elif roll < 0.40:
                segment = rng_cust.choice(["loyal", "vip"])
            else:
                segment = rng_cust.choice(["new", "occasional"])
            city = rng_cust.choice(config.CITIES)

        customers.append({
            "customer_id":   cid,
            "full_name":     fake.name(),
            "email":         fake.email(),
            "phone":         fake.phone_number() if rng_cust.random() > 0.08 else None,
            "gender":        rng_cust.choice(["M", "F", "prefer_not_to_say"]),
            "date_of_birth": str(fake.date_of_birth(minimum_age=18, maximum_age=65)),
            "city":          city,
            "segment":       segment,
            "referral_code": fake.bothify("REF-????##") if rng_cust.random() > 0.6 else None,
            "is_active":     segment != "churned",
            "updated_at":    to_ts(
                batch_ts + timedelta(hours=rng_cust.randint(0, 48))
            ),
        })

    # ── Products ───────────────────────────────────────────────
    products = []
    rng_prod = random.Random(batch * 200)

    CATEGORIES = config.CATEGORIES

    for pid in range(1, config.N_PRODUCTS + 1):
        category = rng_prod.choice(CATEGORIES)
        brand    = fake.company().split()[0]
        cost     = round(rng_prod.uniform(20_000, 2_000_000), -3)

        if batch == 1:
            price = round(cost * rng_prod.uniform(1.3, 2.5), -3)
        elif batch == 2:
            base  = round(cost * rng_prod.uniform(1.3, 2.5), -3)
            price = round(base * rng_prod.choice([1.0, 1.0, 1.10, 1.20, 0.85]), -3) \
                    if rng_prod.random() < 0.20 else base
        else:  # batch 3
            base  = round(cost * rng_prod.uniform(1.3, 2.5), -3)
            price = round(base * rng_prod.choice([0.80, 0.90, 1.10, 1.15]), -3) \
                    if rng_prod.random() < 0.25 else base

        products.append({
            "product_id":    pid,
            "sku":           f"SKU-{str(pid).zfill(5)}",
            "product_name":  f"{brand} {fake.word().capitalize()}".strip(),
            "category":      category,
            "brand":         brand,
            "cost_price":    cost,
            "selling_price": price,
            "weight_gram":   rng_prod.randint(50, 5_000),
            "is_active":     True,
            "updated_at":    to_ts(
                batch_ts + timedelta(hours=rng_prod.randint(0, 48))
            ),
        })

    return pd.DataFrame(customers), pd.DataFrame(products)
