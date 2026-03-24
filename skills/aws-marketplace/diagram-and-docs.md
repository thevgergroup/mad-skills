# AWS Marketplace Diagram and Documentation Guide

## When to read this doc

Read this when creating the architecture diagram required for Marketplace submission, writing product listing content, or generating deployment documentation.

---

## Architecture diagram requirements (Marketplace)

Before picking a tool:

- **Dimensions**: exactly **1100 × 700 pixels** — AWS rejects other sizes
- **Format**: PNG (preferred) or JPG for upload; SVG is acceptable for the listing but PNG is safer
- **Icons**: Must use current AWS Architecture Icons — not custom icons, competitor logos, or third-party graphics
- **Must show**: all VPCs, subnets, network flows, integration points between your services and buyer's AWS account
- **Labels**: All services, data flows, and network boundaries must be labeled clearly

---

## Generating diagrams with drawio-mcp (AI-assisted)

**drawio-mcp** (https://github.com/jgraph/drawio-mcp) is the official MCP server for draw.io, maintained by jGraph. It lets an AI agent generate and open draw.io diagrams directly. This is the recommended path when you want Claude to draft the diagram.

### Setup options

**Option A — MCP Tool Server (recommended for Claude Code)**

Install and add to your MCP config:

```bash
npx @drawio/mcp
```

Claude Desktop / Claude Code `settings.json`:
```json
{
  "mcpServers": {
    "drawio": {
      "command": "npx",
      "args": ["@drawio/mcp"]
    }
  }
}
```

Exposes three tools:
- `open_drawio_xml` — generate a diagram from mxGraphModel XML (full control)
- `open_drawio_csv` — generate from CSV data (org charts, component lists)
- `open_drawio_mermaid` — convert Mermaid.js syntax to an editable draw.io diagram (simplest for AI generation)

**Option B — MCP App Server (hosted, no install)**

Add to your MCP client:
```
https://mcp.draw.io/mcp
```
Exposes `create_diagram` — renders inline as interactive iframe. Requires an MCP host that supports MCP Apps (Claude.ai web).

**Option C — Claude Code Skill (no MCP required)**

The repo includes a CLAUDE.md-based skill that generates `.drawio` files directly with optional PNG/SVG/PDF export. No installation needed.

### How Claude uses drawio-mcp

Provide a description of the architecture and ask Claude to generate the diagram. Claude produces Mermaid or XML content and calls the appropriate tool — the diagram opens in draw.io editor for review and export.

**Example prompt:**
```
Use drawio-mcp to create an AWS Marketplace architecture diagram for a container product
deployed on ECS Fargate. Show: VPC with public/private subnets across 2 AZs, ALB in
public subnets, ECS tasks in private subnets, RDS in private subnets, NAT Gateway,
Marketplace ECR image pull path, and the metering API call to Marketplace. Use AWS
architecture icon style. Canvas size should be 1100x700px for Marketplace submission.
```

### After generation

1. Review the opened diagram in draw.io
2. Load the AWS icon library (see below) to replace placeholder shapes with official icons
3. Export: **File → Export As → PNG** — set width to 1100px, height to 700px
4. Upload to Marketplace listing via portal or `UpdateInformation` changeset

---

## AWS Architecture Icons

**Official source**: https://aws.amazon.com/architecture/icons/

Icons are released quarterly. Always use the current release — AWS reviewers have flagged outdated icon styles.

### For draw.io: community library (recommended)

The built-in draw.io AWS libraries are outdated (2017-2019 era). Use the community-maintained library instead:

**m-radzikowski AWS icons for diagrams.net**
- GitHub: https://github.com/m-radzikowski/diagrams-aws-icons
- Load directly in draw.io: File → Open Library from → URL → paste raw GitHub `.xml` URL
- Covers all current AWS services with current icon styles

**How to load:**
1. Open draw.io / diagrams.net
2. File → Open Library From → URL
3. Paste: `https://raw.githubusercontent.com/m-radzikowski/diagrams-aws-icons/master/aws-en.xml`
4. Click OK — the AWS icon library appears in the left panel

**Alternative — clearscale/aws23-draw.io**: https://github.com/clearscale/aws23-draw.io (2023-era icons)

### For draw.io: built-in library (fallback)

1. Click **More Shapes** at the bottom-left panel
2. Networking → check AWS libraries → Apply
3. Or open with pre-loaded AWS library: `https://www.draw.io/?splash=0&libs=aws4`

---

## Diagram tool comparison

| Tool | Cost | AWS Icons | Best for Marketplace diagrams |
|---|---|---|---|
| **draw.io + m-radzikowski library** | Free | Community (current) | ✅ Best value — free, full control, exports PNG at exact size |
| **Cloudcraft** | $49-120/user/month | Native, current | ✅ Best looking — 3D isometric style, AWS-accurate |
| **AWS Infrastructure Composer** | Free (AWS Console) | Native | ⚠️ Generates from CloudFormation, not polished enough for submission |
| **Lucidchart** | Paid (limited free) | Official AWS integration | ✅ Good if team already uses it |
| **Miro** | Free (3 boards) | Template library | ⚠️ Limited free tier, better for collaboration than precise diagrams |

**Recommendation**: draw.io with the m-radzikowski community library for most sellers. Cloudcraft if you want the most polished result and are willing to pay.

---

## What to put in the Marketplace architecture diagram

The diagram must show the complete deployment topology from the buyer's perspective. Include:

### Required elements

```
┌─────────────────────────── AWS Account (Buyer) ───────────────────────────┐
│                                                                              │
│  ┌─────────────────────────── VPC ─────────────────────────────────────┐   │
│  │                                                                       │   │
│  │  ┌── Public Subnet AZ-1 ──┐   ┌── Public Subnet AZ-2 ──┐           │   │
│  │  │  [ALB]   [NAT GW]      │   │  [ALB]   [NAT GW]      │           │   │
│  │  └────────────────────────┘   └────────────────────────┘           │   │
│  │                                                                       │   │
│  │  ┌── Private Subnet AZ-1 ─┐   ┌── Private Subnet AZ-2 ─┐           │   │
│  │  │  [ECS Task: API]        │   │  [ECS Task: API]        │           │   │
│  │  │  [ECS Task: Worker]     │   │  [ECS Task: Worker]     │           │   │
│  │  └────────────────────────┘   └────────────────────────┘           │   │
│  │                                                                       │   │
│  │  ┌── Private Subnet AZ-1 ─┐   ┌── Private Subnet AZ-2 ─┐           │   │
│  │  │  [RDS Primary]          │   │  [RDS Standby]          │           │   │
│  │  └────────────────────────┘   └────────────────────────┘           │   │
│  │                                                                       │   │
│  └───────────────────────────────────────────────────────────────────┘   │
│                                                                              │
│  ┌── Secrets Manager ──┐  ┌── CloudWatch Logs ──┐                         │
└──────────────────────────────────────────────────────────────────────────┘

External:
  [AWS Marketplace ECR] ──pull── ECS Tasks
  [Marketplace Metering API] ◄── ECS Tasks (MeterUsage call)
  [Buyer Browser] ──HTTPS──► ALB
```

### Labeling conventions

- Label each subnet with: "Private Subnet (AZ-a)" / "Public Subnet (AZ-a)"
- Label all network flows with protocol and direction: `HTTPS (443)`, `PostgreSQL (5432)`
- Show the Marketplace ECR pull path — reviewers look for this
- Show the `MeterUsage` call from ECS to Marketplace Metering API — this validates your metering integration at a glance
- Distinguish buyer's infrastructure (grey/blue) from your product's services (orange/AWS-colored)

### Common mistakes

- Missing the Marketplace ECR image pull path
- No network flow labels (arrows with no protocol/port labels)
- Showing only one AZ (must show multi-AZ for production products)
- Missing secrets/config management (Secrets Manager or Parameter Store)
- Using outdated AWS icons (older styles trigger reviewer scrutiny)

---

## Product listing content templates

### Short description (≤350 characters)

Structure: `[What it does] for [who]. [Key differentiator]. [Deployment model].`

Example:
```
AI-powered code review and repository maintenance platform for engineering teams.
Automates dependency updates, security scanning, and technical debt tracking.
Deploys to your AWS account via CloudFormation in under 15 minutes.
```

Avoid: generic adjectives ("powerful", "innovative", "enterprise-grade"), claims without specifics ("best in class"), vague descriptions ("an AI platform for developers").

### Long description (≤5,000 characters)

Recommended sections:
1. **What it does** (2-3 sentences): concrete capability description
2. **Key features** (3-5 bullets): specific, measurable, technical
3. **Deployment model**: how it deploys, what AWS services it creates, what the buyer controls
4. **Prerequisites**: what the buyer needs before deploying (VPC, GitHub token, etc.)
5. **Support**: how to get help

### Highlights (up to 3 bullets, ~200 chars each)

These appear prominently on the listing card. Make them specific:
- ✅ "Automated dependency updates with PR creation — integrates with GitHub, GitLab, Bitbucket"
- ❌ "Powerful AI-driven automation for modern development teams"

### Usage instructions

Must be complete enough that a buyer can deploy without contacting you. Structure:

```markdown
## Prerequisites
- AWS account with permissions to create ECS, RDS, ALB, and IAM resources
- Existing VPC with at least 2 public and 2 private subnets
- GitHub Personal Access Token (or equivalent) with repo read/write scope

## Deployment Steps
1. Subscribe to the product in AWS Marketplace
2. Click "Launch CloudFormation stack" or copy the template URL
3. Fill in parameters: [list key parameters with descriptions]
4. Wait ~10 minutes for the stack to reach CREATE_COMPLETE
5. Access the service at the ServiceURL output

## Container Images
This product uses images from the AWS Marketplace ECR registry. Images are
automatically accessible to active subscribers — no separate ECR authentication required.

## Post-Deployment Configuration
[Any steps required after stack creation]

## Support
[Support email/URL]
```

### Release notes template

```markdown
## v1.2.0 — [Month Year]

### What's new
- [Feature]: [brief description]
- [Feature]: [brief description]

### Improvements
- [Improvement]: [brief description]

### Bug fixes
- [Fix]: [brief description]

### Upgrade instructions
[If any manual steps are required to upgrade from the previous version]
[If no steps required: "Existing deployments can upgrade by updating the
 container image URIs in your ECS task definitions to point to v1.2.0."]
```

---

## Documentation required for Marketplace submission

| Document | Required | Where to provide |
|---|---|---|
| Architecture diagram (1100×700px PNG) | Required for listing approval | Upload in portal or via `UpdateInformation` |
| Short description | Required | `UpdateInformation` change type |
| Long description | Required | `UpdateInformation` change type |
| Usage/deployment instructions | Required | DeliveryOption `UsageInstructions` field |
| EULA | Required | `UpdateLegalTerms` change type |
| Privacy Policy URL | Required | `UpdateInformation` change type |
| Support contact | Required | `UpdateSupportTerms` change type |
| Screenshots (at least 1) | Required | Upload in portal |
| CloudFormation template URL | Strongly recommended for container products | `UpdateDeliveryOptions` DeploymentResources |
| Release notes | Required per version | Version `ReleaseNotes` field in `AddDeliveryOptions` |
