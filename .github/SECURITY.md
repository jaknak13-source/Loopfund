# Security Policy

## Reporting a vulnerability

Please report security issues privately using GitHub's
**[Report a vulnerability](https://docs.github.com/en/code-security/security-advisories/guidance-on-reporting-and-writing-information-about-vulnerabilities/privately-reporting-a-security-vulnerability)**
feature (Security tab, Advisories) on this repository, rather than opening a
public issue. Include steps to reproduce and the affected version/commit.

## Threat model

loopfund is built to run **locally** for one user:

- The backend binds to `127.0.0.1` by default.
- The dashboard API has **no authentication**. It can write files, change
  settings, write agent briefings, and (if enabled) run model-authored code.
- Treat the API as trusted-local-only. Do **not** expose it to other machines or
  the internet without putting authentication and a firewall in front of it (see
  [deploy/DEPLOY.md](deploy/DEPLOY.md) and the auth example in
  `deploy/nginx.conf`).

## Safe defaults in this repo

- Model-authored code execution is **off by default**
  (`agents.allow_code_execution: false`). When enabled on macOS it runs under
  `sandbox-exec` (writes confined; reads of `.env`/SSH/AWS/GCP secrets denied).
  On Linux/Windows it fails closed unless `LOOPFUND_ALLOW_UNSANDBOXED=1`.
- Outbound URL fetching blocks non-`http(s)` schemes and private/loopback/
  link-local/metadata addresses (SSRF guard).
- Live trading is double-gated (`mode=live` **and** `LOOPFUND_ALLOW_LIVE=1`) and
  the execution adapter is unimplemented. It cannot move real money.
- Secrets live only in `.env`, which is git-ignored. Never commit it.
- The Docker image runs as a non-root user; compose publishes only to localhost.

## Out of scope

- Running the app intentionally exposed to a network without adding auth.
- Enabling `LOOPFUND_ALLOW_UNSANDBOXED=1` and running untrusted model code.
