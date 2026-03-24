# AWS Marketplace Product Architecture Patterns

## When to read this doc

Read this when designing a new product for Marketplace, choosing a deployment model, or structuring a multi-service application for CloudFormation delivery.

---

## The fundamental constraint: you're designing for buyer accounts

When you design for Marketplace, your product deploys into **the buyer's AWS account** — not yours. This changes almost every architectural decision:

- You cannot assume any pre-existing infrastructure (no shared VPC, no existing DB, no existing IAM setup)
- The buyer controls the AWS account, IAM, and networking — your product must work within their constraints
- Your product must provision all its own resources via CloudFormation
- The buyer must be able to delete the stack cleanly without orphaned resources
- You must not require the buyer to contact you during or after deployment
- Deployment must complete in a reasonable time (target: under 15 minutes)

---

## Deployment model decision tree

```
Does your product require Kubernetes-native features?
(operators, CRDs, multi-tenancy via namespaces, Helm delivery)
├── Yes → EKS
│         └── Note: EKS add-on requires AMD64+ARM64 support,
│               more complex IAM (IRSA), longer review process
└── No  → Does your product need GPU instances?
          ├── Yes → EC2 (ECS with EC2 launch type, GPU-enabled instances)
          └── No  → ECS Fargate (recommended default)
                    └── Serverless containers, no instance management,
                          scales to zero, easiest for buyers to operate
```

### ECS Fargate (recommended for most products)

**Best for**: API services, web UIs, background workers, scheduled tasks

Pros:
- No EC2 instances for buyer to manage or patch
- Scales to zero (pay only when running)
- Simpler IAM (task role only, no node role)
- Fastest CloudFormation deployment
- Simplest metering integration (ECS Task Role → `MeterUsage`)

Cons:
- Higher per-vCPU cost than EC2 at sustained load
- Max 4 vCPU / 30 GB RAM per task (use multiple tasks for larger workloads)
- No GPU support

### ECS on EC2

**Best for**: GPU workloads, very high sustained CPU/memory, custom OS requirements

Additional complexity: buyer's stack includes EC2 Auto Scaling Group, launch template, ECS AMI SSM parameter. More surface area for things to go wrong.

### EKS

**Best for**: Products already packaged as Helm charts, multi-tenant SaaS with namespace isolation, products with Kubernetes operators

Additional complexity: cluster creation (or buyer provides existing cluster), IRSA setup, Helm delivery option (stricter image validation rules). Review process is longer. Consider only if you have a strong reason.

---

## Reference architecture: multi-service ECS Fargate product

This is the standard pattern for a product with API + worker + database + cache.

```
                        Internet
                            │
                            ▼
               ┌─── Application Load Balancer ───┐
               │     (Public Subnets, AZ-a/AZ-b) │
               └─────────────┬───────────────────┘
                             │ HTTPS (443)
               ┌─────────────▼───────────────────┐
               │       ECS Cluster               │
               │   ┌──────────────────────┐      │
               │   │  API Service (Fargate)│      │
               │   │  - Task Role (IAM)    │      │
               │   │  - MeterUsage call    │      │
               │   └──────────┬───────────┘      │
               │              │ internal          │
               │   ┌──────────▼───────────┐      │
               │   │  Worker Service      │      │
               │   │  (Fargate)           │      │
               │   └──────────────────────┘      │
               │   (Private Subnets, AZ-a/AZ-b)  │
               └─────────────────────────────────┘
                             │
               ┌─────────────┼─────────────────┐
               │             │                  │
               ▼             ▼                  ▼
         ┌─── RDS ───┐  ┌─ElastiCache─┐  ┌─Secrets─┐
         │  Postgres  │  │    Redis    │  │ Manager │
         │  Multi-AZ  │  │  (optional) │  └─────────┘
         └────────────┘  └─────────────┘

External calls from ECS Tasks:
  → Marketplace ECR (image pull, via NAT or VPC endpoint)
  → Marketplace Metering API (MeterUsage, via NAT or VPC endpoint)
  → Secrets Manager (secret fetch at startup)
  → CloudWatch Logs (log streaming)
```

### CloudFormation resource map for this pattern

| Resource | Type | Notes |
|---|---|---|
| ALB | `AWS::ElasticLoadBalancingV2::LoadBalancer` | Internet-facing, public subnets |
| ALB Listener | `AWS::ElasticLoadBalancingV2::Listener` | HTTPS on 443 with ACM cert, or HTTP on 80 |
| ALB Target Group | `AWS::ElasticLoadBalancingV2::TargetGroup` | Points to ECS service, health check path |
| ECS Cluster | `AWS::ECS::Cluster` | Shared cluster, no instance management |
| API Task Definition | `AWS::ECS::TaskDefinition` | Fargate, task role, container defs, secrets |
| API Service | `AWS::ECS::Service` | Desired count, VPC subnets, SG, target group |
| Worker Task Definition | `AWS::ECS::TaskDefinition` | Fargate, same task role or separate |
| Worker Service | `AWS::ECS::Service` | Private subnets, no ALB |
| ECS Task Role | `AWS::IAM::Role` | `MeterUsage`, Secrets Manager access |
| ECS Task Execution Role | `AWS::IAM::Role` | ECR pull, CloudWatch Logs |
| App Security Group | `AWS::EC2::SecurityGroup` | ECS tasks — inbound from ALB SG only |
| ALB Security Group | `AWS::EC2::SecurityGroup` | Inbound HTTPS/HTTP from internet |
| DB Security Group | `AWS::EC2::SecurityGroup` | Inbound on DB port from App SG only |
| RDS DB Instance | `AWS::RDS::DBInstance` | Multi-AZ, private subnets |
| RDS Subnet Group | `AWS::RDS::DBSubnetGroup` | Private subnets, 2+ AZs |
| Secrets | `AWS::SecretsManager::Secret` | DB password, app secrets |
| Log Groups | `AWS::Logs::LogGroup` | One per service, set retention |
| CloudMap (optional) | `AWS::ServiceDiscovery::*` | For service-to-service discovery |

---

## Accepting vs creating networking infrastructure

**Do not create a VPC.** Enterprise buyers have strict networking controls and will reject products that create new VPCs. Accept the buyer's existing VPC as parameters.

**Pattern: accept existing VPC/subnets as parameters**

```yaml
Parameters:
  VpcId:
    Type: AWS::EC2::VPC::Id

  PublicSubnetIds:
    Type: List<AWS::EC2::Subnet::Id>
    Description: "Public subnets for ALB (minimum 2 AZs, outbound internet access)"

  PrivateSubnetIds:
    Type: List<AWS::EC2::Subnet::Id>
    Description: "Private subnets for ECS tasks and RDS (minimum 2 AZs)"
```

**What the buyer must provide** (document this clearly in usage instructions):
- VPC with at least 2 public subnets and 2 private subnets
- Private subnets with outbound internet access (NAT Gateway) OR the `UseVpcEndpoints: true` parameter set
- If using HTTPS: an ACM certificate in the same region

---

## Multi-AZ requirements

Every production-grade Marketplace product should span at least 2 availability zones:

- ALB: deploy to 2+ public subnets across different AZs
- ECS services: place tasks across 2+ private subnets
- RDS: enable Multi-AZ (`MultiAZ: true` in the CF resource)
- ElastiCache: use a replication group with at least 2 nodes

Single-AZ products will be questioned during review and give enterprise buyers pause. The cost difference is modest; the reliability signal is significant.

---

## Security group design

Least-privilege security group chains are required by both Marketplace policy and cfn-nag:

```
Internet → ALB SG (80/443 open)
         → App SG (only from ALB SG)
         → DB SG (only from App SG on DB port)
         → Cache SG (only from App SG on cache port)
```

Never allow `0.0.0.0/0` on any non-80/443 port. Database and cache ports must only allow traffic from the application security group — never from a CIDR range the buyer inputs.

---

## Database sizing guidance for CloudFormation parameters

Give buyers a sensible set of choices rather than a free-text instance type:

```yaml
DBInstanceClass:
  Type: String
  Default: db.t3.medium
  AllowedValues:
    - db.t3.medium
    - db.t3.large
    - db.r6g.large
    - db.r6g.xlarge
    - db.r6g.2xlarge
  Description: >
    RDS instance size. t3.medium is sufficient for evaluation and small teams (<25 users).
    r6g.large recommended for production (25-100 users). r6g.xlarge for 100+ users.
```

Document the sizing guidance in the parameter description — buyers will follow it.

---

## What enterprise buyers expect architecturally

Enterprise buyers (Fortune 1000, financial services, healthcare) evaluate Marketplace products against internal architecture review checklists. Designing for these expectations avoids objections during their procurement process:

| Expectation | How to meet it |
|---|---|
| No new VPC created | Accept existing VPC as required parameter |
| Encryption at rest | RDS: `StorageEncrypted: true`; Secrets Manager by default |
| Encryption in transit | HTTPS on ALB; `ssl_mode=require` in DB connection |
| No public DB endpoints | RDS in private subnets only, no public accessibility |
| CloudTrail-compatible | IAM roles and policies with specific actions (not wildcards) |
| No hardcoded credentials | All secrets via Secrets Manager; `NoEcho` on all parameters |
| Deletable without orphans | DeletionPolicy, log group retention, no S3 buckets with data left behind |
| Configurable log retention | `LogRetentionDays` parameter, not hardcoded |
| Support for existing IAM boundaries | Do not create `AdministratorAccess` or `PowerUserAccess` roles |

---

## Stateless container design

ECS Fargate tasks must be stateless — all state in RDS/Redis/S3. This matters for Marketplace because:

- Buyers may scale ECS tasks up/down via parameters
- AWS can restart Fargate tasks without notice
- Marketplace review looks for EFS mounts or local state as a red flag

Rules:
- No local file writes to container filesystem for persistent data
- Session state in Redis or the database, not in-process
- Uploaded files go to S3, not local disk
- Configuration from Secrets Manager or environment variables, not config files baked into the image

---

## Deployment time budgeting

Target: stack CREATE_COMPLETE in under 15 minutes. Buyers expect this; longer creates imply complexity.

| Resource | Typical provision time |
|---|---|
| Security groups, IAM roles | ~30 seconds |
| RDS Multi-AZ instance | 5-8 minutes (longest resource) |
| ECS cluster | ~30 seconds |
| ECS service (tasks start) | 1-3 minutes |
| ALB + target group | ~1 minute |
| Secrets Manager secrets | ~10 seconds |

RDS is almost always the limiting factor. For faster deployments in evaluation tiers, offer a `db.t3.micro` option or an Aurora Serverless v2 option that scales to zero.
