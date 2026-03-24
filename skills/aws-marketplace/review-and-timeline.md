# AWS Marketplace Review Process and Timeline

## When to read this doc

Read this before submitting a product for the first time, when planning a launch, or when trying to understand what AWS actually checks during review.

---

## Realistic end-to-end timeline

**Optimistic (clean first submission, no issues):** ~6 weeks
**Realistic (first-time seller, one round of fixes):** 10-14 weeks
**Plan for 45+ days before any external launch event** — AWS does not guarantee review SLAs.

| Phase | Duration | What gates it |
|---|---|---|
| Seller registration + bank/tax | 1–3 weeks | Bank micro-deposit confirmation, EMEA KYC adds 1-2 weeks |
| Product preparation | 1–2 weeks (parallel) | Engineering, image scans, content writing, Helm validation |
| AWS technical + content review | 2–4 weeks | Automated scans + manual policy review; `Action Required` resets the clock |
| Seller approval of limited listing | 1–3 business days | Seller must review and explicitly approve a preview URL |
| Limited → Public visibility | 7–10 business days | Manual AWS Seller Operations action — you cannot self-serve this |

### The clock resets on `Action Required`

If AWS flags issues during review, the status moves to `Action Required`. You fix and resubmit. Each round of `Action Required` → fix → resubmit adds 1-2 weeks minimum. The most common causes of this (by frequency):

1. Helm chart validation errors (images not in `values.yaml`, hardcoded URIs)
2. Usage instructions incomplete or missing
3. CVE in submitted image
4. IAM permissions using wildcards (`*`)
5. CF template security issues (ports open to `0.0.0.0/0`)
6. Missing required offer terms (SupportTerm, RenewalTerm)

---

## What AWS actually checks

### Automated checks (fast — minutes to hours)

These run immediately when a changeset is submitted and complete before human review begins.

**Container image scanning**
- Known CVEs — any CRITICAL or HIGH blocks submission
- Malware
- End-of-Life OS: Ubuntu 18.04, CentOS 7, RHEL 6/7, Debian 9
- End-of-Life package versions (Python 3.8, Node 16, etc.)
- Running as root — containers must run as non-root user
- Hardcoded passwords, private keys, or secrets in image layers
- External registry references — all images must be in `709825985650` Marketplace ECR

**Helm chart validation** (if using Helm delivery)
- `helm lint` — must pass with zero errors
- `helm template` — must render without errors
- All image references in `values.yaml` — hardcoded URIs in deployment templates cause rejection
- All images declared in the version submission request
- No external chart dependencies (must be local `file://` references)
- No sensitive configuration in the JSON schema (passwords, API keys, certificates)

**JSON schema validation** (if using EKS add-on or custom config schema)
- Must use one of four supported JSON Schema draft versions

**CloudFormation template scanning**
- SSH (22) and RDP (3389) not open to `0.0.0.0/0`
- Database ports not open to `0.0.0.0/0`
- IAM policies without wildcards
- No default plaintext passwords

### Human review checks (slow — the 2-4 week window)

These require a reviewer. AWS does not publish reviewer checklists, but patterns from real submissions reveal what they look at:

**Policy compliance**
- Product is production-ready, not beta or alpha
- Does not redirect users to a competing cloud platform
- All deployment dependencies are disclosed in usage instructions
- No unauthorized data collection
- No upsell of services unavailable through Marketplace
- Add-on products include the mandatory disclosure: *"This product extends the functionality of [X] and without it, this product has very limited utility."*

**Technical correctness**
- ECS workloads use IAM task roles (not long-term keys)
- EKS workloads use IRSA or EKS Pod Identity
- Metering integration uses `MeterUsage` (not `BatchMeterUsage`)
- Container terminates on metering failure (non-throttle) at startup

**Content quality**
- Short description is specific and descriptive (not generic marketing copy)
- Long description covers: what the product does, key features, deployment model, dependencies
- Usage instructions cover the complete deployment path
- At least one screenshot or architecture diagram
- Support contact information present
- EULA, Privacy Policy, and Terms of Service linked

**What triggers rejection for content**
- Thin or generic descriptions ("A powerful AI platform for enterprises")
- Missing architecture diagram for SaaS products
- Usage instructions that don't mention the Marketplace ECR images
- Missing or invalid EULA
- Support contact email that bounces
- Pricing dimensions with no values ($0.00 across all tiers)

---

## Architecture review specifics

### Container products (ECS/Fargate or EKS)

There is no separate formal "architecture review" gate for container products in the same way SaaS has one. What AWS reviewers examine:

- **IAM patterns**: ECS task role (not node role), EKS IRSA (not node role or access keys)
- **Network egress**: Are outbound calls documented? What AWS services does the product call?
- **Data handling**: Is customer data stored? Where? Is it encrypted?
- **Metering integration**: Is `MeterUsage` called? Does the container terminate on entitlement failure?
- **CF template security**: Does the template create overly permissive security groups or IAM roles?

**The architecture diagram** (1100 × 700px for the listing, separate from technical review) is evaluated for:
- Uses current AWS Architecture Icons (not custom icons or competitor icons)
- Shows all VPCs, subnets, and network flows
- Shows the integration point between the product and buyer's existing AWS resources
- Labels all services and data flows clearly

### SaaS products (for reference)

SaaS has a more formal architecture review. Reviewers use AWS's Well-Architected Tool against the product's stated architecture. They look for:
- Application plane vs control plane separation
- Multi-tenant data isolation
- Webhook endpoint security (ResolveCustomer call flow)
- No hardcoded endpoints or region assumptions

---

## Hard rejection criteria (zero tolerance)

These cause automatic or immediate rejection with no opportunity to appeal before resubmit:

| Criterion | Detail |
|---|---|
| CVE in image | Any CRITICAL or HIGH severity CVE in any submitted image |
| Container runs as root | Must specify non-root user in Dockerfile |
| EoL OS in image | Ubuntu 18.04, CentOS 7, RHEL 6/7, Debian 9, or similar |
| Hardcoded credentials in image | Any password, key, or secret in image layers |
| External registry reference | Any image not in `709825985650` Marketplace ECR |
| Helm images not in `values.yaml` | Even a single hardcoded image URI in a template |
| IAM wildcard (`Action: "*"`) | In any IAM policy created by the product |
| SSH/RDP open to `0.0.0.0/0` | In any security group in the CF template |
| Pricing model mismatch | Submitting contract pricing when offer was created as free |
| Missing mandatory offer terms | SupportTerm and RenewalTerm both required before release |

---

## How to maximize review speed

### Before submitting

Run this locally and confirm zero failures:

```bash
# Image scan
trivy image --severity CRITICAL,HIGH <image-uri>

# CF template
cfn-lint template.yaml
cfn_nag_scan --input-path template.yaml --fail-on-warnings

# Helm chart (if applicable)
helm lint ./chart
helm template my-release ./chart > /dev/null
```

### Submission completeness checklist

The more complete your submission, the faster it moves. Incomplete submissions sit in review until AWS emails you for changes.

- [ ] Product title: ≤72 chars, ASCII only (no em dashes, smart quotes)
- [ ] Short description: specific, ≤350 chars, describes what the product actually does
- [ ] Long description: ≤5,000 chars, covers features, deployment model, dependencies
- [ ] At least 3 highlights (bullet points)
- [ ] At least 1 screenshot (780×439px recommended) or architecture diagram
- [ ] Logo: 300×150px PNG with transparent background
- [ ] Support email address that actually works
- [ ] EULA linked (Standard Marketplace EULA or custom URL)
- [ ] Privacy Policy URL
- [ ] Usage instructions: complete step-by-step deployment referencing Marketplace ECR image URIs
- [ ] Architecture diagram: 1100×700px using current AWS icons
- [ ] All images: non-root, no CVEs, Marketplace ECR only, semantic version tags
- [ ] CF template: passes cfn-lint and cfn-nag, deployed successfully in us-east-1
- [ ] Metering: `MeterUsage` called at startup with `DryRun=True` validation, container exits on non-throttle failure
- [ ] Offer: pricing terms, legal terms, support terms, renewal terms, name, description — all set before `ReleaseOffer`

### Responding to `Action Required`

When AWS emails you with a list of required changes:

1. Fix **every item** in the list — partial fixes result in another `Action Required` round
2. Test the fix before resubmitting (don't just hope it works)
3. Reply to the email confirming what you changed and how
4. Resubmit via the Management Portal
5. The review clock restarts from zero

Responding quickly matters. AWS reviewers have queues. If you respond within 24 hours vs 5 business days, you move through the queue faster in subsequent rounds.

---

## What happens after approval

1. AWS sends email: product approved, limited listing created
2. You receive a preview URL — review it carefully before approving
3. Log into Management Portal → Requests → approve the limited listing
4. Product moves to Limited visibility (accessible via direct link, not discoverable in search)
5. Test with allowlisted accounts in Limited state
6. When ready for Public: contact AWS Seller Operations (portal or support ticket)
7. AWS manually flips to Public — 7-10 business days
8. You receive email confirmation; product appears in Marketplace search

You cannot self-serve the Limited → Public transition. It is always a manual AWS operations action.
