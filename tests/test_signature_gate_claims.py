"""
Guards for what the supply-chain story is allowed to claim.

Measured 2026-08-08, while scoping "Cosign 어드미션 집행" (the last open approval).
The recorded blocker was:

    "현재는 CI/사람용 게이트까지. API 서버가 미서명 이미지를 거부하려면 policy
     controller라는 새 클러스터 의존성이 필요."

The second sentence is true. It is also **not the binding constraint**, and the
first sentence was not true at all:

  * `cosign sign` appears **nowhere** in this repo — no workflow, no Makefile
    target, no script. Nothing has ever produced a signature.
  * There is no CI at all: `.github/workflows/` does not exist. So the "CI gate"
    half of the claim describes a thing that cannot have run.
  * `scripts/verify_image_signature.py` is invoked by exactly one thing:
    `tests/test_image_signature.py`. Its other two mentions are a docstring and a
    comment in values.yaml. This is the D39 shape again — the only code that
    exercises the mechanism is the test that pins it.
  * The chart deploys `platform-agent:0.1.0` with `digest: ""` — a bare tag with
    no registry host. A cosign signature is an artifact stored *in a registry*
    next to a *digest*, which `verify_image_signature.py`'s own docstring says.
    So there is not even an address at which a signature could exist.

Which inverts the approval. Installing a policy controller today would not "start
enforcing signatures" — it would deny every workload the platform runs, because
there is no signature to find. The prerequisite is a signing path, and that is
cheaper to state than to argue about.

These guards keep both halves honest: the docs may not describe a gate that
nothing invokes, and admission enforcement may not land before signing does.
"""

from __future__ import annotations

import re
import subprocess
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]

#: Where a claim about the supply chain is allowed to live. Checked as text
#: because the claim is prose — there is no symbol to assert on.
CLAIM_DOCS = ("docs/STATUS.md", "docs/NEXT_PLAN.md", "docs/AGENT_BRIEF.md")

#: Paths that are allowed to mention the verifier without being a caller: the
#: script itself, its unit test, and documentation.
_NOT_A_CALLER = ("scripts/verify_image_signature.py", "tests/", "docs/", ".md")


def _grep(pattern: str) -> list[str]:
    """Repo-wide search, excluding vendored and generated trees."""
    result = subprocess.run(
        ["git", "grep", "-rIn", "-e", pattern, "--", ".", ":!node_modules", ":!*/cdk.out/*"],
        cwd=REPO, capture_output=True, text=True,
    )
    return [line for line in result.stdout.splitlines() if line.strip()]


def _signing_producers() -> list[str]:
    """Anything that actually creates a signature."""
    return [ln for ln in _grep(r"cosign \(sign\|attest\)") if not ln.startswith("tests/")]


def _is_comment(grep_line: str) -> bool:
    """A mention inside a comment is documentation, not a call site.

    Written after this guard's first run reported values.yaml's usage example as
    a production caller. Counting prose as a call is the mirror image of the
    defect this file is about, so the detector had to be measured too.
    """
    body = grep_line.split(":", 2)[-1].lstrip()
    return body.startswith(("#", "//", "*", "--"))


def _verifier_callers() -> list[str]:
    """Non-test, non-doc, non-comment invocations of the verification gate."""
    hits = _grep("verify_image_signature")
    return [
        ln for ln in hits
        if not any(marker in ln.split(":")[0] for marker in _NOT_A_CALLER)
        and not _is_comment(ln)
    ]


class TestTheDocsMayNotClaimAGateThatNothingInvokes:
    def test_no_doc_claims_a_ci_signature_gate_while_there_is_no_ci(self):
        """
        `.github/workflows/` does not exist. A doc saying signature verification
        runs "CI까지" describes a step that has never executed, and that is the
        kind of sentence this repo keeps paying for: it reads as a guarantee.
        """
        if (REPO / ".github" / "workflows").is_dir():
            return  # CI exists; this guard has nothing to say

        offenders = []
        for rel in CLAIM_DOCS:
            text = (REPO / rel).read_text(encoding="utf-8")
            for line in text.splitlines():
                if "cosign" not in line.lower():
                    continue
                if re.search(r"CI\s*[/·]\s*사람용 게이트|CI 게이트", line):
                    offenders.append(f"{rel}: {line.strip()[:120]}")
        assert not offenders, (
            "a doc claims a CI signature gate, but .github/workflows/ does not exist:\n  "
            + "\n  ".join(offenders)
        )

    def test_the_verifier_has_no_production_caller_and_the_docs_know_it(self):
        """
        If a caller appears, this assertion is meant to go red — that is the
        signal to promote the wording from "도구는 있다" to "게이트가 돈다".
        Delete the guard then, do not weaken it.
        """
        callers = _verifier_callers()
        assert not callers, (
            "verify_image_signature.py now has a production caller — the supply-chain "
            "wording in docs/ can finally be upgraded, and this guard removed:\n  "
            + "\n  ".join(callers)
        )


class TestAdmissionEnforcementCannotLandBeforeSigning:
    def test_a_policy_controller_requires_something_that_signs(self):
        """
        The trap this exists to hold. Turning on admission enforcement while
        nothing signs does not tighten the supply chain — it denies every
        workload, and the failure surfaces the way Risk 8 describes: Argo reports
        Synced while zero pods run.
        """
        admission = [
            ln for ln in _grep(r"policy-controller\|ClusterImagePolicy\|verifyImages")
            if not ln.split(":")[0].startswith(("tests/", "docs/"))
        ]
        if not admission:
            return  # no admission config yet: nothing to order against

        assert _signing_producers(), (
            "admission enforcement config exists but nothing in this repo signs an image "
            "(`cosign sign` has no producer). Enforcing now denies every workload:\n  "
            + "\n  ".join(admission)
        )

    def test_signing_by_digest_is_still_unaddressable(self):
        """
        Records why a signing path is not simply "add a cosign sign step": the
        chart ships a bare tag with no registry host, and a signature lives in a
        registry beside a digest. Goes red once the chart pins a digest, which is
        the moment signing becomes possible — update the docs then.
        """
        values = (REPO / "infra/helm/platform-agent/values.yaml").read_text(encoding="utf-8")
        digest = re.search(r'^\s*digest:\s*"(.*)"', values, re.MULTILINE)
        assert digest is not None, "values.yaml no longer declares an image.digest key"
        assert digest.group(1) == "", (
            "image.digest is now pinned — the image is addressable by digest, so a cosign "
            "signature has somewhere to live. Revisit the admission approval and this guard."
        )
