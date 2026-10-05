"""Importing accounts from a JSON file, cockpit-tools exports included.

The gateway used to speak exactly one dialect of "an account": the camelCase
shape written by its own export and by the desktop clients. Community tools
export the same credential with snake_case keys and a millisecond expiry, so a
perfectly good file imported as nothing but "invalid - no accessToken" rows.

These tests pin the aliases (wb_accounts.IMPORT_FIELD_ALIASES) and the container
sniffing that decide whether a file is readable, and they drive AccountPool so
the dry run and the real import are both exercised.
"""
import base64
import json
import os
import shutil
import sys
import tempfile
import time
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# The import path writes account files, so this suite gets a directory of its
# own: pointing ACCOUNTS_DIR at the shared test dir would leave rows behind for
# whichever suite runs next.
_TMP = tempfile.mkdtemp(prefix="wb-import-")
os.environ["ACCOUNTS_DIR"] = _TMP
os.environ.setdefault("USAGE_DIR", os.path.join(_TMP, "usage"))

import wb_accounts as A


def make_token(uid, exp=None, issuer="https://api.workbuddy.ai"):
    """A JWT-shaped token carrying just the claims the import path reads."""
    def segment(obj):
        raw = json.dumps(obj, separators=(",", ":")).encode("utf-8")
        return base64.urlsafe_b64encode(raw).decode("ascii").rstrip("=")

    claims = {"sub": uid, "exp": int(time.time() + 3600 if exp is None else exp), "iss": issuer}
    return "%s.%s.%s" % (segment({"alg": "none", "typ": "JWT"}), segment(claims), "signature")


def cockpit_row(uid="cockpit-1", **overrides):
    """One row of a cockpit tools export, field for field."""
    row = {
        "id": "row-1",
        "email": "%s@example.com" % uid,
        "uid": uid,
        "nickname": "Cockpit %s" % uid,
        "access_token": make_token(uid),
        "refresh_token": "refresh-%s" % uid,
        "token_type": "Bearer",
        "expires_at": int((time.time() + 7200) * 1000),
        "domain": "www.workbuddy.ai",
        "status": "active",
    }
    row.update(overrides)
    return row


class CockpitRowTests(unittest.TestCase):
    def test_snake_case_row_normalises(self):
        row = cockpit_row("cockpit-1")
        got = A.normalise_import_row(row)
        self.assertEqual(got["uid"], "cockpit-1")
        self.assertEqual(got["accessToken"], row["access_token"])
        self.assertEqual(got["refreshToken"], "refresh-cockpit-1")
        self.assertEqual(got["nickname"], "Cockpit cockpit-1")
        self.assertEqual(got["domain"], "www.workbuddy.ai")
        self.assertEqual(got["realm"], "intl")
        # Imported credentials are live, not inherited state.
        self.assertEqual(got["source"], "import")
        self.assertTrue(got["enabled"])
        self.assertEqual(got["cooldownUntil"], 0.0)

    def test_millisecond_expiry_becomes_seconds(self):
        soon = int(time.time() + 7200)
        got = A.normalise_import_row(cockpit_row("cockpit-2", expires_at=soon * 1000))
        self.assertEqual(got["expiresAt"], soon)

    def test_second_expiry_is_left_alone(self):
        soon = int(time.time() + 7200)
        got = A.normalise_import_row(cockpit_row("cockpit-3", expires_at=soon))
        self.assertEqual(got["expiresAt"], soon)

    def test_expiry_falls_back_to_the_token(self):
        soon = int(time.time() + 1800)
        row = cockpit_row("cockpit-4", expires_at=0)
        row["access_token"] = make_token("cockpit-4", exp=soon)
        self.assertEqual(A.normalise_import_row(row)["expiresAt"], soon)

    def test_cn_rows_are_detected(self):
        cn = A.normalise_import_row(cockpit_row("cn-1", domain="codebuddy.cn"))
        self.assertEqual(cn["realm"], "cn")
        # No domain at all: the token issuer decides.
        row = cockpit_row("cn-2", domain="")
        row["access_token"] = make_token("cn-2", issuer="https://copilot.tencent.com")
        self.assertEqual(A.normalise_import_row(row)["realm"], "cn")
        # An explicit realm still beats both.
        forced = A.normalise_import_row(cockpit_row("cn-3", domain="codebuddy.cn"), realm="intl")
        self.assertEqual(forced["realm"], "intl")

    def test_uid_falls_back_to_the_token_subject_and_is_sanitised(self):
        row = cockpit_row("unused")
        row.pop("uid")
        self.assertEqual(A.normalise_import_row(row)["uid"], "unused")
        self.assertEqual(A.normalise_import_row(cockpit_row("a:b/c d"))["uid"], "a_b_c_d")

    def test_canonical_spelling_wins_over_the_alias(self):
        # A row carrying both spellings must not resolve differently depending on
        # which one happens to be iterated first.
        row = cockpit_row("both")
        row["accessToken"] = make_token("canonical")
        row["expiresAt"] = 1700000000
        got = A.normalise_import_row(row)
        self.assertEqual(got["accessToken"], row["accessToken"])
        self.assertEqual(got["expiresAt"], 1700000000)

    def test_unusable_rows_are_rejected_with_a_reason(self):
        with self.assertRaises(ValueError) as ctx:
            A.normalise_import_row({"uid": "no-token"})
        self.assertIn("no accessToken", str(ctx.exception))

        with self.assertRaises(ValueError) as ctx:
            A.normalise_import_row({"uid": "short", "access_token": "not-a-jwt"})
        self.assertIn("not a JWT", str(ctx.exception))

        # Nothing usable survives UID sanitisation and the token has no subject.
        with self.assertRaises(ValueError) as ctx:
            A.normalise_import_row({"uid": "!!!", "access_token": make_token("")})
        self.assertIn("cannot determine uid", str(ctx.exception))


class ContainerTests(unittest.TestCase):
    def test_single_cockpit_row_is_a_document(self):
        row = cockpit_row("lone")
        rows, problem = A._coerce_account_rows(row)
        self.assertEqual(problem, "")
        self.assertEqual(rows, [row])

    def test_arrays_and_export_documents_are_unchanged(self):
        rows = [cockpit_row("a"), cockpit_row("b")]
        self.assertEqual(A._coerce_account_rows(rows)[0], rows)
        document = {"format": A.EXPORT_FORMAT, "accounts": rows}
        self.assertEqual(A._coerce_account_rows(document)[0], rows)

    def test_a_foreign_object_is_reported_by_shape(self):
        rows, problem = A._coerce_account_rows({"foo": 1})
        self.assertEqual(rows, [])
        self.assertIn("not an account document", problem)
        self.assertIn("foo", problem)   # the keys are echoed, so the file can be fixed
        self.assertIn("not an account document", A._coerce_account_rows({})[1])
        self.assertEqual(A._coerce_account_rows("nope")[1],
                         "expected an object or a list of accounts")

    def test_desktop_credential_still_imports(self):
        # Regression guard: the nested shape predates the alias table and is what
        # the desktop clients hand over.
        row = {"account": {"uid": "desk-1", "nickname": "Desk"},
               "auth": {"accessToken": make_token("desk-1"), "refreshToken": "r",
                        "expiresAt": 1700000000, "domain": "www.workbuddy.ai"}}
        self.assertEqual(A._coerce_account_rows(row)[0], [row])
        got = A.normalise_import_row(row)
        self.assertEqual(got["uid"], "desk-1")
        self.assertEqual(got["nickname"], "Desk")
        self.assertEqual(got["expiresAt"], 1700000000)

    def test_export_document_round_trips(self):
        row = A.normalise_import_row(cockpit_row("round-1"))
        account = A.Account(row)
        document = A.build_export_document([account])
        again = A.normalise_import_row(document["accounts"][0])
        for key in ("uid", "accessToken", "refreshToken", "domain", "realm", "expiresAt"):
            self.assertEqual(again[key], row[key], key)


class PoolImportTests(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.mkdtemp(prefix="wb-pool-", dir=_TMP)
        self.addCleanup(shutil.rmtree, self.dir, True)
        self.pool = A.AccountPool(self.dir)

    def test_dry_run_agrees_with_the_real_import(self):
        rows = [cockpit_row("pool-1"), cockpit_row("pool-2")]
        preview = self.pool.preview_import_rows(rows)
        self.assertEqual(preview["invalid"], [])
        self.assertEqual(preview["added"], ["pool-1", "pool-2"])
        self.assertEqual(self.pool.accounts, [])      # a preview writes nothing

        report = self.pool.import_rows(rows)
        self.assertEqual(report["added"], preview["added"])
        self.assertEqual(report["invalid"], [])
        self.assertEqual(report["updated"], [])
        self.assertEqual(report["skipped"], [])

        # The credential landed on disk in the module's own shape, so every other
        # reader of the pool (refresh, check-in, the dashboard) sees a normal account.
        with open(os.path.join(self.dir, "pool-1.json"), encoding="utf-8") as fh:
            saved = json.load(fh)
        self.assertEqual(saved["uid"], "pool-1")
        self.assertEqual(saved["realm"], "intl")
        self.assertEqual(saved["refreshToken"], "refresh-pool-1")
        self.assertEqual(saved["expiresAt"],
                         int(rows[0]["expires_at"] / 1000))
        self.assertNotIn("access_token", saved)

        # A second pass is a skip unless the caller asks to overwrite.
        self.assertEqual([s["reason"] for s in self.pool.import_rows(rows)["skipped"]],
                         ["already exists", "already exists"])
        self.assertEqual(self.pool.preview_import_rows(rows, overwrite=True)["updated"],
                         ["pool-1", "pool-2"])

    def test_one_bad_row_does_not_abort_the_file(self):
        rows = [cockpit_row("ok-1"), {"uid": "broken"}, cockpit_row("ok-2")]
        report = self.pool.import_rows(rows)
        self.assertEqual(report["added"], ["ok-1", "ok-2"])
        self.assertEqual(len(report["invalid"]), 1)
        self.assertEqual(report["invalid"][0]["index"], 2)
        self.assertIn("no accessToken", report["invalid"][0]["reason"])

    def test_a_cockpit_file_imports_through_the_http_route(self):
        # The whole point of the feature: the bytes of a cockpit-tools export,
        # straight off the wire, must come back as imported accounts. Anything
        # that parses the JSON before the pool would have to do it the same way.
        body = json.dumps([cockpit_row("http-1")])
        document = json.loads(body)
        rows, problem = A._coerce_account_rows(document)
        self.assertEqual(problem, "")
        report = self.pool.import_rows(rows)
        self.assertEqual(report["added"], ["http-1"])


class DashboardContractTests(unittest.TestCase):
    """The dashboard must not keep its own list of accepted file shapes.

    It used to sniff the document for `accessToken`/`auth` before uploading, so a
    cockpit-tools row (or any shape the server learns later) was refused in the
    browser, where the server never got a say. The whitelist is gone; the dry run
    sends the document itself and the server answers with a readable reason.
    """
    def setUp(self):
        path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                            "dashboard.html")
        with open(path, encoding="utf-8") as fh:
            self.html = fh.read()

    def test_no_client_side_field_whitelist(self):
        self.assertNotIn("doc.accessToken", self.html)
        self.assertNotIn("doc.access_token", self.html)

    def test_the_document_reaches_the_server_intact(self):
        self.assertIn("{data: doc, dryRun: true}", self.html)
        self.assertIn("Array.isArray(doc.accounts)", self.html)


if __name__ == "__main__":
    unittest.main()
