# YAML Schema Reference

Complete YAML schema reference for both rendering engines.

---

## D2 engine schema

Used by `src/generate_d2.py` and `src/architect.py` with `--engine d2`.

```yaml
title: "Diagram Title"
engine: d2
layout: dagre          # dagre (default) or elk

# Optional: define or override connection styles
connection_types:
  https: { color: "#2196F3", style: solid }
  grpc: { color: "#9C27B0", style: solid }
  sql: { color: "#4CAF50", style: solid }
  vpn: { color: "#FF9800", style: dashed }
  kafka: { color: "#E91E63", style: solid }
  replication: { color: "#607D8B", style: dashed }

# Nested containers
boundaries:
  - id: on_prem                 # snake_case, unique within parent
    type: datacenter            # see boundary types below
    label: "On-Premises DC"
    direction: down             # optional: layout direction inside this container
    icon: firewall              # optional: boundary icon (top-left corner)
    children:
      - id: corp_firewall
        label: "Firewall"
        icon: firewall          # leaf node rendered as icon image
      - id: vpc_prod
        type: vpc               # can nest boundaries inside boundaries
        label: "VPC 10.0.0.0/16"
        children:
          - id: az1
            type: availability-zone
            label: "AZ us-east-1a"
            children:
              - id: rds_primary
                label: "RDS Primary"
                icon: rds
                shape: cylinder # optional shape override

# Standalone nodes outside all boundaries
nodes:
  - id: internet
    label: "Internet"
    icon: internet
    shape: oval

# Connections use full dot-path from root
connections:
  - from: on_prem.vpc_prod.az1.rds_primary
    to: internet
    type: https              # maps to connection_types (built-in or custom)
    label: "Optional label"  # short, 1-3 words or omit
```

---

## Boundary types

| Type | Fill | Border | Use for |
|------|------|--------|---------|
| `datacenter` | Warm orange (`#FFF3E0`) | Orange solid | On-premises / co-lo |
| `cloud` | Light blue (`#E3F2FD`) | Blue solid | AWS/GCP/Azure region |
| `vpc` | Light green (`#E8F5E9`) | Green dashed | VPC / VNet |
| `availability-zone` | Light purple (`#F3E5F5`) | Purple dashed | AZ / zone |
| `subnet-public` | Light yellow (`#FFFDE7`) | Orange solid | Public subnets |
| `subnet-private` | Light indigo (`#EDE7F6`) | Indigo solid | Private subnets |
| `ecs-cluster` | Light teal (`#E0F2F1`) | Teal solid | ECS clusters |
| `k8s-cluster` | Light blue-grey (`#E8EAF6`) | Dark blue dashed | EKS/GKE clusters |
| `k8s-namespace` | Light purple (`#F3E5F5`) | Purple dashed | K8s namespaces |
| `security-group` | Light amber (`#FFF8E1`) | Amber dashed | AWS Security Groups |
| `region` | Grey (`#ECEFF1`) | Blue-grey solid | Cloud regions |
| `account` | Light pink (`#FCE4EC`) | Pink solid | Cloud accounts |

---

## Built-in connection types

| Type | Color | Style | Use for |
|------|-------|-------|---------|
| `https` | Blue `#2196F3` | Solid 2px | HTTPS, REST, web traffic |
| `http` | Light blue `#64B5F6` | Solid 1px | HTTP (unencrypted) |
| `grpc` | Purple `#9C27B0` | Solid 2px | gRPC calls |
| `sql` | Green `#4CAF50` | Solid 2px | SQL / database connections |
| `mysql` | Green `#4CAF50` | Solid 2px | MySQL |
| `postgres` | Green `#4CAF50` | Solid 2px | PostgreSQL |
| `vpn` | Orange `#FF9800` | Dashed 2px | VPN tunnels |
| `bgp` | Red `#F44336` | Dashed 2px | BGP peering |
| `direct_connect` | Deep orange `#FF5722` | Solid 3px | AWS Direct Connect |
| `replication` | Grey-blue `#607D8B` | Dashed 1px | DB replication, sync |
| `amqp` | Orange `#FF9800` | Solid 2px | AMQP / RabbitMQ |
| `kafka` | Pink `#E91E63` | Solid 2px | Kafka streams |
| `tcp` | Brown `#795548` | Solid 1px | Raw TCP |
| `tls` | Teal `#009688` | Solid 2px | TLS/mTLS |
| `redis` | Red `#F44336` | Solid 2px | Redis connections |
| `internal` | Grey `#9E9E9E` | Dashed 1px | Internal / admin traffic |

You can define additional types or override these in the `connection_types` block.

---

## Node shapes

| Shape | D2 shape | Use for |
|-------|----------|---------|
| `rectangle` | rectangle | Generic services (default) |
| `cylinder` | cylinder | Databases, object storage |
| `oval` | oval | Internet, users, external actors |
| `hexagon` | hexagon | Gateways, firewalls, load balancers |
| `queue` | queue | Message queues, streams |
| `diamond` | diamond | Decision points |
| `parallelogram` | parallelogram | Data flows |
| `document` | document | Documents, reports |
| `package` | package | Packages, libraries |
| `circle` | circle | Small services |
| `cloud` | cloud | Cloud shape |

---

## Layout options

```yaml
layout: dagre   # dagre (default) or elk
```

- `dagre` — fast, good for most diagrams
- `elk` — Eclipse Layout Kernel; better for complex diagrams with many crossing edges

The `direction` field can be set on individual boundaries to control their internal layout:

```yaml
boundaries:
  - id: az1
    type: availability-zone
    direction: down    # children stack vertically inside this AZ
```

---

## Full annotated example

```yaml
title: "Production AWS Hybrid Architecture"
engine: d2
layout: dagre

# Override or add connection types
connection_types:
  https: { color: "#2196F3", style: solid }
  vpn: { color: "#FF9800", style: dashed }
  direct_connect: { color: "#FF5722", style: solid, width: 3 }
  replication: { color: "#607D8B", style: dashed }

boundaries:
  - id: on_prem
    type: datacenter
    label: "On-Premises DC"
    children:
      - id: corp_firewall
        label: "Firewall"
        icon: firewall
      - id: corp_router
        label: "BGP Router"
        icon: router

  - id: aws
    type: cloud
    label: "AWS us-east-1"
    children:
      - id: tgw
        label: "Transit Gateway"
        icon: tgw
      - id: vpc_prod
        type: vpc
        label: "VPC 10.0.0.0/16"
        children:
          - id: alb
            label: "ALB"
            icon: alb
          - id: az1
            type: availability-zone
            label: "AZ us-east-1a"
            direction: down
            children:
              - id: pub_subnet_1
                type: subnet-public
                label: "Public 10.0.1.0/24"
                children:
                  - id: nat1
                    label: "NAT GW"
                    icon: nat-gateway
              - id: priv_subnet_1
                type: subnet-private
                label: "Private 10.0.2.0/24"
                children:
                  - id: ecs_cluster
                    type: ecs-cluster
                    label: "ECS Cluster"
                    children:
                      - id: svc_api
                        label: "API Service"
                        icon: fargate
                  - id: rds_primary
                    label: "RDS Primary"
                    icon: rds

nodes:
  - id: internet
    label: "Internet"
    icon: internet
    shape: oval
  - id: s3
    label: "S3 Bucket"
    icon: s3

connections:
  - from: internet
    to: aws.vpc_prod.alb
    type: https
    label: "HTTPS"
  - from: aws.vpc_prod.alb
    to: aws.vpc_prod.az1.priv_subnet_1.ecs_cluster.svc_api
    type: https
  - from: aws.vpc_prod.az1.priv_subnet_1.ecs_cluster.svc_api
    to: aws.vpc_prod.az1.priv_subnet_1.rds_primary
    type: sql
    label: "5432"
  - from: aws.vpc_prod.az1.priv_subnet_1.ecs_cluster.svc_api
    to: s3
    type: https
    label: "uploads"
  - from: on_prem.corp_router
    to: aws.tgw
    type: vpn
    label: "IPSec VPN"
  - from: aws.tgw
    to: aws.vpc_prod.alb
    type: https
    label: "internal"
```

---

## Python diagrams engine schema

Used by `src/generate_diagram.py` and `src/architect.py` with `--engine diagrams`.

```yaml
title: "My Architecture"

layout:
  direction: LR           # LR (left-to-right) or TB (top-to-bottom)
  ranksep: "1.5"          # space between ranks (increase for crowded diagrams)
  nodesep: "0.9"          # space between nodes in the same rank
  splines: ortho          # ortho (90-degree), curved, or line
  pad: "0.8"
  fontsize: "13"
  node_fontsize: "11"
  edge_fontsize: "10"
  node_width: "1.4"
  node_height: "1.8"
  edge_penwidth: "1.5"

nodes:
  - id: cdn
    label: "CloudFront CDN"
    icon: "aws.network.CloudFront"   # dotted provider.module.ClassName path

  - id: alb
    label: "ALB"
    icon: "aws.network.ALB"

groups:
  - id: web_tier
    label: "Web Tier (Auto Scaling)"
    color: "#E8F4FD"       # hex background for the cluster box
    style: dashed
    nodes: [ec2_1, ec2_2]

connections:
  - from: cdn
    to: alb
    label: "HTTPS"
    style: solid           # solid or dashed
```

### Rules for the diagrams engine

- Every node ID must be unique and snake_case.
- Every node referenced in `groups` or `connections` must exist in `nodes`.
- Connections reference node IDs, not group IDs.
- Keep edge labels very short (1-3 words) or omit them.
- Aim for 5-15 nodes for readability; group aggressively for larger systems.
- `LR` direction works best for pipeline/request-flow diagrams.
- `TB` works for hierarchical or tier-based layouts.
