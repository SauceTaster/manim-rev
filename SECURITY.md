# Security Policy

## Supported versions

Before the first tagged release, security fixes target the default branch on a
best-effort basis. After releases begin, fixes target the latest minor release
line and the default branch until the project reaches 1.0.

| Version | Supported |
| --- | --- |
| Default branch before the first release | Best effort |
| Latest tagged 0.x release, when available | Yes |
| Older 0.x releases | No |

## Reporting a vulnerability

Please do not open a public issue for a suspected vulnerability.

Use GitHub's private vulnerability reporting flow from the canonical
repository's [Security page](https://github.com/SauceTaster/manim-rev/security)
under **Advisories → Report a vulnerability**. Include:

- the affected version or commit;
- a concise impact statement and realistic threat model;
- reproduction steps or a minimal proof of concept;
- relevant platform and Python/Manim versions;
- any suggested mitigation, if known.

If private vulnerability reporting is not enabled, open a public issue that
contains only a request for a private security contact. Do not include
vulnerability details in that issue.

Maintainers aim to acknowledge a complete report within five business days and
provide an initial assessment within ten. Timelines for a fix and disclosure
depend on severity and release complexity. Please allow a reasonable period
for coordinated remediation before publishing details.

These response targets express maintainer intent, not a service-level
agreement. General usage support is best-effort through
[GitHub Issues](https://github.com/SauceTaster/manim-rev/issues).

## Scope notes

The core library renders caller-provided snapshot models; it is not intended
to execute or sandbox binaries. Vulnerabilities in parsing adapter data,
package installation, generated file handling, or CI/release integrity are in
scope. Reports that only demonstrate expected execution of a user-authored
Manim scene are generally out of scope unless a documented security boundary
is crossed.

Manim Rev is an educational animation library, not a security product. Its
examples and rendered diagrams are not findings, exploit mitigations, or
assurances about the safety of analyzed software.

Please report conduct concerns through [CODE_OF_CONDUCT.md](CODE_OF_CONDUCT.md),
not through the security advisory channel.
