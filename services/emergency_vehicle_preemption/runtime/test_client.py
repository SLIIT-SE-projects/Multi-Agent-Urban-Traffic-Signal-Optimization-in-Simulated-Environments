import asyncio
import websockets
import json

async def test():
    uri = "ws://localhost:5000/ws" 
    async with websockets.connect(uri) as websocket:
        print(f"Connected to Integrated Backend at {uri}")
        while True:
            try:
                message = await websocket.recv()
                data = json.loads(message)
                # Print Lat/Lon specifically
                if "lat" in data:
                    print(f"RECEIVED: Lat={data['lat']}, Lon={data['lon']}")
            except Exception as e:
                print(f"Error: {e}")
                break

if __name__ == "__main__":
    asyncio.run(test())