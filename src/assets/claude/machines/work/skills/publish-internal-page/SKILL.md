---
name: publish-internal-page
description: Publish one or a few static HTML pages so they are reachable only by colleagues on the company VPN / private network, by riding infrastructure that already exists (a host with no public IP, private DNS, VPN routes) plus a simple Caddy file server. Use this whenever the user wants to share an HTML page, report, guide, or dashboard "with the team", "internally", "on the intranet", or says it "must not be public" / "internal only" — even if they never mention Caddy, a server, or a VPC. Also use it when the user asks how to update or redeploy a page that is already served this way.
---

# Publish an internal-only static page

Turn "I have an HTML file" into "here's a link that only people on the company VPN can open" — with as close to zero new infrastructure as possible. The core insight: most companies already have everything needed (a VPN, private DNS, always-on servers with no public IP). Your job is to *discover and reuse* that, not to build. A page that needs a new load balancer, bucket policy, or certificate to ship internally is over-engineered.

## The security model (understand this before touching anything)

The page is private because of two locks and one door, none of which is the web server:

1. **No route** — the serving host has only a private IP. The public internet cannot deliver a packet to it, regardless of firewall rules.
2. **No name** — the hostname lives in a private DNS zone that only resolves for queries originating inside the network. Outsiders can't even look it up. (Treat this as the convenience lock, not the load-bearing one: short internal suffixes like `.prod` or `.dev` can collide with real public TLDs, so "doesn't resolve publicly" is circumstance, not guarantee. Lock 1 is the guarantee.)
3. **The one door** — an authenticated VPN session, which is exactly the audience.

Consequences that guide every decision below:
- A permissive firewall rule (e.g. port 80 open to 0.0.0.0/0) on a no-public-IP host is inert, not an emergency. Verify the *IP situation*, don't panic about the rule.
- The web server needs no auth, no TLS, no hardening theater. Plain HTTP is fine: the VPN already encrypts the path, and public CAs can't issue certs for private names anyway. Don't use the server's self-signed/internal CA option for a shared link — every visitor gets a trust warning, which is worse than the "Not secure" label.
- Never reach for public-facing patterns (CloudFront/CDN with IP allowlists, public S3 website, public ALB). Those are "public with a filter", which violates the requirement even when the filter is tight.

## Phase 1 — Discover what already exists

Work from cheapest signal to most expensive, and stop as soon as you find prior art:

1. **Prior art first.** Search the repo/org docs for an existing internal-page deployment: `rg -i 'caddy|/srv/www|scp .*html' --glob '*.md'`. If a previous page documented its deploy command, **reuse that host, docroot, and pattern verbatim** — consistency beats novelty, and the verification below has already been done once. You may be finished after just adding one file.
2. **The user's own machine leaks the topology.** The SSH config (`~/.ssh/config`) reveals internal hostnames and the naming scheme. On macOS, `scutil --dns` shows which domains resolve through the private resolver (the split-DNS match domains) — a page hosted under one of those domains will "just work" for every VPN user. `netstat -rn` shows which CIDRs route through the VPN tunnel.
3. **Cloud introspection** (read-only; e.g. on AWS):
   - Instances and their exposure: `aws ec2 describe-instances --filters Name=instance-state-name,Values=running --query '...{Name,PrivateIp,PublicIp,SGs}'` — candidates are always-on hosts with `PublicIp: null`.
   - Private DNS: `aws route53 list-hosted-zones` — look for `Config.PrivateZone: true`; then list records to see if the candidate host already has a name.
   - Firewall: `aws ec2 describe-security-groups` for the candidate — is port 80 already reachable from the VPN's address space?

Pick a host that is: always on, already reachable by VPN users, low-blast-radius for a new tenant (a static file server is the gentlest possible tenant, but still say what else runs there), and ideally already named in private DNS. If several qualify, prefer the one already serving internal pages.

## Phase 2 — Verify before installing anything

Confirm each item and tell the user what you found (this doubles as the security review):

- [ ] Host has **no public IP** (or provider equivalent). This is the load-bearing fact.
- [ ] An internal DNS name resolves to it from VPN clients — or a private zone exists where a one-line A record can be added. A raw private IP works as a fallback link, but a name is far more shareable.
- [ ] Port 80 inbound is allowed from the VPN users' address space (check the security group / firewall).
- [ ] **What already listens on port 80?** (`ss -tlnp | grep :80` on the host.) If a web server is already there, add a location/vhost to *it* instead of installing Caddy — never run two servers fighting over a port.

If you cannot reach the host yourself (sandboxed SSH, no credentials), hand the user exact commands to run and interpret the output they paste back — don't guess.

## Phase 3 — Install Caddy (only if nothing serves port 80 yet)

Caddy over alternatives because the entire config is ~4 lines, the package ships a systemd unit that auto-enables at boot, and file changes need no reload. On Debian/Ubuntu (Caddy is not in the default archive):

```bash
apt install -y debian-keyring debian-archive-keyring apt-transport-https curl
curl -1sLf 'https://dl.cloudsmith.io/public/caddy/stable/gpg.key' | gpg --dearmor -o /usr/share/keyrings/caddy-stable-archive-keyring.gpg
curl -1sLf 'https://dl.cloudsmith.io/public/caddy/stable/debian.deb.txt' | tee /etc/apt/sources.list.d/caddy-stable.list
apt update && apt install -y caddy
```

Replace `/etc/caddy/Caddyfile` with:

```
:80 {
    root * /srv/www
    try_files {path}.html {path} {path}/
    file_server
}
```

Why this exact shape:
- `:80` (no hostname) serves regardless of how the visitor addressed the box (name or raw IP), and a bare port means Caddy won't attempt a public ACME certificate that would fail for a private name.
- `try_files {path}.html ...` gives clean extension-less URLs: `/team/runbook` serves `/srv/www/team/runbook.html`. It also lets `foo.html` and a `foo/` directory coexist, so pages can grow companion pages later.
- One docroot (`/srv/www`) with meaningful subdirectories means every future page is just another file — no config changes ever again.

Then `systemctl reload caddy` (or `enable --now` on first install) and confirm boot persistence with `systemctl is-enabled caddy`.

## Phase 4 — Prepare the page

- Choose a URL path that says what the page is (`/runner-monitor/response-guide`, not `/page1`). The path is doing the labeling work a domain name usually does.
- HTML files authored as fragments (common for generated pages) start with `<style>` or `<div>` — served raw, browsers render them in **quirks mode** and show a bare URL as the tab title. Prepend:
  ```html
  <!doctype html>
  <meta charset="utf-8">
  <title>Human-Readable Page Name</title>
  ```
- Add a favicon as an inline SVG data URI (`<link rel="icon" href="data:image/svg+xml,...">`) so the page stays a single self-contained file. A simple mark on a solid tile reads fine at 16px.
- The repo copy is the source of truth. The served copy is a build artifact.

## Phase 5 — Deploy and verify

Deployment is one copy, no restart:

```bash
scp path/to/page.html <host>:/srv/www/<area>/<page-name>.html
```

Verify from the user's machine **on the VPN**: `curl -si http://<internal-name>/<area>/<page-name> | head -3` → expect `200`. If feasible, confirm the negative too: from off-VPN the name should fail to resolve. If DNS resolves but the request hangs, the VPN likely isn't pushing a route for that subnet — check the routing table, not the server.

## Phase 6 — Document it where the source lives

In the README/docs next to the source file, record: what serves the page (host, Caddy, docroot), the shareable URL, and the **exact scp command**. Two sentences and a code block. This is not optional — the whole approach depends on the next person (or the next session) finding the pattern in Phase 1 instead of re-deriving it. Deployment knowledge that lives only in a chat transcript is lost.

## Pitfalls

- **Name doesn't resolve for a teammate** → their VPN client isn't receiving the split-DNS push, or the name sits outside the matched domains. Diagnose with `scutil --dns` (macOS) on *their* machine; it's a VPN-config issue, not a server issue.
- **User asks for the browser padlock** → the only clean route is a real certificate on a real (public) domain resolving to the private IP, issued via DNS-01 challenge (requires a DNS-plugin build of Caddy plus DNS-edit credentials). Offer it, but recommend against unless it matters: for an internal page over an encrypted VPN, HTTP is not a real risk.
- **Tempted to create new cloud resources** (bucket, ALB, records in public zones) → re-read the security model; the existing private host almost certainly suffices, and public-zone DNS leaks internal naming.
