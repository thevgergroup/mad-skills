#!/usr/bin/env python3
"""
architect.py — Natural language → architecture diagram, powered by Claude.

Routes to the appropriate rendering engine based on complexity:
  - engine: d2   → generate_d2.py   (nested VPC/AZ/subnet/K8s, hybrid)
  - engine: diagrams (default) → generate_diagram.py (simple, conceptual)

Usage:
    python3 architect.py "3-tier web app with CloudFront, ALB, EC2, RDS, Redis, S3"
    python3 architect.py "Hybrid AWS VPC with ECS and on-prem DC" --engine d2
    python3 architect.py "EKS platform with namespaces and service mesh" --engine d2
    python3 architect.py --file description.txt --format svg
    python3 architect.py --interactive
"""

import sys
import os
import json
import argparse
import subprocess
import tempfile
from pathlib import Path

import anthropic
import yaml


# ---------------------------------------------------------------------------
# System prompt for Claude
# ---------------------------------------------------------------------------

D2_SYSTEM_PROMPT = """You are an expert cloud architect who generates D2 architecture diagram specifications.

Given a natural language description of a system, you output a YAML specification that is rendered
using a D2-based generator (generate_d2.py). D2 excels at deeply nested infrastructure: VPCs,
Availability Zones, subnets, ECS clusters, EKS namespaces, and hybrid on-prem/cloud diagrams.

## Schema

```yaml
title: "Diagram Title"
engine: d2
layout: dagre  # dagre (default) or elk

# Optional: define or override connection styles
connection_types:
  https: { color: "#2196F3", style: solid }
  grpc: { color: "#9C27B0", style: solid }
  sql: { color: "#4CAF50", style: solid }
  vpn: { color: "#FF9800", style: dashed }
  kafka: { color: "#E91E63", style: solid }
  replication: { color: "#607D8B", style: dashed }

# Nested containers — use type to drive visual style
boundaries:
  - id: snake_case_id
    type: cloud | datacenter | vpc | availability-zone | subnet-public | subnet-private | ecs-cluster | k8s-cluster | k8s-namespace | region | account
    label: "Human readable label"
    direction: down  # optional: controls layout inside this container
    children:
      - id: child_id
        label: "Child label"
        # can be another boundary (with type/children) or a leaf node (with optional shape)
        shape: rectangle | cylinder | oval | hexagon | queue | diamond  # leaf nodes only

# Standalone nodes outside all boundaries
nodes:
  - id: node_id
    label: "Label"
    shape: oval  # optional

# Connections use full dot-path from root
connections:
  - from: boundary_id.child_id.leaf_id
    to: other_boundary.other_child
    type: https  # maps to connection_types
    label: "Optional label"
```

## Boundary type → visual style
- datacenter: orange border, warm fill — for on-prem / co-lo
- cloud: blue border, light blue fill — for AWS/GCP/Azure regions
- vpc: green dashed border — for VPCs / VNets
- availability-zone: purple dashed border — for AZs / zones
- subnet-public: yellow border — for public subnets
- subnet-private: indigo border — for private subnets
- ecs-cluster: teal border — for ECS clusters
- k8s-cluster: dark blue dashed — for EKS/GKE clusters
- k8s-namespace: purple dashed — for K8s namespaces
- region: grey border — for cloud regions
- account: pink border — for cloud accounts

## Connection dot-paths
When nodes are nested inside boundaries, the connection must use the FULL dot-path from root:
  - `aws.vpc_prod.az1.priv_subnet.ecs_cluster.api_service`
  - `on_prem.corp_router`

## Rules
1. All IDs must be snake_case and unique within their parent container
2. Connections reference the FULL dot-path from the root (not relative paths)
3. Standalone nodes (internet, S3, monitoring) go in the top-level `nodes` list
4. Use `shape: cylinder` for databases, `shape: oval` for internet/users, `shape: hexagon` for gateways/firewalls, `shape: queue` for message queues
5. Keep labels concise — multiline not needed, just use spaces
6. Output ONLY valid YAML, no markdown code blocks, no explanations
"""

SYSTEM_PROMPT = """You are an expert cloud architect who generates architecture diagram specifications.

Given a natural language description of a system, you output a YAML specification that can be
rendered into a clean architecture diagram using the Python `diagrams` library.

## Icon Reference

### AWS Icons
- Internet / Users: aws.general.InternetAlt1, aws.general.Users, aws.general.Client
- CDN: aws.network.CloudFront
- DNS: aws.network.Route53
- Load Balancers: aws.network.ALB (Application), aws.network.NLB (Network), aws.network.ELB (Classic)
- Compute: aws.compute.EC2, aws.compute.EC2Instances, aws.compute.ECS, aws.compute.EKS,
           aws.compute.Lambda, aws.compute.Fargate, aws.compute.ElasticBeanstalk,
           aws.compute.AutoScaling
- Databases: aws.database.RDS, aws.database.Aurora, aws.database.DynamoDB,
             aws.database.ElastiCache, aws.database.ElasticacheForRedis,
             aws.database.DocumentDB, aws.database.Redshift
- Storage: aws.storage.S3, aws.storage.EBS, aws.storage.EFS
- Messaging: aws.integration.SQS, aws.integration.SNS, aws.integration.Eventbridge,
             aws.integration.MQ
- API: aws.mobile.APIGateway
- Security: aws.security.IAM, aws.security.WAF, aws.security.Cognito,
            aws.security.SecretsManager
- Network: aws.network.VPC, aws.network.InternetGateway, aws.network.NATGateway,
           aws.network.DirectConnect, aws.network.TransitGateway
- Monitoring: aws.management.Cloudwatch

### GCP Icons
- Compute: gcp.compute.GCE, gcp.compute.GKE, gcp.compute.Functions, gcp.compute.CloudRun
- Load Balancing: gcp.network.LoadBalancing
- CDN: gcp.network.CDN
- Databases: gcp.database.SQL, gcp.database.Spanner, gcp.database.Firestore,
             gcp.database.Memorystore
- Storage: gcp.storage.GCS
- Messaging: gcp.analytics.Pub

### Azure Icons
- Compute: azure.compute.VM, azure.compute.AKS, azure.compute.FunctionApps,
           azure.compute.AppServices
- Load Balancers: azure.network.ApplicationGateway, azure.network.LoadBalancers
- CDN: azure.network.CDNProfiles
- Databases: azure.database.SQLDatabases, azure.database.CosmosDb,
             azure.database.CacheForRedis
- Storage: azure.storage.BlobStorage
- Messaging: azure.integration.ServiceBus, azure.integration.EventHubs

## Layout Guidelines

- Use `direction: LR` (left-to-right) for pipeline/flow architectures
- Use `direction: TB` (top-to-bottom) for hierarchical or tier-based architectures
- Group related nodes in clusters (e.g., "Auto Scaling Group", "VPC", "Database Tier")
- Use distinct colors for different tiers: web tier (#E8F4FD), app tier (#FEF9E7), data tier (#E8F8E8)
- Keep labels short and clear

## Output Format

Output ONLY valid YAML, no markdown code blocks, no explanations. The YAML must conform exactly
to this schema:

```
title: "Human-readable diagram title"
layout:
  direction: LR           # LR, TB, RL, BT
  ranksep: "1.5"          # spacing between ranks (increase for more space)
  nodesep: "0.9"          # spacing between nodes in same rank
  splines: ortho          # ortho (90-degree), curved, or line
  pad: "0.8"
  fontsize: "13"
  node_fontsize: "11"
  edge_fontsize: "10"
  node_width: "1.4"
  node_height: "1.8"
  edge_penwidth: "1.5"

nodes:
  - id: unique_snake_case_id
    label: "Short Display Label"
    icon: "provider.module.ClassName"

groups:
  - id: group_id
    label: "Group Label"
    color: "#E8F4FD"
    style: dashed
    nodes: [node_id_1, node_id_2]

connections:
  - from: source_node_id
    to: target_node_id
    label: "Optional edge label"
    style: solid    # solid or dashed
```

Rules:
1. Every node ID must be unique snake_case
2. Every node referenced in groups or connections must exist in the nodes list
3. connections reference node IDs, not group IDs
4. Keep edge labels very short (1-3 words max) or omit them
5. Aim for 5-15 nodes for readability; for larger systems, group aggressively
"""


def description_to_yaml(description: str, client: anthropic.Anthropic, engine: str = "auto") -> str:
    """Use Claude to convert a natural language description to YAML spec."""
    # Choose prompt based on engine
    if engine == "d2":
        system = D2_SYSTEM_PROMPT
    elif engine == "auto":
        # Use D2 for infrastructure-heavy descriptions, diagrams for simple ones
        d2_keywords = [
            "vpc", "subnet", "availability zone", "az ", "eks", "ecs", "kubernetes", "k8s",
            "hybrid", "on-prem", "on prem", "datacenter", "data center", "transit gateway",
            "direct connect", "vpn", "namespace", "microservice", "service mesh",
        ]
        desc_lower = description.lower()
        if any(kw in desc_lower for kw in d2_keywords):
            system = D2_SYSTEM_PROMPT
            engine = "d2"
        else:
            system = SYSTEM_PROMPT
            engine = "diagrams"
    else:
        system = SYSTEM_PROMPT

    message = client.messages.create(
        model="claude-haiku-4-5",
        max_tokens=4096,
        system=system,
        messages=[
            {
                "role": "user",
                "content": f"Generate a diagram specification for the following architecture:\n\n{description}",
            }
        ],
    )

    content = message.content[0].text.strip()

    # Strip markdown code fences if Claude added them despite instructions
    if content.startswith("```"):
        lines = content.split("\n")
        # Remove first line (```yaml or ```) and last line (```)
        content = "\n".join(lines[1:-1] if lines[-1].strip() == "```" else lines[1:])

    return content, engine


def validate_yaml_spec(yaml_str: str) -> tuple[bool, str, dict]:
    """
    Validate the YAML spec. Returns (is_valid, error_message, parsed_dict).
    """
    try:
        spec = yaml.safe_load(yaml_str)
    except yaml.YAMLError as e:
        return False, f"YAML parse error: {e}", {}

    if not isinstance(spec, dict):
        return False, "Spec must be a YAML mapping", {}

    errors = []

    # Check required sections
    if "nodes" not in spec:
        errors.append("Missing required 'nodes' section")
    else:
        node_ids = {n["id"] for n in spec["nodes"] if isinstance(n, dict) and "id" in n}

        # Validate groups reference valid nodes
        for g in spec.get("groups", []):
            for nid in g.get("nodes", []):
                if nid not in node_ids:
                    errors.append(f"Group '{g.get('id')}' references unknown node '{nid}'")

        # Validate connections reference valid nodes
        for conn in spec.get("connections", []):
            for key in ("from", "to"):
                nid = conn.get(key)
                if nid and nid not in node_ids:
                    errors.append(f"Connection references unknown node '{nid}'")

    if errors:
        return False, "\n".join(errors), spec
    return True, "", spec


def generate_from_description(
    description: str,
    output_path: str,
    output_format: str = "png",
    save_yaml: bool = False,
    yaml_path: str | None = None,
    engine: str = "auto",
    icons: str = "local",
) -> str:
    """
    Full pipeline: natural language → YAML → diagram.

    engine:
      "auto"     — detect from keywords (d2 for VPC/K8s/hybrid, diagrams for simple)
      "d2"       — force D2 engine (nested infrastructure)
      "diagrams" — force Python diagrams engine (simple conceptual)

    Returns the path to the generated diagram file.
    """
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        print("ERROR: ANTHROPIC_API_KEY environment variable not set", file=sys.stderr)
        sys.exit(1)

    client = anthropic.Anthropic(api_key=api_key)

    print("Generating diagram spec from description...")
    yaml_str, resolved_engine = description_to_yaml(description, client, engine)
    print(f"Engine: {resolved_engine}")

    # For diagrams engine, validate the spec
    if resolved_engine != "d2":
        is_valid, error, spec = validate_yaml_spec(yaml_str)
        if not is_valid:
            print(f"WARNING: Spec validation issues:\n{error}", file=sys.stderr)
            print("Attempting to render anyway...", file=sys.stderr)

    # Save YAML if requested
    if save_yaml:
        ypath = yaml_path or f"{output_path}.yaml"
        Path(ypath).write_text(yaml_str)
        print(f"Saved spec: {ypath}")

    # Write to temp file and dispatch to the right generator
    with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
        f.write(yaml_str)
        temp_yaml = f.name

    script_dir = Path(__file__).parent

    try:
        if resolved_engine == "d2":
            cmd = [
                sys.executable,
                str(script_dir / "generate_d2.py"),
                temp_yaml,
                "--output", output_path,
                "--icons", icons,
            ]
            # D2 only supports PNG natively (SVG too, but PNG is default)
            if output_format not in ("png", "svg"):
                print(f"WARNING: D2 engine supports png/svg, using png instead of {output_format}",
                      file=sys.stderr)
                output_format = "png"
        else:
            cmd = [
                sys.executable,
                str(script_dir / "generate_diagram.py"),
                temp_yaml,
                "--output", output_path,
                "--format", output_format,
            ]

        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode != 0:
            print(f"ERROR generating diagram:\n{result.stderr}", file=sys.stderr)
            sys.exit(1)
        if result.stdout:
            print(result.stdout, end="")
        if result.stderr:
            print(result.stderr, end="", file=sys.stderr)
    finally:
        os.unlink(temp_yaml)

    return f"{output_path}.{output_format}"


def interactive_mode(client: anthropic.Anthropic):
    """Interactive REPL for diagram generation."""
    print("Architecture Diagram Generator — Interactive Mode")
    print("Type your architecture description and press Enter twice to generate.")
    print("Type 'quit' or 'exit' to stop.\n")

    while True:
        print("Description (press Enter twice when done):")
        lines = []
        while True:
            line = input()
            if line.lower() in ("quit", "exit"):
                print("Goodbye!")
                return
            if line == "" and lines and lines[-1] == "":
                break
            lines.append(line)

        description = "\n".join(lines).strip()
        if not description:
            continue

        output_name = input("Output filename (without extension) [diagram]: ").strip()
        if not output_name:
            output_name = "diagram"

        fmt = input("Format [png/svg/pdf] (default: png): ").strip().lower()
        if fmt not in ("png", "svg", "pdf"):
            fmt = "png"

        save = input("Save YAML spec? [y/N]: ").strip().lower() == "y"

        eng = input("Engine [auto/d2/diagrams] (default: auto): ").strip().lower()
        if eng not in ("auto", "d2", "diagrams"):
            eng = "auto"

        icons = input("Icons [local/online/none] (default: local): ").strip().lower()
        if icons not in ("local", "online", "none"):
            icons = "local"

        output_path = generate_from_description(
            description,
            output_name,
            output_format=fmt,
            save_yaml=save,
            yaml_path=f"{output_name}_spec.yaml" if save else None,
            engine=eng,
            icons=icons,
        )
        print(f"\nDiagram saved: {output_path}\n")


def main():
    parser = argparse.ArgumentParser(
        description="Generate architecture diagrams from natural language using Claude."
    )

    input_group = parser.add_mutually_exclusive_group()
    input_group.add_argument(
        "description",
        nargs="?",
        help="Natural language architecture description",
    )
    input_group.add_argument(
        "--file", "-i",
        help="File containing the architecture description",
    )
    input_group.add_argument(
        "--interactive",
        action="store_true",
        help="Run in interactive mode",
    )

    parser.add_argument(
        "--output", "-o",
        help="Output file path (without extension). Default: 'diagram'",
        default="diagram",
    )
    parser.add_argument(
        "--format", "-f",
        choices=["png", "svg", "pdf"],
        default="png",
        help="Output format (default: png)",
    )
    parser.add_argument(
        "--save-yaml", "-s",
        action="store_true",
        help="Save the generated YAML spec alongside the diagram",
    )
    parser.add_argument(
        "--yaml-output",
        help="Path to save the YAML spec (implies --save-yaml)",
    )
    parser.add_argument(
        "--engine", "-e",
        choices=["auto", "d2", "diagrams"],
        default="auto",
        help=(
            "Rendering engine: 'd2' for nested VPC/K8s/hybrid diagrams, "
            "'diagrams' for simple conceptual diagrams, "
            "'auto' to detect from description keywords (default)"
        ),
    )
    parser.add_argument(
        "--icons",
        choices=["local", "online", "none"],
        default="local",
        help=(
            "Icon source for D2 diagrams: local (use installed diagrams PNGs), "
            "online (Terrastruct CDN URLs), none (shapes only). Default: local"
        ),
    )

    args = parser.parse_args()

    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        print("ERROR: ANTHROPIC_API_KEY environment variable not set", file=sys.stderr)
        sys.exit(1)

    if args.interactive:
        client = anthropic.Anthropic(api_key=api_key)
        interactive_mode(client)
        return

    if args.file:
        description = Path(args.file).read_text().strip()
    elif args.description:
        description = args.description
    else:
        parser.print_help()
        sys.exit(1)

    save_yaml = args.save_yaml or bool(args.yaml_output)
    yaml_path = args.yaml_output

    output_path = generate_from_description(
        description,
        args.output,
        output_format=args.format,
        save_yaml=save_yaml,
        yaml_path=yaml_path,
        engine=args.engine,
        icons=args.icons,
    )
    print(f"Diagram: {output_path}")


if __name__ == "__main__":
    main()
