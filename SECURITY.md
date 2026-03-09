# Security Policy

## Supported Versions

| Version | Supported          |
| ------- | ------------------ |
| latest  | :white_check_mark: |

## Reporting a Vulnerability

If you discover a security vulnerability in DevShowcase, please report it responsibly.

**Do NOT open a public GitHub issue for security vulnerabilities.**

### How to Report

1. Go to the [Security Advisories](../../security/advisories/new) page for this repository
2. Click "New draft security advisory"
3. Fill in the details of the vulnerability

Alternatively, email the maintainers with:
- A description of the vulnerability
- Steps to reproduce
- Potential impact
- Suggested fix (if any)

### Response Timeline

- **Acknowledgment**: Within 48 hours of report
- **Initial assessment**: Within 5 business days
- **Fix timeline**: Depends on severity
  - Critical: Patch within 7 days
  - High: Patch within 14 days
  - Medium/Low: Addressed in next release

### Scope

The following are in scope for security reports:

- Authentication and authorization bypasses
- Injection vulnerabilities (SQL, command, XSS)
- Sensitive data exposure (tokens, credentials, PII)
- Server-side request forgery (SSRF)
- Insecure cryptographic practices
- Dependency vulnerabilities with known exploits

### Out of Scope

- Vulnerabilities in third-party services (GitHub, LinkedIn, E2B)
- Social engineering attacks
- Denial of service via rate limiting (already mitigated)
- Issues requiring physical access to infrastructure
