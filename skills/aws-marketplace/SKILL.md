---
name: aws-marketplace
description: Publish paid container products to AWS Marketplace. Covers the full lifecycle — seller onboarding, ECR image pipeline, pricing, CloudFormation templates, AWS review, and post-launch operations. Based on direct experience shipping a real paid listing.
license: MIT
metadata:
  author: thevgergroup
  version: "3.0.0"
user-invocable: true
argument-hint: "[task description]"
---

# AWS Marketplace Publishing Skill

## Overview

This skill helps publish software products to AWS Marketplace. It is based on
**direct experience shipping a real paid container product** and verified AWS documentation.
Where AWS docs and reality diverge, this skill reflects reality.

**The platform is more restrictive than it appears.** Read the constraints section
before doing anything. Many decisions are permanent and cannot be undone.

## Companion documents

Load these on-demand based on the task at hand:

| Task | Document |
|---|---|
| First time selling on Marketplace, registration, tax, bank setup | `seller-onboarding.md` |
| Container image preparation, ECR push, metering integration, CI scanning | `container-packaging.md` |
| CloudFormation template for customer deployment, VPC, cfn-nag | `cloudformation-guide.md` |
| Designing a new product: ECS vs EKS, multi-AZ, service decomposition, CF resources | `product-architecture.md` |
| Auditing an existing product: phase-by-phase runbook with CLI commands | `product-audit.md` |
| Creating diagrams (drawio-mcp, AWS icons, tool options) and listing content templates | `diagram-and-docs.md` |
| Creating custom pricing for enterprise buyers, Flexible Payment Scheduler | `private-offers.md` |
| Post-launch: CVE re-scan failures, versioning, disbursement, subscriber SNS | `post-launch-operations.md` |
| What AWS checks during review, timeline, hard rejection criteria, submission checklist | `review-and-timeline.md` |
| ISV Accelerate, FTR, partner programs — and why none are required to sell | `isv-accelerate.md` |
| Full product creation sequence, battle-tested 14-step flow | This document (see below) |

---

## The AWS Marketplace Entity Model

Understanding the data model prevents the most costly mistakes.

```
ContainerProduct
├── Description         (title, short/long desc, logo, highlights, keywords, categories)
├── PromotionalResources (logo URL, videos, additional resources)
├── SupportInformation  (support description)
├── RegionAvailability  (which AWS regions buyers can deploy to)
├── Targeting           (allowlist of buyer account IDs — only matters while Limited)
├── Repositories[]      (ECR repos — PERMANENT, bound to this product forever)
├── Dimensions[]        (pricing dimensions — key, name, description, unit, types)
│   └── Key, Name, Description, Unit, Types
│       (Types: "Entitled" for contract, "Metered" for usage-based)
└── Versions[]
    └── Version
        ├── VersionTitle, ReleaseNotes, UpgradeInstructions
        ├── Sources[]
        │   └── Source (Type: DockerImages, Images: [ECR URIs], Compatibility)
        └── DeliveryOptions[]
            └── DeliveryOption
                ├── Title, ShortDescription, Type (ElasticContainerRegistry)
                ├── SourceId (links to a Source above)
                ├── Compatibility (AWSServices: ECS, EKS, etc.)
                ├── Instructions.Usage
                └── Recommendations.DeploymentResources[] (CF template URL goes here)

Offer  (separate entity, linked to a product via ProductId)
├── Name, Description
├── ProductId           (links to ContainerProduct)
├── State               (Draft → Released)
├── Rules               (buyer targeting rules)
└── Terms[]
    ├── ConfigurableUpfrontPricingTerm  (contract pricing — rates per dimension per duration)
    ├── LegalTerm                       (EULA — StandardEula or custom URL)
    ├── SupportTerm                     (refund policy text)
    └── RenewalTerm                     (auto-renewal behaviour)
```

**Key relationships:**
- A Product has one or more Dimensions (the billable units)
- A Product has Repositories (ECR) and Versions (the actual container images + delivery method)
- An Offer is a separate entity that references a Product and defines the commercial terms
- Pricing lives on the Offer, not the Product — but Dimensions (the keys) live on the Product
- One public Offer per Product maximum. You cannot delete an Offer. You cannot change an Offer's pricing model after release.

---

## Platform Constraints — Read Before Starting

These are permanent or near-permanent decisions. Getting them wrong means recreating the product.

### Things You Cannot Do
- **Cannot delete a product.** Once created, a product exists forever. You can only move it to Restricted or Deprecated status. Test products will permanently appear in your seller account.
- **Cannot delete an offer.** Offers can be released or restricted, not deleted.
- **Cannot change a free offer to a paid offer.** The pricing model is set at offer creation. `INCOMPATIBLE_PRICING_MODEL` if you try. If you need to go from free to paid, you must create a new product from scratch.
- **Cannot have two public offers on one product.** `TOO_MANY_OFFERS` if you try to release a second public offer.
- **Cannot re-register an ECR repository.** Once a repo is registered to a product via `AddRepositories`, it is permanently bound to that product. `DUPLICATE_ECR_REPOSITORY_NAME` if another product tries to claim it. Use product-scoped naming from the start (e.g. `myproduct-api`, not `api`).
- **Cannot remove a registered repository** from a product.
- **Cannot make changes while a visibility request is under review.** Submitting for Public locks the product entity. `ResourceInUseException` on any subsequent changeset until AWS approves.

### Things That Are Confusing
- **The portal and the API are not in sync.** If you register repos via the API, the portal wizard doesn't know — it will try to re-register them and fail with `DUPLICATE_ECR_REPOSITORY_NAME`. Pick one approach and stick to it. Prefer the API for repeatability.
- **The portal gives useless error messages.** "Failed" with no detail. Use `aws marketplace-catalog describe-change-set --change-set-id <id>` to get the actual `ErrorCode` and `ErrorMessage`.
- **There is no sandbox.** Every action is real. Every failed product creation is a permanent entry in your seller account. There is no "test mode" or dry run.
- **`PREPARING` is not failing.** When `AddDeliveryOptions` is submitted, it enters `PREPARING` for 20-45 minutes while AWS scans the container images for vulnerabilities. Do not cancel, do not resubmit. Just wait.
- **AWS review takes 3-5 business days** for a Public visibility request. No expedite path. No status API — you wait for email.
- **Prices are locked for 90 days** once the Public visibility request is approved. You cannot change pricing for 90 days after going public.
- **The `RepositoryName` field in `AddRepositories` is the short name only.** AWS automatically prepends your seller prefix (e.g. `my-company/`). If you pass `my-company/myrepo`, the actual repo becomes `my-company/my-company/myrepo`.
- **`ListEntities` uses entity type without version suffix** (e.g. `ContainerProduct`), but `StartChangeSet` requires the versioned form (e.g. `ContainerProduct@1.0`).

---

## Product Lifecycle (Visibility States)

```
[Draft] ──────── ReleaseProduct+ReleaseOffer ──────────► [Limited]
                                                              │
                                                     UpdateVisibility (Public)
                                                     + AWS review (3-5 days)
                                                              │
                                                              ▼
                                                          [Public]
                                                              │
                                                    UpdateVisibility (Restricted)
                                                              │
                                                              ▼
                                                         [Restricted]
                                                    (existing buyers keep access,
                                                     new buyers cannot subscribe)
```

**Limited**: Only allowlisted AWS account IDs can see and subscribe. Good for internal testing and early access. Allowlist is ignored once product goes Public. Add allowlisted accounts via `UpdateTargeting` change type.

**Public**: Visible to all buyers on AWS Marketplace. Requires AWS Seller Operations review (up to 37 days max, typically 3-5 business days). Prices lock for 90 days on approval.

**Restricted**: Use to sunset a product. Existing subscribers retain access per their agreement terms.

---

## Correct Product Creation Sequence (Paid Container Product)

Every step is an API changeset. Steps 1-10 can be done in any order across multiple changesets. Steps 11-14 must be in the exact order shown.

**Before you start — decide these permanently:**
- [ ] Pricing model: contract (upfront), usage-based (metered), or free. Cannot change later.
- [ ] ECR repository names: must be unique across all your products. Use a product-specific prefix.
- [ ] Product title: max 72 characters, ASCII only (no em dashes `—`, no curly quotes).

```
Step 1:  CreateProduct
         └── ProductTitle ≤72 chars, ASCII only

Step 2:  AddDimensions
         └── Details = JSON array: [{Name, Description, Key, Unit, Types}]
         └── NOT {"Dimensions": [...]} — bare array only
         └── Types: ["Entitled"] for contract, ["Metered"] for usage-based

Step 3:  AddRepositories
         └── {"Repositories": [{"RepositoryName": "myproduct-api", "RepositoryType": "ECR"}]}
         └── Short name only — prefix is auto-added by AWS
         └── Name is permanent — choose carefully

Step 4:  CreateOffer
         └── {"ProductId": "<product-id>"}
         └── Or use $CreateProduct.Entity.Identifier if in the same changeset

Step 5:  UpdatePricingTerms (on Offer)
         └── ConfigurableUpfrontPricingTerm for contract pricing
         └── ISO 8601 durations: P1M (monthly), P12M (annual), P24M, P36M
         └── One RateCard per duration, referencing Dimension Keys from Step 2

Step 6:  UpdateLegalTerms (on Offer)
         └── StandardEula with version "2022-07-14"
         └── Or custom EULA URL

Step 7:  UpdateSupportTerms (on Offer)
         └── {"Terms": [{"Type": "SupportTerm", "RefundPolicy": "<text>"}]}

Step 8:  UpdateRenewalTerms (on Offer)
         └── {"Terms": [{"Type": "RenewalTerm"}]}
         └── No extra properties — {"AutoRenewable": true} will fail validation

Step 9:  UpdateInformation (on Offer)
         └── Name and Description are required before release

Step 10: UpdateInformation (on Product)
         └── Must include LogoUrl and Categories or the changeset fails
         └── LogoUrl: fetch from PromotionalResources on existing product entity

Step 11: ReleaseProduct + ReleaseOffer  ← MUST be in the same changeset
         └── Wait for SUCCEEDED (~2-3 minutes)
         └── Product is now Limited visibility

Step 12: AddDeliveryOptions  ← only possible after Step 11
         └── {"Version": {VersionTitle, ReleaseNotes},
               "DeliveryOptions": [{Title, Details: {EcrDeliveryOptionDetails: {
                 Description, CompatibleServices, ContainerImages, UsageInstructions}}}]}
         └── ContainerImages: full ECR URIs including tag
         └── Wait for SUCCEEDED (~20-45 minutes — image security scan)
         └── PREPARING status during scan is normal — do not cancel

Step 13: Finalize remaining changes (CF template URL, metadata, allowlist)
         └── Add CF template URL via UpdateDeliveryOptions.Recommendations.DeploymentResources
         └── Batch everything — product will be locked after Step 14

Step 14: Submit "Update visibility to Public" via portal
         └── Portal: product overview → "Update visibility" → Public → Submit
         └── Confirm pricing dimensions shown — prices lock for 90 days on approval
         └── Product entity is now locked — no changes until AWS approves (3-5 days)
         └── Watch for email from AWS Marketplace Seller Operations
```

---

## Submitting for Public Visibility

This cannot be done via the Catalog API alone — it requires a portal interaction to confirm pricing.

1. Navigate to the Marketplace Management Portal → Server products → your product
2. Click **"Update visibility"** (appears as a notification banner on the product page)
3. Select **Public**
4. The page expands to show all contract dimension prices for confirmation
5. Review the prices — **they will be locked for 90 days after approval**
6. Click **Submit**
7. You are redirected to a Request page showing `Status: Under review`
8. The product entity is now locked — `ResourceInUseException` on any API changes until approved

**After approval:**
- Product is publicly visible on AWS Marketplace
- Offers management page becomes accessible
- You can now update delivery options, add CF template URLs, etc.
- Deprecate any old free/test products

---

## Two-Registry Image Pipeline (Container Products)

AWS Marketplace requires images in the **Marketplace-owned ECR** (`709825985650`). You cannot use your own private ECR or ECR Public for paid products — AWS enforces subscription access control on `709825985650`.

```
Your build pipeline
       │
       ▼
Private ECR (your account)          ← build target, internal use
<your-account-id>.dkr.ecr.us-east-1.amazonaws.com/myproduct-api:1.2.0
       │
       │  docker pull → docker tag → docker push
       ▼
Marketplace ECR (AWS-owned)         ← what buyers pull, what the listing references
709825985650.dkr.ecr.us-east-1.amazonaws.com/<your-seller-prefix>/myproduct-api:1.2.0
```

Repos in the Marketplace ECR are created automatically by AWS when you call `AddRepositories`. You cannot create them manually. They are named `your-seller-prefix/<RepositoryName>`.

**Why not ECR Public (`public.ecr.aws`):** Anyone can pull without subscribing — no access control. Prohibited for paid Marketplace products.

See `container-packaging.md` for image security requirements, metering integration, and the startup validation pattern.

---

## Updating an Existing Product (New Version)

To publish a new version after the product is Public:

```
1. AddDeliveryOptions with new VersionTitle and updated ContainerImages URIs
   └── Wait 20-45 minutes for image scan
2. The new version appears alongside old versions
3. Old versions can be restricted via RestrictDeliveryOptions if needed
4. No AWS review required for version updates — takes effect immediately
```

**Important**: Version updates do not require re-submitting for Public visibility. Only initial publication and pricing/visibility changes require AWS review.

---

## AWS CLI Reference

```bash
# List your products (no version suffix on entity type)
aws marketplace-catalog list-entities \
  --catalog AWSMarketplace \
  --entity-type ContainerProduct

# Get product details
aws marketplace-catalog describe-entity \
  --catalog AWSMarketplace \
  --entity-id <product-id>

# Start a changeset (use versioned entity type: ContainerProduct@1.0)
aws marketplace-catalog start-change-set \
  --catalog AWSMarketplace \
  --change-set '[{"ChangeType": "...", "Entity": {"Type": "ContainerProduct@1.0", "Identifier": "<id>"}, "Details": "..."}]'

# Poll changeset status (do this, not the portal — better error messages)
aws marketplace-catalog describe-change-set \
  --catalog AWSMarketplace \
  --change-set-id <id> \
  --output json | python3 -c "
import sys,json; d=json.load(sys.stdin)
print('Status:', d.get('Status'))
for cs in d.get('ChangeSet',[]):
    for e in cs.get('ErrorDetailList',[]):
        print(cs['ChangeType'], '-', e['ErrorCode'], ':', e['ErrorMessage'])
"

# List all changesets for a product (useful for debugging history)
aws marketplace-catalog list-change-sets \
  --catalog AWSMarketplace \
  --filter-list '[{"Name": "EntityId", "ValueList": ["<product-id>"]}]'
```

**Available change types for `ContainerProduct@1.0`:**

| Change type | When |
|---|---|
| `CreateProduct` | Step 1 — creates in Draft |
| `AddDimensions` | Add pricing dimensions |
| `UpdateDimensions` | Modify existing dimensions |
| `AddRepositories` | Register ECR repos (permanent) |
| `UpdateInformation` | Title, description, logo, categories, keywords |
| `UpdateTargeting` | Add/remove allowlisted account IDs (Limited state) |
| `ReleaseProduct` | Draft → Limited (must pair with ReleaseOffer) |
| `UpdateVisibility` | Limited → Public, or Public → Restricted |
| `AddDeliveryOptions` | Add new version (after Limited) |
| `UpdateDeliveryOptions` | Update release notes, CF template URL |
| `RestrictDeliveryOptions` | Restrict old versions |

**Available change types for `Offer@1.0`:**

| Change type | When |
|---|---|
| `CreateOffer` | Step 4 |
| `UpdatePricingTerms` | Set contract prices |
| `UpdateLegalTerms` | Set EULA |
| `UpdateSupportTerms` | Set refund policy |
| `UpdateRenewalTerms` | Set renewal behavior |
| `UpdateInformation` | Offer name and description |
| `ReleaseOffer` | Release alongside ReleaseProduct |

---

## Pre-Creation Checklist

Run through this before calling `CreateProduct`. These cannot be changed later.

- [ ] **Pricing model decided**: contract / metered / free — permanent
- [ ] **ECR repo names chosen**: product-scoped prefix, unique across all your products — permanent
- [ ] **Product title**: ≤72 chars, ASCII only, no Unicode punctuation
- [ ] **Dimensions defined**: key names, display names, descriptions, unit types
- [ ] **Do not start with a free product** as a placeholder if you intend to charge later — you will have to recreate the product
- [ ] **Seller registration complete** for paid products — see `seller-onboarding.md`

---

## Pre-Release Checklist

Run through this before `ReleaseProduct + ReleaseOffer`.

- [ ] All dimensions added
- [ ] All repositories registered
- [ ] Offer has: pricing terms, legal terms, support terms, renewal terms, name, description
- [ ] Product has: LogoUrl, Categories set in UpdateInformation
- [ ] No delivery option added yet (that comes after release)

---

## Pre-Public-Submission Checklist

Run through this before submitting for Public visibility. The product locks after submission.

- [ ] Delivery option added with correct ECR image URIs (Marketplace ECR: `709825985650`)
- [ ] Images pass security scan (no CVEs, non-root, no EoL OS — see `container-packaging.md`)
- [ ] CF template passes Marketplace security validation — see `cloudformation-guide.md`
- [ ] CF template URL added to DeliveryOptions.Recommendations.DeploymentResources
- [ ] Architecture diagram ready: 1100×700px, uses current AWS icons
- [ ] Metering integration tested in us-east-1 with a running container
- [ ] All metadata complete and reviewed
- [ ] Pricing confirmed — prices lock for 90 days on approval
- [ ] Old/test products deprecated or restricted
- [ ] No pending changes needed — you cannot modify until AWS approves

---

## Common Errors and Fixes

| Error | Cause | Fix |
|---|---|---|
| `INCOMPATIBLE_PRICING_MODEL` | Trying to add contract pricing to a free offer | Create a new product — cannot be fixed |
| `TOO_MANY_OFFERS` | Releasing a second public offer | Not fixable on existing product — one public offer only |
| `DUPLICATE_ECR_REPOSITORY_NAME` | Repo already registered to another product | Use a different repo name — permanent per product |
| `INCOMPATIBLE_PRODUCT_STATUS` on AddDeliveryOptions | Product is still Draft | Run ReleaseProduct first, then AddDeliveryOptions |
| `INVALID_INPUT` on ReleaseProduct | ReleaseOffer not in same changeset | Add ReleaseOffer to the same changeset |
| `MISSING_MANDATORY_TERMS` | Offer missing SupportTerm or RenewalTerm | Add UpdateSupportTerms + UpdateRenewalTerms before release |
| `MISSING_NAME` / `MISSING_DESCRIPTION` | Offer has no name or description | Run UpdateInformation on the Offer |
| `MISSING_LOGO_URL` / missing Categories | UpdateInformation without required fields | Always include LogoUrl and Categories |
| `ResourceInUseException` | Product locked by pending changeset or review | Wait for the pending changeset to complete |
| `SCAN_ERROR` on AddDeliveryOptions | Image failed security scan | URL returned in DescribeChangeSet (valid 60 days) — fix image, resubmit |
| `INVALID_HELM_UNDECLARED_IMAGES` | Helm image not in Marketplace ECR | Move all image refs to values.yaml and declare in ECR repos |
| Portal shows `Failed` with no detail | Portal error messaging is useless | Use `describe-change-set` CLI to get actual errors |
| `PREPARING` for 20-45 min on AddDeliveryOptions | Image security scan in progress | Wait — this is normal, do not cancel |

---

## Decision Framework: Support Ticket vs. Start Over vs. Wait

When something goes wrong, you face three options. Choosing the wrong one costs days.
Use this table to decide quickly.

| Situation | Support ticket? | Start over? | Just wait? |
|---|---|---|---|
| Wrong pricing model on existing product | No (7+ day wait, won't help) | **Yes** — new product is faster | No |
| ECR repo name clash with another product | No | **Yes** — new repos, new product if needed | No |
| Product title too long or wrong | No (cannot change after creation) | **Yes** if not yet public | No |
| `PREPARING` on AddDeliveryOptions | No | No | **Yes** — 20-45 min scan |
| `SCAN_ERROR` on image submission | No | No | Fix image, resubmit |
| AWS review taking > 5 business days | **Maybe** — Marketplace support only | No | Yes first |
| Portal shows a field you can't edit via API | **Maybe** — but check API first | Consider if pre-public | No |
| Product locked by pending changeset | No | No | **Yes** — wait for changeset |
| Price needs changing within 90-day lock | **Yes** — only path, expect 7+ days | No | No |
| Metadata field rejected by API (em dash, etc.) | No | No | Fix and resubmit |

**General rules:**
- A support ticket to AWS Marketplace Seller Operations takes **5-7 business days minimum** for a first response, often longer. It is almost never the fastest path for pre-launch issues.
- If the product has **no buyers**, recreating it is almost always faster than a support ticket. The cost is a permanent deprecated entry in your seller account — acceptable.
- If the product **has active buyers**, do not recreate it. Open a support ticket, wait, and communicate with buyers.
- Before opening a ticket, confirm the action is truly impossible via the API. The portal frequently shows fields as non-editable that the API can change.

**How to open a Marketplace support ticket (when warranted):**
1. Go to AWS Support → Create case → Service: AWS Marketplace
2. Category: Seller issues → Subcategory: Product/listing management
3. Include: product ID, offer ID, exact error message or field name, what you tried via API
4. Expect 5-7 days first response. Follow up after 3 days if no reply.

---

## Timings Reference

Use these when planning work. AWS Marketplace has several mandatory wait periods that cannot be expedited.

| Action | Typical duration | Notes |
|---|---|---|
| Changeset apply (metadata, pricing, offers) | 1-3 minutes | Poll `describe-change-set` |
| ReleaseProduct + ReleaseOffer | 2-5 minutes | |
| AddDeliveryOptions (image scan) | 20-45 minutes | `PREPARING` status is normal |
| AWS Public visibility review | 3-37 days | Typically 3-5 business days; email notification only, no status API |
| Support ticket first response | 5-7 business days | Often longer |
| Price change after 90-day lock expires | 90 days from Public approval | Only path is support ticket during lock |
| Deprecated product removal from account | Never | Permanent — plan accordingly |

---

## Seller Perspective: What to Expect

- **There is no undo.** Test products, wrong repo names, abandoned products — all permanent entries in your seller account. Plan before acting.
- **The portal lags the API.** Changes submitted via API may take minutes to appear in the portal. The portal also has its own set of bugs — it may show incorrect state or try to redo steps already completed via API.
- **Error messages are often opaque in the portal.** Always diagnose via the CLI `describe-change-set`.
- **AWS review is a black box.** 3-37 days, email notification only, no status API. If they need changes they will email with a list.
- **Prices lock for 90 days.** Once approved for Public, you cannot change pricing for 90 days. Get pricing right before submitting.
- **The allowlist becomes irrelevant once Public.** Don't invest time curating it — it only applies while Limited.
- **Version updates don't need re-review.** Adding new delivery option versions to an existing Public product does not trigger another AWS review cycle.
- **Starting over is often faster than a support ticket.** If you have no buyers and something is permanently wrong, create a new product. It takes hours, not days. The only cost is a deprecated product entry in your account — acceptable pre-launch.
- **AWS continuously re-scans published images.** EoL packages added to a published image will trigger re-scan failures and potential listing suspension. Keep base images updated.

---

## Resources

- AWS Marketplace Management Portal: https://aws.amazon.com/marketplace/management/
- Catalog API reference: `aws marketplace-catalog help`
- Companion docs in this skill directory: `seller-onboarding.md`, `container-packaging.md`, `cloudformation-guide.md`

## Version

3.0.0 - Restructured into skill suite with companion docs; added metering, image security, CF requirements, entity type versioning (March 2026)
