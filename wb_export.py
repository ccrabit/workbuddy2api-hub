"""Account export documents (WP-E5: the cockpit format comes back).

Two formats leave this gateway:

* ``native`` - the existing ``workbuddy-accounts`` envelope built by
  :func:`wb_accounts.build_export_document`. Round-trips through
  ``POST /accounts/import``; this module only names the file.
* ``cockpit`` - a **bare array** of snake_case rows for the Go panel's
  ``/api/import/cockpit`` endpoint (and anything else that reads the
  ``cockpit tools`` format). Field names, order and units mirror that panel's
  ``cockpitAccount`` struct (``internal/panel/import.go``) field for field, so a
  file written here imports exactly like one the panel exported itself.

Cockpit units are the part that bites: the panel reads ``expires_at`` as
**milliseconds** and does ``ExpiresAt / 1000`` on it, while the sibling
timestamps (``usage_updated_at`` / ``last_checkin_time`` / ``created_at`` /
``last_used``) are wall-clock **seconds** and are never read back. Our stored
``Account.expires_at`` is seconds, so it is the one value that must be
multiplied.

The panel also derives the realm from ``domain`` alone (``isGlobalDomain``), and
an empty domain resolves to ``cn`` - so an intl account must carry a
``workbuddy.ai`` host or it silently lands in the CN pool on the far side. The
same rule cuts the other way: the row has no ``realm`` field, so a stored domain
that contradicts the account's realm (a cn account holding a
``www.workbuddy.ai`` host) would move it into the global pool on re-import.
:func:`account_domain` therefore writes the realm's own host whenever the stored
one is blank or disagrees, and the stored host verbatim when it agrees.

Rows missing ``uid`` / ``access_token`` / ``refresh_token`` (or carrying a uid
outside ``[A-Za-z0-9_-]{1,64}``) are imported as *skipped* by the panel. We
export them anyway - the file is a faithful snapshot, and dropping an account
from an export is worse than a row that the importer reports on.
"""

import time

try:  # wb_credits owns the epoch 口径 (sec/ms sniffing); reuse it when present.
    from wb_credits import to_epoch_ms as _shared_to_epoch_ms
except Exception:  # pragma: no cover - wb_credits is a Phase D sibling module
    _shared_to_epoch_ms = None

NATIVE_FORMAT = "native"
COCKPIT_FORMAT = "cockpit"
EXPORT_FORMATS = (NATIVE_FORMAT, COCKPIT_FORMAT)

#: Cockpit row schema, in the Go struct's declaration order.
COCKPIT_FIELDS = (
    "id",
    "email",
    "uid",
    "nickname",
    "access_token",
    "refresh_token",
    "token_type",
    "expires_at",
    "domain",
    "dosage_notify_code",
    "payment_type",
    "status",
    "usage_updated_at",
    "last_checkin_time",
    "checkin_streak",
    "created_at",
    "last_used",
)

COCKPIT_TOKEN_TYPE = "Bearer"
COCKPIT_STATUS_ACTIVE = "active"
COCKPIT_STATUS_DISABLED = "disabled"

#: Epoch values at or above this are already milliseconds (year 5138 in seconds).
_MS_THRESHOLD = 100000000000

#: Canonical hosts used when wb_accounts is unavailable - the two values the
#: panel's own export writes (every row of the reference sample uses one).
REALM_FALLBACK_DOMAINS = {"cn": "www.codebuddy.cn", "intl": "www.workbuddy.ai"}


def _as_int(value, default=0):
    try:
        if isinstance(value, bool):
            return default
        return int(value)
    except (TypeError, ValueError):
        return default


def to_epoch_ms(value):
    """Epoch milliseconds from a stored timestamp, 0 when unknown.

    Delegates to ``wb_credits.to_epoch_ms`` when that module is importable so
    both sides sniff seconds-vs-milliseconds identically, and falls back to a
    local threshold check otherwise.
    """
    if callable(_shared_to_epoch_ms):
        try:
            return int(_shared_to_epoch_ms(value))
        except Exception:
            pass
    raw = _as_int(value, 0)
    if raw <= 0:
        return 0
    return raw if raw >= _MS_THRESHOLD else raw * 1000


def epoch_seconds(value):
    """Wall-clock seconds from a stored timestamp, 0 when unknown."""
    ms = to_epoch_ms(value)
    return int(ms // 1000) if ms > 0 else 0


def timestamp_seconds(value):
    """Seconds from either an epoch stamp or the ``YYYY-mm-dd HH:MM:SS`` text.

    ``Account.last_checkin`` is wall-clock text on this side (``wb_tasks``
    writes it with ``time.strftime``), so a plain epoch conversion would drop
    it; the cockpit field is informational for the panel either way, but it
    should not silently read 0.
    """
    if isinstance(value, str) and value.strip():
        try:
            return int(time.mktime(time.strptime(value.strip(), "%Y-%m-%d %H:%M:%S")))
        except (TypeError, ValueError, OverflowError):
            return 0
    return epoch_seconds(value)


def _credits_field(account, key, default=0):
    credits = getattr(account, "credits", None)
    if isinstance(credits, dict):
        return credits.get(key, default)
    return default


def realm_for_domain(domain):
    """Realm the Go panel infers from a cockpit ``domain``.

    Mirrors ``isGlobalDomain`` (panel ``internal/auth/auth.go``): global iff the
    host is ``workbuddy.ai`` or a ``*.workbuddy.ai`` subdomain; every other host
    - empty included - lands in the CN pool. Cockpit rows carry no ``realm``
    field, so this is the only attribution the importer has.
    """
    host = str(domain or "").strip().lower()
    for prefix in ("https://", "http://"):
        if host.startswith(prefix):
            host = host[len(prefix):]
    host = host.split("/")[0].split(":")[0]
    if host == "workbuddy.ai" or host.endswith(".workbuddy.ai"):
        return "intl"
    return "cn"


def realm_domain(realm):
    """The bare host the panel itself writes for ``realm``.

    Taken from ``REALM_CONFIGS[realm]["origin"]`` with the scheme stripped
    (``www.codebuddy.cn`` / ``www.workbuddy.ai``) - the two values every row of
    the reference cockpit export uses.
    """
    try:
        from wb_accounts import REALM_CONFIGS

        config = REALM_CONFIGS.get(realm or "") or {}
    except Exception:
        config = {}
    for key in ("origin", "domain"):
        host = str(config.get(key) or "").strip()
        if not host:
            continue
        for prefix in ("https://", "http://"):
            if host.startswith(prefix):
                host = host[len(prefix):]
        return host.rstrip("/")
    return REALM_FALLBACK_DOMAINS.get(realm or "", "")


def domain_conflicts_realm(account, realm=None):
    """True when the stored domain would import into the *other* pool."""
    stored = str(getattr(account, "domain", "") or "").strip()
    realm = realm or str(getattr(account, "realm", "") or "")
    if not stored or not realm:
        return False
    return realm_for_domain(stored) != realm


def account_domain(account, realm):
    """Host to write into a cockpit row, chosen so the realm survives the trip.

    The row has no ``realm`` field and the importer reads ``domain`` alone, so a
    domain that does not agree with the account's realm would move the account
    into the other pool without anyone noticing. Two cases therefore fall back
    to the realm's own host:

    * a blank domain (the importer reads empty as CN);
    * a domain that contradicts the realm (a cn account still carrying a
      ``www.workbuddy.ai`` host, say - our proxy routes by ``realm``, so the
      stale host is the wrong side of the truth).

    A domain that agrees with the realm is written verbatim: it may be a real
    per-account host, and replacing it would invent data.
    """
    stored = str(getattr(account, "domain", "") or "").strip()
    if not realm:
        return stored or realm_domain("intl")
    if stored and realm_for_domain(stored) == realm:
        return stored
    return realm_domain(realm) or stored


def cockpit_row(account):
    """One account -> one cockpit row (bare-array element)."""
    uid = str(getattr(account, "uid", "") or "")
    nickname = str(getattr(account, "nickname", "") or "")
    realm = str(getattr(account, "realm", "") or "")
    enabled = getattr(account, "enabled", True) is not False
    return {
        # The panel's error text keys on `id`, and its own exports carry
        # id == uid, so a mismatch would only confuse a diff between files.
        "id": uid,
        # We have no separate mailbox; the panel also imports `email` as the
        # nickname fallback, which stays empty on purpose.
        "email": "",
        "uid": uid,
        "nickname": nickname,
        "access_token": str(getattr(account, "access_token", "") or ""),
        "refresh_token": str(getattr(account, "refresh_token", "") or ""),
        "token_type": COCKPIT_TOKEN_TYPE,
        # Stored in seconds, written in milliseconds: the panel divides by 1000.
        "expires_at": to_epoch_ms(getattr(account, "expires_at", 0)),
        "domain": account_domain(account, realm),
        "dosage_notify_code": "",
        "payment_type": "",
        # Parsed but unused by the panel importer; kept truthful for readers.
        "status": COCKPIT_STATUS_ACTIVE if enabled else COCKPIT_STATUS_DISABLED,
        "usage_updated_at": epoch_seconds(_credits_field(account, "updated_at", 0)),
        "last_checkin_time": timestamp_seconds(getattr(account, "last_checkin", 0)),
        "checkin_streak": 0,
        "created_at": epoch_seconds(getattr(account, "added_at", 0)),
        "last_used": 0,
    }


def normalize_format(raw, default=NATIVE_FORMAT):
    """Map a caller-supplied ``format`` onto a known one.

    Returns ``(format, error)``: a missing/empty value takes ``default``, an
    unknown one returns the message the route should answer with (400) instead
    of silently exporting the wrong thing.
    """
    if raw is None or str(raw).strip() == "":
        return default, None
    value = str(raw).strip().lower()
    if value in EXPORT_FORMATS:
        return value, None
    return None, "format must be one of: %s" % ", ".join(EXPORT_FORMATS)


def select_accounts(accounts, realm=None, uids=None):
    """Filter accounts the way the native export does: realm first, then uids."""
    wanted = None
    if uids is not None:
        wanted = {str(u) for u in uids}
    picked = []
    for account in accounts or []:
        if realm and getattr(account, "realm", None) != realm:
            continue
        if wanted is not None and str(getattr(account, "uid", "")) not in wanted:
            continue
        picked.append(account)
    return picked


def build_cockpit_rows(accounts, realm=None, uids=None):
    """Build the bare-array payload (list of :data:`COCKPIT_FIELDS` dicts)."""
    return [cockpit_row(a) for a in select_accounts(accounts, realm=realm, uids=uids)]


def export_label(realm=None, uids=None):
    """Filename label: a single uid's prefix, else the realm, else nothing."""
    if uids:
        uids = list(uids)
        if len(uids) == 1:
            return str(uids[0])[:8]
    return "%s-" % realm if realm else ""


def export_filename(fmt, realm=None, uids=None, stamp=None):
    """Filename for an export; cockpit files keep the panel's ``.cockpit.json``."""
    stamp = stamp or time.strftime("%Y%m%d-%H%M%S")
    label = export_label(realm=realm, uids=uids)
    if fmt == COCKPIT_FORMAT:
        return "workbuddy-accounts-%s%s.cockpit.json" % (label, stamp)
    return "workbuddy-accounts-%s%s.json" % (label, stamp)


def build_document(fmt, accounts, realm=None, uids=None, include_secrets=True):
    """Build one export. Returns ``(payload, filename, count)``.

    ``native`` returns the self-describing envelope plus a JSON filename;
    ``cockpit`` returns the bare array plus a ``.cockpit.json`` filename.
    ``include_secrets`` is native-only - a credential-free cockpit file would
    import nothing, so the caller must reject that combination.
    """
    if fmt == COCKPIT_FORMAT:
        rows = build_cockpit_rows(accounts, realm=realm, uids=uids)
        return rows, export_filename(fmt, realm=realm, uids=uids), len(rows)
    from wb_accounts import build_export_document

    document = build_export_document(
        accounts, realm=realm, include_secrets=include_secrets, uids=uids
    )
    return document, export_filename(fmt, realm=realm, uids=uids), len(document.get("accounts") or [])
