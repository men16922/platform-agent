"""
Phase 4a is folded (2026-09-01, D50) — and the rule that made it safe is not.

The AMP workspace, the IAM user `amp-remote-write-4a` and its access key are
deleted, so `kube-prometheus-stack.yaml` no longer carries a `remoteWrite`
destination. **D48 survives the fold**: *remote_write is never attached without
an allowlist.* Unfiltered, this cluster ships 5.13 B samples/mo — **128× the
40 M `Always Free` tier**, ≈$180/mo — which is what 4b costs and therefore
erases the reason 4a was picked over 4b in the first place.

⚠️ Why this file was not deleted along with the block it used to pin.

The old version asserted nine properties of a live `remoteWrite:` entry. With
that entry gone every one of them would have been vacuously true — *"the
allowlist is exactly these four"* passes beautifully when there is no allowlist.
That is the failure this repository has named twice (Risk 12③, and M39's two
rules that lost their load when `JUSTIFIED_GAPS` emptied): **a rule that cannot
fail is not a rule.** Deleting the file instead would have thrown away the only
written-down thing standing between a future one-line `remoteWrite:` and a
$180/mo bill.

So the contract moved out of the assertions and into `remote_write_violations()`,
a function. Two different callers keep it honest:

  * the **live file** — which must currently have *no* destination, and must
    satisfy the contract if one ever comes back; and
  * a **synthetic table** — nine deliberately broken shapes, each of which the
    function must reject. That is what proves the function still bites with
    nothing to bite in the real file.

⚠️ The synthetic table is not the contract being asserted against itself. The
function is the thing under test; the table only demonstrates it can say no. The
live file is where it says yes or no for real. (A previous guard in this repo
picked a fixture value that happened to equal the wrong default and passed a
defect through — M18. Every synthetic case below therefore differs from the
approved shape in exactly one named way.)

⚠️ The approved workspace id is deliberately **not** pinned any more. It named a
workspace that no longer exists, so pinning it would be a rule that can only
ever be wrong. Re-adding a destination goes through the plan
(`docs/plans/2026-08-15-4a-remote-write-allowlist.md` §4, §8, §10), which is
where the next workspace id gets named and approved.
"""

from __future__ import annotations

import copy
import pathlib
import re

import pytest
import yaml

ROOT = pathlib.Path(__file__).resolve().parents[1]
VALUES = ROOT / "infra/onprem/addons/values/kube-prometheus-stack.yaml"

# The allowlist approved 2026-08-16 and measured live 2026-08-17: 308 of the
# cluster's 52,438 series (0.59%). Counts are from AMP itself, not from intent.
APPROVED_METRICS = frozenset({
    "kube_pod_container_status_restarts_total",   # the demo alarm rule reads this
    "kube_pod_status_phase",                      # what state the pod is in
    "kube_deployment_status_replicas_unavailable",  # did it reach availability
    "up",                                         # proof the pipe is alive
})

# 287 of the 308 shipped series came from this one ServiceMonitor. With 4a
# folded the interval is no longer a *cost* handle — it is pinned now because
# the demo alarm rule integrates over `[5m]`, i.e. five samples at this value.
KSM_INTERVAL = "60s"

# Prometheus anchors a `writeRelabelConfigs` regex, so `kube_.*` is not a typo
# that fails loudly — it is a working expression that quietly matches thousands
# of series. These are the ways a list silently becomes a pattern.
FORBIDDEN_METACHARS = (".*", ".+", "[", "?", "(?")


# --------------------------------------------------------------------------
# The contract, as a function. This is the thing under test.
# --------------------------------------------------------------------------

def remote_write_violations(values: dict) -> list[str]:
    """Return every way `values` breaks the 4a remote_write contract.

    An empty list means "no destination, or a destination that is safe". The
    caller decides which of those two is acceptable — this function does not,
    because "should there be a pipe at all" is a D50/plan decision and "is the
    pipe affordable" is arithmetic.
    """
    spec = (values.get("prometheus") or {}).get("prometheusSpec") or {}
    targets = spec.get("remoteWrite") or []
    problems: list[str] = []

    if not targets:
        return problems

    if len(targets) != 1:
        problems.append(
            "multiple-destinations: "
            f"expected exactly one destination, found {len(targets)}: "
            f"{[t.get('url') for t in targets]}. Two writers double the volume, "
            "and the second is easy to add without noticing."
        )

    for target in targets:
        url = target.get("url") or ""
        if "aps-workspaces" not in url or "/api/v1/remote_write" not in url:
            problems.append(
                f"not-amp-endpoint: destination is not an AMP remote_write endpoint: {url!r}"
            )

        rules = target.get("writeRelabelConfigs") or []
        keeps = [r for r in rules if r.get("action") == "keep"]
        if len(keeps) != 1:
            problems.append(
                "keep-rule-count: "
                f"expected exactly one `keep` rule, found {len(keeps)}. With no "
                "`keep` at all Prometheus ships **everything** — 5.13 B samples/mo, "
                "128× the 40 M free tier, ≥$180/mo."
            )
        else:
            rule = keeps[0]
            if rule.get("sourceLabels") != ["__name__"]:
                problems.append(
                    "wrong-source-label: "
                    f"the keep rule filters on {rule.get('sourceLabels')!r}, not "
                    "['__name__']. `action: drop` with this regex is the exact "
                    "inversion: it ships the 52,130 series the list excludes."
                )
            regex = rule.get("regex") or ""
            declared = set(regex.split("|"))
            if declared != set(APPROVED_METRICS):
                problems.append(
                    "allowlist-drift: extra="
                    f"{sorted(declared - APPROVED_METRICS)} "
                    f"missing={sorted(APPROVED_METRICS - declared)}. Each addition "
                    "looks small and the bill is not linear in obviousness: all of "
                    "kube-state-metrics is 4,188 series → 181 M samples/mo, 4.5× "
                    "the free tier. Update the plan's §2 and §4 in the same commit."
                )
            for metachar in FORBIDDEN_METACHARS:
                if metachar in regex:
                    problems.append(
                        "regex-wildcard: "
                        f"the allowlist regex contains {metachar!r}: {regex!r}. A "
                        "pattern instead of a list means nobody can read the bill "
                        "off this file."
                    )

        sigv4 = target.get("sigv4") or {}
        for field in ("accessKey", "secretKey"):
            ref = sigv4.get(field)
            if not (isinstance(ref, dict) and "name" in ref and "key" in ref):
                problems.append(
                    f"credential-embedded: sigv4.{field} must reference a Secret "
                    f"by name, got {ref!r}. "
                    "A key pasted into a values file is a key in git forever."
                )

    return problems


# --------------------------------------------------------------------------
# Caller 1 — the live file.
# --------------------------------------------------------------------------

def _values() -> dict:
    return yaml.safe_load(VALUES.read_text(encoding="utf-8"))


def test_4a_is_folded_the_live_file_has_no_destination():
    """D50 said folding means all three go: workspace, IAM user, access key.

    All three were deleted 2026-09-01. If a `remoteWrite:` reappears here while
    no workspace is approved, this goes red — which is the point: the next one
    has to be a decision someone makes on purpose, in the plan, with an IAM user
    whose whole policy is `aps:RemoteWrite` on that one workspace.
    """
    spec = (_values().get("prometheus") or {}).get("prometheusSpec") or {}
    assert "remoteWrite" not in spec, (
        "a remote_write destination is back in the values file. 4a was folded "
        "because the price of a warm demo pipe was a long-lived IAM access key — "
        "not because it cost money ($0.00 measured). Re-attaching means going "
        "through docs/plans/2026-08-15-4a-remote-write-allowlist.md."
    )


def test_the_live_file_would_satisfy_the_contract_if_it_ever_has_one():
    """Vacuous today by construction, and kept on purpose: the day someone adds a
    destination, this is the assertion that reads the contract off the real file
    rather than off the synthetic table below."""
    assert remote_write_violations(_values()) == []


def test_the_scrape_interval_stays_pinned_where_the_series_are():
    """No longer a cost handle — the alarm rule is why it survives the fold.

    `increase(kube_pod_container_status_restarts_total{...}[5m]) > 2` integrates
    over five minutes, i.e. **five samples at 60s**. At 30s the same rule sees
    ten, at 120s it sees two and the `> 2` threshold becomes unreachable.
    """
    monitor = ((_values().get("kube-state-metrics") or {})
               .get("prometheus") or {}).get("monitor") or {}
    assert monitor.get("interval") == KSM_INTERVAL, (
        f"kube-state-metrics ServiceMonitor interval is {monitor.get('interval')!r}, "
        f"not {KSM_INTERVAL!r}. The demo alarm rule's `[5m]` window is counted in "
        "samples, not seconds."
    )


def test_no_global_scrape_interval():
    """The rejected alternative, still rejected — for a reason that outlived 4a.

    `prometheusSpec.scrapeInterval: 60s` would halve the resolution of every
    metric in the cluster, including the 52,130 series that were never shipped
    anywhere. That was true when the motive was the AMP bill and it is still true
    now that there is no bill.
    """
    spec = (_values().get("prometheus") or {}).get("prometheusSpec") or {}
    assert "scrapeInterval" not in spec, (
        "a global scrapeInterval appeared. If that is intentional, say so in the "
        "plan's §8 table and delete this test — but do not reach for it as a "
        "cheap way to cut scrape volume."
    )


# --------------------------------------------------------------------------
# Caller 2 — the synthetic table. This is what keeps the function load-bearing
# now that the live file has nothing for it to reject.
# --------------------------------------------------------------------------

APPROVED_SHAPE: dict = {
    "prometheus": {
        "prometheusSpec": {
            "remoteWrite": [
                {
                    "url": (
                        "https://aps-workspaces.ap-northeast-2.amazonaws.com"
                        "/workspaces/ws-0000000/api/v1/remote_write"
                    ),
                    "sigv4": {
                        "region": "ap-northeast-2",
                        "accessKey": {"name": "amp-remote-write", "key": "access_key_id"},
                        "secretKey": {"name": "amp-remote-write", "key": "secret_access_key"},
                    },
                    "writeRelabelConfigs": [
                        {
                            "sourceLabels": ["__name__"],
                            "regex": "|".join(sorted(APPROVED_METRICS)),
                            "action": "keep",
                        }
                    ],
                }
            ]
        }
    }
}


def _broken(mutate) -> dict:
    values = copy.deepcopy(APPROVED_SHAPE)
    mutate(values["prometheus"]["prometheusSpec"]["remoteWrite"])
    return values


def _keep(targets: list[dict]) -> dict:
    return targets[0]["writeRelabelConfigs"][0]


def test_the_approved_shape_is_accepted():
    """The other half of every rejection test: a guard that says no to everything
    is as useless as one that says yes to everything."""
    assert remote_write_violations(APPROVED_SHAPE) == []


def test_an_empty_file_is_not_a_violation():
    """"No pipe" is the folded state, not a contract breach. The *live* test above
    is what insists on it; this function must not conflate the two."""
    assert remote_write_violations({}) == []
    assert remote_write_violations({"prometheus": {"prometheusSpec": {}}}) == []


# Each case names **which rule must fire**, not merely that *something* did.
#
# ⚠️ This attribution is not decoration — it is the finding that built this
# table. The first version asserted only `violations != []`, and deleting the
# wildcard check outright left the suite green: `kube_.*` also trips
# `allowlist-drift`, so the wildcard rule was being counted by another rule's
# shadow. That is the failure this repo named in M17 — **do not count a defect
# by its shadow.** Asserting the code is what gives each rule its own load.
BREAKAGES = {
    "second_destination": (
        lambda t: t.append(copy.deepcopy(t[0])), "multiple-destinations"),
    "not_an_amp_endpoint": (
        lambda t: t[0].__setitem__("url", "http://localhost:9090/write"), "not-amp-endpoint"),
    "no_keep_rule": (
        lambda t: t[0].__setitem__("writeRelabelConfigs", []), "keep-rule-count"),
    "drop_instead_of_keep": (
        lambda t: _keep(t).__setitem__("action", "drop"), "keep-rule-count"),
    "filters_on_the_wrong_label": (
        lambda t: _keep(t).__setitem__("sourceLabels", ["job"]), "wrong-source-label"),
    "a_fifth_metric": (
        lambda t: _keep(t).__setitem__("regex", _keep(t)["regex"] + "|kube_pod_info"),
        "allowlist-drift"),
    "a_missing_metric": (
        lambda t: _keep(t).__setitem__("regex", "up"), "allowlist-drift"),
    "a_wildcard_instead_of_a_list": (
        lambda t: _keep(t).__setitem__("regex", "kube_.*"), "regex-wildcard"),
    "an_embedded_credential": (
        lambda t: t[0]["sigv4"].__setitem__("accessKey", "AKIAEXAMPLE"), "credential-embedded"),
}


@pytest.mark.parametrize("name", sorted(BREAKAGES))
def test_the_contract_rejects_each_way_of_breaking_it(name):
    """One named difference from the approved shape per case (M18: a fixture that
    happens to equal the wrong default proves nothing)."""
    mutate, expected_code = BREAKAGES[name]
    violations = remote_write_violations(_broken(mutate))
    assert violations, f"{name} was accepted by the contract"
    assert any(v.startswith(expected_code) for v in violations), (
        f"{name} was rejected, but not by {expected_code!r} — by {violations!r}. "
        "A rule that only ever fires alongside another rule has no load of its "
        "own: delete the check that fired, and this case still passes."
    )


def test_every_rule_is_reachable_by_exactly_one_case_that_needs_it():
    """The table above must not leave a rule with no case that isolates it.

    Counted here rather than trusted: if a `remote_write_violations` branch grows
    a new code and nobody adds a breakage for it, that code is unexercised and the
    next person will read the function as guarded when it is not.
    """
    declared = {code for _, code in BREAKAGES.values()}
    source = pathlib.Path(__file__).read_text(encoding="utf-8")
    body = source.split("def remote_write_violations")[1].split("\n# ---")[0]
    emitted = set(re.findall(r'"([a-z]+(?:-[a-z]+)+): ', body))
    assert emitted <= declared, (
        f"these violation codes have no breakage case that isolates them: "
        f"{sorted(emitted - declared)}"
    )
