# AWS Marketplace CloudFormation Guide

## When to read this doc

Read this when working on the CloudFormation template that customers use to deploy the product from Marketplace, or when preparing for Marketplace technical review.

---

## Marketplace-Specific CF Requirements

### Required metadata block

Organize parameters with `AWS::CloudFormation::Interface` — this controls what customers see in the CF console:

```yaml
Metadata:
  AWS::CloudFormation::Interface:
    ParameterGroups:
      - Label:
          default: "Container Images"
        Parameters:
          - ApiImageUri
          - WorkerImageUri
      - Label:
          default: "Database Configuration"
        Parameters:
          - DBInstanceClass
          - DBPassword
      - Label:
          default: "Network Configuration"
        Parameters:
          - VpcId
          - PrivateSubnetIds
          - PublicSubnetIds
    ParameterLabels:
      ApiImageUri:
        default: "API Service Image URI"
      DBPassword:
        default: "Database Password (stored in Secrets Manager)"
      VpcId:
        default: "VPC ID (existing VPC to deploy into)"
```

### Sensitive parameters must use NoEcho

```yaml
Parameters:
  DBPassword:
    Type: String
    NoEcho: true
    MinLength: 16
    MaxLength: 128
    AllowedPattern: "^[a-zA-Z0-9!#$%^&*()_+=<>?-]+$"
    ConstraintDescription: >
      16-128 characters. Letters, numbers, and !#$%^&*()_+=<>?- only.
      Excludes /@\"' which cause issues in connection strings and shell quoting.
    Description: "Database master password. Stored in Secrets Manager after stack creation."
```

**Critical**: The `AllowedPattern` must exclude characters that break connection strings and shell interpolation. Common problem characters:
- `/` — breaks URI paths
- `@` — breaks `user@host` connection string format
- `"` and `'` — break shell quoting
- `\` — escape sequences in YAML and JSON
- `` ` `` — shell command substitution

If using `aws secretsmanager get-secret-value` with `--secret-string` for auto-generated passwords, use `ExcludePunctuation` or an explicit `ExcludeCharacters` list:

```yaml
DBPasswordSecret:
  Type: AWS::SecretsManager::Secret
  Properties:
    GenerateSecretString:
      SecretStringTemplate: '{"username": "dbadmin"}'
      GenerateStringKey: "password"
      PasswordLength: 32
      ExcludeCharacters: '/@"'' \`'   # excludes / @ " ' space backslash backtick
```

---

## Networking and VPC Strategy

Customers deploy into their **existing VPC** — do not create a new VPC in the template unless absolutely necessary. Most enterprise customers have strict network controls and will refuse a product that creates its own VPC.

### Accept existing VPC as parameters

```yaml
Parameters:
  VpcId:
    Type: AWS::EC2::VPC::Id
    Description: "Existing VPC to deploy into"

  PrivateSubnetIds:
    Type: List<AWS::EC2::Subnet::Id>
    Description: "Private subnets for application services (ECS tasks, RDS). Minimum 2 AZs."

  PublicSubnetIds:
    Type: List<AWS::EC2::Subnet::Id>
    Description: "Public subnets for load balancer. Minimum 2 AZs."
```

### Outbound connectivity: VPC endpoints vs NAT Gateway

Containers need outbound internet access for:
- Pulling from Marketplace ECR (`709825985650`)
- Calling the Marketplace Metering API (`marketplace.metering.region.amazonaws.com`)
- Calling Secrets Manager, CloudWatch Logs, etc.

**Option A: NAT Gateway (simpler, costs money)**

Containers in private subnets route outbound traffic via NAT Gateway. The customer is responsible for providing subnets with NAT access. Document this requirement clearly:

```yaml
Parameters:
  PrivateSubnetIds:
    Description: >
      Private subnets with outbound internet access via NAT Gateway or equivalent.
      Required for ECR image pulls and AWS API calls.
```

**Option B: VPC Endpoints (no NAT required, more complex)**

Use Interface Endpoints for AWS services — eliminates NAT costs and keeps traffic on AWS network:

```yaml
# Required VPC endpoints for fully private deployment
ECRApiEndpoint:
  Type: AWS::EC2::VPCEndpoint
  Properties:
    ServiceName: !Sub "com.amazonaws.${AWS::Region}.ecr.api"
    VpcEndpointType: Interface
    VpcId: !Ref VpcId
    SubnetIds: !Ref PrivateSubnetIds
    SecurityGroupIds: [!Ref VpcEndpointSecurityGroup]
    PrivateDnsEnabled: true

ECRDockerEndpoint:
  Type: AWS::EC2::VPCEndpoint
  Properties:
    ServiceName: !Sub "com.amazonaws.${AWS::Region}.ecr.dkr"
    VpcEndpointType: Interface
    VpcId: !Ref VpcId
    SubnetIds: !Ref PrivateSubnetIds
    SecurityGroupIds: [!Ref VpcEndpointSecurityGroup]
    PrivateDnsEnabled: true

SecretsManagerEndpoint:
  Type: AWS::EC2::VPCEndpoint
  Properties:
    ServiceName: !Sub "com.amazonaws.${AWS::Region}.secretsmanager"
    VpcEndpointType: Interface
    VpcId: !Ref VpcId
    SubnetIds: !Ref PrivateSubnetIds
    SecurityGroupIds: [!Ref VpcEndpointSecurityGroup]
    PrivateDnsEnabled: true

MarketplaceMeteringEndpoint:
  Type: AWS::EC2::VPCEndpoint
  Properties:
    ServiceName: !Sub "com.amazonaws.${AWS::Region}.metering.marketplace"
    VpcEndpointType: Interface
    VpcId: !Ref VpcId
    SubnetIds: !Ref PrivateSubnetIds
    SecurityGroupIds: [!Ref VpcEndpointSecurityGroup]
    PrivateDnsEnabled: true

# S3 Gateway endpoint (free — always add this)
S3GatewayEndpoint:
  Type: AWS::EC2::VPCEndpoint
  Properties:
    ServiceName: !Sub "com.amazonaws.${AWS::Region}.s3"
    VpcEndpointType: Gateway
    VpcId: !Ref VpcId
    RouteTableIds: [!Ref PrivateRouteTableId]
```

**Interface endpoint pricing**: ~$0.01/hour per endpoint per AZ. For 4 endpoints × 2 AZs = ~$58/month. Compare to NAT Gateway (~$32/month + data transfer). VPC endpoints win for high-volume deployments; NAT wins for simplicity.

**Recommendation**: Offer both via a parameter:

```yaml
Parameters:
  UseVpcEndpoints:
    Type: String
    AllowedValues: ["true", "false"]
    Default: "false"
    Description: >
      Create VPC endpoints for AWS services (ECR, Secrets Manager, Marketplace Metering).
      Set true for private subnets without NAT Gateway access.
      Set false if your subnets have outbound internet access via NAT.

Conditions:
  CreateVpcEndpoints: !Equals [!Ref UseVpcEndpoints, "true"]

ECRApiEndpoint:
  Type: AWS::EC2::VPCEndpoint
  Condition: CreateVpcEndpoints
  ...
```

---

## Security Validation (Marketplace will reject templates that fail these)

AWS performs automated security scanning on submitted templates. These are hard blocks:

### Network security

```yaml
# BAD — will be rejected
IngressRule:
  Type: AWS::EC2::SecurityGroupIngress
  Properties:
    CidrIp: "0.0.0.0/0"
    FromPort: 22       # SSH
    ToPort: 22
    IpProtocol: tcp

# ALSO REJECTED: port 3389 (RDP), 5432 (Postgres), 3306 (MySQL) to 0.0.0.0/0

# GOOD — require explicit CIDR, no default
Parameters:
  AllowedSSHCidr:
    Type: String
    Default: ""
    AllowedPattern: "^(\\d{1,3}\\.\\d{1,3}\\.\\d{1,3}\\.\\d{1,3}/\\d{1,2})?$"
    Description: "CIDR for SSH access. Leave empty to disable SSH."
```

### IAM permissions

```yaml
# BAD — wildcard actions
- Effect: Allow
  Action: "s3:*"
  Resource: "*"

# GOOD — specific, scoped permissions
- Effect: Allow
  Action:
    - s3:GetObject
    - s3:PutObject
  Resource: !Sub "arn:aws:s3:::${BucketName}/*"
```

### No default plaintext passwords

```yaml
# BAD — will be rejected
Parameters:
  DBPassword:
    Default: "admin123"

# GOOD — no default, NoEcho, pattern constraint
Parameters:
  DBPassword:
    Type: String
    NoEcho: true
    AllowedPattern: "^[a-zA-Z0-9!#$%^&*()_+=<>?-]{16,128}$"
    # No Default
```

### No community or third-party AMIs

Use AWS-managed AMIs via SSM Parameter Store:

```yaml
Parameters:
  LatestECSOptimizedAMI:
    Type: AWS::SSM::Parameter::Value<AWS::EC2::Image::Id>
    Default: /aws/service/ecs/optimized-ami/amazon-linux-2023/recommended/image_id
```

---

## Container Image Parameters

For container products, image URIs are passed as parameters with defaults pointing to Marketplace ECR (`709825985650`):

```yaml
Parameters:
  ApiImageUri:
    Type: String
    Default: "709825985650.dkr.ecr.us-east-1.amazonaws.com/<seller-prefix>/product-api:v1.2.0"
    Description: "API service container image URI from AWS Marketplace ECR"

  WorkerImageUri:
    Type: String
    Default: "709825985650.dkr.ecr.us-east-1.amazonaws.com/<seller-prefix>/product-worker:v1.2.0"
    Description: "Worker service container image URI from AWS Marketplace ECR"
```

Replace `<seller-prefix>` with your seller prefix from the Management Portal. `709825985650` is AWS's account — the same for all sellers.

---

## ECS Task Role for Metering

```yaml
ECSTaskRole:
  Type: AWS::IAM::Role
  Properties:
    AssumeRolePolicyDocument:
      Version: "2012-10-17"
      Statement:
        - Effect: Allow
          Principal:
            Service: ecs-tasks.amazonaws.com
          Action: sts:AssumeRole
    Policies:
      - PolicyName: MarketplaceMetering
        PolicyDocument:
          Version: "2012-10-17"
          Statement:
            - Effect: Allow
              Action: aws-marketplace:MeterUsage
              Resource: "*"
      - PolicyName: SecretsAccess
        PolicyDocument:
          Version: "2012-10-17"
          Statement:
            - Effect: Allow
              Action:
                - secretsmanager:GetSecretValue
              Resource: !Ref AppSecrets
```

---

## Secrets Management Pattern

Store sensitive configuration in Secrets Manager — never pass plaintext values into container env vars:

```yaml
AppSecrets:
  Type: AWS::SecretsManager::Secret
  Properties:
    Description: "Application secrets"
    SecretString: !Sub |
      {
        "DB_PASSWORD": "${DBPassword}",
        "AUTH_SECRET_KEY": "${AuthSecretKey}"
      }

# Reference in ECS task definition — values are injected at container start
TaskDefinition:
  Type: AWS::ECS::TaskDefinition
  Properties:
    ContainerDefinitions:
      - Name: api
        Secrets:
          - Name: DB_PASSWORD
            ValueFrom: !Sub "${AppSecrets}:DB_PASSWORD::"
          - Name: AUTH_SECRET_KEY
            ValueFrom: !Sub "${AppSecrets}:AUTH_SECRET_KEY::"
```

---

## Template Linting and Static Analysis

Run these tools locally and in CI before submitting to Marketplace. They catch issues before AWS's scanner does.

### cfn-lint (CloudFormation Linter)

Validates syntax, resource properties, and common misconfigurations:

```bash
pip install cfn-lint
cfn-lint template.yaml

# Strict mode — fails on warnings too
cfn-lint template.yaml --include-checks W
```

### cfn-nag

Security-focused static analysis. Flags the same issues Marketplace scanning catches:

```bash
gem install cfn-nag
cfn_nag_scan --input-path template.yaml

# Exit 1 on any WARN or FAIL (good for CI gate)
cfn_nag_scan --input-path template.yaml --fail-on-warnings
```

Common cfn-nag rules relevant to Marketplace:

| Rule | Issue |
|---|---|
| `W9` | Security group allows all inbound traffic (`0.0.0.0/0`) |
| `W2` | Security group ingress on non-443/80 port allows 0.0.0.0/0 |
| `W5` | Security group egress allows 0.0.0.0/0 (warning, not fail) |
| `F1000` | Missing egress rule on security group |
| `W11` | IAM policy allows `*` on Resource |
| `W12` | IAM policy uses `Action: *` |
| `W28` | Resource has explicit name (prevents replacement on stack update) |
| `W35` | S3 bucket without access logging |
| `W68` | CloudWatch Log group without retention policy |

### TaskCat (multi-region deployment testing)

```bash
pip install taskcat
taskcat test run
```

Configure `.taskcat.yml`:

```yaml
project:
  name: my-marketplace-product
  regions:
    - us-east-1
    - us-west-2
    - eu-west-1
tests:
  default:
    template: template.yaml
    parameters:
      VpcId: $[taskcat_genval_vpc]
      PrivateSubnetIds: $[taskcat_genval_subnets]
```

### Recommended CI pipeline order

```
Build images → Trivy scan images → cfn-lint → cfn-nag → Deploy to test account →
Integration tests → Push to Marketplace ECR → AddDeliveryOptions
```

Do not skip cfn-nag before submitting. Marketplace's own scanner will catch the same issues and return them as opaque `INVALID_INPUT` errors, forcing a resubmission cycle.

---

## Nested Stack Parameters (if using nested stacks)

If your product uses S3-hosted nested templates, these parameter names are **reserved and required**:

```yaml
Parameters:
  MPS3BucketName:
    Type: String
    Description: "S3 bucket with nested templates (populated by Marketplace)"
  MPS3BucketRegion:
    Type: String
    Description: "Region of S3 bucket (populated by Marketplace)"
  MPS3KeyPrefix:
    Type: String
    Description: "S3 key prefix (populated by Marketplace)"

Resources:
  NestedStack:
    Type: AWS::CloudFormation::Stack
    Properties:
      TemplateURL: !Sub >
        https://${MPS3BucketName}.s3.${MPS3BucketRegion}.${AWS::URLSuffix}/${MPS3KeyPrefix}nested.yaml
```

---

## Outputs Section

Always include outputs — customers need to know the endpoint after deployment:

```yaml
Outputs:
  ServiceURL:
    Description: "URL for the service"
    Value: !Sub "https://${ApplicationLoadBalancer.DNSName}"
    Export:
      Name: !Sub "${AWS::StackName}-ServiceURL"
```

---

## Architecture Diagram Requirements

AWS requires an architecture diagram in the product listing:

- Dimensions: exactly **1100 × 700 pixels**
- Format: PNG or SVG
- Must use current [AWS Architecture Icons](https://aws.amazon.com/architecture/icons/)
- Must show: all VPCs, subnets, networks, integration points, services deployed
- Upload URL via `UpdateInformation` on the product entity (or via portal)

---

## Testing Checklist Before Submission

### Static analysis
- [ ] `cfn-lint template.yaml` — zero errors
- [ ] `cfn_nag_scan --input-path template.yaml --fail-on-warnings` — zero failures
- [ ] All sensitive parameters have `NoEcho: true` and `AllowedPattern` excluding `/`, `@`, `"`, `'`

### Deployment testing
- [ ] Template deploys successfully in `us-east-1` (required for AWS ops validation)
- [ ] Template deploys in at least 2 additional target regions
- [ ] VPC endpoint path tested (if `UseVpcEndpoints: true` option provided)
- [ ] Stack creates in under 15 minutes
- [ ] Stack deletes cleanly (no orphaned resources — check for retained Secrets, S3 buckets, log groups)

### Security
- [ ] No SSH/RDP/DB ports open to `0.0.0.0/0`
- [ ] IAM policies use specific actions, not wildcards
- [ ] ECS task role has `aws-marketplace:MeterUsage` permission
- [ ] Secrets stored in Secrets Manager, not passed as plaintext env vars
- [ ] `aws cloudformation describe-stacks` does not expose NoEcho values

### Metering
- [ ] Container startup validates metering (DryRun call) and terminates on non-throttle failure
- [ ] Metering tested in us-east-1 with a real running container

### Outputs
- [ ] Outputs section includes service URL

---

## Linking Template to Delivery Option

After `AddDeliveryOptions`, add the CF template URL via `UpdateDeliveryOptions`:

```json
{
  "ChangeType": "UpdateDeliveryOptions",
  "Entity": {
    "Type": "ContainerProduct@1.0",
    "Identifier": "<product-id>"
  },
  "Details": {
    "Version": {
      "VersionTitle": "v1.2.0",
      "ReleaseNotes": "..."
    },
    "DeliveryOptions": [
      {
        "Id": "<delivery-option-id>",
        "Details": {
          "EcrDeliveryOptionDetails": {
            "DeploymentResources": [
              {
                "Name": "CloudFormation Template",
                "Url": "https://s3.amazonaws.com/your-bucket/template.yaml"
              }
            ]
          }
        }
      }
    ]
  }
}
```

The template URL must be publicly accessible (S3 bucket with public read policy, or presigned URL with long expiry). Host in a stable, versioned S3 path — customers link to this URL from their own documentation.
