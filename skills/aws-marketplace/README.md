# AWS Marketplace Publishing Skill

Battle-tested skill for publishing paid container products to AWS Marketplace. Based on direct experience shipping a real paid listing, not just documentation.

## Documents in this skill

| File | Use when |
|---|---|
| `SKILL.md` | Main reference — entity model, 14-step creation sequence, CLI commands, error table, checklists |
| `seller-onboarding.md` | First time registering as a seller — eligibility, tax forms, bank, IAM setup |
| `container-packaging.md` | Preparing images — ECR pipeline, security, CI scanning, metering with `MeterUsage` |
| `cloudformation-guide.md` | CloudFormation template — security, VPC endpoints, password constraints, cfn-nag, cfn-lint |
| `product-architecture.md` | Designing a new product — ECS vs EKS, multi-AZ layout, CF resource map, enterprise buyer expectations |
| `product-audit.md` | Auditing an existing product — phase-by-phase runbook with CLI commands, pass/fail criteria |
| `diagram-and-docs.md` | Creating diagrams (drawio-mcp, AWS icons) and listing content templates |
| `private-offers.md` | Enterprise deals — targeted offers, custom pricing, Flexible Payment Scheduler |
| `post-launch-operations.md` | After launch — CVE re-scan failures, new versions, subscriber notifications, disbursement |
| `review-and-timeline.md` | What AWS checks, hard rejection criteria, realistic timeline, submission completeness checklist |
| `isv-accelerate.md` | Partner programs — ISV Accelerate and FTR explained, **neither is required to sell** |

## Quick Start

```
Use the aws-marketplace skill to [your request]
```

Examples:
- `Use the aws-marketplace skill to walk me through creating a new paid container product`
- `Use the aws-marketplace skill — what do I need before I can sell on Marketplace?`
- `Use the aws-marketplace skill to help me implement metering in my container`
- `Use the aws-marketplace skill to review my CloudFormation template for Marketplace submission`

## Key facts (read before doing anything)

- **No sandbox.** Every action is real and permanent.
- **ECR repos are permanent.** Once registered to a product, cannot be moved.
- **Free → paid requires a new product.** Cannot convert pricing model.
- **AddDeliveryOptions requires Limited status first** (ReleaseProduct must happen first).
- **Container products use `MeterUsage`**, not `BatchMeterUsage` (that's SaaS only).
- **Public visibility takes 3-37 days** and locks the product during review.
- **Prices lock for 90 days** once approved for Public.

## Version

3.0.0 - Restructured into skill suite with companion docs (March 2026)
