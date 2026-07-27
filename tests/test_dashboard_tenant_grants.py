"""
Behavioural guards for tenant grant validation (`platform-roster.ts`).

`visibility.ts` decides what a grant *shows*. Until now nothing decided whether
the grant named anything real: an admin could grant `acmee`, the record stored
it, the users table rendered it as access, and the fleet view matched zero rows
— forever, silently, in the direction that looks fine.

Executed rather than grepped, for the same reason the visibility tests are: an
inverted condition in `checkGrants` leaves every string a grep test looks for
exactly where it is, while unknown tenants sail through.

The row that matters most is the unreachable registry. Falling back to "accept
anything" when the roster cannot be fetched restores exactly the unchecked grant
this module exists to prevent, and does it precisely when nobody is watching.
"""

from __future__ import annotations

import json
import shutil
import subprocess
import tempfile
from pathlib import Path

import pytest

SRC = Path("dashboard/src/lib/platform-roster.ts")

pytestmark = pytest.mark.skipif(
    shutil.which("npx") is None or not SRC.is_file(),
    reason="npx/platform-roster.ts unavailable — cannot execute the grant policy",
)

ROSTER = "{tenants:['acme','globex'],identities:['acme/dev','globex/dev']}"


def _run(script: str):
    """Compile platform-roster.ts standalone and evaluate `script` against it."""
    with tempfile.TemporaryDirectory() as out:
        subprocess.run(
            ["npx", "tsc", str(SRC), "--outDir", out, "--module", "commonjs",
             "--target", "es2020", "--skipLibCheck"],
            capture_output=True, text=True, timeout=180,
        )
        emitted = Path(out) / "platform-roster.js"
        assert emitted.is_file(), "platform-roster.ts did not emit — cannot verify policy"
        proc = subprocess.run(
            ["node", "-e", f"const r=require({str(emitted)!r});{script}"],
            capture_output=True, text=True, timeout=60,
        )
        assert proc.returncode == 0, proc.stderr
        return json.loads(proc.stdout.strip())


def _check(requested: str, roster: str = ROSTER):
    return _run(f"console.log(JSON.stringify(r.checkGrants({requested},{roster})))")


class TestGrantsAreCheckedAgainstTheRegistry:
    def test_declared_tenant_is_accepted(self):
        assert _check("['acme']") == {"ok": True, "tenants": ["acme"], "unknown": []}

    def test_undeclared_tenant_is_rejected_by_name(self):
        """The typo case that motivated this: stored, displayed, matches nothing."""
        got = _check("['acmee']")
        assert got["ok"] is False
        assert got["unknown"] == ["acmee"], "the admin must be told which name is wrong"

    def test_one_bad_name_rejects_the_whole_write(self):
        """Partial application would leave the admin believing they granted two.

        Storing the good half and reporting an error is the worst of both: the
        screen and the record disagree about what just happened.
        """
        got = _check("['acme','nope']")
        assert got["ok"] is False
        assert got["tenants"] == []

    def test_matching_is_case_sensitive(self):
        """Registry names are DNS-label-safe lowercase.

        Accepting `ACME` would store a grant no namespace, RoleBinding or push
        report will ever agree with — an unchecked grant wearing a check.
        """
        assert _check("['ACME']")["ok"] is False


class TestNormalization:
    def test_whitespace_and_blanks_are_not_tenants(self):
        got = _check("['  acme  ','']")
        assert got == {"ok": True, "tenants": ["acme"], "unknown": []}

    def test_duplicates_collapse(self):
        assert _check("['acme','acme']")["tenants"] == ["acme"]


class TestUnverifiableRosterFailsClosed:
    def test_unreachable_registry_rejects_the_grant(self):
        got = _check("['acme']", "null")
        assert got["ok"] is False, "unverified is not approved"
        assert got["unverifiable"] is True, (
            "the caller must be able to say 'could not check' rather than "
            "'that tenant does not exist' — the admin's next action differs"
        )

    def test_revocation_still_works_with_no_roster(self):
        """Taking access away needs no roster, and refusing it would strand an
        admin who needs to revoke while the hub is down."""
        assert _check("[]", "null") == {"ok": True, "tenants": [], "unknown": []}

    def test_empty_roster_is_not_the_same_as_no_roster(self):
        no_roster = _check("['acme']", "null")
        empty = _check("['acme']", "{tenants:[],identities:[]}")
        assert empty["ok"] is False
        assert empty.get("unverifiable") is None, (
            "'the registry declares no tenants' is a real answer; "
            "'I could not ask' is not"
        )
        assert no_roster["unverifiable"] is True


class TestWiring:
    """The seam is worthless if the write path does not call it.

    Every defect this repo has paid for in this area was the same shape: a
    policy that existed and a caller that did not consult it.
    """

    ROUTE = Path("dashboard/src/app/api/dashboard/users/route.ts")
    STORE = Path("dashboard/src/lib/user-data.ts")

    def test_the_users_route_validates_before_storing(self):
        body = self.ROUTE.read_text(encoding="utf-8")
        assert "checkGrants" in body and "fetchRoster" in body
        assert body.index("checkGrants") < body.index("upsertUserRecord(username"), (
            "grants must be checked before the record is written"
        )

    def test_a_role_change_does_not_silently_revoke_grants(self):
        """The whole-item Put wiped `tenants` on every role update.

        The two controls sit in the same panel and nothing said one erased the
        other, so this is asserted on the store rather than left to the caller.
        """
        body = self.STORE.read_text(encoding="utf-8")
        assert "tenants === undefined" in body, (
            "absent grants must mean keep, not revoke"
        )
