# AWS Marketplace Post-Launch Operations

## When to read this doc

Read this after a product is Public — managing subscribers, versioning, revenue, CVE re-scan failures, and support.

---

## Disbursement schedule

AWS Marketplace pays sellers **60 days after month-end** for the billing period in which revenue was recognized.

- January revenue → disbursed ~March 31
- Annual contract signed January 15 → full year's value recognized in January → payment ~March 31
- FPS installments follow the same schedule per `ChargeDate`

Track revenue and upcoming disbursements in the **AWS Marketplace Management Portal → Revenue Recognition** dashboard. The dashboard shows recognized revenue vs. disbursed vs. pending.

---

## Subscriber management

### Checking active entitlements

For contract products, use the Entitlement Service:

```python
import boto3

client = boto3.client('marketplace-entitlement', region_name='us-east-1')

response = client.get_entitlements(
    ProductCode=os.environ['PRODUCT_CODE'],
    Filter={
        'CUSTOMER_IDENTIFIER': [customer_identifier]
    }
)

for entitlement in response['Entitlements']:
    print(f"Dimension: {entitlement['Dimension']}")
    print(f"Value: {entitlement['Value']}")
    print(f"Expires: {entitlement['ExpirationDate']}")
```

`customer_identifier` comes from the `ResolveCustomer` call (SaaS) or from the SNS subscription notification. For container products, the ECS/EKS task identity is used — `MeterUsage` validates entitlement implicitly.

### SNS subscription notifications

AWS sends subscription lifecycle events to an SNS topic created per product. This is primarily relevant for **hourly-priced** container products and SaaS. For contract-only container products it is less critical but still useful for tracking subscriber churn.

**SNS topic**: Created automatically, named `aws-mp-subscription-notification-{PRODUCTCODE}`. The ARN is provided at product creation — if lost, contact AWS Seller Operations.

**Recommended setup**: Subscribe an SQS queue to the SNS topic (fanout pattern), then poll SQS in a background process.

**Message format**:
```json
{
  "action": "subscribe-success",
  "customer-identifier": "X01EXAMPLEX",
  "product-code": "n0123EXAMPLEXXXXXXXXXXXX",
  "offer-identifier": "offer-abcexample123"
}
```

**Action types**:

| Action | Meaning | What to do |
|---|---|---|
| `subscribe-success` | Customer subscribed | Provision access, send welcome |
| `subscribe-fail` | Subscription failed | Log, no action needed |
| `unsubscribe-pending` | Unsubscribe initiated (still active) | Warn customer, prepare offboarding |
| `unsubscribe-success` | Unsubscribe complete | Deprovision access |

Note: `offer-identifier` is only included in `subscribe-success` / `subscribe-fail` messages, and only for offers created January 2024 onward.

---

## Publishing a new version

Adding a new version to a Public product does **not** require re-submitting for AWS review. It does require a new image security scan (~20-45 minutes).

```
1. Push new images to Marketplace ECR with new version tag
2. AddDeliveryOptions with new VersionTitle and updated ContainerImages URIs
   └── Wait 20-45 minutes for PREPARING → SUCCEEDED
3. Old versions remain available to existing subscribers
4. New subscribers get the latest version by default
5. Optionally restrict old versions via RestrictDeliveryOptions
```

**Do not restrict old versions immediately** — existing subscribers may be pinned to a specific version. Give at least 30 days notice before restricting.

---

## Handling a CVE re-scan failure on a live listing

AWS continuously re-scans all published container images. When a published image fails:

1. AWS emails the seller at the registered support email
2. The product is suspended for **new** subscribers (existing subscribers retain access)
3. You have a window (typically 30 days per the email) to fix before broader action

**Response playbook**:
```
1. Identify which image/layer contains the CVE (AWS provides scan details)
2. Update the base image or package to a patched version
3. Rebuild and re-scan locally with Trivy before pushing:
      trivy image --severity CRITICAL,HIGH <new-image>
4. Push new image to Marketplace ECR with new version tag
5. Submit AddDeliveryOptions with the new image
6. Wait for PREPARING → SUCCEEDED (~20-45 min)
7. Reply to AWS's email confirming the new version was submitted
8. AWS will re-enable new subscriptions after validating the new version
```

**Do not ignore the email.** If unresolved, AWS can pull the listing entirely.

---

## Updating listing metadata on a live product

After a product is Public, metadata changes (description, screenshots, pricing) publish automatically without another full AWS review. However:

- **Price changes** are locked for 90 days after Public approval. To change pricing within the lock: open an AWS Marketplace Seller Operations support ticket (expect 5-7 days).
- **Adding new pricing dimensions** requires a support ticket — you cannot add dimensions to a live listing without AWS assistance.
- **Category/keyword changes** apply immediately after submitting `UpdateInformation`.
- **Logo and screenshots** update within a few hours.

---

## Support ticket escalation contacts

| Issue | Where to go |
|---|---|
| Listing/product issues (rejected submission, locked fields) | AWS Support → Service: AWS Marketplace → Category: Seller issues → Subcategory: Product/listing management |
| Billing and disbursement questions | AWS Support → Service: AWS Marketplace → Category: Seller issues → Subcategory: Billing and payments |
| CVE re-scan failure (live product) | Reply directly to the email from `no-reply@marketplace.aws` |
| ISV Accelerate / co-sell | Contact your Partner Development Representative (PDR) in Partner Central |
| Emergency (listing taken down, active subscriber impact) | Open Severity 1 case in AWS Support |

**First response SLA**: 5-7 business days for standard cases. Severity 1 gets faster response but requires documented customer impact. Follow up after 3 days if no response on standard cases.

---

## Deprecating old products or versions

When you have test products or outdated versions that should no longer be visible:

```bash
# Restrict an old delivery option version (stops new subscriptions to that version)
aws marketplace-catalog start-change-set \
  --catalog AWSMarketplace \
  --change-set '[{
    "ChangeType": "RestrictDeliveryOptions",
    "Entity": {"Type": "ContainerProduct@1.0", "Identifier": "<product-id>"},
    "DetailsDocument": {
      "DeliveryOptionIds": ["<delivery-option-id>"]
    }
  }]'

# Move a product to Restricted status (no new subscribers, existing keep access)
# Use UpdateVisibility change type with visibility: "Restricted"
```

**You cannot delete products.** Deprecated and restricted products remain in your seller account permanently. Name them clearly (e.g., `[DEPRECATED] My Product - Test`) so they're identifiable.

---

## Key metrics to track

In the AWS Marketplace Management Portal → Reports:

- **Subscriber count**: Active subscriptions by product
- **Revenue by month**: Billed amounts before disbursement
- **Disbursement report**: What has been paid out
- **Usage report**: Metering calls by dimension (for usage-based products)
- **Subscriber churn**: `unsubscribe-success` events vs new `subscribe-success` events

Reports are available as downloadable CSVs. There is no real-time API for subscriber metrics — download is the only mechanism.
