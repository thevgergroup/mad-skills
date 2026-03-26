#!/usr/bin/env python3
"""
generate_d2.py — Generate D2 architecture diagrams from YAML specifications.

Handles deeply nested boundaries (VPC/AZ/subnet/cluster) with per-type visual
styling, full dot-path connections, and connection type styling.

Usage:
    python3 generate_d2.py examples/complex_aws_hybrid.yaml
    python3 generate_d2.py examples/complex_aws_hybrid.yaml --output output/my_diagram
    python3 generate_d2.py examples/eks_microservices.yaml --layout elk
    python3 generate_d2.py examples/complex_aws_hybrid.yaml --icons local
    python3 generate_d2.py examples/complex_aws_hybrid.yaml --icons online
    python3 generate_d2.py examples/complex_aws_hybrid.yaml --icons none
"""

import sys
import os
import argparse
import subprocess
import json
import time
import urllib.request
import urllib.parse
import urllib.error
import re
from pathlib import Path

import yaml


# ---------------------------------------------------------------------------
# Online icon support — Terrastruct icon service
# ---------------------------------------------------------------------------

TERRASTRUCT_BASE = "https://icons.terrastruct.com"
TERRASTRUCT_MANIFEST = "https://icons.terrastruct.com/icons.json"
ICON_CACHE_DIR = Path.home() / ".cache" / "architect-diagram" / "terrastruct"

# Verified against the live manifest at https://icons.terrastruct.com/icons.json
TERRASTRUCT_ALIASES = {
    "ec2": "aws/Compute/Amazon-EC2.svg",
    "ecs": "aws/Compute/Amazon-Elastic-Container-Service.svg",
    "eks": "aws/Compute/Amazon-Elastic-Kubernetes-Service.svg",
    "fargate": "aws/Compute/AWS-Fargate.svg",
    "lambda": "aws/Compute/AWS-Lambda.svg",
    "alb": "aws/Networking & Content Delivery/Elastic-Load-Balancing.svg",
    "nlb": "aws/Networking & Content Delivery/Elastic-Load-Balancing.svg",
    "cloudfront": "aws/Networking & Content Delivery/Amazon-CloudFront.svg",
    "route53": "aws/Networking & Content Delivery/Amazon-Route-53.svg",
    "nat": "aws/Networking & Content Delivery/Amazon-VPC_NAT-Gateway_light-bg.svg",
    "nat-gateway": "aws/Networking & Content Delivery/Amazon-VPC_NAT-Gateway_light-bg.svg",
    "tgw": "aws/Networking & Content Delivery/AWS-Transit-Gateway.svg",
    "transit-gateway": "aws/Networking & Content Delivery/AWS-Transit-Gateway.svg",
    "direct-connect": "aws/Networking & Content Delivery/AWS-Direct-Connect.svg",
    "vpc": "aws/Networking & Content Delivery/Amazon-VPC.svg",
    "igw": "aws/Networking & Content Delivery/Amazon-VPC_Internet-Gateway_light-bg.svg",
    "internet-gateway": "aws/Networking & Content Delivery/Amazon-VPC_Internet-Gateway_light-bg.svg",
    "waf": "aws/Security, Identity, & Compliance/AWS-WAF.svg",
    "iam": "aws/Security, Identity, & Compliance/AWS-Identify-and-Access-Management_IAM.svg",
    "secrets-manager": "aws/Security, Identity, & Compliance/AWS-Secrets-Manager.svg",
    "cognito": "aws/Security, Identity, & Compliance/Amazon-Cognito.svg",
    "rds": "aws/Database/Amazon-RDS.svg",
    "aurora": "aws/Database/Amazon-Aurora.svg",
    "dynamodb": "aws/Database/Amazon-DynamoDB.svg",
    "elasticache": "aws/Database/Amazon-ElastiCache.svg",
    "s3": "aws/Storage/Amazon-Simple-Storage-Service-S3.svg",
    "sqs": "aws/Application Integration/Amazon-Simple-Queue-Service-SQS.svg",
    "sns": "aws/Application Integration/Amazon-Simple-Notification-Service-SNS.svg",
    "cloudwatch": "aws/Management & Governance/Amazon-CloudWatch.svg",
    "api-gateway": "aws/Networking & Content Delivery/Amazon-API-Gateway.svg",
    "apigw": "aws/Networking & Content Delivery/Amazon-API-Gateway.svg",
    "msk": "aws/Analytics/Amazon-Managed-Streaming-for-Kafka.svg",
    "ecr": "aws/Compute/Amazon-EC2-Container-Registry.svg",
    "vpn": "aws/Networking & Content Delivery/AWS-Site-to-Site-VPN.svg",
}

# Module-level cache for manifest data
_terrastruct_manifest: list[str] | None = None
_terrastruct_index: dict[str, str] | None = None


def fetch_terrastruct_manifest() -> list[str]:
    """
    Fetch or load the Terrastruct icon manifest.
    Uses a local cache file that expires after 7 days.
    Returns a list of icon path strings.
    """
    global _terrastruct_manifest
    if _terrastruct_manifest is not None:
        return _terrastruct_manifest

    ICON_CACHE_DIR.mkdir(parents=True, exist_ok=True)
    cache_file = ICON_CACHE_DIR / "icons.json"
    max_age_seconds = 7 * 24 * 3600  # 7 days

    # Use cached file if fresh
    if cache_file.exists():
        age = time.time() - cache_file.stat().st_mtime
        if age < max_age_seconds:
            try:
                data = json.loads(cache_file.read_text())
                _terrastruct_manifest = data.get("icons", [])
                return _terrastruct_manifest
            except (json.JSONDecodeError, KeyError):
                pass  # Fall through to re-fetch

    # Fetch from network
    try:
        with urllib.request.urlopen(TERRASTRUCT_MANIFEST, timeout=15) as resp:
            raw = resp.read()
        data = json.loads(raw)
        cache_file.write_bytes(raw)
        _terrastruct_manifest = data.get("icons", [])
        return _terrastruct_manifest
    except Exception as exc:
        print(
            f"WARNING: Could not fetch Terrastruct manifest: {exc}",
            file=sys.stderr,
        )
        return []


def build_terrastruct_index(manifest: list[str]) -> dict[str, str]:
    """
    Build a normalised search index from the manifest path list.
    Keys are lowercase normalised strings; values are the original path strings.
    """
    index: dict[str, str] = {}

    for path in manifest:
        # Only index .svg files
        if not path.endswith(".svg"):
            continue

        stem = Path(path).stem  # e.g. "Amazon-EC2", "AWS-Fargate"

        # Strip common vendor prefixes
        normalised = stem
        for prefix in ("Amazon-", "AWS-", "Google-", "Azure-"):
            if normalised.startswith(prefix):
                normalised = normalised[len(prefix):]
                break

        # Lowercase, keep hyphens as separators
        normalised = normalised.lower()

        # Store full normalised name
        if normalised not in index:
            index[normalised] = path

        # Also store each hyphen-separated word as a short key (first match wins)
        parts = normalised.split("-")
        for part in parts:
            if len(part) > 2 and part not in index:
                index[part] = path

        # Store underscore-split sub-parts (e.g. Amazon-VPC_NAT-Gateway → nat, gateway)
        for segment in normalised.split("_"):
            segment = segment.strip("-")
            if len(segment) > 2 and segment not in index:
                index[segment] = path

    # Apply manual aliases on top (they take precedence)
    for alias, path in TERRASTRUCT_ALIASES.items():
        index[alias] = path

    return index


def _get_terrastruct_index() -> dict[str, str]:
    global _terrastruct_index
    if _terrastruct_index is None:
        manifest = fetch_terrastruct_manifest()
        _terrastruct_index = build_terrastruct_index(manifest)
    return _terrastruct_index


def _icon_local_path(icon_path: str) -> Path:
    """
    Compute the local cache path for a Terrastruct icon.

    D2's bundler URL-encodes path components when it reads icon paths from a D2
    file, so any spaces or special characters (spaces, '&', ',') in the path
    cause the open() call inside D2 to fail.  We therefore store every icon in a
    flat two-level structure:

        ICON_CACHE_DIR / <provider> / <sanitized-filename>.svg

    where <provider> is the first path component (e.g. "aws", "gcp") and
    <sanitized-filename> replaces every non-alphanumeric character (except
    hyphens and underscores) with a hyphen so that no special characters appear
    in the path D2 opens.
    """
    parts = icon_path.split("/")
    provider = parts[0] if len(parts) > 1 else "misc"
    filename = parts[-1]  # e.g. "Amazon-EC2.svg"
    # Replace anything that isn't a letter, digit, hyphen, underscore, or dot
    safe_filename = re.sub(r"[^\w.\-]", "-", filename)
    return ICON_CACHE_DIR / provider / safe_filename


def fetch_terrastruct_icon(icon_path: str) -> Path | None:
    """
    Download a single Terrastruct icon to the local cache if not already present.
    Icons are stored with sanitized paths (no spaces or special characters) so
    that D2's file bundler can reference them without encoding issues.
    Returns the local Path, or None on error.
    """
    local_path = _icon_local_path(icon_path)
    if local_path.exists():
        return local_path

    # Create parent directory
    local_path.parent.mkdir(parents=True, exist_ok=True)

    url = f"{TERRASTRUCT_BASE}/{urllib.parse.quote(icon_path, safe='/')}"
    print(f"Downloading icon: {icon_path}", file=sys.stderr)

    try:
        with urllib.request.urlopen(url, timeout=15) as resp:
            local_path.write_bytes(resp.read())
        return local_path
    except urllib.error.HTTPError as exc:
        print(f"WARNING: Icon not found (HTTP {exc.code}): {icon_path}", file=sys.stderr)
        return None
    except Exception as exc:
        print(f"WARNING: Failed to download icon {icon_path}: {exc}", file=sys.stderr)
        return None


def resolve_online_icon(icon_str: str) -> str | None:
    """
    Resolve an icon name to a locally cached SVG path via the Terrastruct service.
    Returns the absolute local path string, or None if not found.
    """
    key = icon_str.lower().strip().replace("_", "-").replace(" ", "-")
    index = _get_terrastruct_index()

    icon_path = index.get(key)
    if not icon_path:
        return None

    local = fetch_terrastruct_icon(icon_path)
    if local is None:
        return None
    return str(local)


# ---------------------------------------------------------------------------
# Icon registry
# ---------------------------------------------------------------------------

# Auto-detect resources directory from diagrams package install
def _detect_resources_dir() -> Path | None:
    try:
        import diagrams as _diagrams_pkg
        candidate = Path(_diagrams_pkg.__file__).parent.parent / "resources"
        if candidate.is_dir():
            return candidate
    except ImportError:
        pass
    return None


RESOURCES_DIR = _detect_resources_dir()

# Common aliases for short icon names → full path keys in the registry
ICON_ALIASES = {
    "alb": "aws/network/elb-application-load-balancer",
    "nlb": "aws/network/elb-network-load-balancer",
    "clb": "aws/network/elb-classic-load-balancer",
    "nat-gateway": "aws/network/nat-gateway",
    "nat_gateway": "aws/network/nat-gateway",
    "nat": "aws/network/nat-gateway",
    "transit-gateway": "aws/network/transit-gateway",
    "tgw": "aws/network/transit-gateway",
    "direct-connect": "aws/network/direct-connect",
    "vpc": "aws/network/vpc",
    "internet-gateway": "aws/network/internet-gateway",
    "igw": "aws/network/internet-gateway",
    "cloudfront": "aws/network/cloudfront",
    "route53": "aws/network/route-53",
    "waf": "aws/security/waf",
    "ec2": "aws/compute/ec2",
    "ecs": "aws/compute/elastic-container-service",
    "eks": "aws/compute/elastic-kubernetes-service",
    "fargate": "aws/compute/fargate",
    "lambda": "aws/compute/lambda",
    "rds": "aws/database/rds",
    "aurora": "aws/database/aurora",
    "elasticache": "aws/database/elasticache",
    "dynamodb": "aws/database/dynamodb",
    "s3": "aws/storage/s3",
    "sqs": "aws/integration/simple-queue-service-sqs",
    "sns": "aws/integration/simple-notification-service-sns",
    "kafka": "onprem/queue/kafka",
    "redis": "onprem/database/redis",
    "postgres": "onprem/database/postgresql",
    "mysql": "onprem/database/mysql",
    "prometheus": "onprem/monitoring/prometheus",
    "grafana": "onprem/monitoring/grafana",
    "nginx": "onprem/network/nginx",
    "k8s": "k8s/others/crd",
    "k8s-deploy": "k8s/compute/deploy",
    "deployment": "k8s/compute/deploy",
    "k8s-pod": "k8s/compute/pod",
    "pod": "k8s/compute/pod",
    "k8s-service": "k8s/network/svc",
    "service": "k8s/network/svc",
    "k8s-ingress": "k8s/network/ing",
    "ingress": "k8s/network/ing",
    "k8s-namespace": "k8s/others/crd",
    "internet": "generic/network/firewall",  # fallback — no internet icon in generic
    "firewall": "generic/network/firewall",
    "router": "generic/network/router",
    "user": "generic/other/user",
    "users": "generic/group/users",
    "secrets-manager": "aws/security/secrets-manager",
    "cloudwatch": "aws/management/cloudwatch",
    "iam": "aws/security/iam",
    "vpn": "aws/network/site-to-site-vpn",
    "api-gateway": "aws/network/api-gateway",
    "apigw": "aws/network/api-gateway",
    "cognito": "aws/security/cognito",
    "msk": "aws/integration/managed-streaming-for-kafka",
    "ecr": "aws/compute/ec2-container-registry",
}

def build_icon_registry(resources_dir: Path) -> dict[str, str]:
    """
    Walk the resources directory and build a dict mapping normalized names to
    absolute PNG paths.

    Keys:
      - Full path key: "aws/compute/ec2"  → /path/to/resources/aws/compute/ec2.png
      - Short alias: "ec2"                → same path (first match wins)
    """
    registry: dict[str, str] = {}
    short_registry: dict[str, str] = {}

    for png_path in sorted(resources_dir.rglob("*.png")):
        # Build the full key: provider/category/name (relative to resources_dir, no extension)
        rel = png_path.relative_to(resources_dir)
        parts = list(rel.parts)
        # Drop the .png suffix from the last part
        parts[-1] = parts[-1][:-4]  # remove ".png"
        full_key = "/".join(parts)

        registry[full_key] = str(png_path)

        # Short name alias (last part only), first match wins
        short_name = parts[-1]
        if short_name not in short_registry:
            short_registry[short_name] = str(png_path)

    # Merge short names into registry (don't overwrite full keys)
    for short, path in short_registry.items():
        if short not in registry:
            registry[short] = path

    return registry


# Module-level registry (built lazily)
_icon_registry: dict[str, str] | None = None


def _get_icon_registry() -> dict[str, str]:
    global _icon_registry
    if _icon_registry is None:
        if RESOURCES_DIR is not None and RESOURCES_DIR.is_dir():
            _icon_registry = build_icon_registry(RESOURCES_DIR)
        else:
            _icon_registry = {}
    return _icon_registry


def resolve_local_icon(icon_str: str) -> str | None:
    """
    Resolve an icon string to an absolute local PNG path.
    Returns None if not found.
    """
    registry = _get_icon_registry()
    key = icon_str.lower().strip()

    # Direct registry lookup (full key or short)
    if key in registry:
        return registry[key]

    # Check aliases
    if key in ICON_ALIASES:
        alias_key = ICON_ALIASES[key]
        if alias_key in registry:
            return registry[alias_key]
        # Try short name of alias
        short = alias_key.split("/")[-1]
        if short in registry:
            return registry[short]

    # Try normalizing: replace underscores/spaces with dashes
    normalized = key.replace("_", "-").replace(" ", "-")
    if normalized in registry:
        return registry[normalized]
    if normalized in ICON_ALIASES:
        alias_key = ICON_ALIASES[normalized]
        if alias_key in registry:
            return registry[alias_key]

    return None


def resolve_icon(icon_str: str, mode: str) -> str | None:
    """
    Resolve icon string based on mode: 'local', 'online', or 'none'.
    Returns the icon value (file path) or None.
    """
    if mode == "none" or not icon_str:
        return None
    if mode == "online":
        result = resolve_online_icon(icon_str)
        if result:
            return result
        # Fall back to local if online resolution fails for this specific icon
        return resolve_local_icon(icon_str)
    return resolve_local_icon(icon_str)


# ---------------------------------------------------------------------------
# Visual style mappings
# ---------------------------------------------------------------------------

BOUNDARY_STYLES = {
    "datacenter": {
        "fill": '"#FFF3E0"',
        "stroke": '"#E65100"',
        "stroke-width": 2,
        "border-radius": 4,
    },
    "cloud": {
        "fill": '"#E3F2FD"',
        "stroke": '"#1565C0"',
        "stroke-width": 2,
        "border-radius": 4,
    },
    "vpc": {
        "fill": '"#E8F5E9"',
        "stroke": '"#2E7D32"',
        "stroke-width": 2,
        "stroke-dash": 5,
        "border-radius": 4,
    },
    "availability-zone": {
        "fill": '"#F3E5F5"',
        "stroke": '"#6A1B9A"',
        "stroke-width": 1,
        "stroke-dash": 3,
        "border-radius": 4,
    },
    "subnet-public": {
        "fill": '"#FFFDE7"',
        "stroke": '"#F57F17"',
        "stroke-width": 1,
        "border-radius": 2,
    },
    "subnet-private": {
        "fill": '"#EDE7F6"',
        "stroke": '"#4527A0"',
        "stroke-width": 1,
        "border-radius": 2,
    },
    "ecs-cluster": {
        "fill": '"#E0F2F1"',
        "stroke": '"#00695C"',
        "stroke-width": 1,
        "border-radius": 2,
    },
    "k8s-cluster": {
        "fill": '"#E8EAF6"',
        "stroke": '"#283593"',
        "stroke-width": 2,
        "stroke-dash": 3,
        "border-radius": 4,
    },
    "k8s-namespace": {
        "fill": '"#F3E5F5"',
        "stroke": '"#7B1FA2"',
        "stroke-width": 1,
        "stroke-dash": 3,
        "border-radius": 2,
    },
    "security-group": {
        "fill": '"#FFF8E1"',
        "stroke": '"#F9A825"',
        "stroke-width": 1,
        "stroke-dash": 2,
        "border-radius": 2,
    },
    "region": {
        "fill": '"#ECEFF1"',
        "stroke": '"#546E7A"',
        "stroke-width": 2,
        "border-radius": 4,
    },
    "account": {
        "fill": '"#FCE4EC"',
        "stroke": '"#880E4F"',
        "stroke-width": 2,
        "border-radius": 6,
    },
    # Default for unknown types
    "default": {
        "fill": '"#F5F5F5"',
        "stroke": '"#9E9E9E"',
        "stroke-width": 1,
        "border-radius": 2,
    },
}

SHAPE_MAP = {
    "cylinder": "cylinder",
    "queue": "queue",
    "oval": "oval",
    "hexagon": "hexagon",
    "rectangle": "rectangle",
    "diamond": "diamond",
    "parallelogram": "parallelogram",
    "document": "document",
    "package": "package",
    "circle": "circle",
    "cloud": "cloud",
}

# Connection type → D2 style attributes
CONNECTION_STYLES = {
    "https": {"stroke": '"#2196F3"', "stroke-width": 2},
    "http": {"stroke": '"#64B5F6"', "stroke-width": 1},
    "grpc": {"stroke": '"#9C27B0"', "stroke-width": 2},
    "sql": {"stroke": '"#4CAF50"', "stroke-width": 2},
    "mysql": {"stroke": '"#4CAF50"', "stroke-width": 2},
    "postgres": {"stroke": '"#4CAF50"', "stroke-width": 2},
    "vpn": {"stroke": '"#FF9800"', "stroke-dash": 5, "stroke-width": 2},
    "bgp": {"stroke": '"#F44336"', "stroke-dash": 5, "stroke-width": 2},
    "direct_connect": {"stroke": '"#FF5722"', "stroke-width": 3},
    "replication": {"stroke": '"#607D8B"', "stroke-dash": 5, "stroke-width": 1},
    "amqp": {"stroke": '"#FF9800"', "stroke-width": 2},
    "kafka": {"stroke": '"#E91E63"', "stroke-width": 2},
    "tcp": {"stroke": '"#795548"', "stroke-width": 1},
    "tls": {"stroke": '"#009688"', "stroke-width": 2},
    "redis": {"stroke": '"#F44336"', "stroke-width": 1},
    "internal": {"stroke": '"#9E9E9E"', "stroke-dash": 3, "stroke-width": 1},
}


# ---------------------------------------------------------------------------
# D2 code generation
# ---------------------------------------------------------------------------

class D2Generator:
    """Generates D2 source from a YAML architecture spec."""

    def __init__(self, spec: dict, icon_mode: str = "local"):
        self.spec = spec
        self.title = spec.get("title", "Architecture Diagram")
        self.layout = spec.get("layout", "dagre")
        self.icon_mode = icon_mode
        self.lines: list[str] = []
        self.indent_level = 0
        # Map from yaml-path to d2-path for connection resolution
        # yaml path: list of ids like ["aws", "vpc_prod", "az1", "priv_subnet_1", "ecs_cluster", "svc_api"]
        self.node_paths: dict[str, str] = {}
        # Override connection styles from spec
        self.conn_type_styles = dict(CONNECTION_STYLES)
        for ctype, cstyle in spec.get("connection_types", {}).items():
            merged = dict(CONNECTION_STYLES.get(ctype, {}))
            if "color" in cstyle:
                merged["stroke"] = f'"{cstyle["color"]}"'
            if "style" in cstyle and cstyle["style"] == "dashed":
                merged["stroke-dash"] = 5
            if "width" in cstyle:
                merged["stroke-width"] = cstyle["width"]
            self.conn_type_styles[ctype] = merged

    # --- Output helpers ---

    def emit(self, line: str = ""):
        indent = "  " * self.indent_level
        self.lines.append(f"{indent}{line}" if line else "")

    def emit_block_open(self, header: str):
        self.emit(f"{header} {{")
        self.indent_level += 1

    def emit_block_close(self):
        self.indent_level -= 1
        self.emit("}")

    # --- Node path registry ---

    def register_node(self, yaml_path: list[str], d2_path: str):
        """Register a node so connections can reference it by yaml-path string."""
        key = ".".join(yaml_path)
        self.node_paths[key] = d2_path

    def resolve_ref(self, ref: str) -> str:
        """
        Resolve a connection reference to a D2 path.
        The ref is a dot-separated yaml-path like 'aws.vpc_prod.az1.priv_subnet_1.svc_api'.
        Returns the D2 dot-path string.
        """
        if ref in self.node_paths:
            return self.node_paths[ref]
        # If not found explicitly, fall back to the ref itself (may be a top-level node id)
        return ref

    # --- Shape / style emitters ---

    def emit_node_style(self, node: dict):
        """Emit D2 shape and optional style for a leaf node."""
        shape_str = node.get("shape", "")
        if shape_str and shape_str in SHAPE_MAP:
            self.emit(f"shape: {SHAPE_MAP[shape_str]}")

    def emit_boundary_style(self, btype: str, node: dict):
        """Emit D2 style block for a boundary container."""
        style = dict(BOUNDARY_STYLES.get(btype, BOUNDARY_STYLES["default"]))
        # Allow per-node overrides
        if "fill" in node:
            style["fill"] = f'"{node["fill"]}"'
        if "stroke" in node:
            style["stroke"] = f'"{node["stroke"]}"'

        for key, val in style.items():
            self.emit(f"style.{key}: {val}")

    # --- Recursive boundary rendering ---

    def render_boundary(self, node: dict, parent_yaml_path: list[str]):
        """
        Recursively render a boundary container and its children.
        parent_yaml_path is the yaml id path from root to this node's parent.
        """
        node_id = node["id"]
        label = node.get("label", node_id)
        btype = node.get("type", "default")
        yaml_path = parent_yaml_path + [node_id]
        d2_path = ".".join(yaml_path)

        self.register_node(yaml_path, d2_path)

        self.emit_block_open(f'{node_id}: "{label}"')

        # Direction override
        if "direction" in node:
            self.emit(f'direction: {node["direction"]}')

        # Style
        self.emit_boundary_style(btype, node)

        # Icon for container boundary (top-left positioning)
        icon_str = node.get("icon", "")
        if icon_str:
            icon_val = resolve_icon(icon_str, self.icon_mode)
            if icon_val:
                self.emit(f"icon: {icon_val}")
                self.emit("icon.near: top-left")

        # Children
        children = node.get("children", [])
        for child in children:
            child_type = child.get("type", "")
            if child_type or child.get("children"):
                # It's a sub-boundary
                self.render_boundary(child, yaml_path)
            else:
                # It's a leaf node
                self.render_leaf(child, yaml_path)

        self.emit_block_close()

    def render_leaf(self, node: dict, parent_yaml_path: list[str]):
        """Render a leaf node (no children)."""
        node_id = node["id"]
        label = node.get("label", node_id)
        yaml_path = parent_yaml_path + [node_id]
        d2_path = ".".join(yaml_path)

        self.register_node(yaml_path, d2_path)

        shape_str = node.get("shape", "")
        icon_str = node.get("icon", "")
        icon_val = resolve_icon(icon_str, self.icon_mode) if icon_str else None

        # If we have an icon for a leaf node, use shape: image
        if icon_val:
            self.emit_block_open(f'{node_id}: "{label}"')
            self.emit("shape: image")
            self.emit(f"icon: {icon_val}")
            self.emit_block_close()
        elif shape_str and shape_str in SHAPE_MAP:
            self.emit_block_open(f'{node_id}: "{label}"')
            self.emit(f"shape: {SHAPE_MAP[shape_str]}")
            self.emit_block_close()
        else:
            self.emit(f'{node_id}: "{label}"')

    # --- Top-level node rendering ---

    def render_standalone_node(self, node: dict):
        """Render a top-level standalone node."""
        node_id = node["id"]
        label = node.get("label", node_id)
        shape_str = node.get("shape", "")
        icon_str = node.get("icon", "")
        yaml_path = [node_id]
        d2_path = node_id

        self.register_node(yaml_path, d2_path)

        icon_val = resolve_icon(icon_str, self.icon_mode) if icon_str else None

        if icon_val:
            self.emit_block_open(f'{node_id}: "{label}"')
            self.emit("shape: image")
            self.emit(f"icon: {icon_val}")
            self.emit_block_close()
        elif shape_str and shape_str in SHAPE_MAP:
            self.emit_block_open(f'{node_id}: "{label}"')
            self.emit(f"shape: {SHAPE_MAP[shape_str]}")
            self.emit_block_close()
        else:
            self.emit(f'{node_id}: "{label}"')

    # --- Connection rendering ---

    def render_connection(self, conn: dict):
        """Render a single connection."""
        from_ref = self.resolve_ref(conn["from"])
        to_ref = self.resolve_ref(conn["to"])
        label = conn.get("label", "")
        ctype = conn.get("type", "")

        # Build style block
        style_attrs = {}
        if ctype and ctype in self.conn_type_styles:
            style_attrs = dict(self.conn_type_styles[ctype])

        # Per-connection overrides
        if "color" in conn:
            style_attrs["stroke"] = f'"{conn["color"]}"'
        if "style" in conn and conn["style"] == "dashed":
            style_attrs["stroke-dash"] = 5

        # Build the connection line
        if label:
            conn_header = f'{from_ref} -> {to_ref}: "{label}"'
        else:
            conn_header = f"{from_ref} -> {to_ref}"

        if style_attrs:
            self.emit_block_open(conn_header)
            for key, val in style_attrs.items():
                self.emit(f"style.{key}: {val}")
            self.emit_block_close()
        else:
            self.emit(conn_header)

    # --- Main generate method ---

    def generate(self) -> str:
        """Generate the full D2 source."""
        # Title
        self.emit("title: |md")
        self.indent_level += 1
        self.emit(f"# {self.title}")
        self.indent_level -= 1
        self.emit("|")
        self.emit()

        # Standalone nodes
        standalone = self.spec.get("nodes", [])
        if standalone:
            self.emit("# Standalone nodes")
            for node in standalone:
                self.render_standalone_node(node)
            self.emit()

        # Boundaries
        boundaries = self.spec.get("boundaries", [])
        if boundaries:
            self.emit("# Boundaries")
            for boundary in boundaries:
                self.render_boundary(boundary, [])
            self.emit()

        # Connections
        connections = self.spec.get("connections", [])
        if connections:
            self.emit("# Connections")
            for conn in connections:
                self.render_connection(conn)

        return "\n".join(self.lines)


# ---------------------------------------------------------------------------
# File I/O and CLI
# ---------------------------------------------------------------------------

def load_spec(path: str) -> dict:
    """Load YAML architecture spec."""
    p = Path(path)
    if not p.exists():
        print(f"ERROR: Spec file not found: {path}", file=sys.stderr)
        sys.exit(1)
    text = p.read_text()
    try:
        spec = yaml.safe_load(text)
    except yaml.YAMLError as e:
        print(f"ERROR: YAML parse error: {e}", file=sys.stderr)
        sys.exit(1)
    if not isinstance(spec, dict):
        print("ERROR: Spec must be a YAML mapping", file=sys.stderr)
        sys.exit(1)
    return spec


def render_d2(d2_source: str, output_path: str, layout: str = "dagre") -> str:
    """Write D2 source to file and invoke d2 to render PNG."""
    d2_file = output_path + ".d2"
    png_file = output_path + ".png"

    Path(d2_file).parent.mkdir(parents=True, exist_ok=True)
    Path(d2_file).write_text(d2_source)
    print(f"Wrote D2 source: {d2_file}")

    cmd = ["d2", "--layout", layout, d2_file, png_file]
    print(f"Running: {' '.join(cmd)}")
    result = subprocess.run(cmd, capture_output=True, text=True)

    if result.stdout:
        print(result.stdout, end="")
    if result.stderr:
        print(result.stderr, end="", file=sys.stderr)

    if result.returncode != 0:
        print(f"ERROR: d2 exited with code {result.returncode}", file=sys.stderr)
        sys.exit(1)

    return png_file


def main():
    parser = argparse.ArgumentParser(
        description="Generate D2 architecture diagrams from YAML specs."
    )
    parser.add_argument("spec", help="Path to YAML architecture spec file")
    parser.add_argument(
        "--output", "-o",
        help="Output path (without extension). Defaults to spec filename stem in same dir.",
        default=None,
    )
    parser.add_argument(
        "--layout",
        choices=["dagre", "elk"],
        default="dagre",
        help="D2 layout engine (default: dagre)",
    )
    parser.add_argument(
        "--print-d2",
        action="store_true",
        help="Print generated D2 source to stdout without rendering",
    )
    parser.add_argument(
        "--icons",
        choices=["local", "online", "none"],
        default="local",
        help=(
            "Icon source: local (use installed diagrams PNGs), "
            "online (Terrastruct CDN URLs), "
            "none (shapes only)"
        ),
    )

    args = parser.parse_args()

    spec = load_spec(args.spec)

    # Determine layout: spec can override, CLI can override spec
    spec_layout = spec.get("layout", "dagre")
    layout = args.layout if args.layout != "dagre" else spec_layout
    if layout not in ("dagre", "elk"):
        layout = "dagre"

    # Warn if local icons requested but resources dir not found
    if args.icons == "local" and RESOURCES_DIR is None:
        print(
            "WARNING: --icons=local requested but 'diagrams' package not found. "
            "Falling back to no icons. Install with: pip install diagrams",
            file=sys.stderr,
        )

    generator = D2Generator(spec, icon_mode=args.icons)
    d2_source = generator.generate()

    if args.print_d2:
        print(d2_source)
        return

    # Determine output path
    spec_path = Path(args.spec)
    if args.output:
        output_path = args.output
    else:
        output_path = str(spec_path.parent / spec_path.stem)

    png_path = render_d2(d2_source, output_path, layout)
    print(f"Done: {png_path}")


if __name__ == "__main__":
    main()
