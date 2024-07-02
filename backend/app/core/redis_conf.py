from redis import Redis
from app.core.config import settings

redis_client = Redis(
    host=settings.REDIS_HOST, port=settings.REDIS_PORT, db=1, decode_responses=True
)


def test_redis_connection():
    try:
        result = redis_client.ping()
        if result:
            print("Redis connection successful.")
            redis_client.set("test_key", "test_value")
            value = redis_client.get("test_key")
            print(f"Redis read value: {value}")
            if value == "test_value":
                print("Redis read/write successful.")
            else:
                print("Redis read/write failed.")
        else:
            print("Redis connection failed.")
    except Exception as e:
        print(f"Failed to connect to Redis: {str(e)}")


if __name__ == "__main__":
    test_redis_connection()
