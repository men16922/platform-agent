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

Which inverted the approval. Installing a policy controller in that state would
not "start enforcing signatures" — it would deny every workload the platform
runs, because there is no signature to find. The prerequisite was a signing path.

**That path now exists** (`make sign-image` / `scripts/build_and_sign_image.sh`,
same day): build → push by digest → `cosign sign` → verify through this repo's own
`verify_image_signature.py`, which gave that script its first production caller.
So the findings above are history, not current state — what these guards hold is
the ordering that made them findings:

  * something must still sign, and verification must still go through the repo's
    own gate (delete either and the supply-chain wording becomes false again);
  * admission enforcement may not land before signing does;
  * the chart's `image.digest` stays empty, because a digest committed here is a
    claim about an image nobody else has.

Still absent on purpose, and not to be over-read: there is no CI, the key is a
local-dev key with an empty password, and nothing enforces signatures at
admission. See STATUS Risk 6.
"""

from __future__ import annotations

import re
import subprocess
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]

#: Paths that are allowed to mention the verifier without being a caller: the
#: script itself, its unit test, and documentation.
_NOT_A_CALLER = ("scripts/verify_image_signature.py", "tests/", "docs/", ".md")


def _grep(pattern: str) -> list[str]:
    """Repo-wide search, excluding vendored and generated trees.

    ``--untracked`` is load-bearing, not tidiness. Without it `git grep` searches
    only tracked files, so a brand-new script would be invisible to these guards
    until it was committed — i.e. the guard would go quiet exactly when the change
    it exists to notice is being written. Caught by this file's own first run:
    `scripts/build_and_sign_image.sh` added a real caller of the verifier and
    ``test_the_verifier_has_no_production_caller`` stayed green.
    """
    result = subprocess.run(
        ["git", "grep", "--untracked", "-rIn", "-e", pattern,
         "--", ".", ":!node_modules", ":!*/cdk.out/*"],
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
    # REMOVED 2026-08-08, the same day it was written: a guard that grepped
    # CLAIM_DOCS for "CI 게이트" near "cosign" and failed while
    # `.github/workflows/` was absent.
    #
    # It caught the real defect once — the docs did claim a CI gate that could
    # not have run — and then failed the corrected sentence, because the fixed
    # STATUS line says the CI gate *did not exist* and a regex cannot tell an
    # assertion from its denial. Patching the pattern would only move where it
    # misreads Korean prose.
    #
    # Deleted rather than weakened, per this repo's own lesson (수호 테스트 자신이
    # 안티패턴일 수 있다). What actually keeps the docs honest is below: the claim
    # is derived from code facts, and the code facts are guarded. If signing or
    # verification disappears, `test_the_verification_gate_has_a_producer` goes
    # red and the wording has to be revisited by a human who can read the sentence.

    def test_the_verification_gate_has_a_producer(self):
        """
        Inverted the same day it was written. The first version asserted the
        verifier had NO production caller — true at the time, and designed to go
        red when one appeared. `scripts/build_and_sign_image.sh` made it red, so
        the invariant flipped: from here the risk is not "we claim a gate that
        does not exist" but "the signing path gets deleted and the claim silently
        becomes false again".
        """
        assert _signing_producers(), (
            "nothing signs an image any more (`cosign sign` has no producer). "
            "Restore it or downgrade the supply-chain wording in docs/ — a verifier "
            "with nothing to verify is the state this file was written about."
        )
        assert _verifier_callers(), (
            "scripts/verify_image_signature.py lost its production caller. Signing "
            "without verifying through the repo's own gate means 'verified' can drift "
            "away from what that script means by it."
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
