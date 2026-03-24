# AWS Marketplace Product Audit Runbook

## When to read this doc

Read this when reviewing an existing product before Marketplace submission, after receiving an `Action Required` status, or as a pre-submission gate in CI.

---

## Runbook overview

Run these checks in order. Each section can be run independently. Every check has a clear pass/fail condition and a fix instruction.

---

## Phase 1: Image audit (run before pushing to Marketplace ECR)

### 1.1 — CVE scan

```bash
# Scan for CRITICAL and HIGH CVEs
trivy image --severity CRITICAL,HIGH --exit-code 1 <image-uri>
```

**Pass**: exit code 0, zero CRITICAL/HIGH findings
**Fail**: any CRITICAL or HIGH CVE

Fix: update the base image to the latest patch release. For package-level CVEs, update the specific package in your Dockerfile. Re-run until clean.

```bash
# Check which packages are EoL
trivy image --scanners vuln --severity CRITICAL,HIGH,MEDIUM \
  --format json <image-uri> | jq '.Results[].Vulnerabilities[]? | select(.Status == "end_of_life")'
```

### 1.2 — Root user check

```bash
# Extract the USER from the final stage of your Dockerfile
docker inspect <image-uri> --format '{{.Config.User}}'
```

**Pass**: any non-empty, non-root value (e.g. `appuser`, `1000`, `nobody`)
**Fail**: empty string or `root` or `0`

Fix: add to Dockerfile final stage:
```dockerfile
RUN addgroup --system appuser && adduser --system --ingroup appuser appuser
USER appuser
```

### 1.3 — No secrets in image layers

```bash
# Scan for hardcoded secrets
trivy image --scanners secret <image-uri>

# Also check with gitleaks if available
docker save <image-uri> | tar -x -O | gitleaks detect --source /dev/stdin
```

**Pass**: zero secret findings
**Fail**: any API key, password, private key, or credential found in any layer

Fix: never copy `.env`, credential files, or SSH keys into the image. Use multi-stage builds and confirm the secret is not in any intermediate layer.

### 1.4 — Registry check

```bash
# Confirm all image references in your compose/task defs point to Marketplace ECR
grep -r "709825985650" docker-compose.yml infrastructure/ .github/
```

**Pass**: all image URIs contain `709825985650.dkr.ecr.us-east-1.amazonaws.com`
**Fail**: any image URI pointing to Docker Hub, ECR Public, private ECR, or Quay

Fix: update all image URIs to the Marketplace ECR path. For Helm charts, ensure all image references are in `values.yaml` using template variables.

### 1.5 — Image tag check

```bash
# Confirm no "latest" tags are used
docker inspect <image-uri> | jq '.[].RepoTags[]' | grep "latest"
```

**Pass**: no `latest` tags
**Fail**: any image tagged `latest`

Fix: use semantic version tags only: `v1.2.0` or `1.2.0`.

---

## Phase 2: CloudFormation template audit

### 2.1 — cfn-lint

```bash
pip install cfn-lint
cfn-lint template.yaml
```

**Pass**: zero errors (E-prefixed findings)
**Fail**: any E-prefixed error

Warnings (W-prefixed) are acceptable but should be reviewed. Fix all errors before continuing.

### 2.2 — cfn-nag security scan

```bash
gem install cfn-nag
cfn_nag_scan --input-path template.yaml --fail-on-warnings
```

**Pass**: zero FAIL and zero WARN findings
**Fail**: any FAIL or WARN

Critical rules for Marketplace:

| Rule | Issue | Fix |
|---|---|---|
| W9/W2 | Security group allows inbound from `0.0.0.0/0` on non-80/443 | Restrict to specific CIDR parameter or source SG |
| W11 | IAM policy `Resource: "*"` | Scope to specific resource ARN |
| W12 | IAM policy `Action: "*"` | List specific actions |
| F1000 | Missing egress rule | Add explicit egress rule |
| W35 | S3 bucket without access logging | Add logging config or suppress with justification |
| W68 | CloudWatch Log group without retention | Set `RetentionInDays` |

### 2.3 — Sensitive parameter checks

```bash
# Confirm all sensitive params have NoEcho
python3 -c "
import yaml, sys
t = yaml.safe_load(open('template.yaml'))
params = t.get('Parameters', {})
sensitive = ['password', 'secret', 'key', 'token', 'credential']
for name, props in params.items():
    if any(s in name.lower() for s in sensitive):
        if not props.get('NoEcho'):
            print(f'FAIL: {name} is missing NoEcho: true')
        if not props.get('AllowedPattern'):
            print(f'WARN: {name} has no AllowedPattern — check for dangerous characters')
"
```

**Pass**: all sensitive parameters have `NoEcho: true` and an `AllowedPattern`
**Fail**: any sensitive parameter missing `NoEcho`

Also confirm parameters exclude problem characters: `/`, `@`, `"`, `'`, `\` (break connection strings).

### 2.4 — Deploy test in us-east-1

```bash
# Deploy and confirm CREATE_COMPLETE
aws cloudformation create-stack \
  --stack-name marketplace-audit-test \
  --template-body file://template.yaml \
  --capabilities CAPABILITY_IAM \
  --parameters [your test params] \
  --region us-east-1

aws cloudformation wait stack-create-complete \
  --stack-name marketplace-audit-test \
  --region us-east-1

echo "Stack outputs:"
aws cloudformation describe-stacks \
  --stack-name marketplace-audit-test \
  --query 'Stacks[0].Outputs' \
  --region us-east-1
```

**Pass**: `CREATE_COMPLETE` in under 15 minutes, all expected Outputs present
**Fail**: `CREATE_FAILED`, `ROLLBACK_COMPLETE`, or stack takes >20 minutes

After verifying the stack works:
```bash
# Always clean up test stacks
aws cloudformation delete-stack --stack-name marketplace-audit-test --region us-east-1
aws cloudformation wait stack-delete-complete --stack-name marketplace-audit-test --region us-east-1
```

Confirm the delete leaves no orphaned resources (check S3 buckets, log groups, Secrets Manager secrets with `DeletionPolicy: Retain`).

### 2.5 — IAM role audit

```bash
# List all IAM roles and policies in the template
python3 -c "
import yaml
t = yaml.safe_load(open('template.yaml'))
for name, r in t.get('Resources', {}).items():
    if r['Type'] in ['AWS::IAM::Role', 'AWS::IAM::ManagedPolicy', 'AWS::IAM::Policy']:
        print(f'{name} ({r[\"Type\"]})')
        import json
        print(json.dumps(r.get('Properties', {}).get('Policies', r.get('Properties', {})), indent=2))
"
```

Review each policy for:
- No `Action: "*"` or `Action: "service:*"`
- No `Resource: "*"` except where unavoidable (`aws-marketplace:MeterUsage` requires `*`)
- ECS task role has `aws-marketplace:MeterUsage`
- ECS execution role has `ecr:GetAuthorizationToken`, `ecr:BatchGetImage`, `logs:CreateLogStream`, `logs:PutLogEvents`

---

## Phase 3: Metering integration audit

### 3.1 — MeterUsage call confirmed

Search the codebase for `MeterUsage`:
```bash
grep -r "MeterUsage\|meter_usage\|meterUsage" apps/ src/ --include="*.py" --include="*.js" --include="*.ts"
```

**Pass**: `MeterUsage` found in application code
**Fail**: not found, or `BatchMeterUsage` found (that's SaaS-only — wrong API)

### 3.2 — Startup validation present

Search for the DryRun startup pattern:
```bash
grep -r "DryRun.*True\|dry_run.*true\|dryRun.*true" apps/ src/ --include="*.py" --include="*.js" --include="*.ts"
```

**Pass**: DryRun call present at startup
**Fail**: no DryRun validation found

### 3.3 — Non-throttle termination

Search for the termination-on-failure pattern:
```bash
grep -r "ThrottlingException\|CustomerNotEntitled" apps/ src/ --include="*.py" --include="*.js" --include="*.ts"
```

**Pass**: code handles `ThrottlingException` with retry, and all other exceptions with `sys.exit(1)` or equivalent
**Fail**: no error handling on metering, or swallowing exceptions

### 3.4 — Dimension keys match listing

```bash
# Get current dimensions from the product entity
aws marketplace-catalog describe-entity \
  --catalog AWSMarketplace \
  --entity-id <product-id> \
  --query 'Details' | python3 -c "
import sys,json
d=json.loads(sys.stdin.read())
dims = json.loads(d).get('Dimensions', [])
print('Registered dimension keys:')
for dim in dims:
    print(f'  {dim[\"Key\"]} ({dim[\"Unit\"]})')
"
```

Compare the output against `UsageDimension` values in your application code. Every key used in `MeterUsage` calls must appear in the listing.

---

## Phase 4: Listing content audit

### 4.1 — Fetch current product entity

```bash
aws marketplace-catalog describe-entity \
  --catalog AWSMarketplace \
  --entity-id <product-id> \
  --query 'Details' | python3 -c "
import sys,json
d=json.loads(json.loads(sys.stdin.read()))
desc = d.get('Description', {})
print('Title:', desc.get('ProductTitle', 'MISSING'))
print('Short desc length:', len(desc.get('ShortDescription', '')))
print('Long desc length:', len(desc.get('LongDescription', '')))
print('Logo URL:', desc.get('LogoUrl', 'MISSING'))
print('Categories:', desc.get('Categories', 'MISSING'))
print('Highlights count:', len(desc.get('Highlights', [])))
print('Keywords:', desc.get('SearchKeywords', []))
"
```

### 4.2 — Content checklist

| Field | Required | Limit | Check |
|---|---|---|---|
| ProductTitle | ✅ | ≤72 chars, ASCII only | No em dashes, curly quotes, or special chars |
| ShortDescription | ✅ | ≤350 chars | Specific — not generic marketing |
| LongDescription | ✅ | ≤5,000 chars | Covers features, deployment, dependencies |
| LogoUrl | ✅ | 300×150px PNG | URL must be accessible |
| Categories | ✅ | 1-3 | Set at product level |
| Highlights | Recommended | ≤3 bullets | Specific and technical |
| SearchKeywords | Recommended | ≤15, ≤50 chars each | Relevant to the product |

**Title check** — catch problematic characters:
```python
import re
title = "Your Product Title Here"
if len(title) > 72:
    print(f"FAIL: title is {len(title)} chars (max 72)")
if re.search(r'[—""'']', title):
    print("FAIL: title contains Unicode punctuation — use ASCII only")
```

### 4.3 — Offer terms audit

```bash
# List offers for the product and check terms
aws marketplace-catalog list-entities \
  --catalog AWSMarketplace \
  --entity-type Offer \
  --filter-list '[{"Name": "ProductId", "ValueList": ["<product-id>"]}]'

# For each offer ID:
aws marketplace-catalog describe-entity \
  --catalog AWSMarketplace \
  --entity-id <offer-id> \
  --query 'Details' | python3 -c "
import sys,json
d=json.loads(json.loads(sys.stdin.read()))
terms = [t['Type'] for t in d.get('Terms', [])]
name = d.get('Name', 'MISSING')
state = d.get('State', 'MISSING')
print('Offer Name:', name)
print('State:', state)
print('Terms present:', terms)
required = ['ConfigurableUpfrontPricingTerm', 'LegalTerm', 'SupportTerm', 'RenewalTerm']
for r in required:
    status = '✅' if r in terms else '❌ MISSING'
    print(f'  {r}: {status}')
"
```

---

## Phase 5: End-to-end submission readiness

Run this final checklist manually before any Marketplace submission:

### Images
- [ ] Trivy scan: zero CRITICAL/HIGH CVEs on exact image SHA being submitted
- [ ] Container runs as non-root user (`docker inspect` confirms non-empty, non-root User)
- [ ] No secrets in image layers
- [ ] All images in Marketplace ECR (`709825985650`) with semantic version tags
- [ ] No `latest` tags

### CloudFormation
- [ ] `cfn-lint`: zero errors
- [ ] `cfn-nag --fail-on-warnings`: zero failures
- [ ] Deployed successfully in `us-east-1`
- [ ] Stack deletes cleanly (no orphaned resources)
- [ ] Stack creates in <15 minutes
- [ ] All sensitive parameters have `NoEcho: true` and `AllowedPattern`
- [ ] ECS task role has `aws-marketplace:MeterUsage` permission
- [ ] No SSH/RDP/DB ports open to `0.0.0.0/0`
- [ ] IAM policies use specific actions, not wildcards

### Metering
- [ ] `MeterUsage` used (not `BatchMeterUsage`)
- [ ] DryRun startup validation present
- [ ] Container terminates on non-`ThrottlingException` metering failure
- [ ] All dimension keys in code match listing exactly
- [ ] Metering tested with real running container in us-east-1

### Listing content
- [ ] Title: ≤72 chars, ASCII only
- [ ] Short description: specific, ≤350 chars
- [ ] Long description: complete, ≤5,000 chars
- [ ] Logo uploaded (300×150px PNG)
- [ ] Categories set (1-3)
- [ ] At least 1 screenshot (780×439px recommended)
- [ ] Architecture diagram: 1100×700px PNG with AWS icons
- [ ] Usage instructions: complete deployment path
- [ ] Offer: pricing terms, legal terms, support terms, renewal terms, name, description — all set

### Offer state
- [ ] `ReleaseProduct` and `ReleaseOffer` submitted in same changeset
- [ ] Product is in `Limited` state before attempting `AddDeliveryOptions`
- [ ] All changesets are in `SUCCEEDED` state (no `IN_PROGRESS` or `FAILED`)

---

## Interpreting `Action Required` from AWS

When AWS flags your submission, `DescribeChangeSet` gives the actual errors:

```bash
aws marketplace-catalog describe-change-set \
  --catalog AWSMarketplace \
  --change-set-id <id> \
  --output json | python3 -c "
import sys,json
d=json.load(sys.stdin)
print('Status:', d.get('Status'))
print('Failure code:', d.get('FailureCode', 'none'))
for cs in d.get('ChangeSet', []):
    errs = cs.get('ErrorDetailList', [])
    if errs:
        print(f'  {cs[\"ChangeType\"]}:')
        for e in errs:
            print(f'    [{e[\"ErrorCode\"]}] {e[\"ErrorMessage\"]}')
"
```

Fix **every item** in the error list before resubmitting. Partial fixes result in another `Action Required` round and reset the review clock.
