# simulator/config.py
# ─────────────────────────────────────────────────────────────────
# Single source of truth untuk semua konstanta simulator.
# Diimport oleh generators.py dan main.py.
# ─────────────────────────────────────────────────────────────────

from datetime import datetime

# ── Time range ────────────────────────────────────────────────────
START_DATE = datetime(2023, 1, 1)
END_DATE   = datetime(2024, 12, 31)

# ── Volume ────────────────────────────────────────────────────────
N_CUSTOMERS = 500
N_PRODUCTS  = 120
N_ORDERS    = 5_000
N_EVENTS    = 25_000

# ── Output ────────────────────────────────────────────────────────
OUTPUT_DIR = "retail_raw_data"

# ── Metadata ──────────────────────────────────────────────────────
BATCH_ID      = "batch_001"
SOURCE_SYSTEM = "retail_simulator"

# ── Domain values ─────────────────────────────────────────────────
CATEGORIES = ["Electronics", "Apparel", "Home & Living", "Beauty", "Sports", "Books"]

CHANNELS = [
    "web",
    "mobile_app",
    "marketplace_tokopedia",
    "marketplace_shopee",
    "store_offline",
]

PAYMENT_METHODS = [
    "credit_card",
    "debit_card",
    "bank_transfer",
    "e-wallet_gopay",
    "e-wallet_ovo",
    "cod",
    "paylater",
]

CITIES = [
    "Jakarta", "Surabaya", "Bandung", "Medan", "Semarang",
    "Makassar", "Yogyakarta", "Palembang", "Depok", "Tangerang",
]

SEGMENTS = ["new", "occasional", "loyal", "vip", "churned"]

PROMO_CODES = [f"PROMO{str(i).zfill(3)}" for i in range(1, 31)]

# ── Snapshot batch config ─────────────────────────────────────────
# Batch 1 = initial state (load sebelum dbt snapshot pertama)
# Batch 2 = segment upgrades + price changes
# Batch 3 = churn events + final price adjustments
SNAPSHOT_BATCH_TIMESTAMPS = {
    1: datetime(2023, 1, 15),
    2: datetime(2023, 9, 1),
    3: datetime(2024, 6, 1),
}
