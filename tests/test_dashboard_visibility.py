"""
Behavioural guards for the read-side tenant boundary (Phase 3③).

Every other dashboard test in this repo asserts *file content*, because there is
no TypeScript test runner here. That is fine for wiring — "does the route call
the seam" — and useless for this module: an inverted condition in
`resolveVisibility` would leave every string these tests grep for exactly where
it is, while the fleet view showed one tenant another's topology.

So this compiles the module and runs it. The four rows below are the whole
policy, and the one that matters is the default: **no grant means nothing**, not
everything.
"""

from __future__ import annotations

import json
import shutil
import subprocess
import tempfile
from pathlib import Path

import pytest

SRC = Path("dashboard/src/lib/visibility.ts")

pytestmark = pytest.mark.skipif(
    shutil.which("npx") is None or not SRC.is_file(),
    reason="npx/visibility.ts unavailable — cannot execute the TS policy",
)


def _run(script: str):
    """Compile visibility.ts standalone and evaluate `script` against it."""
    with tempfile.TemporaryDirectory() as out:
        # The `@/lib/auth` import is type-only and erases, so a standalone
        # compile emits working JS; it reports the unresolved path alias and
        # still writes the output, which is why the return code is not checked.
        subprocess.run(
            ["npx", "tsc", str(SRC), "--outDir", out, "--module", "commonjs",
             "--target", "es2020", "--skipLibCheck"],
            capture_output=True, text=True, timeout=180,
        )
        emitted = Path(out) / "visibility.js"
        assert emitted.is_file(), "visibility.ts did not emit — cannot verify policy"
        proc = subprocess.run(
            ["node", "-e", f"const v=require({str(emitted)!r});{script}"],
            capture_output=True, text=True, timeout=60,
        )
        assert proc.returncode == 0, proc.stderr
        return json.loads(proc.stdout.strip())


class TestDefaultIsNothing:
    def test_anonymous_caller_is_restricted(self):
        got = _run("console.log(JSON.stringify(v.resolveVisibility(null)))")
        assert got["restricted"] is True
        assert got["tenants"] == []
        assert got["reason"] == "unauthenticated"

    def test_signed_in_user_without_grants_sees_nothing(self):
        got = _run(
            "console.log(JSON.stringify(v.resolveVisibility({role:'viewer'})))"
        )
        assert got["restricted"] is True, "absent grants must not mean all grants"
        assert got["tenants"] == []
        assert got["reason"] == "no-grants"

    def test_restricted_is_distinguishable_from_empty(self):
        """
        `restricted` and "there are no tenants" must not collapse into one
        state — the same reason `connected: false` is not `[]` elsewhere here.
        """
        anon = _run("console.log(JSON.stringify(v.resolveVisibility(null)))")
        granted = _run(
            "console.log(JSON.stringify(v.resolveVisibility({role:'viewer',tenants:['acme']})))"
        )
        assert anon["restricted"] != granted["restricted"]


class TestGrants:
    def test_viewer_sees_only_granted_tenants(self):
        got = _run(
            "console.log(JSON.stringify(v.resolveVisibility({role:'viewer',tenants:['acme']})))"
        )
        assert got == {"tenants": ["acme"], "restricted": False, "reason": "granted"}

    def test_admin_sees_everything(self):
        got = _run("console.log(JSON.stringify(v.resolveVisibility({role:'admin'})))")
        assert got["tenants"] is None, "null means unfiltered; [] would mean nothing"
        assert got["restricted"] is False

    def test_empty_strings_are_not_grants(self):
        got = _run(
            "console.log(JSON.stringify(v.resolveVisibility({role:'viewer',tenants:['','  '.trim()]})))"
        )
        assert got["restricted"] is True


class TestFleetFiltering:
    FEED = (
        "{statuses:[{tenant:'acme',env:'dev'},{tenant:'globex',env:'dev'}],"
        "freshness:[{identity:'acme/dev'},{identity:'globex/dev'}],"
        "tenancy:{'acme/dev':{},'globex/dev':{}},"
        "missing:['globex/prod','acme/prod']}"
    )

    def test_neighbour_tenant_is_dropped_from_every_field(self):
        got = _run(
            f"const vis=v.resolveVisibility({{role:'viewer',tenants:['acme']}});"
            f"console.log(JSON.stringify(v.filterFleet({self.FEED},vis)))"
        )
        assert [s["tenant"] for s in got["statuses"]] == ["acme"]
        assert [f["identity"] for f in got["freshness"]] == ["acme/dev"]
        assert list(got["tenancy"]) == ["acme/dev"]
        assert got["missing"] == ["acme/prod"], (
            "`missing` names declared tenant/envs — it leaks the tenant roster "
            "precisely when those tenants have no status to leak"
        )

    def test_admin_filtering_is_a_passthrough(self):
        got = _run(
            f"const vis=v.resolveVisibility({{role:'admin'}});"
            f"console.log(JSON.stringify(v.filterFleet({self.FEED},vis)))"
        )
        assert len(got["statuses"]) == 2
        assert len(got["missing"]) == 2


class TestRowFiltering:
    ROWS = (
        "[{id:'a',tenant:'acme'},{id:'g',tenant:'globex'},{id:'legacy'}]"
    )

    def test_viewer_sees_only_their_tenants_rows(self):
        got = _run(
            f"const vis=v.resolveVisibility({{role:'viewer',tenants:['acme']}});"
            f"console.log(JSON.stringify(v.filterRows({self.ROWS},vis)))"
        )
        assert [r["id"] for r in got["rows"]] == ["a"]
        assert got["withheld"] == 2

    def test_rows_with_no_recorded_tenant_are_admin_only(self):
        """
        Mostly incidents written before the executor persisted tenancy. On a
        shared screen the safe reading of "we do not know whose this is" is not
        "everyone's" — that hides history from viewers, and the alternative
        leaks. A partition that is right except for the old rows is not one.
        """
        viewer = _run(
            f"const vis=v.resolveVisibility({{role:'viewer',tenants:['acme']}});"
            f"console.log(JSON.stringify(v.filterRows({self.ROWS},vis)))"
        )
        assert "legacy" not in [r["id"] for r in viewer["rows"]]

        admin = _run(
            f"const vis=v.resolveVisibility({{role:'admin'}});"
            f"console.log(JSON.stringify(v.filterRows({self.ROWS},vis)))"
        )
        assert [r["id"] for r in admin["rows"]] == ["a", "g", "legacy"]
        assert admin["withheld"] == 0

    def test_withheld_count_lets_the_ui_say_so_instead_of_shortening_silently(self):
        got = _run(
            "const vis=v.resolveVisibility({role:'viewer',tenants:['nobody']});"
            f"console.log(JSON.stringify(v.filterRows({self.ROWS},vis)))"
        )
        assert got["rows"] == [] and got["withheld"] == 3
