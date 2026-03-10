"""
lambda_function.py
------------------
AWS Lambda entry-point for a single USOS (OrbitalNet OS) Satellite Node.

Architecture overview
~~~~~~~~~~~~~~~~~~~~~
Each satellite is deployed as an independent Lambda function subscribed to
two SNS standard topics:

  * usos-tasks  – carries new task announcements from the ground controller.
  * usos-bids   – carries bid messages that all satellites publish and receive.

Persistent node state (battery level, orbital position, status, last bid score)
is stored in a single DynamoDB table called *SwarmState*, keyed by ``node_id``.

Contract Net Protocol flow
~~~~~~~~~~~~~~~~~~~~~~~~~~
1. Ground controller publishes a TASK message → usos-tasks.
2. Every subscribed satellite Lambda fires simultaneously (Route 1).
   Each satellite reads its own state from DynamoDB, computes a bid score,
   publishes the bid to usos-bids, and sets its status to BIDDING.
3. Every bid on usos-bids triggers every satellite Lambda (Route 2).
   Each satellite compares the incoming bid score against its own stored
   score.  The node whose score is highest claims the task (EXECUTING),
   drains battery, simulates work, then returns to IDLE.  Losers simply
   return to IDLE immediately.
"""

import json
import logging
import os
import time
from decimal import Decimal

import boto3

import config

# ---------------------------------------------------------------------------
# Module-level setup
# ---------------------------------------------------------------------------

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

# Re-use boto3 clients across warm Lambda invocations for lower latency.
_dynamodb = boto3.resource("dynamodb")
_sns = boto3.client("sns")

# The unique identifier for THIS satellite node is injected as an environment
# variable so the same deployment package can serve multiple nodes.
NODE_ID: str = os.environ.get("NODE_ID", "satellite-node-default")


# ---------------------------------------------------------------------------
# DynamoDB helpers
# ---------------------------------------------------------------------------


def _get_table():
    """Return the DynamoDB Table resource for SwarmState.

    Using a helper keeps the table reference easy to mock in unit tests.
    """
    return _dynamodb.Table(config.TABLE_NAME)


def get_node_state(node_id: str) -> dict:
    """Fetch this node's current state record from DynamoDB.

    Returns a plain Python dict with keys:
        battery  (float)  – current charge level 0-100
        position (str)    – current sector, e.g. "SECTOR_3"
        status   (str)    – one of IDLE | BIDDING | EXECUTING
        last_score (float)– the bid score submitted in the most recent auction

    DynamoDB returns numeric attributes as ``decimal.Decimal``; this function
    converts them to ``float`` so the rest of the code can do normal arithmetic.

    If no record exists yet (first invocation), sensible defaults are returned
    and a fresh record is written to DynamoDB.
    """
    table = _get_table()
    response = table.get_item(Key={"node_id": node_id})
    item = response.get("Item")

    if item is None:
        logger.info("No existing state found for %s – initialising defaults.", node_id)
        default_state = {
            "node_id": node_id,
            "battery": Decimal(str(config.MAX_BATTERY)),
            "position": config.SECTORS[0],
            "status": "IDLE",
            "last_score": Decimal("0"),
        }
        table.put_item(Item=default_state)
        return {
            "battery": float(config.MAX_BATTERY),
            "position": config.SECTORS[0],
            "status": "IDLE",
            "last_score": 0.0,
        }

    # Convert Decimal → float for all numeric fields.
    return {
        "battery": float(item.get("battery", 0)),
        "position": str(item.get("position", config.SECTORS[0])),
        "status": str(item.get("status", "IDLE")),
        "last_score": float(item.get("last_score", 0)),
    }


def update_node_status(node_id: str, status: str) -> None:
    """Update only the *status* field of a node's DynamoDB record.

    Parameters
    ----------
    node_id:
        The unique satellite identifier (DynamoDB partition key).
    status:
        New status string – typically one of IDLE, BIDDING, or EXECUTING.
    """
    table = _get_table()
    table.update_item(
        Key={"node_id": node_id},
        UpdateExpression="SET #s = :s",
        ExpressionAttributeNames={"#s": "status"},
        ExpressionAttributeValues={":s": status},
    )
    logger.info("[%s] Status updated → %s", node_id, status)


def update_node_after_bid(node_id: str, score: float) -> None:
    """Persist the bid score and set status to BIDDING atomically.

    Storing *last_score* in DynamoDB ensures that when a competing bid
    arrives over usos-bids the node can compare without re-computing.

    Parameters
    ----------
    node_id:
        The unique satellite identifier (DynamoDB partition key).
    score:
        The numeric bid score just submitted to usos-bids.
    """
    table = _get_table()
    table.update_item(
        Key={"node_id": node_id},
        UpdateExpression="SET #s = :s, last_score = :ls",
        ExpressionAttributeNames={"#s": "status"},
        ExpressionAttributeValues={
            ":s": "BIDDING",
            ":ls": Decimal(str(score)),
        },
    )
    logger.info("[%s] Stored last_score=%.2f, status → BIDDING", node_id, score)


def drain_battery_and_execute(node_id: str) -> None:
    """Deduct BATTERY_DRAIN_TASK from the node's battery and mark EXECUTING.

    Uses a DynamoDB conditional update to prevent the battery from dropping
    below zero even under concurrent invocations.

    Parameters
    ----------
    node_id:
        The unique satellite identifier (DynamoDB partition key).
    """
    table = _get_table()
    table.update_item(
        Key={"node_id": node_id},
        UpdateExpression=(
            "SET #s = :s, battery = battery - :drain"
        ),
        ConditionExpression="battery >= :drain",
        ExpressionAttributeNames={"#s": "status"},
        ExpressionAttributeValues={
            ":s": "EXECUTING",
            ":drain": Decimal(str(config.BATTERY_DRAIN_TASK)),
        },
    )
    logger.info(
        "[%s] Battery drained by %d, status → EXECUTING",
        node_id,
        config.BATTERY_DRAIN_TASK,
    )


# ---------------------------------------------------------------------------
# SNS helpers
# ---------------------------------------------------------------------------


def publish_bid(node_id: str, score: float, task_location: str) -> None:
    """Publish this node's bid to the usos-bids SNS topic.

    The bid message is a JSON object understood by all peer nodes:
        {
            "node_id":       "<satellite-id>",
            "score":         <float>,
            "task_location": "<SECTOR_X>"
        }

    Parameters
    ----------
    node_id:
        The unique satellite identifier acting as the bidder.
    score:
        Calculated bid score for this auction round.
    task_location:
        The sector of the task being bid on – echoed so that receivers can
        verify they are comparing bids for the same task.
    """
    message_body = json.dumps(
        {"node_id": node_id, "score": score, "task_location": task_location}
    )
    _sns.publish(
        TopicArn=config.BIDS_TOPIC_ARN,
        Message=message_body,
        Subject="USOS_BID",
    )
    logger.info(
        "[%s] Published bid score=%.2f for task at %s",
        node_id,
        score,
        task_location,
    )


# ---------------------------------------------------------------------------
# Bid score calculator
# ---------------------------------------------------------------------------


def calculate_bid_score(battery: float, position: str, task_location: str) -> float:
    """Compute a bid score using battery level and proximity to the task.

    Formula
    ~~~~~~~
        score = (battery × 0.5) + (100 if position == task_location else 0)

    A node that is already in the task's sector receives a 100-point bonus,
    strongly favouring close-proximity nodes while still accounting for
    remaining energy.

    Parameters
    ----------
    battery:
        Current battery level (0-100).
    position:
        The node's current orbital sector.
    task_location:
        The sector where the task must be performed.

    Returns
    -------
    float
        Numeric bid score; higher is better.
    """
    proximity_bonus = 100.0 if position == task_location else 0.0
    score = (battery * 0.5) + proximity_bonus
    return round(score, 4)


# ---------------------------------------------------------------------------
# Route handlers
# ---------------------------------------------------------------------------


def handle_task_received(message: dict) -> None:
    """Handle a new task announcement arriving via the usos-tasks SNS topic.

    Implements the *Contract Net Protocol* CFP (Call For Proposals) response:
      1. Read this node's state from DynamoDB.
      2. Calculate a bid score.
      3. Publish the bid to usos-bids.
      4. Persist the bid score and set status to BIDDING in DynamoDB.

    Parameters
    ----------
    message:
        Parsed JSON message from the SNS notification.  Expected shape:
        ``{"type": "TASK", "location": "<SECTOR_X>"}``.
    """
    task_location: str = message.get("location", "")
    if task_location not in config.SECTORS:
        logger.warning(
            "[%s] Received task with unknown location '%s' – ignoring.",
            NODE_ID,
            task_location,
        )
        return

    # 1. Read current state.
    state = get_node_state(NODE_ID)
    battery = state["battery"]
    position = state["position"]

    logger.info(
        "[%s] Task received for %s. Current state: battery=%.1f, position=%s",
        NODE_ID,
        task_location,
        battery,
        position,
    )

    # 2. Calculate bid score.
    score = calculate_bid_score(battery, position, task_location)

    # 3. Publish bid.
    publish_bid(NODE_ID, score, task_location)

    # 4. Persist score + BIDDING status.
    update_node_after_bid(NODE_ID, score)


def handle_bid_received(message: dict) -> None:
    """Handle an incoming bid arriving via the usos-bids SNS topic.

    Implements the Contract Net Protocol award decision for this node:
      - If the incoming bid's score is strictly lower than this node's own
        stored bid score, THIS node wins the auction: it sets status to
        EXECUTING, drains battery, simulates work (3-second sleep), then
        returns to IDLE.
      - Otherwise (incoming score >= our score), this node yields: it simply
        sets its status back to IDLE.

    NOTE: A node ignores bids that it published itself to avoid self-comparison
    triggering a false win.

    Parameters
    ----------
    message:
        Parsed JSON message from the SNS notification.  Expected shape:
        ``{"node_id": "<id>", "score": <float>, "task_location": "<SECTOR_X>"}``.
    """
    incoming_node_id: str = message.get("node_id", "")
    incoming_score: float = float(message.get("score", 0.0))
    task_location: str = message.get("task_location", "")

    # Ignore bids this node published itself.
    if incoming_node_id == NODE_ID:
        logger.info("[%s] Ignoring own bid (self-echo from SNS fan-out).", NODE_ID)
        return

    # Read our stored last_score from DynamoDB.
    state = get_node_state(NODE_ID)
    my_score: float = state["last_score"]

    logger.info(
        "[%s] Bid received from %s: score=%.2f. My score=%.2f.",
        NODE_ID,
        incoming_node_id,
        incoming_score,
        my_score,
    )

    if my_score > incoming_score:
        # This node has the highest bid seen so far – claim the task.
        logger.info(
            "[%s] Won auction for task at %s (score %.2f > %.2f). Executing...",
            NODE_ID,
            task_location,
            my_score,
            incoming_score,
        )
        try:
            drain_battery_and_execute(NODE_ID)
        except _dynamodb.meta.client.exceptions.ConditionalCheckFailedException:
            # Battery already too low – gracefully yield.
            logger.warning(
                "[%s] Not enough battery to execute task. Yielding.", NODE_ID
            )
            update_node_status(NODE_ID, "IDLE")
            return

        # Simulate the actual task work.
        logger.info("[%s] Working on task at %s...", NODE_ID, task_location)
        time.sleep(3)

        update_node_status(NODE_ID, "IDLE")
        logger.info("[%s] Task complete. Status → IDLE.", NODE_ID)

    else:
        # A peer has a higher or equal score – yield immediately.
        logger.info(
            "[%s] Lost or tied auction (%.2f ≤ %.2f). Yielding.",
            NODE_ID,
            my_score,
            incoming_score,
        )
        update_node_status(NODE_ID, "IDLE")


# ---------------------------------------------------------------------------
# Lambda entry-point
# ---------------------------------------------------------------------------


def lambda_handler(event: dict, context) -> dict:
    """Main AWS Lambda entry-point for a USOS Satellite Node.

    This function is invoked by AWS Lambda whenever an SNS message is
    delivered to any topic this function is subscribed to.

    The SNS event structure wraps one or more records; each record contains
    the originating topic ARN and the JSON-encoded message body.  The handler
    routes each record to the correct business-logic function based on the
    topic ARN:

      * TASKS_TOPIC_ARN  → ``handle_task_received``
      * BIDS_TOPIC_ARN   → ``handle_bid_received``

    Parameters
    ----------
    event:
        The raw Lambda event dict injected by the AWS runtime.  For SNS
        triggers its top-level key is ``"Records"``, a list of SNS event
        records.
    context:
        The Lambda context object (execution metadata).  Not used directly
        but accepted per the Lambda handler contract.

    Returns
    -------
    dict
        A simple status response.  AWS Lambda does not use this return value
        for SNS-triggered invocations, but it is useful for manual test
        invocations and CloudWatch Logs.
    """
    logger.info("[%s] Lambda invoked. Event: %s", NODE_ID, json.dumps(event))

    records = event.get("Records", [])
    if not records:
        logger.warning("[%s] No SNS records found in event.", NODE_ID)
        return {"statusCode": 200, "body": "No records to process"}

    for record in records:
        sns_data = record.get("Sns", {})
        topic_arn: str = sns_data.get("TopicArn", "")
        raw_message: str = sns_data.get("Message", "{}")

        try:
            message = json.loads(raw_message)
        except json.JSONDecodeError as exc:
            logger.error(
                "[%s] Failed to parse SNS message body: %s – %s",
                NODE_ID,
                raw_message,
                exc,
            )
            continue

        logger.info(
            "[%s] Processing record from topic %s: %s",
            NODE_ID,
            topic_arn,
            message,
        )

        if topic_arn == config.TASKS_TOPIC_ARN:
            handle_task_received(message)

        elif topic_arn == config.BIDS_TOPIC_ARN:
            handle_bid_received(message)

        else:
            logger.warning(
                "[%s] Received message from unknown topic ARN: %s",
                NODE_ID,
                topic_arn,
            )

    return {"statusCode": 200, "body": "Processing complete"}
