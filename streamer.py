import asyncio
import websockets
import redis.asyncio as aioredis
from redis.exceptions import ConnectionError as RedisConnectionError
import json

# Connect to the async version of Redis
r = aioredis.Redis(host='localhost', port=6379, db=0, decode_responses=True)

async def broadcast_telemetry(websocket):
    print("UI Connected! Streaming telemetry...")
    while True:
        try:
            await asyncio.sleep(0.5)
            
            keys = await r.keys('STARLINK-*')
            subset_keys = keys[:1000]
            
            if not subset_keys:
                continue

            raw_data = await r.mget(subset_keys)
            
            # Fetch active mission state for targeted laser drawing
            active_mission_raw = await r.get("ACTIVE_MISSION")
            
            payload = {
                "satellites": [json.loads(item) for item in raw_data if item],
                "active_mission": json.loads(active_mission_raw) if active_mission_raw else None
            }
            
            await websocket.send(json.dumps(payload))

        except RedisConnectionError:
            print("⚠️ Redis connection dropped. Auto-reconnecting in 1s...")
            await asyncio.sleep(1)
            continue
        except websockets.exceptions.ConnectionClosed:
            print("UI Disconnected.")
            break
        except Exception as e:
            print(f"⚠️ Unexpected error: {e}. Retrying...")
            await asyncio.sleep(1)
            continue

async def main():
    print("Booting WebSocket Bridge on ws://localhost:8765...")
    async with websockets.serve(broadcast_telemetry, "localhost", 8765):
        await asyncio.Future()  # run forever

if __name__ == "__main__":
    asyncio.run(main())
