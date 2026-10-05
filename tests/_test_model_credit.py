"""每 M tokens 多少积分: the model breakdown needs per-model credits.

The metrics page prints, inside each model's pill, what a million tokens of
that model cost. That rate cannot be derived from the model totals alone: the
per-model buckets used to keep requests / tokens / reasoning only, so the
credit column of the log was dropped for everything except the account-level
sums, and the rate could not be computed at all.

Three semantics matter and are pinned here:
  * credits are summed per model, per account, in both the selected window and
    all time;
  * a rate is a ratio (credits / tokens), so two accounts using one model at
    the same price both read the same number;
  * a model billed by quota (international realm) reports 0.00 credits, and
    the page must print "—" rather than a rate computed from an empty total.

No network: the usage log is synthesised in a temp directory.
"""
import io
import json
import os
import shutil
import sys
import tempfile
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
_TMP = tempfile.mkdtemp(prefix="wb-modelcredit-")
os.environ["ACCOUNTS_DIR"] = os.path.join(_TMP, "accounts")
os.environ["WB_PROXY_USAGE_DIR"] = _TMP
os.makedirs(os.environ["ACCOUNTS_DIR"], exist_ok=True)

import wb_proxy as P

# Same reason as run_all.py's PYTHONIOENCODING: run directly on Windows and
# the labels below (they quote the panel) would raise UnicodeEncodeError.
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

PASS = FAIL = 0


def check(label, cond, extra=""):
    global PASS, FAIL
    if cond:
        PASS += 1
        print("  [PASS] " + label)
    else:
        FAIL += 1
        print("  [FAIL] " + label + ("  " + str(extra) if extra else ""))


def row(at, model, account, tokens, credit, outcome="completed", realm="cn"):
    return {
        "at": at, "iso": time.strftime("%Y-%m-%dT%H:%M:%S", time.localtime(at)),
        "model": model, "stream": True, "outcome": outcome,
        "elapsed_ms": 900, "ttft_ms": 300, "gen_ms": 600,
        "prompt_tokens": tokens * 3 // 4, "completion_tokens": tokens // 4,
        "reasoning_tokens": 0, "cached_tokens": 0,
        "total_tokens": tokens, "credit": credit,
        "account": account, "realm": realm, "tokens_per_sec": 100.0,
        "cache_hit_pct": 0.0,
    }


now = time.time()
rows = [
    # acct-A: two requests of the same model, 2.5 credits per million tokens.
    row(now - 300, "codebuddy-v3", "acct-A", 1_000_000, 2.5),
    row(now - 240, "codebuddy-v3", "acct-A", 500_000, 1.25),
    # acct-B: same model, same rate, a tenth of the traffic.
    row(now - 180, "codebuddy-v3", "acct-B", 100_000, 0.25),
    # A quota-billed model: tokens yes, credits no.
    row(now - 120, "glm-5.3", "acct-A", 200_000, 0.0),
    # A failed request is not part of what the page prices: same rule the
    # request counter uses.
    row(now - 60, "codebuddy-v3", "acct-A", 900_000, 5.0, outcome="failed"),
]
with io.open(P.USAGE_LOG, "w", encoding="utf-8") as fh:
    for r in rows:
        fh.write(json.dumps(r, ensure_ascii=False) + chr(10))

print("[1] the per-model buckets carry credits")
payload = P.compute_usage_analytics(ttl=0)
accts = {a["uid"]: a for a in payload["accounts"]}
a = accts["acct-A"]["window_models"]
check("both completed requests of the model are counted",
      a["codebuddy-v3"]["requests"] == 2, a["codebuddy-v3"]["requests"])
check("their tokens add up", a["codebuddy-v3"]["tokens"] == 1_500_000,
      a["codebuddy-v3"]["tokens"])
check("and so do their credits", round(a["codebuddy-v3"]["credit"], 4) == 3.75,
      a["codebuddy-v3"]["credit"])
check("the failed request stays out of the model bucket",
      a["codebuddy-v3"]["tokens"] == 1_500_000,
      "900,000 tokens of a failed request leaked into the model totals")
check("a model billed by quota reports zero credits, not a guess",
      a["glm-5.3"]["credit"] == 0.0 and a["glm-5.3"]["tokens"] == 200_000,
      a["glm-5.3"])

print()
print("[2] the rate is a ratio, so equal prices read equal")
rate_a = a["codebuddy-v3"]["credit"] / a["codebuddy-v3"]["tokens"] * 1e6
rate_b = (accts["acct-B"]["window_models"]["codebuddy-v3"]["credit"]
          / accts["acct-B"]["window_models"]["codebuddy-v3"]["tokens"] * 1e6)
check("每 M tokens 积分 for the heavy account", round(rate_a, 2) == 2.50, rate_a)
check("每 M tokens 积分 for the light account", round(rate_b, 2) == 2.50, rate_b)
check("the two accounts agree", round(rate_a, 4) == round(rate_b, 4),
      (rate_a, rate_b))

print()
print("[3] all-time buckets carry credits too (the page switches windows)")
allm = accts["acct-A"]["all_models"]
check("all-time credits match the window when the window is everything",
      round(allm["codebuddy-v3"]["credit"], 4) == 3.75, allm["codebuddy-v3"]["credit"])

print()
print("[4] the window really filters, and the buckets follow it")
# A window is only a window: like /usage, an explicit bound needs the "custom"
# range, otherwise the caller gets everything (pinned in _test_usage_range.py).
# What matters here is that the per-model buckets obey whichever bound won.
bounded = P.compute_usage_analytics(ttl=0, range="custom", since=now - 200)
acct_a = {x["uid"]: x for x in bounded["accounts"]}["acct-A"]["window_models"]
acct_b = {x["uid"]: x for x in bounded["accounts"]}["acct-B"]["window_models"]
check("a model that only ran before the window is gone from it",
      "codebuddy-v3" not in acct_a, list(acct_a))
check("the model inside the window is still there",
      acct_a.get("glm-5.3", {}).get("tokens") == 200_000, acct_a.get("glm-5.3"))
check("the other account's request inside the window kept its credit",
      round(acct_b["codebuddy-v3"]["credit"], 4) == 0.25,
      acct_b["codebuddy-v3"])
check("and its rate is unchanged by the window",
      round(acct_b["codebuddy-v3"]["credit"] / acct_b["codebuddy-v3"]["tokens"] * 1e6, 2) == 2.50,
      acct_b["codebuddy-v3"])

shutil.rmtree(_TMP, ignore_errors=True)
print()
print("PASS=%d FAIL=%d" % (PASS, FAIL))
sys.exit(1 if FAIL else 0)
