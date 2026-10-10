"""Sandbox shim: make httpx's optional CLI import fail cleanly.

httpx imports ``click`` only for its command line entry point and guards that
import with ``except ImportError``.  The installed click builds on ``match``
statements, which this machine's only usable interpreter (Python 3.9) cannot
compile.  Raising ImportError here lets httpx fall back to its stub ``main``
so the library part stays importable.  Only used by local evidence tooling.
"""

raise ImportError("click CLI shim: not available under the evidence runtime")
