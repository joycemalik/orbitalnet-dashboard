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
import random
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
        random_battery = float(random.randint(50, config.MAX_BATTERY))
        random_angle = float(random.uniform(0.0, 360.0))
        sector_idx = int(random_angle // 60) + 1
        random_position = f"SECTOR_{sector_idx}"
        
        default_state = {
            "node_id": node_id,
            "battery": Decimal(str(random_battery)),
            "position": random_position,
            "current_angle": Decimal(str(random_angle)),
            "status": "IDLE",
            "last_score": Decimal("0"),
            "last_updated": Decimal(str(time.time())),
            "reputation": Decimal("0"),
            "last_task_time": Decimal("0"),
            "last_task_id": "0",
        }
        table.put_item(Item=default_state)
        return {
            "battery": random_battery,
            "position": random_position,
            "current_angle": random_angle,
            "status": "IDLE",
            "last_score": 0.0,
            "last_updated": time.time(),
            "reputation": 0,
            "last_task_time": 0.0,
            "last_task_id": "0",
        }

    # Convert Decimal → float for all numeric fields.
    return {
        "battery": float(item.get("battery", 0)),
        "position": str(item.get("position", config.SECTORS[0])),
        "current_angle": float(item.get("current_angle", 0.0)),
        "status": str(item.get("status", "IDLE")),
        "last_score": float(item.get("last_score", 0)),
        "last_updated": float(item.get("last_updated", time.time())),
        "reputation": int(item.get("reputation", 0)),
        "last_task_time": float(item.get("last_task_time", 0)),
        "last_task_id": str(item.get("last_task_id", "0")),
    }


def update_node_status(node_id: str, status: str, battery: float = None, current_angle: float = None, position: str = None) -> None:
    """Update only the *status* field of a node's DynamoDB record.

    Parameters
    ----------
    node_id:
        The unique satellite identifier (DynamoDB partition key).
    status:
        New status string – typically one of IDLE, BIDDING, or EXECUTING.
    battery:
        Optional continuous battery float to sync with DB.
    current_angle:
        Optional continuous current angle to sync with DB.
    position:
        Optional sector position to sync with DB.
    """
    table = _get_table()
    
    update_expr = "SET #s = :s"
    expr_vals = {":s": status}
    
    if battery is not None and current_angle is not None and position is not None:
        update_expr += ", battery = :b, current_angle = :ca, #pos = :pos, last_updated = :lu"
        expr_vals[":b"] = Decimal(str(battery))
        expr_vals[":ca"] = Decimal(str(current_angle))
        expr_vals[":pos"] = position
        expr_vals[":lu"] = Decimal(str(time.time()))

    expression_attribute_names = {"#s": "status"}
    if position is not None:
        expression_attribute_names["#pos"] = "position"

    table.update_item(
        Key={"node_id": node_id},
        UpdateExpression=update_expr,
        ExpressionAttributeNames=expression_attribute_names,
        ExpressionAttributeValues=expr_vals,
    )
    logger.info("[%s] Status updated → %s", node_id, status)


def update_node_after_bid(node_id: str, score: float, task_id: str, battery: float, current_angle: float, position: str) -> None:
    """Persist the bid score and set status to BIDDING atomically.

    Storing *last_score* in DynamoDB ensures that when a competing bid
    arrives over usos-bids the node can compare without re-computing.

    Parameters
    ----------
    node_id:
        The unique satellite identifier (DynamoDB partition key).
    score:
        The numeric bid score just submitted to usos-bids.
    task_id:
        The current sequence identifier for the task.
    battery:
        The newly calculated continuous battery float.
    current_angle:
        The newly calculated continuous current angle.
    position:
        The sector position.
    """
    table = _get_table()
    table.update_item(
        Key={"node_id": node_id},
        UpdateExpression="SET #s = :s, last_score = :ls, last_task_id = :tid, battery = :b, current_angle = :ca, #pos = :pos, last_updated = :lu",
        ExpressionAttributeNames={"#s": "status", "#pos": "position"},
        ExpressionAttributeValues={
            ":s": "BIDDING",
            ":ls": Decimal(str(score)),
            ":tid": task_id,
            ":b": Decimal(str(battery)),
            ":ca": Decimal(str(current_angle)),
            ":pos": position,
            ":lu": Decimal(str(time.time())),
        },
    )
    logger.info("[%s] Stored last_score=%.2f, status → BIDDING", node_id, score)

def drain_battery_and_execute(node_id: str, battery: float, current_angle: float, position: str) -> None:
    """Deduct BATTERY_DRAIN_TASK from the node's battery and mark EXECUTING.

    Uses a DynamoDB conditional update to prevent the battery from dropping
    below zero even under concurrent invocations. Also increments reputation
    and sets last_task_time.

    Parameters
    ----------
    node_id:
        The unique satellite identifier (DynamoDB partition key).
    battery:
        The calculated continuous battery state.
    current_angle:
        The calculated continuous current angle.
    position:
        The sector position.
    """
    table = _get_table()
    
    # We update the battery to continuous value before draining
    new_battery = max(0, battery - config.BATTERY_DRAIN_TASK)
    
    table.update_item(
        Key={"node_id": node_id},
        UpdateExpression=(
            "SET #s = :s, battery = :new_batt, current_angle = :ca, #pos = :pos, reputation = reputation + :rep_inc, last_task_time = :ltt, last_updated = :lu"
        ),
        ConditionExpression="battery >= :drain",
        ExpressionAttributeNames={"#s": "status", "#pos": "position"},
        ExpressionAttributeValues={
            ":s": "EXECUTING",
            ":new_batt": Decimal(str(new_battery)),
            ":ca": Decimal(str(current_angle)),
            ":pos": position,
            ":rep_inc": Decimal("1"),
            ":ltt": Decimal(str(time.time())),
            ":lu": Decimal(str(time.time())),
            ":drain": Decimal(str(config.BATTERY_DRAIN_TASK)),
        },
    )
    logger.info(
        "[%s] Battery drained by %d, status → EXECUTING, reputation +1",
        node_id,
        config.BATTERY_DRAIN_TASK,
    )


# ---------------------------------------------------------------------------
# SNS helpers
# ---------------------------------------------------------------------------


def publish_bid(node_id: str, score: float, task_location: str, task_id: str) -> None:
    """Publish this node's bid to the usos-bids SNS topic.

    The bid message is a JSON object understood by all peer nodes:
        {
            "node_id":       "<satellite-id>",
            "score":         <float>,
            "task_location": "<SECTOR_X>",
            "task_id":       "<task-id>"
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
    task_id:
        The sequence ID of the task to prevent processing stale bids.
    """
    message_body = json.dumps(
        {"node_id": node_id, "score": score, "task_location": task_location, "task_id": task_id}
    )
    _sns.publish(
        TopicArn=config.BIDS_TOPIC_ARN,
        Message=message_body,
        Subject="USOS_BID",
    )
    logger.info(
        "[%s] Published bid score=%.2f for task at %s (task_id: %s)",
        node_id,
        score,
        task_location,
        task_id
    )


# ---------------------------------------------------------------------------
# Bid score calculator
# ---------------------------------------------------------------------------

def update_orbital_state(state):
    now = time.time()
    last_ts = float(state.get('last_updated', now))
    elapsed_mins = (now - last_ts) / 60.0
    
    # 1. Update Angle
    last_angle = float(state.get('current_angle', 0.0))
    new_angle = (last_angle + (config.ORBITAL_SPEED * elapsed_mins)) % 360.0
    
    # 2. Map Angle to Sector Name
    sector_idx = int(new_angle // 60) + 1
    new_sector = f"SECTOR_{sector_idx}"
    
    # 3. Dynamic Battery Calculation
    battery = float(state.get('battery', 100.0))
    # Passive drain happens everywhere
    battery -= config.PASSIVE_DRAIN_RATE * elapsed_mins
    
    # Rapid recharge happens only in the sunlit hemisphere
    if config.SUNLIT_ANGLE_RANGE[0] <= new_angle <= config.SUNLIT_ANGLE_RANGE[1]:
        battery += config.SOLAR_RECHARGE_RATE * elapsed_mins
        
    return {
        "battery": min(100.0, max(0.0, battery)),
        "position": new_sector,
        "current_angle": new_angle,
        "last_updated": now
    }


def calculate_bid_score(battery: float, position: str, task_location: str, reputation: int, last_task_time: float) -> float:
    # Base: Proximity is 40% of the weight
    proximity_score = 100 if position == task_location else 0
    
    # Reliability: Nodes that have done more work are trusted more (up to 20 pts)
    reputation_bonus = min(20, reputation * 0.5)
    
    # Readiness: If it worked in the last 2 mins, it's "fatigued" (-30 pts)
    cooldown_penalty = 30 if (time.time() - last_task_time) < 120 else 0
    
    # Combined Raft-style score
    score = (battery * 0.5) + proximity_score + reputation_bonus - cooldown_penalty
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
        ``{"type": "TASK", "location": "<SECTOR_X>", "task_id": "12345"}``.
    """
    task_location: str = message.get("location", "")
    task_id: str = message.get("task_id", str(time.time()))
    if task_location not in config.SECTORS:
        logger.warning(
            "[%s] Received task with unknown location '%s' – ignoring.",
            NODE_ID,
            task_location,
        )
        return

    # 1. Read current state.
    state = get_node_state(NODE_ID)
    
    # Apply continuous orbital and battery logic
    orbital_state = update_orbital_state(state)
    battery = orbital_state["battery"]
    position = orbital_state["position"]
    current_angle = orbital_state["current_angle"]
    reputation = state["reputation"]
    last_task_time = state["last_task_time"]

    logger.info(
        "[%s] Task received for %s. Current state: battery=%.1f, position=%s, angle=%.1f",
        NODE_ID,
        task_location,
        battery,
        position,
        current_angle
    )

    # 2. Calculate bid score.
    score = calculate_bid_score(battery, position, task_location, reputation, last_task_time)

    # 3. Publish bid.
    publish_bid(NODE_ID, score, task_location, task_id)

    # 4. Persist score + BIDDING status.
    update_node_after_bid(NODE_ID, score, task_id, battery, current_angle, position)


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
        ``{"node_id": "<id>", "score": <float>, "task_location": "<SECTOR_X>", "task_id": "12345"}``.
    """
    incoming_node_id: str = message.get("node_id", "")
    incoming_score: float = float(message.get("score", 0.0))
    task_location: str = message.get("task_location", "")
    incoming_task_id: str = str(message.get("task_id", ""))

    # Ignore bids this node published itself.
    if incoming_node_id == NODE_ID:
        logger.info("[%s] Ignoring own bid (self-echo from SNS fan-out).", NODE_ID)
        return

    # Read our stored state from DynamoDB.
    state = get_node_state(NODE_ID)
    my_score: float = state["last_score"]
    my_task_id: str = state["last_task_id"]
    orbital_state = update_orbital_state(state)
    battery = orbital_state["battery"]
    current_angle = orbital_state["current_angle"]
    position = orbital_state["position"]
    
    # Raft-inspired: Term/Sequence ID freshness check
    if my_task_id != incoming_task_id:
        logger.warning(
            "[%s] Ignoring stale bid from %s (task_id mismatch: %s != %s).",
            NODE_ID,
            incoming_node_id,
            incoming_task_id,
            my_task_id
        )
        return

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
            drain_battery_and_execute(NODE_ID, battery, current_angle, position)
        except _dynamodb.meta.client.exceptions.ConditionalCheckFailedException:
            # Battery already too low – gracefully yield.
            logger.warning(
                "[%s] Not enough battery to execute task. Yielding.", NODE_ID
            )
            update_node_status(NODE_ID, "IDLE", battery, current_angle, position)
            return

        try:
            # Simulate the actual task work.
            logger.info("[%s] Working on task at %s...", NODE_ID, task_location)
            time.sleep(3)
        finally:
            update_node_status(NODE_ID, "IDLE", battery, current_angle, position)
            logger.info("[%s] Task complete. Status → IDLE.", NODE_ID)

    else:
        # A peer has a higher or equal score – yield immediately.
        logger.info(
            "[%s] Lost or tied auction (%.2f ≤ %.2f). Yielding.",
            NODE_ID,
            my_score,
            incoming_score,
        )
        update_node_status(NODE_ID, "IDLE", battery, current_angle, position)


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
