# Icon Reference

Icon support for the D2 engine (`src/generate_d2.py`).

---

## Icon modes

The `--icons` flag controls how icons are sourced:

| Mode | Source | Notes |
|------|--------|-------|
| `local` | PNGs from installed `diagrams` package | No network required; default |
| `online` | Terrastruct CDN (SVG), cached locally | Requires network on first use |
| `none` | No icons — shapes only | Fastest; same as pre-icon behavior |

```bash
python3 src/generate_d2.py examples/complex_aws_hybrid.yaml --icons local
python3 src/generate_d2.py examples/complex_aws_hybrid.yaml --icons online
python3 src/generate_d2.py examples/complex_aws_hybrid.yaml --icons none
```

**Online mode**: icons are fetched from `https://icons.terrastruct.com` and cached in `~/.cache/architect-diagram/terrastruct/`. The manifest is cached for 7 days. After the first fetch, subsequent runs work offline.

**Local mode**: resolves icons from the `diagrams` package's installed PNG resources (`diagrams/resources/`). No network required. Requires `diagrams` to be installed.

---

## Setting icons in YAML

Set the `icon:` field on any node or boundary using a short name or full path:

```yaml
boundaries:
  - id: vpc_prod
    type: vpc
    label: "VPC 10.0.0.0/16"
    icon: vpc                # boundary icon appears in the top-left corner
    children:
      - id: ec2_web
        label: "Web Server"
        icon: ec2             # leaf node is rendered as an icon image

nodes:
  - id: s3
    label: "S3 Bucket"
    icon: s3
```

Full paths are also accepted:

```yaml
icon: aws/compute/ec2
icon: onprem/database/redis
icon: k8s/compute/deploy
```

---

## AWS icon short names

| Short name | Service | Local path |
|-----------|---------|------------|
| `alb` | Application Load Balancer | `aws/network/elb-application-load-balancer` |
| `nlb` | Network Load Balancer | `aws/network/elb-network-load-balancer` |
| `clb` | Classic Load Balancer | `aws/network/elb-classic-load-balancer` |
| `nat` / `nat-gateway` | NAT Gateway | `aws/network/nat-gateway` |
| `tgw` / `transit-gateway` | Transit Gateway | `aws/network/transit-gateway` |
| `direct-connect` | Direct Connect | `aws/network/direct-connect` |
| `vpc` | VPC | `aws/network/vpc` |
| `igw` / `internet-gateway` | Internet Gateway | `aws/network/internet-gateway` |
| `cloudfront` | CloudFront | `aws/network/cloudfront` |
| `route53` | Route 53 | `aws/network/route-53` |
| `api-gateway` / `apigw` | API Gateway | `aws/network/api-gateway` |
| `waf` | WAF | `aws/security/waf` |
| `ec2` | EC2 | `aws/compute/ec2` |
| `ecs` | Elastic Container Service | `aws/compute/elastic-container-service` |
| `eks` | Elastic Kubernetes Service | `aws/compute/elastic-kubernetes-service` |
| `fargate` | Fargate | `aws/compute/fargate` |
| `lambda` | Lambda | `aws/compute/lambda` |
| `ecr` | ECR | `aws/compute/ec2-container-registry` |
| `rds` | RDS | `aws/database/rds` |
| `aurora` | Aurora | `aws/database/aurora` |
| `elasticache` | ElastiCache | `aws/database/elasticache` |
| `dynamodb` | DynamoDB | `aws/database/dynamodb` |
| `s3` | S3 | `aws/storage/s3` |
| `sqs` | SQS | `aws/integration/simple-queue-service-sqs` |
| `sns` | SNS | `aws/integration/simple-notification-service-sns` |
| `msk` | MSK (Managed Kafka) | `aws/integration/managed-streaming-for-kafka` |
| `cloudwatch` | CloudWatch | `aws/management/cloudwatch` |
| `iam` | IAM | `aws/security/iam` |
| `secrets-manager` | Secrets Manager | `aws/security/secrets-manager` |
| `cognito` | Cognito | `aws/security/cognito` |
| `vpn` | Site-to-Site VPN | `aws/network/site-to-site-vpn` |

---

## Kubernetes icon short names

| Short name | Resource | Local path |
|-----------|----------|------------|
| `k8s-deploy` / `deployment` | Deployment | `k8s/compute/deploy` |
| `k8s-pod` / `pod` | Pod | `k8s/compute/pod` |
| `k8s-service` / `service` | Service | `k8s/network/svc` |
| `k8s-ingress` / `ingress` | Ingress | `k8s/network/ing` |
| `k8s-namespace` | Namespace | `k8s/others/crd` |
| `k8s` | Generic K8s | `k8s/others/crd` |

---

## On-premises / generic icon short names

| Short name | Service | Local path |
|-----------|---------|------------|
| `kafka` | Apache Kafka | `onprem/queue/kafka` |
| `redis` | Redis | `onprem/database/redis` |
| `postgres` | PostgreSQL | `onprem/database/postgresql` |
| `mysql` | MySQL | `onprem/database/mysql` |
| `prometheus` | Prometheus | `onprem/monitoring/prometheus` |
| `grafana` | Grafana | `onprem/monitoring/grafana` |
| `nginx` | Nginx | `onprem/network/nginx` |
| `firewall` | Firewall | `generic/network/firewall` |
| `router` | Router | `generic/network/router` |
| `user` | User | `generic/other/user` |
| `users` | Users / team | `generic/group/users` |
| `internet` | Internet (fallback: firewall icon) | `generic/network/firewall` |

---

## Provider coverage

**Local mode** (from `diagrams` package):
- AWS — comprehensive: compute, networking, databases, storage, security, integration, management
- GCP — compute, networking, databases, storage, analytics
- Azure — compute, networking, databases, storage, integration
- Kubernetes — workloads, network, storage, others
- On-prem / generic — databases, queues, monitoring, networking

**Online mode** (from Terrastruct CDN):
- AWS — full official icon set (SVG)
- GCP, Azure — partial (what Terrastruct has published)

---

## Using custom icons

Set the `icon:` field to a local file path:

```yaml
nodes:
  - id: my_service
    label: "My Service"
    icon: /path/to/my-icon.png
```

Relative paths are resolved from the working directory where you run the script.

---

## Online mode: how icon resolution works

1. On first use, the Terrastruct manifest (`https://icons.terrastruct.com/icons.json`) is fetched and cached at `~/.cache/architect-diagram/terrastruct/icons.json` for 7 days.
2. Short names are matched against the manifest using normalised keys (lowercase, hyphens as separators, vendor prefixes stripped).
3. Matched icons are downloaded to `~/.cache/architect-diagram/terrastruct/<provider>/<sanitized-filename>.svg`.
4. D2 references the local cached path in the generated `.d2` file.
5. If an icon cannot be found online, it falls back to local resolution.

The explicit `TERRASTRUCT_ALIASES` dict in `src/generate_d2.py` takes precedence over the manifest index for the listed short names.
