import asyncio
import websockets
import redis.asyncio as redis
import json

# Connect to the async version of Redis
r = redis.Redis(host='localhost', port=6379, db=0, decode_responses=True)

async def broadcast_telemetry(websocket):
    print("UI Connected! Streaming telemetry...")
    try:
        while True:
            # For the initial UI test, let's grab a subset to avoid overwhelming the browser
            # We will grab the first 200 keys for smooth rendering
            keys = await r.keys('STARLINK-*')
            subset_keys = keys[:900] 
            
            if not subset_keys:
                await asyncio.sleep(1)
                continue

            # Fetch the live JSON states for these satellites
            raw_data = await r.mget(subset_keys)
            
            # Filter out Nones and parse JSON
            payload = []
            for item in raw_data:
                if item:
                    payload.append(json.loads(item))
            
            # Shove the massive payload down the WebSocket to the browser
            await websocket.send(json.dumps(payload))
            
            # Match the 1Hz tick of the physics engine
            await asyncio.sleep(1)
            
    except websockets.exceptions.ConnectionClosed:
        print("UI Disconnected.")

async def main():
    print("Booting WebSocket Bridge on ws://localhost:8765...")
    async with websockets.serve(broadcast_telemetry, "localhost", 8765):
        await asyncio.Future()  # run forever

if __name__ == "__main__":
    asyncio.run(main())
