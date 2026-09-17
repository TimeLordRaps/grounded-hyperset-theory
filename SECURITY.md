# Security Policy

## Supported release

Only the latest tagged public release is supported. Bug fixes and security patches
are published additively via semver tags.

## Reporting

Do not disclose exploit payloads or sensitive vulnerability details in a public issue.
Use **Security** -> **Report a vulnerability** in the canonical GitHub repository:

`https://github.com/TimeLordRaps/grounded-hyperset-theory/security/advisories/new`

If the private security advisory route is temporarily unavailable, report only the non-sensitive
fact of its unavailability in a public issue.

## Scope

Grounded Hyperset Theory is a pure mathematical library with zero runtime dependencies.
Security boundaries focus on algorithmic complexity bounds (avoiding algorithmic denial-of-service
in graph traversals and cycle detection), arbitrary code execution prevention during quotation/AST
unquotation, and strict packaging supply-chain integrity.
