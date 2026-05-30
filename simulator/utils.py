# simulator/utils.py

import random
import uuid
from datetime import timedelta
from config import START_DATE, END_DATE


def rand_ts(start=None, end=None):
    """Return a random datetime between start and end."""
    s = start or START_DATE
    e = end   or END_DATE
    delta = e - s
    return s + timedelta(seconds=random.randint(0, int(delta.total_seconds())))


def to_ts(dt):
    """Format datetime to ISO string."""
    return dt.strftime("%Y-%m-%d %H:%M:%S")


def new_uuid():
    return str(uuid.uuid4())


# kept for backward compat with old generators.py call sites
def generate_random_timestamp():
    return rand_ts()
