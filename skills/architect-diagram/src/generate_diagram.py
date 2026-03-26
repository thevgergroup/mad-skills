#!/usr/bin/env python3
"""
generate_diagram.py — Generate clean architecture diagrams from YAML/JSON descriptions.

Usage:
    python3 generate_diagram.py architecture.yaml
    python3 generate_diagram.py architecture.yaml --output my_diagram
    python3 generate_diagram.py architecture.yaml --format svg
    python3 generate_diagram.py architecture.json
"""

import sys
import os
import json
import argparse
import importlib
from pathlib import Path

import yaml


# ---------------------------------------------------------------------------
# Icon resolution
# ---------------------------------------------------------------------------

# Map of provider -> module_path -> list of class names
ICON_REGISTRY = {
    # AWS
    "aws": {
        "compute": ["EC2", "EC2Instances", "ECS", "EKS", "Lambda", "LambdaFunction",
                    "Fargate", "ElasticBeanstalk", "Batch", "AutoScaling",
                    "EC2AutoScaling", "AppRunner"],
        "network": ["CloudFront", "ELB", "ALB", "NLB", "CLB", "Route53", "VPC",
                    "APIGateway", "InternetGateway", "IGW", "NATGateway",
                    "GlobalAccelerator", "DirectConnect", "TransitGateway",
                    "ElasticLoadBalancing", "ElbApplicationLoadBalancer"],
        "database": ["RDS", "Aurora", "DynamoDB", "DDB", "Dynamodb", "DynamodbTable", "ElastiCache",
                     "ElasticacheForRedis", "ElasticacheForMemcached", "DocumentDB",
                     "Neptune", "Redshift", "DAX"],
        "storage": ["S3", "EBS", "EFS", "S3Glacier", "StorageGateway", "Backup",
                    "SimpleStorageServiceS3"],
        "security": ["IAM", "KMS", "WAF", "Shield", "Cognito", "SecretsManager",
                     "CertificateManager", "Guardduty"],
        "integration": ["SQS", "SNS", "Eventbridge", "MQ", "SF", "StepFunctions",
                        "Appsync"],
        "management": ["Cloudwatch", "Cloudtrail", "Cloudformation", "SSM",
                       "Config", "Organizations"],
        "analytics": ["Kinesis", "Redshift", "Glue", "Athena", "EMR", "ES",
                      "Quicksight", "PubSub", "Pubsub"],
        "ml": ["Sagemaker", "Bedrock", "Rekognition", "Comprehend", "Lex", "Polly"],
        "general": ["InternetGateway", "Client", "User", "Users", "MobileClient",
                    "InternetAlt1", "InternetAlt2", "GenericDatabase",
                    "GenericFirewall"],
    },
    # GCP
    "gcp": {
        "compute": ["GCE", "GKE", "Functions", "AppEngine", "CloudRun",
                    "ComputeEngine", "KubernetesEngine"],
        "network": ["LoadBalancing", "CDN", "DNS", "VPC", "Armor",
                    "VirtualPrivateCloud"],
        "database": ["SQL", "Spanner", "Firestore", "Bigtable", "Memorystore",
                     "CloudSQL"],
        "storage": ["GCS", "Filestore", "PersistentDisk", "Storage"],
        "security": ["IAP", "KMS", "SecurityCommandCenter"],
        "analytics": ["Bigquery", "Dataflow", "Dataproc", "Pub", "PubSub",
                      "Composer"],
        "ml": ["AIPlatform", "AutoML", "VisionAPI", "NaturalLanguageAPI",
               "TranslationAPI"],
    },
    # Azure
    "azure": {
        "compute": ["VM", "AKS", "FunctionApps", "AppServices", "ContainerInstances",
                    "VirtualMachines"],
        "network": ["ApplicationGateway", "CDNProfiles", "LoadBalancers",
                    "VirtualNetworks", "APIManagement", "Frontdoor",
                    "TrafficManagerProfiles"],
        "database": ["SQLDatabases", "CosmosDb", "CacheForRedis", "SQLServers",
                     "DatabaseForMysqlServers", "DatabaseForPostgresqlServers"],
        "storage": ["BlobStorage", "StorageAccounts", "DataLakeStorage",
                    "ManagedDisks"],
        "security": ["KeyVaults", "ActiveDirectory", "ApplicationSecurityGroups"],
        "integration": ["ServiceBus", "EventHubs", "EventGrid", "LogicApps"],
    },
    # Generic / on-prem
    "generic": {
        "compute": ["Server", "Rack"],
        "network": ["Firewall", "Router", "Switch", "Internet"],
        "storage": ["Storage"],
        "database": ["Sql", "Nosql"],
    },
    "onprem": {
        "compute": ["Server", "Client", "Users", "Worker"],
        "network": ["Firewall", "Router", "Switch", "Internet"],
        "database": ["Postgresql", "Mysql", "MongoDB", "Cassandra", "Redis"],
        "monitoring": ["Prometheus", "Grafana", "Datadog"],
        "queue": ["Kafka", "Rabbitmq", "Celery"],
    },
}

# Flat lookup: lowercase class name -> (module_path, class_name)
_ICON_FLAT: dict[str, tuple[str, str]] = {}


def _build_icon_flat():
    """Build a flattened icon lookup dict (done once)."""
    for provider, modules in ICON_REGISTRY.items():
        for module_name, classes in modules.items():
            for cls in classes:
                key = cls.lower()
                mod_path = f"diagrams.{provider}.{module_name}"
                if key not in _ICON_FLAT:
                    _ICON_FLAT[key] = (mod_path, cls)


_build_icon_flat()


def resolve_icon(icon_str: str):
    """
    Resolve an icon string to a diagrams class.

    Accepts:
      - "aws.compute.EC2"            (fully qualified)
      - "EC2" / "ec2"                (short name, searched across all providers)
      - "aws.EC2"                    (provider-prefixed short name)
    """
    if not icon_str:
        # Default to generic server
        from diagrams.onprem.compute import Server
        return Server

    parts = icon_str.split(".")

    if len(parts) == 3:
        # Fully qualified: provider.module.ClassName
        mod_path = f"diagrams.{parts[0]}.{parts[1]}"
        class_name = parts[2]
    elif len(parts) == 2:
        # provider.ClassName — search modules
        provider = parts[0].lower()
        class_name = parts[1]
        mod_path = None
        if provider in ICON_REGISTRY:
            for module_name, classes in ICON_REGISTRY[provider].items():
                if class_name in classes or class_name.lower() in [c.lower() for c in classes]:
                    # Find exact case
                    for c in classes:
                        if c.lower() == class_name.lower():
                            class_name = c
                            break
                    mod_path = f"diagrams.{provider}.{module_name}"
                    break
        if mod_path is None:
            raise ValueError(f"Cannot resolve icon '{icon_str}'. Unknown provider or class.")
    else:
        # Short name — search flat index
        class_name = parts[0]
        key = class_name.lower()
        if key in _ICON_FLAT:
            mod_path, class_name = _ICON_FLAT[key]
        else:
            # Fall back to generic Server
            print(f"WARNING: Icon '{icon_str}' not found, using generic Server", file=sys.stderr)
            from diagrams.onprem.compute import Server
            return Server

    try:
        module = importlib.import_module(mod_path)
        return getattr(module, class_name)
    except (ImportError, AttributeError) as e:
        print(f"WARNING: Failed to import {mod_path}.{class_name}: {e}", file=sys.stderr)
        from diagrams.onprem.compute import Server
        return Server


# ---------------------------------------------------------------------------
# Diagram generation
# ---------------------------------------------------------------------------

def load_spec(path: str) -> dict:
    """Load YAML or JSON architecture spec."""
    p = Path(path)
    text = p.read_text()
    if p.suffix.lower() in (".yaml", ".yml"):
        return yaml.safe_load(text)
    elif p.suffix.lower() == ".json":
        return json.loads(text)
    else:
        # Try YAML first, then JSON
        try:
            return yaml.safe_load(text)
        except Exception:
            return json.loads(text)


def build_graph_attrs(spec: dict) -> dict:
    """Extract graph-level Graphviz attributes from spec, with sensible defaults."""
    layout = spec.get("layout", {})
    direction = layout.get("direction", "LR")  # LR = left-to-right gives clean flow

    attrs = {
        # Spacing: pad, ranksep controls vertical/horizontal gap between ranks,
        # nodesep controls gap between nodes in the same rank
        "pad": str(layout.get("pad", "0.8")),
        "ranksep": str(layout.get("ranksep", "1.2")),
        "nodesep": str(layout.get("nodesep", "0.8")),
        "splines": layout.get("splines", "ortho"),   # ortho gives clean 90° lines
        "rankdir": direction,
        "fontsize": str(layout.get("fontsize", "13")),
        "fontname": layout.get("fontname", "Helvetica"),
        "concentrate": "false",
        "overlap": "false",
    }
    return attrs


def build_node_attrs(spec: dict) -> dict:
    """Node-level graphviz attributes."""
    layout = spec.get("layout", {})
    return {
        "fontsize": str(layout.get("node_fontsize", "11")),
        "fontname": layout.get("fontname", "Helvetica"),
        "labelloc": "b",      # label below icon
        "imagescale": "true",
        "fixedsize": "true",
        "width": str(layout.get("node_width", "1.4")),
        "height": str(layout.get("node_height", "1.8")),
    }


def build_edge_attrs(spec: dict) -> dict:
    """Edge-level graphviz attributes."""
    layout = spec.get("layout", {})
    return {
        "fontsize": str(layout.get("edge_fontsize", "10")),
        "fontname": layout.get("fontname", "Helvetica"),
        "penwidth": str(layout.get("edge_penwidth", "1.5")),
        "color": layout.get("edge_color", "#666666"),
    }


def generate_diagram(spec: dict, output_path: str, output_format: str = "png"):
    """
    Generate a diagram from an architecture spec dict.

    Spec structure:
        title: "My Architecture"
        layout:
          direction: LR         # LR, TB, RL, BT
          ranksep: "1.2"
          nodesep: "0.8"
          splines: ortho        # ortho, curved, line, polyline, spline
        nodes:
          - id: cdn
            label: "CloudFront CDN"
            icon: "aws.network.CloudFront"
          - id: alb
            label: "App Load Balancer"
            icon: "ALB"
        groups:
          - id: web_tier
            label: "Web Tier"
            color: "#E8F4FD"
            nodes: [ec2_1, ec2_2]
        connections:
          - from: cdn
            to: alb
            label: "HTTPS"
    """
    from diagrams import Diagram, Cluster, Edge

    title = spec.get("title", "Architecture Diagram")
    graph_attrs = build_graph_attrs(spec)
    node_attrs = build_node_attrs(spec)
    edge_attrs = build_edge_attrs(spec)

    # Index nodes from spec
    node_specs = {n["id"]: n for n in spec.get("nodes", [])}
    group_specs = {g["id"]: g for g in spec.get("groups", [])}

    # Determine which nodes belong to a group
    grouped_node_ids: set[str] = set()
    for g in spec.get("groups", []):
        for nid in g.get("nodes", []):
            grouped_node_ids.add(nid)

    # Track instantiated diagram node objects by spec id
    diagram_nodes: dict[str, object] = {}

    def make_node(node_spec: dict) -> object:
        """Instantiate a single diagram node."""
        icon_cls = resolve_icon(node_spec.get("icon", ""))
        label = node_spec.get("label", node_spec["id"])
        return icon_cls(label)

    with Diagram(
        title,
        filename=output_path,
        outformat=output_format,
        show=False,
        graph_attr=graph_attrs,
        node_attr=node_attrs,
        edge_attr=edge_attrs,
        direction=graph_attrs["rankdir"],
    ):
        # Create ungrouped nodes first
        for nid, nspec in node_specs.items():
            if nid not in grouped_node_ids:
                diagram_nodes[nid] = make_node(nspec)

        # Create grouped nodes inside Clusters
        for gspec in spec.get("groups", []):
            gid = gspec["id"]
            glabel = gspec.get("label", gid)
            bg_color = gspec.get("color", "#F5F5F5")
            gstyle = gspec.get("style", "dashed")

            # Cluster graph attrs
            cluster_attrs = {
                "bgcolor": bg_color,
                "style": gstyle,
                "fontsize": "12",
                "fontname": "Helvetica Bold",
            }

            with Cluster(glabel, graph_attr=cluster_attrs):
                for nid in gspec.get("nodes", []):
                    if nid in node_specs:
                        diagram_nodes[nid] = make_node(node_specs[nid])
                    else:
                        print(f"WARNING: Group '{gid}' references unknown node '{nid}'",
                              file=sys.stderr)

        # Create edges
        for conn in spec.get("connections", []):
            from_id = conn.get("from")
            to_id = conn.get("to")
            label = conn.get("label", "")
            style = conn.get("style", "solid")
            color = conn.get("color", edge_attrs["color"])
            penwidth = conn.get("penwidth", edge_attrs["penwidth"])

            if from_id not in diagram_nodes:
                print(f"WARNING: Connection from unknown node '{from_id}'", file=sys.stderr)
                continue
            if to_id not in diagram_nodes:
                print(f"WARNING: Connection to unknown node '{to_id}'", file=sys.stderr)
                continue

            edge = Edge(label=label, style=style, color=color, penwidth=str(penwidth))
            diagram_nodes[from_id] >> edge >> diagram_nodes[to_id]


def main():
    parser = argparse.ArgumentParser(
        description="Generate architecture diagrams from YAML/JSON specs."
    )
    parser.add_argument("spec", help="Path to YAML or JSON architecture spec file")
    parser.add_argument(
        "--output", "-o",
        help="Output file path (without extension). Defaults to spec filename stem.",
        default=None,
    )
    parser.add_argument(
        "--format", "-f",
        choices=["png", "svg", "pdf"],
        default="png",
        help="Output format (default: png)",
    )
    parser.add_argument(
        "--outdir", "-d",
        help="Output directory (default: current directory)",
        default=".",
    )

    args = parser.parse_args()

    spec_path = Path(args.spec)
    if not spec_path.exists():
        print(f"ERROR: Spec file not found: {args.spec}", file=sys.stderr)
        sys.exit(1)

    spec = load_spec(args.spec)

    if args.output:
        output_path = args.output
    else:
        output_dir = Path(args.outdir)
        output_dir.mkdir(parents=True, exist_ok=True)
        output_path = str(output_dir / spec_path.stem)

    print(f"Generating diagram: {output_path}.{args.format}")
    generate_diagram(spec, output_path, args.format)
    print(f"Done: {output_path}.{args.format}")


if __name__ == "__main__":
    main()
