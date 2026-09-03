# Security Policy

## Reporting a vulnerability

Please report security issues privately — open a GitHub security advisory on this
repository rather than a public issue. Include what you found, how to reproduce
it, and what an attacker could achieve. Expect an acknowledgement within a few
days.

Please do not test against a deployment you do not own.

## Scope and threat model

This service accepts arbitrary files from untrusted users and produces documents
intended to support a legal complaint. Two consequences shape the design:

1. **Uploads are hostile until proven otherwise.** Every file is validated by
   extension *and* magic number, size-capped mid-stream, stored under a
   server-generated name, and never executed or interpreted.
2. **A result that overstates its confidence is a safety problem, not just a
   quality one.** A deployment without trained weights is marked non-evidential
   in the API, the interface and the PDF.

## Controls in place

| Area | Control |
|---|---|
| Authentication | JWT bearer tokens; pbkdf2-sha256 password hashing with per-password salts |
| User enumeration | Unknown and wrong-password logins return an identical response, and both perform a hash |
| Authorisation | A job belonging to an account is readable only by that account; unauthorised access returns 404, never 403 |
| Upload validation | Extension allow-list, magic-number cross-check, streaming size limit, server-generated filenames |
| Path traversal | Evidence paths are resolved and confirmed to sit inside the evidence directory |
| Rate limiting | Per-account and per-IP hourly caps; rejected uploads consume budget too |
| Transport | HSTS in production; TLS terminated at the reverse proxy |
| Response headers | CSP, `X-Content-Type-Options`, `X-Frame-Options`, `Referrer-Policy`, `Permissions-Policy` set by the API itself |
| Error handling | Unhandled exceptions log server-side and return an opaque body with a request id |
| Configuration | Production refuses to start with a placeholder or short signing key, with `DEBUG` on, or with wildcard CORS |
| Secrets | Never committed; `docker-compose.yml` has no defaults for them, so the stack fails rather than booting insecurely |
| Dependencies | Pinned; Dependabot weekly; `pip-audit` and `bandit` run in CI |
| Data protection | User-initiated erasure removes the record, the media, evidence images and reports |

## Known limitations

- Reports are hashed, not cryptographically signed. Hashes detect alteration;
  they do not establish authorship. Real evidentiary use needs a signature from
  a recognised certifying authority.
- Uploaded media is not scanned for malware. It is never executed, but a
  deployment handling third-party files should add scanning at the ingest point.
- The rate limiter is per-process and database-backed; a multi-region deployment
  needs a shared store.
