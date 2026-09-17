# Contributing to Grounded Hyperset Theory

Contributions are welcome when they make mathematical definitions more precise,
algorithms more robust, or verification boundaries more refutable without weakening claims.

## Required for a normative change

- identify the affected mathematical module, layer, and formal calculus pathway;
- state compatibility effects, including graph invariants or canonical forms affected;
- include a falsification condition;
- add tests that fail before the change and pass after it;
- maintain zero required runtime dependencies (`dependencies = []`);
- ensure all presentation and boundary checks pass (`python scripts/check_presentation.py`).

Do not mask non-well-founded cycle failures or invent bisimulation equivalences where congruence relations fail.

Unless explicitly stated otherwise, contributions intentionally submitted for
inclusion in this repository are provided under the Apache License 2.0.

## Commits

Commits in this repository are GPG-signed (`git commit -S`). Pull requests are expected to
carry signed commits, and automated contributors must never bypass signing. A commit
signature binds bytes to a signing key; it does not establish correctness, independence,
authorization, or safety.

## Reporting issues

Use GitHub issues for bug reports, counterexamples, and algorithmic improvements. Send
security vulnerability details only through the private route in `SECURITY.md`.
