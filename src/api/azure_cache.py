import redis
import os
import json
import dotenv
dotenv.load_dotenv()

print('Host: ',os.getenv("REDIS_HOST"))
print('key: ', os.getenv("REDIS_PASSWORD"))
print('port', os.getenv("REDIS_PORT"))
def get_redis_client():
    return redis.StrictRedis(
        host=os.getenv("REDIS_HOST"),
        port=int(os.getenv("REDIS_PORT", 6380)),
        password=os.getenv("REDIS_PASSWORD"),
        ssl=True,
        decode_responses=True
    )

def get_cache(key: str):
    try:
        client = get_redis_client()
        val = client.get(key)
        return json.loads(val) if val else None
    except Exception as e:
        print(f"[REDIS GET ERROR]: {e}")
        return None

def set_cache(key: str, value, ttl=600):
    try:
        client = get_redis_client()
        client.setex(key, ttl, json.dumps(value))
    except Exception as e:
        print(f"[REDIS SET ERROR]: {e}")

set_cache("recommendation", {"test": "Hello Azure Redis!"})
print(get_cache('recommendation'))