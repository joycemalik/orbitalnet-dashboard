# USOS (OrbitalNet OS) — Satellite Node Technical Specification

## 1. Overview

USOS is a distributed satellite autonomy simulation that implements the **Contract Net Protocol (CNP)** for autonomous task allocation across a swarm of satellite nodes. Each node is an independent AWS Lambda function that communicates exclusively via Amazon SNS and persists its state in Amazon DynamoDB.

This document describes the AWS-native serverless architecture that replaces the legacy local UDP-broadcast / flat-JSON-file design.

---

## 2. Why the Old Architecture Was Replaced

| Concern | Old Architecture (UDP + JSON files) | New Architecture (SNS + DynamoDB) |
|---|---|---|
| **Compute model** | Always-on processes on local VMs | Event-driven Lambda functions — zero cost at rest |
| **Node discovery** | UDP multicast (LAN only) | SNS fan-out — works globally across regions |
| **State durability** | Local JSON files (lost on restart) | DynamoDB (durable, consistent, replicated) |
| **Scalability** | Manual process management | AWS auto-scales Lambda concurrency automatically |
| **Fault tolerance** | Single point of failure per machine | Managed services with built-in redundancy |
| **Deployment** | Machine-specific setup | Deploy once; runs anywhere Lambda is available |

---

## 3. System Components

```
┌─────────────────────────────────────────────────────────┐
│                   Ground Controller                     │
│          (publishes task to usos-tasks SNS topic)       │
└────────────────────────┬────────────────────────────────┘
                         │ SNS fan-out
          ┌──────────────┼──────────────┐
          ▼              ▼              ▼
   ┌────────────┐ ┌────────────┐ ┌────────────┐
   │ Satellite  │ │ Satellite  │ │ Satellite  │
   │  Node A    │ │  Node B    │ │  Node C    │
   │ (Lambda)   │ │ (Lambda)   │ │ (Lambda)   │
   └─────┬──────┘ └─────┬──────┘ └─────┬──────┘
         │              │              │
         └──────────────┼──────────────┘
                        │ all publish bids to usos-bids
                        ▼
              ┌──────────────────┐
              │  usos-bids SNS   │
              │  topic (fan-out) │
              └──────────────────┘
                        │ each node receives every bid
                        ▼
              ┌──────────────────┐
              │   DynamoDB       │
              │  SwarmState      │
              │  table           │
              └──────────────────┘
```

### 3.1 AWS Lambda — Satellite Nodes

* Each satellite is **one Lambda function** with a unique `NODE_ID` environment variable.
* The same deployment package (zip) is reused for every satellite; only environment variables differ.
* Lambda is triggered **directly by SNS** — no polling or HTTP endpoints required.
* Cold-start latency is acceptable because SNS re-delivers if the Lambda fails.

### 3.2 Amazon SNS — Messaging Bus

Two standard SNS topics replace the old UDP broadcast bus:

| Topic | Logical Name | Direction | Purpose |
|---|---|---|---|
| `usos-tasks` | Tasks Topic | Ground → All Nodes | Announces a new task needing assignment |
| `usos-bids` | Bids Topic | Any Node → All Nodes | Carries bid proposals during an auction round |

**Why SNS Standard (not FIFO)?**
Standard topics deliver to *all* subscribed Lambda functions simultaneously (fan-out), which is exactly what CNP requires — every node must receive the same task announcement and every node must see every bid.

### 3.3 Amazon DynamoDB — Node State Store

**Table name:** `SwarmState`

**Primary key:** `node_id` (String, partition key — no sort key)

| Attribute | Type | Description |
|---|---|---|
| `node_id` | String | Unique satellite identifier, e.g. `satellite-node-A` |
| `battery` | Number | Current battery level (0 – 100). Stored as Decimal in DynamoDB |
| `position` | String | Current orbital sector, one of `SECTOR_1` … `SECTOR_6` |
| `status` | String | Current FSM state: `IDLE`, `BIDDING`, or `EXECUTING` |
| `last_score` | Number | Bid score submitted in the most recent auction round |

**DynamoDB Decimal handling:** boto3 maps Python floats to DynamoDB's `Number` type via `decimal.Decimal`. The codebase always converts DynamoDB `Decimal` values to `float` on read and back to `Decimal` (via `Decimal(str(value))`) on write to avoid precision loss.

---

## 4. Contract Net Protocol — Detailed Flow

### Step 1 – Task Announcement (CFP)

1. The ground controller publishes to **usos-tasks**:
   ```json
   { "type": "TASK", "location": "SECTOR_3" }
   ```
2. SNS delivers this message to **every** satellite Lambda simultaneously.

### Step 2 – Bid Submission (Proposal)

Each satellite Lambda (Execution Path 1 — `handle_task_received`):
1. Reads its own `battery` and `position` from DynamoDB.
2. Computes a bid score:
   $$\text{score} = (\text{battery} \times 0.5) + \begin{cases}100 & \text{if position} = \text{task\_location}\\0 & \text{otherwise}\end{cases}$$
3. Publishes its bid to **usos-bids**:
   ```json
   { "node_id": "satellite-node-A", "score": 150.0, "task_location": "SECTOR_3" }
   ```
4. Persists `last_score` and sets `status = BIDDING` in DynamoDB.

### Step 3 – Winner Selection (Award / Rejection)

Each satellite Lambda (Execution Path 2 — `handle_bid_received`) fires for every bid:
1. Self-bid messages are **ignored** (a node cannot award itself by reacting to its own bid).
2. The node reads its own `last_score` from DynamoDB.
3. **If `my_score > incoming_score`** → this node currently has the highest visible bid:
   - Sets `status = EXECUTING` and decrements `battery` by `BATTERY_DRAIN_TASK` (10) in a single atomic DynamoDB update with a conditional check (`battery >= drain`).
   - Sleeps 3 seconds to simulate task execution.
   - Sets `status = IDLE`.
4. **If `my_score ≤ incoming_score`** → another node has a higher or equal score:
   - Sets `status = IDLE` and yields.

> **Note on convergence:** Because every bid triggers the decision logic on every peer, the node with the true highest score will evaluate every other bid and consistently win, while all peers see a bid greater than or equal to their own and yield. The 3-second simulated-work guard also prevents duplicate execution across overlapping invocations.

---

## 5. Environment Variables

Set these on each Lambda function's configuration:

| Variable | Example Value | Description |
|---|---|---|
| `NODE_ID` | `satellite-node-A` | Unique identifier for this satellite |
| `TASKS_TOPIC_ARN` | `arn:aws:sns:us-east-1:123456789012:usos-tasks` | ARN of the task announcement topic |
| `BIDS_TOPIC_ARN` | `arn:aws:sns:us-east-1:123456789012:usos-bids` | ARN of the bid exchange topic |
| `TABLE_NAME` | `SwarmState` | DynamoDB table for node state persistence |

---

## 6. IAM Permissions Required

Each satellite Lambda's execution role needs:

```json
{
  "Effect": "Allow",
  "Action": [
    "dynamodb:GetItem",
    "dynamodb:PutItem",
    "dynamodb:UpdateItem"
  ],
  "Resource": "arn:aws:dynamodb:*:*:table/SwarmState"
},
{
  "Effect": "Allow",
  "Action": [
    "sns:Publish"
  ],
  "Resource": "<BIDS_TOPIC_ARN>"
}
```

---

## 7. Deployment Checklist

1. **DynamoDB:** Create the `SwarmState` table with `node_id` (String) as the partition key. Enable on-demand capacity mode.
2. **SNS Topics:** Create `usos-tasks` and `usos-bids` as Standard topics.
3. **Lambda:** For each satellite —
   - Upload the deployment zip (contains `lambda_function.py`, `config.py`, `requirements.txt` dependencies).
   - Set handler to `lambda_function.lambda_handler`.
   - Configure environment variables (`NODE_ID`, `TASKS_TOPIC_ARN`, `BIDS_TOPIC_ARN`, `TABLE_NAME`).
   - Attach the IAM execution role with the permissions above.
4. **SNS Subscriptions:** Subscribe each Lambda function to **both** `usos-tasks` and `usos-bids`.
5. **Test:** Publish a test task message manually from the AWS Console to `usos-tasks` and observe CloudWatch Logs for all nodes.

---

## 8. File Reference

| File | Purpose |
|---|---|
| `requirements.txt` | Lambda dependency list — only `boto3` (pre-installed in Lambda runtime but listed for local dev) |
| `config.py` | Constants (sectors, battery limits) and environment-variable-backed AWS resource identifiers |
| `lambda_function.py` | Lambda handler, SNS routing, DynamoDB access, bid-score logic, CNP state machine |
| `TECHNICAL_SPEC.md` | This document |
