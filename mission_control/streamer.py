import asyncio
import websockets
import websockets.exceptions
import redis.asyncio as aioredis
from redis.exceptions import ConnectionError as RedisConnectionError
import json
import logging

# Silence noisy Streamlit iframe reconnect handshakes and normal browser disconnects
logging.getLogger("websockets.server").setLevel(logging.CRITICAL)
logging.getLogger("websockets.protocol").setLevel(logging.CRITICAL)
logging.getLogger("websockets").setLevel(logging.CRITICAL)

r = aioredis.Redis(host='127.0.0.1', port=6379, db=0, decode_responses=True, max_connections=1000)


async def broadcast_telemetry(websocket):
    print("UI Connected! Streaming telemetry...")
    cached_keys = None
    while True:
        try:
            await asyncio.sleep(0.5)

            if not cached_keys:
                keys = await r.keys('STARLINK-*')
                if not keys:
                    await asyncio.sleep(1)
                    continue
                cached_keys = keys[:7641]

            raw_data = await r.mget(cached_keys)

            # ALL active missions from the CNP ledger
            missions_raw = await r.hgetall("MISSIONS_LEDGER")
            active_missions = [json.loads(m) for m in missions_raw.values()] if missions_raw else []

            # Rolling Enclave legacy target (CURRENT_MISSION)
            current_mission_raw = await r.get("CURRENT_MISSION")

            # Daylight cycle
            current_sun_lon = await r.get("CURRENT_SUN_LON")

            payload = {
                "satellites":      [json.loads(item) for item in raw_data if item],
                "active_missions": active_missions,
                "current_mission": json.loads(current_mission_raw) if current_mission_raw else None,
                "sun_lon":         float(current_sun_lon) if current_sun_lon else 0.0
            }

            await websocket.send(json.dumps(payload))

        except RedisConnectionError:
            print("⚠️ Redis dropped. Reconnecting in 1s...")
            await asyncio.sleep(1)
            continue
        except (websockets.exceptions.ConnectionClosed,
                websockets.exceptions.ConnectionClosedOK,
                websockets.exceptions.ConnectionClosedError):
            print("UI Disconnected.")
            break
        except Exception as e:
            # Silently skip handshake / protocol errors from iframe reloads
            if "handshake" in str(e).lower() or "opening" in str(e).lower():
                break
            print(f"⚠️ Streamer error: {e}")
            await asyncio.sleep(1)
            continue


async def main():
    print("Booting WebSocket Bridge on ws://localhost:8765...")
    async with websockets.serve(
        broadcast_telemetry,
        "localhost",
        8765,
        ping_interval=None,      # Disable keep-alive pings (Streamlit iframes don't support them)
        ping_timeout=None,       # No timeout required
        close_timeout=5,
        max_size=50 * 1024 * 1024,  # 50MB max frame for large fleet payloads
    ):
        await asyncio.Future()   # run forever


if __name__ == "__main__":
    asyncio.run(main())
