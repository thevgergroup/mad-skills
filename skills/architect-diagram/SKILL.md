---
name: architect-diagram
description: Generate clean architecture diagrams from natural language or YAML specs. Supports AWS/GCP/Azure with VPC/AZ/subnet/ECS/K8s nesting, hybrid on-prem/cloud topologies, and proper cloud provider icons.
license: MIT
metadata:
  author: thevgergroup
  version: "1.0.0"
user-invocable: true
argument-hint: "[architecture description or yaml path]"
---

# Architecture Diagram Skill

## Overview

This skill generates clean cloud architecture diagrams from either natural language descriptions or YAML specs. It routes to the appropriate rendering engine based on diagram complexity:

- **D2 engine** (`src/generate_d2.py`) — for infrastructure diagrams with nested VPCs, AZs, subnets, ECS/EKS clusters, and hybrid on-prem/cloud topologies
- **Python diagrams engine** (`src/generate_diagram.py`) — for simple conceptual diagrams (5-15 services, no deep nesting)
- **Natural language mode** (`src/architect.py`) — calls Claude to convert a description to YAML, then dispatches to the correct engine

`src/architect.py` auto-detects the engine from keywords in the description (vpc, subnet, eks, hybrid, etc.) and can be overridden with `--engine d2` or `--engine diagrams`.

## Companion documents

Load these on-demand based on the task at hand:

| Task | Document |
|---|---|
| Installing dependencies on any platform | `installation.md` |
| Full YAML schema: boundary types, connection types, shapes, layout options | `yaml-schema.md` |
| All icon short names, local vs online mode, custom icons | `icon-reference.md` |

## Reference examples

Use these as starting points or templates. Each has a `.yaml` spec and a rendered `.png` in `examples/`.

| File | Engine | What it demonstrates |
|------|--------|----------------------|
| `examples/complex_aws_hybrid.yaml` | D2 | VPC + 2 AZs + ECS Fargate cluster + RDS Multi-AZ + NAT Gateways + CloudFront/WAF edge + on-prem DC via IPSec VPN through Transit Gateway. Use as a template for any hybrid or multi-AZ AWS diagram. |
| `examples/eks_microservices.yaml` | D2 | EKS cluster with 3 namespaces (frontend/backend/data) + Aurora + MSK Kafka + ElastiCache + gRPC service mesh + Debezium CDC + CloudFront/NLB ingress. Use as a template for K8s or microservices platform diagrams. |
| `examples/three_tier_web_app.yaml` | D2 | Classic 3-tier: Route 53 → CloudFront → ALB → EC2 in 2 AZs → RDS Primary/Replica + ElastiCache + S3. Use as a template for straightforward AWS web app diagrams. |
| `examples/microservices_gcp.yaml` | D2 | GCP: Cloud CDN → Load Balancer → Cloud Run services → Cloud SQL, Firestore, Memorystore, Pub/Sub, Cloud Storage. Use as a template for GCP diagrams or multi-service architectures. |
| `examples/serverless_event_pipeline.yaml` | D2 | Serverless: Cognito → API Gateway → Lambda → SQS → processing Lambda → DynamoDB + S3 + SNS fan-out + CloudWatch. Use as a template for event-driven or serverless pipeline diagrams. |

When a user describes an architecture, identify the closest matching example and use its YAML structure as a template — adapting boundaries, nodes, and connections rather than generating from scratch.

---

## Installation

### Dependencies
This skill requires two things installed on the system:

**1. D2 diagram renderer**
| Platform | Command |
|----------|---------|
| macOS | `brew install d2` |
| Linux | `curl -fsSL https://d2lang.com/install.sh \| sh` |
| Windows | `winget install terrastruct.d2` or download from https://github.com/terrastruct/d2/releases |

Verify: `d2 --version`

**2. Python packages**
```bash
pip install pyyaml anthropic diagrams
```

**3. Graphviz** (required by the `diagrams` package for simple diagrams)
| Platform | Command |
|----------|---------|
| macOS | `brew install graphviz` |
| Linux (Debian/Ubuntu) | `apt-get install graphviz` |
| Linux (RHEL/Amazon) | `yum install graphviz` |
| Windows | Download from https://graphviz.org/download/ |

Verify: `dot -V`

**4. ANTHROPIC_API_KEY** — required only for natural language mode (`src/architect.py`)
```bash
export ANTHROPIC_API_KEY=sk-ant-...
```

See `installation.md` for troubleshooting and platform-specific details.

---

## Usage

### Option 1: Natural language (requires ANTHROPIC_API_KEY)

```bash
# Auto-detect engine from keywords:
python3 src/architect.py "3-tier web app with CloudFront, ALB, EC2 auto-scaling, RDS MySQL with replica, ElastiCache Redis, S3"

# Force D2 engine for VPC/K8s/hybrid diagrams:
python3 src/architect.py "AWS VPC with two AZs, ECS cluster in private subnets, RDS Aurora, on-prem DC via VPN" --engine d2

# Force diagrams engine:
python3 src/architect.py "GKE microservices with Cloud SQL, Memorystore, Pub/Sub" --engine diagrams

# Save the generated YAML spec for inspection or reuse:
python3 src/architect.py "EKS cluster with ALB, RDS Aurora, ElastiCache" --save-yaml --engine d2

# Interactive mode:
python3 src/architect.py --interactive
```

### Option 2: From a YAML spec (no API key needed)

```bash
# D2 engine — nested infrastructure
python3 src/generate_d2.py examples/complex_aws_hybrid.yaml
python3 src/generate_d2.py examples/eks_microservices.yaml --output output/eks --layout elk

# Python diagrams engine — simple conceptual
python3 src/generate_diagram.py examples/three_tier_web_app.yaml
python3 src/generate_diagram.py examples/microservices_gcp.yaml --output my_diagram --format svg
```

### Output options

```bash
# architect.py flags:
--output diagram       # output filename without extension (default: diagram)
--format png           # png, svg, pdf (default: png; D2 only supports png/svg)
--engine auto          # auto, d2, diagrams
--icons local          # local, online, none (D2 mode only)
--save-yaml            # save generated YAML spec alongside diagram
--file description.txt # read description from file
--interactive          # interactive REPL
```

---

## YAML Schema (D2 engine)

Full schema reference is in `yaml-schema.md`. Quick overview:

```yaml
title: "Diagram Title"
engine: d2
layout: dagre          # dagre (default) or elk

boundaries:
  - id: aws
    type: cloud        # see boundary types below
    label: "AWS us-east-1"
    children:
      - id: vpc_prod
        type: vpc
        label: "VPC 10.0.0.0/16"
        children:
          - id: az1
            type: availability-zone
            label: "AZ us-east-1a"
            children:
              - id: ec2_web
                label: "Web Server"
                icon: ec2

nodes:
  - id: internet
    label: "Internet"
    icon: internet
    shape: oval

connections:
  - from: internet
    to: aws.vpc_prod.az1.ec2_web
    type: https
    label: "HTTPS"
```

### Boundary types

| Type | Visual | Use for |
|------|--------|---------|
| `datacenter` | Orange border, warm fill | On-premises / co-lo |
| `cloud` | Blue border, light blue fill | AWS/GCP/Azure region |
| `vpc` | Green dashed border | VPC / VNet |
| `availability-zone` | Purple dashed border | AZ / zone |
| `subnet-public` | Yellow border | Public subnets |
| `subnet-private` | Indigo border | Private subnets |
| `ecs-cluster` | Teal border | ECS clusters |
| `k8s-cluster` | Dark blue dashed | EKS/GKE clusters |
| `k8s-namespace` | Purple dashed | K8s namespaces |
| `region` | Grey border | Cloud regions |
| `account` | Pink border | Cloud accounts |

### Connection types

| Type | Color | Style |
|------|-------|-------|
| `https` | Blue | Solid |
| `grpc` | Purple | Solid |
| `sql` | Green | Solid |
| `vpn` | Orange | Dashed |
| `bgp` | Red | Dashed |
| `direct_connect` | Deep orange | Solid thick |
| `replication` | Grey-blue | Dashed |
| `kafka` | Pink | Solid |
| `redis` | Red | Solid |
| `internal` | Grey | Dashed thin |

### Icon short names (AWS)

| Short name | Service |
|-----------|---------|
| `ec2` | EC2 |
| `ecs` | Elastic Container Service |
| `eks` | Elastic Kubernetes Service |
| `fargate` | Fargate |
| `lambda` | Lambda |
| `alb` | Application Load Balancer |
| `nlb` | Network Load Balancer |
| `nat` / `nat-gateway` | NAT Gateway |
| `tgw` / `transit-gateway` | Transit Gateway |
| `igw` / `internet-gateway` | Internet Gateway |
| `vpc` | VPC |
| `cloudfront` | CloudFront |
| `route53` | Route 53 |
| `waf` | WAF |
| `rds` | RDS |
| `aurora` | Aurora |
| `elasticache` | ElastiCache |
| `dynamodb` | DynamoDB |
| `s3` | S3 |
| `sqs` | SQS |
| `sns` | SNS |
| `cloudwatch` | CloudWatch |
| `iam` | IAM |
| `secrets-manager` | Secrets Manager |
| `api-gateway` / `apigw` | API Gateway |
| `cognito` | Cognito |
| `msk` | MSK (Managed Kafka) |
| `ecr` | ECR |
| `vpn` | Site-to-Site VPN |

### Icon short names (generic / on-prem)

| Short name | Service |
|-----------|---------|
| `internet` | Internet / network |
| `firewall` | Firewall |
| `router` | Router |
| `user` | User |
| `users` | Users / team |
| `kafka` | Apache Kafka |
| `redis` | Redis |
| `postgres` | PostgreSQL |
| `mysql` | MySQL |
| `nginx` | Nginx |
| `grafana` | Grafana |
| `prometheus` | Prometheus |

### Node shapes

| Shape | Use for |
|-------|---------|
| `cylinder` | Databases, object storage |
| `oval` | Internet, users, external actors |
| `hexagon` | Gateways, firewalls, load balancers |
| `queue` | Message queues, streams |
| `rectangle` | Generic services (default) |
| `diamond` | Decision points |

### Connection dot-paths

Connections to nested nodes use the full dot-path from the root:

```yaml
connections:
  - from: aws.vpc_prod.az1.priv_subnet_1.ecs_cluster.api_service
    to: aws.vpc_prod.az1.priv_subnet_1.rds_primary
    type: sql
    label: "5432"
  - from: on_prem.corp_router
    to: aws.tgw
    type: vpn
    label: "IPSec VPN"
```

---

## YAML Schema (diagrams engine)

```yaml
title: "My Architecture"
layout:
  direction: LR        # LR (left-to-right) or TB (top-to-bottom)
  ranksep: "2.0"
  nodesep: "1.0"
  splines: ortho

nodes:
  - id: cdn
    label: "CloudFront CDN"
    icon: "aws.network.CloudFront"

groups:
  - id: web_tier
    label: "Web Tier"
    color: "#FEF9E7"
    style: dashed
    nodes: [ec2_1, ec2_2]

connections:
  - from: cdn
    to: alb
    label: "HTTPS"
    style: solid
```

Icons for the diagrams engine use dotted paths: `aws.compute.EC2`, `gcp.compute.GKE`, `azure.compute.AKS`. See `icon-reference.md` for the full list.

---

## Rules for generating good diagrams

When generating YAML from a description, follow these guidelines:

1. **All IDs must be snake_case and unique within their parent container.**
2. **Connections reference the FULL dot-path from the root** — not relative paths.
3. **Standalone nodes** (internet, S3, monitoring services) go in the top-level `nodes` list.
4. **Use appropriate shapes**: `cylinder` for databases, `oval` for internet/users, `hexagon` for gateways/firewalls, `queue` for message queues.
5. **Keep labels concise** — no need for multiline labels.
6. **Reduce connections**: connect to a representative node (e.g., one ECS service, not every task). The boundary container implies all children share the same pattern.
7. **Use boundaries aggressively**: VPCs, AZs, subnets, and clusters should be modeled as boundaries with the correct type — not flat nodes.
8. **D2 for infrastructure, diagrams for conceptual**: if the description mentions VPC, subnet, AZ, ECS, EKS, hybrid, or on-prem, use D2. Otherwise, use diagrams.
9. **Output ONLY valid YAML** — no markdown code fences, no explanations.

---

## Examples

```bash
# D2 — complex nested infrastructure
python3 src/generate_d2.py examples/complex_aws_hybrid.yaml
python3 src/generate_d2.py examples/eks_microservices.yaml

# Python diagrams — simple conceptual
python3 src/generate_diagram.py examples/three_tier_web_app.yaml
python3 src/generate_diagram.py examples/microservices_gcp.yaml
python3 src/generate_diagram.py examples/serverless_event_pipeline.yaml

# Icon modes for D2
python3 src/generate_d2.py examples/complex_aws_hybrid.yaml --icons local    # default
python3 src/generate_d2.py examples/complex_aws_hybrid.yaml --icons online
python3 src/generate_d2.py examples/complex_aws_hybrid.yaml --icons none
```

---

## Version

1.0.0 - Restructured into skill suite with companion docs (March 2026)
