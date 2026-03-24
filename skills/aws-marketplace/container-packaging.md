# AWS Marketplace Container Packaging Guide

## When to read this doc

Read this when working on image preparation, ECR push workflows, metering integration, or image security requirements.

---

## ECR Registry Architecture

AWS Marketplace requires images in the **Marketplace-owned ECR**. Private ECR and ECR Public (`public.ecr.aws`) are both prohibited for paid products — AWS enforces subscription access control on the Marketplace registry.

The Marketplace ECR account ID is `709825985650` and the registry is `709825985650.dkr.ecr.us-east-1.amazonaws.com`. This is AWS's account, not yours — it is the same for all sellers.

### Two-registry pipeline (required pattern)

```
GitHub Actions / local build
        │
        ▼
Private ECR (your account)          ← build target, internal deployments
<your-account-id>.dkr.ecr.us-east-1.amazonaws.com/<product>-<service>:v1.2.0
        │
        │  docker pull → docker tag → docker push
        ▼
Marketplace ECR (AWS-owned)         ← what buyers pull, what the listing references
709825985650.dkr.ecr.us-east-1.amazonaws.com/<your-seller-prefix>/<product>-<service>:v1.2.0
                                    (709825985650 is AWS's account ID — same for all sellers)
```

Repos in the Marketplace ECR are created by AWS when you call `AddRepositories` — you cannot create them manually. They are named `<your-seller-prefix>/<RepositoryName>` where `RepositoryName` is the short name you supply (no prefix needed in the API call).

### Repository naming rules

- Lowercase with hyphens: `myproduct-api`, `myproduct-worker`
- Include a product-scoped prefix: `myproduct-<service>` (not just `api`)
- Short names only in `AddRepositories` — AWS auto-prepends your seller prefix
- Max 70 repositories per product
- **Permanent** — once registered to a product, cannot be moved or deleted

### Authenticate to Marketplace ECR

```bash
aws ecr get-login-password --region us-east-1 | \
  docker login --username AWS --password-stdin \
  709825985650.dkr.ecr.us-east-1.amazonaws.com
```

---

## Image Security Requirements

AWS scans images during submission (`AddDeliveryOptions` → `PREPARING` state, 20-45 min) and **continuously re-scans published listings**. Failures after publication cause email notification and potential listing suspension for new subscribers.

### Hard disqualifiers

- Any known CVE (Critical, High severity)
- Malware
- End-of-Life OS: Ubuntu 18.04, CentOS 7, RHEL 6/7, Debian 9 — use current LTS
- End-of-Life package versions (e.g. Python 3.8, Node 16)
- Hardcoded passwords, private keys, credentials, or secrets (even hashed)
- Running as root by default
- External image references in Helm templates not in `values.yaml`

### Required image hygiene

```dockerfile
# Run as non-root
RUN addgroup --system appuser && adduser --system --group appuser
USER appuser

# Use multi-stage builds to minimize attack surface
# Pin base image digests (sha256) for reproducible builds
# Remove package manager caches
RUN apt-get install -y ... && rm -rf /var/lib/apt/lists/*

# Do not include dev tools, shells (if avoidable), or test files
# No .env files, .git directories, or credential files in image layers
```

### Image tagging

- Use semantic version tags: `v1.2.0`, `1.2.0`
- `latest` tag is **prohibited** in Marketplace ECR
- Tags are permanent once referenced in a delivery option

### Helm chart additional requirements

- All image references in `values.yaml`, not hardcoded in templates
- Use standard templating: `{{ .Values.image.repository }}:{{ .Values.image.tag }}`
- Every image referenced by the Helm chart must be in a Marketplace ECR repo
- `INVALID_HELM_UNDECLARED_IMAGES` error if any image is not declared
- Helm 3.19.0+ required for AWS validation (`helm lint`, `helm template`)

---

## CI Pipeline Security Scanning

**Scan before you push to Marketplace ECR.** AWS will scan on submission and re-scan continuously. Finding a CVE after publication is far more disruptive than catching it in CI.

### Recommended tools

| Tool | What it catches | When to run |
|---|---|---|
| [Trivy](https://github.com/aquasecurity/trivy) | CVEs, secrets, misconfigurations, EoL packages | On every image build in CI |
| [Grype](https://github.com/anchore/grype) | CVEs (alternative to Trivy) | On every image build |
| [Syft](https://github.com/anchore/syft) | SBOM generation (required for some enterprise buyers) | On release builds |
| [Docker Scout](https://docs.docker.com/scout/) | CVEs + fix suggestions | Ad hoc during development |

### Trivy in GitHub Actions (recommended pattern)

```yaml
- name: Scan image for vulnerabilities
  uses: aquasecurity/trivy-action@master
  with:
    image-ref: ${{ env.IMAGE_URI }}
    format: sarif
    output: trivy-results.sarif
    severity: CRITICAL,HIGH
    exit-code: '1'        # fail the build on CRITICAL/HIGH

- name: Upload scan results
  uses: github/codeql-action/upload-sarif@v3
  if: always()
  with:
    sarif_file: trivy-results.sarif
```

### Scan output: what to do with findings

- **CRITICAL/HIGH CVEs** — block the build; must fix before pushing to Marketplace ECR
- **MEDIUM CVEs** — review; do not block build but track and fix in next release
- **LOW/NEGLIGIBLE** — log only; do not block
- **EoL OS/packages** — treat as HIGH; AWS will reject on these

### Review scan results before each Marketplace submission

Do not assume a clean scan from 2 weeks ago is still clean. Re-scan the exact image SHA you're about to push to Marketplace ECR:

```bash
# Scan by digest to confirm what you're actually submitting
trivy image --severity CRITICAL,HIGH \
  709825985650.dkr.ecr.us-east-1.amazonaws.com/<seller-prefix>/<repo>@sha256:<digest>
```

If AWS returns `SCAN_ERROR` on `AddDeliveryOptions`, the `DescribeChangeSet` response includes a URL (valid 60 days) with the full scan report. Review it before resubmitting.

---

## Metering Integration

### Critical: Container products use `MeterUsage`, NOT `BatchMeterUsage`

`BatchMeterUsage` is for **SaaS products** only. Container products call `MeterUsage`. This is the most common metering confusion point.

### MeterUsage API

```python
import boto3
import time

client = boto3.client('marketplace-metering', region_name=os.environ['AWS_REGION'])

response = client.meter_usage(
    ProductCode=os.environ['PRODUCT_CODE'],  # from Marketplace listing
    Timestamp=int(time.time()),
    UsageDimension='users',    # must match dimension Key configured in listing
    UsageQuantity=5,           # integer only
    DryRun=False,
    # Optional: cost allocation tags
    UsageAllocations=[
        {
            'AllocatedUsageQuantity': 5,
            'Tags': [{'Key': 'Department', 'Value': 'Engineering'}]
        }
    ]
)
```

### Metering rules

- One API call per dimension per hour maximum
- AWS recommends hourly calls; you can aggregate but not send more frequently
- Dimensions must match Keys configured in the product listing exactly
- Up to 24 pricing dimensions per product
- `DryRun=True` available for startup validation (does not bill buyer)

### Required startup validation pattern

AWS requires metering to succeed at container start. If metering fails at startup (non-throttle), the container must terminate.

```python
import boto3
import sys
from botocore.exceptions import ClientError

def validate_metering():
    client = boto3.client('marketplace-metering')
    try:
        client.meter_usage(
            ProductCode=os.environ['PRODUCT_CODE'],
            Timestamp=int(time.time()),
            UsageDimension='primary_dimension',
            UsageQuantity=0,
            DryRun=True,   # validation only, does not bill
        )
    except ClientError as e:
        code = e.response['Error']['Code']
        if code == 'ThrottlingException':
            # Retry on throttle — do NOT terminate
            time.sleep(60)
            return validate_metering()
        else:
            # Any other error: CustomerNotEntitledException, InvalidProductCodeException, etc.
            # Terminate the container — buyer is not entitled
            print(f"Metering validation failed: {code}", file=sys.stderr)
            sys.exit(1)
```

### IAM requirements for metering (by deployment platform)

| Platform | Required auth method |
|---|---|
| Amazon ECS | ECS Task IAM Role |
| Amazon EKS | IAM Roles for Service Accounts (IRSA) |
| EC2 | Instance IAM Role |

**Node roles, long-term access keys, and EKS Pod Identity are explicitly not supported** for metering. Your CloudFormation template must create the correct IAM role with metering permissions and attach it to the task/pod.

### Minimum IAM policy for metering

```json
{
  "Effect": "Allow",
  "Action": "aws-marketplace:MeterUsage",
  "Resource": "*"
}
```

### Metering validation (for listing approval)

AWS ops team validates metering before approving Public visibility. You must:
- Deploy and run your container in **us-east-1** at least once
- Show that `MeterUsage` is called and records are received
- Test every pricing dimension

---

## UsageAllocation (cost allocation tags)

Optional but recommended for enterprise buyers doing cost attribution:

- Max 5 tags per allocation record
- Max 2,500 allocations per `MeterUsage` call
- Sum of `AllocatedUsageQuantity` across allocations must equal `UsageQuantity`
- Tags appear in buyer's Cost Explorer

---

## Pricing Dimension Types

| Type | Usage |
|---|---|
| `Entitled` | Contract/subscription pricing (upfront purchase) |
| `Metered` | Usage-based pricing (billed per unit per hour) |

Dimension unit options: `Users`, `Hosts`, `GB`, `MB`, `TB`, `Gbps`, `Mbps`, `Requests`, `Units`, `UserHrs`, `UnitHrs`, `HostHrs`, `TierHrs`, `TaskHrs`

Dimension key rules:
- Pattern: `[A-Za-z0-9_.-]+`
- Max 100 characters
- **Permanent** after adding — keys cannot be renamed
