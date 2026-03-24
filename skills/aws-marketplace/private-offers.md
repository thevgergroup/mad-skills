# AWS Marketplace Private Offers

## When to read this doc

Read this when closing enterprise deals, creating custom pricing for specific buyers, or when a customer asks for a non-public contract.

---

## What private offers are

A private offer is a custom commercial agreement targeted at a specific AWS account (or small group of accounts). It overrides the public listing price and terms entirely — the buyer gets a dedicated URL and sees only what you put in the offer.

**Private offers are how most B2B SaaS revenue on Marketplace actually transacts.** The public listing sets a floor and enables discoverability; private offers close deals.

### Public listing vs private offer

| Aspect | Public listing | Private offer |
|---|---|---|
| Visibility | All AWS customers | Only targeted AWS account IDs |
| Pricing | Fixed, public | Fully negotiated |
| EULA | Standard Marketplace EULA | Can use a custom EULA |
| Contract duration | Standard terms | Negotiated (1 month to 5 years) |
| Payment schedule | Standard | Flexible installments (FPS) |
| Initiation | Buyer self-serves | Seller creates, buyer accepts |

---

## Creating a private offer (Catalog API)

Private offers use the same `Offer@1.0` entity type as public offers but are targeted to specific buyer accounts. The workflow is always seller-initiated — buyers cannot request a private offer from the portal.

### Required change types (in order)

```
1. CreateOffer            → creates offer in Draft state
2. UpdateInformation      → set Name and Description (Name: 1-150 chars, required)
3. UpdateTargeting        → designate specific buyer account IDs
4. UpdatePricingTerms     → set pricing model and dimension rates
5. UpdateLegalTerms       → set EULA (custom or Standard)
6. UpdateSupportTerms     → set refund policy
7. UpdateRenewalTerms     → set renewal behavior
8. UpdateValidityTerms    → set contract duration and offer expiry date
9. UpdateAvailability     → set AvailabilityEndDate (deadline for buyer to accept)
10. ReleaseOffer          → buyer can now see and accept the offer
```

### Step 3: UpdateTargeting (buyer account IDs)

```json
{
  "ChangeType": "UpdateTargeting",
  "Entity": { "Type": "Offer@1.0", "Identifier": "<offer-id>" },
  "DetailsDocument": {
    "PositiveTargeting": {
      "BuyerAccounts": ["123456789012", "098765432109"]
    }
  }
}
```

- Max 26 buyer accounts per private offer
- Each entry is a 12-digit AWS account ID (no dashes)
- The buyer must use the account that matches exactly

### Step 8: UpdateValidityTerms (contract duration)

```json
{
  "ChangeType": "UpdateValidityTerms",
  "Entity": { "Type": "Offer@1.0", "Identifier": "<offer-id>" },
  "DetailsDocument": {
    "Terms": [{
      "Type": "ValidityTerm",
      "AgreementDuration": "P12M"
    }]
  }
}
```

`AgreementDuration` uses ISO 8601 durations: `P1M`, `P3M`, `P6M`, `P12M`, `P24M`, `P36M`, `P60M` (up to 5 years for container contract products).

### Step 9: UpdateAvailability (offer acceptance deadline)

```json
{
  "ChangeType": "UpdateAvailability",
  "Entity": { "Type": "Offer@1.0", "Identifier": "<offer-id>" },
  "DetailsDocument": {
    "AvailabilityEndDate": "2024-03-31"
  }
}
```

This is the deadline by which the buyer must accept — not the contract end date. Set this to the end of your sales quarter or a negotiated date. After this date the offer expires and cannot be accepted.

---

## Flexible Payment Scheduler (FPS)

FPS lets you split the total contract value into installments. Useful for large deals where the buyer wants to spread payments across quarters or years.

### Supported product types

- Container contract products ✅
- Container hourly with long-term ✅
- AMI contract products ✅
- SaaS contract products ✅
- Container hourly-only products ✗ (not supported)

### Limits

- Max 60 installments
- Max contract duration: 5 years (container contracts), 3 years (container hourly with long-term)
- Frequency: monthly, quarterly, annual, or custom arbitrary dates
- Buyers are invoiced at 00:00 UTC on each `ChargeDate`

### UpdatePaymentScheduleTerms

```json
{
  "ChangeType": "UpdatePaymentScheduleTerms",
  "Entity": { "Type": "Offer@1.0", "Identifier": "<offer-id>" },
  "DetailsDocument": {
    "Terms": [{
      "Type": "PaymentScheduleTerm",
      "CurrencyCode": "USD",
      "Schedule": [
        { "ChargeDate": "2024-01-15", "ChargeAmount": "15000.00" },
        { "ChargeDate": "2024-07-15", "ChargeAmount": "15000.00" },
        { "ChargeDate": "2025-01-15", "ChargeAmount": "15000.00" }
      ]
    }]
  }
}
```

**Critical constraint**: `UpdatePaymentScheduleTerms` cannot be applied after `ReleaseOffer`. Once the offer is released, the payment schedule is locked. Create a new offer to change the schedule.

Also: only one `ChargeDate` may fall on or before the `AvailabilityEndDate`. If you set the acceptance deadline to March 31, no more than one installment can be due on or before that date.

---

## How buyers experience a private offer

1. Seller creates and releases the offer
2. Buyer logs into AWS Marketplace console → "Manage subscriptions" → "Private offers"
3. Buyer sees the offer with the negotiated terms and pricing
4. Buyer clicks "Accept" → AWS Marketplace processes the subscription
5. AWS sends `subscribe-success` SNS notification to the seller's topic (if configured)
6. The subscription appears in both seller and buyer revenue dashboards

There is no mechanism for buyers to request a private offer. The seller must initiate. AWS does not send the buyer an email notification when the offer is created — the seller should notify the buyer directly (send them the offer URL from the portal).

---

## Disbursement on private offers

AWS Marketplace disburses funds to sellers **60 days after month-end** for the billing period in which the transaction occurred. For FPS installments, each `ChargeDate` payment is disbursed 60 days after the end of that billing month.

Example: An installment due January 15 → billed in January → disbursed ~March 31.

---

## Amending vs. creating new offers

You **cannot amend a released private offer**. To change pricing, payment schedule, or terms:

1. Create a new offer (new `ChangeSetId`, new `OfferId`)
2. Target the same buyer account(s)
3. Set a new `AvailabilityEndDate`
4. Restrict or let the old offer expire

For this reason, finalize all terms before calling `ReleaseOffer`. Run `DescribeChangeSet` on every change before releasing to confirm the offer content is exactly right.
