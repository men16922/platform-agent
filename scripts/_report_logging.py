"""Point library logging at the report's stream.

THE THIRD DOOR. `tests/test_report_streams.py` sweeps the two streams a process
writes *directly* — `print` and `sys.stderr`. There is a third way a line reaches
a reader, and it has neither in it: `src/` attaches **no logging handler anywhere**
(measured 2026-08-11: zero `basicConfig`/`StreamHandler`/`addHandler`/`dictConfig`),
so a `logger.warning` falls through to Python's `logging.lastResort`, which writes
WARNING and above to **stderr**.

For a REPORT CLI — stdout is prose a person reads — that puts library warnings on
the stream the reader is not holding. Two were found live:

  * `push_addon_status` → `collector.warn_if_ambient_read`: "the spoke reads this
    cluster with the ambient kubectl context and filters tenants in code."
  * `live_net_demo` → `aws_session`: "STS assume_role failed …; **falling back to
    in-account credentials**."

Both are credential-boundary events. Both were leaving by the wrong door.

Call this first thing in `main()`. `force=True` because a caller may already have
configured the root logger, and the report's stream wins for the duration of a CLI
run — this module is imported by CLIs, never by library code.

WHICH CLIs NEED IT is not a judgement call: `TestTheLibraryUsesTheSameDoor`
recomputes the import graph of every REPORT CLI, finds the ones that can reach a
WARNING+ call, and requires exactly those to call this. Adding an import that can
warn therefore turns the gate red until this is called.
"""

from __future__ import annotations

import logging
import sys


def send_library_logs_to_the_report() -> None:
    """Route WARNING+ to stdout, where the rest of the report already is."""
    logging.basicConfig(stream=sys.stdout, format="%(levelname)s %(message)s", force=True)
