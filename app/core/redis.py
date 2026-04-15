import json
from redis.asyncio import Redis

redis_client = Redis.from_url("redis://localhost:6379/0", encoding="utf-8", decode_responses=True)



async def main():

    async def consume():
        async with redis_client.pubsub() as pubsub:
            await pubsub.subscribe("test")

            try:

                existing = await redis_client.get("test")
                if existing:
                    print("existing", existing)
                    return

                async for message in pubsub.listen():
                    print("Message Type: ", message["type"], "\tMessage: ", message)

                    if message["type"] == "message":
                        result = await redis_client.get("test")
                        print("result", result)
                        return
            finally:
                print("finally")
                await pubsub.unsubscribe("test")
                await redis_client.delete("test")

    asyncio.create_task(consume())

    await redis_client.publish("test", json.dumps({"name": "test"}, ensure_ascii=False))

if __name__ == "__main__":
    import asyncio
    asyncio.run(main())