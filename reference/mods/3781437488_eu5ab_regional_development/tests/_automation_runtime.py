"""Shared setup for harnesses that enter after monthly/queue initialization."""

from tests._governor_script_vm import parse
from tests._generated import _blocks_for_token


def country_counter_initializers(effects):
    """Use actual top-level zero writes, never invent missing counter defaults.

    These harnesses skip the monthly economic setup. Backfill and watchdog
    counters that are absent at this boundary must remain absent in tests.
    """
    entries = []
    for name in ("eu5ab_run_regional_development_policy", "eu5ab_prepare_engine_candidate_queue"):
        body = parse(_blocks_for_token(effects, "\n" + name + " = ")[0])[0][2]
        for entry in body:
            key, _, value = entry
            if key == "set_variable" and isinstance(value, list):
                data = {k: v for k, _, v in value}
                if data.get("value") == "0":
                    entries.append(entry)
    return entries
