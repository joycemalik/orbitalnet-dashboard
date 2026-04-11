import asyncio
import websockets
import redis.asyncio as redis
import json

# Connect to the async version of Redis
r = redis.Redis(host='localhost', port=6379, db=0, decode_responses=True)

async def broadcast_telemetry(websocket):
    print("UI Connected! Streaming telemetry...")
    while True:
        try:
            # Added a slight delay to stop Windows from panicking over socket spam
            await asyncio.sleep(0.5) 
            
            keys = await r.keys('STARLINK-*')
            subset_keys = keys[:1000] # Adjust this limit based on your UI performance
            
            if not subset_keys:
                continue

            raw_data = await r.mget(subset_keys)
            
            # Fetch active mission state for targeted laser drawing
            active_mission_raw = await r.get("ACTIVE_MISSION")
            
            payload = {
                "satellites": [json.loads(item) for item in raw_data if item],
                "active_mission": json.loads(active_mission_raw) if active_mission_raw else None
            }
            
            # Shove the massive payload down the WebSocket to the browser
            await websocket.send(json.dumps(payload))
            
        except redis.exceptions.ConnectionError:
            print("⚠️ Windows network bridge dropped. Auto-reconnecting...")
            await asyncio.sleep(1) # Wait a second for the socket to clear, then loop again
            continue
        except websockets.exceptions.ConnectionClosed:
            print("UI Disconnected.")
            break


async def main():
    print("Booting WebSocket Bridge on ws://localhost:8765...")
    async with websockets.serve(broadcast_telemetry, "127.0.0.1", 8765):
        await asyncio.Future()  # run forever

if __name__ == "__main__":
    asyncio.run(main())
