import time
import uuid
from concurrent.futures import ThreadPoolExecutor

import redis

r = redis.Redis(
    host="localhost",
    port=6379,
    decode_responses=True
)

def race(fn, n=50):
    """Run fn(i) from n threads and return the results."""
    with ThreadPoolExecutor(max_workers=n) as pool:
        return list(pool.map(fn, range(n)))

if __name__ == "__main__":
    print("Redis connection:", r.ping())
    print("TicketRush environment ready!")
def hold_naive(event, seat, user):
    key = f"hold:{event}:{seat}"
    if r.get(key) is None:
        time.sleep(0.01)
        r.set(key, user, ex=300)
        return True
    return False


def hold_nx(event, seat, user, ttl=300):
    return bool(
        r.set(f"hold:{event}:{seat}", user, nx=True, ex=ttl)
    )


print("\n--- STEP 1: NAIVE GET + SET ---")
r.flushdb()
wins = race(
    lambda i: hold_naive("c1", "A1", f"user{i}")
)
print("Naive winners:", sum(wins))
print("Actual owner:", r.get("hold:c1:A1"))

print("\n--- STEP 1: ATOMIC SET NX EX ---")
r.flushdb()
wins = race(
    lambda i: hold_nx("c1", "A1", f"user{i}")
)
print("Atomic winners:", sum(wins))
print("Actual owner:", r.get("hold:c1:A1"))
print("TTL:", r.ttl("hold:c1:A1"))

HOLD = r.register_script("""
if redis.call('SISMEMBER', KEYS[2], ARGV[2]) == 1 then return 0 end
if redis.call('SET', KEYS[1], ARGV[1], 'NX', 'EX', ARGV[3]) then return 1 end
return 0
""")

CONFIRM = r.register_script("""
if redis.call('GET', KEYS[1]) == ARGV[1] then
    redis.call('SADD', KEYS[2], ARGV[2])
    redis.call('DEL', KEYS[1])
    return 1
end
return 0
""")

RELEASE = r.register_script("""
if redis.call('GET', KEYS[1]) == ARGV[1] then
    return redis.call('DEL', KEYS[1])
end
return 0
""")

def hold(event, seat, user, ttl=300):
    return bool(HOLD(
        keys=[f"hold:{event}:{seat}", f"sold:{event}"],
        args=[user, seat, ttl]
    ))

def confirm(event, seat, user):
    return bool(CONFIRM(
        keys=[f"hold:{event}:{seat}", f"sold:{event}"],
        args=[user, seat]
    ))

def release(event, seat, user):
    return bool(RELEASE(
        keys=[f"hold:{event}:{seat}"],
        args=[user]
    ))

def seat_map(event, seats):
    sold = r.smembers(f"sold:{event}")
    return {
        s: "sold" if s in sold
        else "held" if r.exists(f"hold:{event}:{s}")
        else "free"
        for s in seats
    }

print("\n--- STEP 2: ATOMIC HOLD / CONFIRM / RELEASE ---")
r.flushdb()

print("Linh holds A1:", hold("c1", "A1", "linh"))
print("Nam holds A1:", hold("c1", "A1", "nam"))
print("Nam confirms A1:", confirm("c1", "A1", "nam"))
print("Linh confirms A1:", confirm("c1", "A1", "linh"))
print("Nam holds sold A1:", hold("c1", "A1", "nam"))
print("Seat map:", seat_map("c1", ["A1", "A2"]))
print("Sold seats:", r.smembers("sold:c1"))

print("\n--- STEP 2: RELEASE TEST ---")
print("Nam holds A2:", hold("c1", "A2", "nam"))
print("Linh releases A2:", release("c1", "A2", "linh"))
print("Nam releases A2:", release("c1", "A2", "nam"))
print("Seat map after release:", seat_map("c1", ["A1", "A2"]))

def buy_general(event, user):
    left = r.decr(f"stock:{event}")

    if left < 0:
        r.incr(f"stock:{event}")
        return False

    r.sadd(f"buyers:{event}", user)
    return True


print("\n--- STEP 3: FLASH SALE (500 USERS, 100 TICKETS) ---")
r.flushdb()
r.set("stock:g1", 100)

ok = race(
    lambda i: buy_general("g1", f"user{i}"),
    n=500
)

print("Successful purchases:", sum(ok))
print("Remaining stock:", r.get("stock:g1"))
print("Unique buyers:", r.scard("buyers:g1"))

assert sum(ok) == 100
assert int(r.get("stock:g1")) == 0
assert r.scard("buyers:g1") == 100

print("Result: PASS - No overselling")

def allow_fixed(user, limit=5, window=10):
    key = f"rl:fixed:{user}:{int(time.time() // window)}"
    pipe = r.pipeline()
    pipe.incr(key)
    pipe.expire(key, window, nx=True)
    count, _ = pipe.execute()
    return count <= limit


SLIDING = r.register_script("""
local now, window, limit =
    tonumber(ARGV[1]), tonumber(ARGV[2]), tonumber(ARGV[3])
redis.call('ZREMRANGEBYSCORE', KEYS[1], 0, now - window)
if redis.call('ZCARD', KEYS[1]) < limit then
    redis.call('ZADD', KEYS[1], now, ARGV[4])
    redis.call('PEXPIRE', KEYS[1], window)
    return 1
end
return 0
""")


def allow_sliding(user, limit=5, window_ms=10000):
    now = int(time.time() * 1000)
    return bool(SLIDING(
        keys=[f"rl:sliding:{user}"],
        args=[now, window_ms, limit, uuid.uuid4().hex]
    ))


print("\n--- STEP 4A: FIXED WINDOW ---")
r.flushdb()

fixed_results = [allow_fixed("linh") for _ in range(8)]
print("Fixed window results:", fixed_results)
print("Allowed:", sum(fixed_results))
print("Rejected:", len(fixed_results) - sum(fixed_results))

print("\n--- STEP 4B: SLIDING WINDOW ---")
sliding_results = [allow_sliding("linh") for _ in range(8)]
print("Sliding window results:", sliding_results)
print("Allowed:", sum(sliding_results))
print("Rejected:", len(sliding_results) - sum(sliding_results))

print("\n--- STEP 4C: SLIDING WINDOW + TICKET HOLD ---")

def try_hold(event, seat, user):
    if not allow_sliding(user):
        return "rate_limited"
    return "ok" if hold(event, seat, user) else "taken"


r.flushdb()
attempts = [
    try_hold("c1", f"B{i}", "bot")
    for i in range(8)
]
print("Hold attempts:", attempts)

assert sum(fixed_results) == 5
assert sum(sliding_results) == 5
assert attempts.count("ok") == 5
assert attempts.count("rate_limited") == 3

print("Result: PASS - Rate limiting works")

def join_queue(event, user):
    r.zadd(
        f"queue:{event}",
        {user: time.time()},
        nx=True
    )
    rank = r.zrank(f"queue:{event}", user)
    return rank + 1 if rank is not None else None


def admit(event, n):
    return [
        user
        for user, score in r.zpopmin(f"queue:{event}", n)
    ]


print("\n--- STEP 5: VIRTUAL WAITING ROOM ---")
r.flushdb()

for name in ["u1", "u2", "u3"]:
    print(name, "position:", join_queue("c1", name))
    time.sleep(0.01)

print("u1 rejoins, position:", join_queue("c1", "u1"))
print("Admitted users:", admit("c1", 2))
print("u3 new position:", join_queue("c1", "u3"))
print("Remaining queue:", r.zrange("queue:c1", 0, -1))

assert r.zrange("queue:c1", 0, -1) == ["u3"]
print("Result: PASS - Queue ordering works")
import random

SEATS = [f"S{i}" for i in range(1, 21)]


def buyer(i):
    user = f"user{i}"

    for seat in SEATS:
        if hold("c1", seat, user):
            time.sleep(random.random() * 0.05)

            if confirm("c1", seat, user):
                return seat

    return None


print("\n--- STEP 6: FINAL STRESS TEST ---")

for run in range(1, 11):
    r.flushdb()
    got = [s for s in race(buyer, n=100) if s is not None]

    sold_count = len(got)
    unique_count = len(set(got))
    redis_count = r.scard("sold:c1")

    passed = (
        sold_count == 20
        and unique_count == 20
        and redis_count == 20
    )

    print(
        f"Run {run:02d}: "
        f"Sold={sold_count}, "
        f"Unique={unique_count}, "
        f"Redis={redis_count}, "
        f"Result={'PASS' if passed else 'FAIL'}"
    )

    assert passed, f"Stress test failed on run {run}"

print("\nFINAL RESULT: ALL 10 STRESS TESTS PASSED")

print("\n--- STEP 7A: LEADERBOARD ---")
r.flushdb()

players = {
    "Linh": 1200,
    "Nam": 950,
    "Mai": 1430,
    "An": 1100,
    "Hoa": 800
}

r.zadd("leaderboard", players)

top3 = r.zrevrange(
    "leaderboard", 0, 2, withscores=True
)

print("TOP 3 PLAYERS:")
for rank, (name, score) in enumerate(top3, 1):
    print(f"Rank {rank}: {name} - {int(score)} points")

print("\nPLAYER RANKINGS:")
for name in players:
    rank = r.zrevrank("leaderboard", name)
    print(f"{name}: Rank {rank + 1}")

assert [name for name, _ in top3] == ["Mai", "Linh", "An"]

print("\nResult: PASS - Leaderboard works")

print("\n--- STEP 7B: USER PROFILE AND CITY INDEX ---")
r.flushdb()

users = {
    "101": {"name": "Linh", "age": "21", "city": "Hanoi"},
    "102": {"name": "Nam", "age": "23", "city": "HCMC"},
    "103": {"name": "Mai", "age": "22", "city": "Hanoi"},
    "104": {"name": "An", "age": "20", "city": "Danang"},
    "105": {"name": "Hoa", "age": "24", "city": "Hanoi"}
}

for user_id, profile in users.items():
    r.hset(f"user:{user_id}", mapping=profile)
    r.sadd(f"city:{profile['city']}", user_id)

print("USER PROFILE:")
print("User 101:", r.hgetall("user:101"))

print("\nUSERS IN HANOI:")
hanoi_ids = sorted(r.smembers("city:Hanoi"))

for user_id in hanoi_ids:
    print(user_id, r.hgetall(f"user:{user_id}"))

print("\nHANOI USER COUNT:", len(hanoi_ids))

assert hanoi_ids == ["101", "103", "105"]
assert r.hget("user:101", "name") == "Linh"

print("Result: PASS - User hash and city index work")
import json

print("\n--- STEP 7C: CACHE-ASIDE BENCHMARK ---")
r.flushdb()

def slow_query(product_id):
    time.sleep(0.01)
    return {
        "id": product_id,
        "title": "Python Basics",
        "price": 12.5
    }


def get_product(product_id):
    key = f"product:{product_id}"
    cached = r.get(key)

    if cached is not None:
        return json.loads(cached)

    product = slow_query(product_id)
    r.set(key, json.dumps(product), ex=300)
    return product


# Test 1: Without Redis cache
start = time.perf_counter()

for _ in range(100):
    slow_query(7)

without_cache = time.perf_counter() - start


# Test 2: With Redis cache
r.delete("product:7")
start = time.perf_counter()

for _ in range(100):
    get_product(7)

with_cache = time.perf_counter() - start

speedup = (
    without_cache / with_cache
    if with_cache > 0 else float("inf")
)

print(f"Without cache (100 requests): {without_cache:.4f} seconds")
print(f"With cache (100 requests): {with_cache:.4f} seconds")
print(f"Speedup: {speedup:.2f}x")
print("Cached product:", get_product(7))
print("Cache TTL:", r.ttl("product:7"))

assert with_cache < without_cache
assert get_product(7)["title"] == "Python Basics"

print("Result: PASS - Cache-aside improves performance")
