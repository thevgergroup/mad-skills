# AWS Marketplace Seller Onboarding

## When to read this doc

Read this before you have a seller account, or when the user asks about requirements, eligibility, tax forms, bank setup, or seller registration.

---

## Eligibility

### Any product (free or paid)

- Active AWS account in good standing
- Valid non-alias email on the account
- Use IAM roles (not root) for Management Portal access
- Production-ready software with a defined support process

### Paid products

Must be a permanent resident, citizen, or business entity in an eligible jurisdiction:

**Eligible countries/regions**: United States, Canada, EU member states, UK, Australia, New Zealand, Japan, South Korea, India, Israel, UAE, Qatar, Bahrain, Norway, Switzerland, Colombia, Hong Kong SAR

If your business is not based in an eligible jurisdiction, **you cannot sell paid products on AWS Marketplace**. There is no waiver path.

---

## Registration Steps (in order)

1. **Public profile** — company/individual name, description, support URLs
2. **Tax information** — W-9 (US), W-8BEN/W-8BEN-E (non-US), or DAC7 Questionnaire (EU professional services)
3. **Bank account** — must accept USD disbursements; SWIFT code required for non-US banks
4. **Disbursement preferences** — frequency, currency
5. **KYC verification** — required if: selling to EMEA, paid for Korea transactions, or using UK bank
6. **Bank verification** — small deposit/withdrawal confirmation

**All steps are blocking.** You cannot publish a paid listing until registration is complete. Plan 1-3 business days for bank verification.

---

## Tax Forms

| Seller type | Form |
|---|---|
| US individual or entity | W-9 |
| Non-US individual | W-8BEN |
| Non-US entity | W-8BEN-E |
| EU professional services | DAC7 Tax Questionnaire |

VAT/GST registration numbers required where applicable. As of April 1, 2025, AWS collects Japanese Consumption Tax (JCT) at 10% for products sold in Japan — sellers don't need to handle this separately.

---

## Bank Account Requirements

- Must accept USD disbursements
- US sellers: US bank account required (Hyperwallet virtual account available if no US bank)
- Non-US sellers: bank with SWIFT code, must be in an eligible jurisdiction
- Cannot use a personal account in a different name from the seller entity

---

## IAM Permissions for Publishing

The IAM user/role used for Marketplace operations needs:

```json
{
  "Effect": "Allow",
  "Action": [
    "aws-marketplace:*",
    "aws-marketplace-management:*",
    "marketplace-catalog:*",
    "ecr:CreateRepository",
    "ecr:BatchCheckLayerAvailability",
    "ecr:GetAuthorizationToken",
    "ecr:InitiateLayerUpload",
    "ecr:UploadLayerPart",
    "ecr:CompleteLayerUpload",
    "ecr:PutImage",
    "ecr:DescribeRepositories"
  ],
  "Resource": "*"
}
```

For the Marketplace ECR (`709825985650`), authenticate as:
```bash
aws ecr get-login-password --region us-east-1 | \
  docker login --username AWS --password-stdin \
  709825985650.dkr.ecr.us-east-1.amazonaws.com
```

---

## After Registration

Once registered:
- You get a **seller ID** (visible in Management Portal profile)
- Your seller prefix is auto-assigned for ECR repos (e.g., `your-company/`)
- You can create products immediately — even before bank verification completes
- Paid listings cannot go Public until registration is fully complete
