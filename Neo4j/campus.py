
import os
import sys
from neo4j import GraphDatabase

URI = os.getenv("NEO4J_URI", "bolt://localhost:7687")
AUTH = (
    os.getenv("NEO4J_USER", "neo4j"),
    os.getenv("NEO4J_PASSWORD", "learnneo4j")
)

driver = GraphDatabase.driver(URI, auth=AUTH)

# Dataset: 13 courses
COURSES = [
    ("CS101", "Intro to Programming", 3),
    ("MATH101", "Calculus", 3),
    ("MATH102", "Linear Algebra", 3),
    ("STAT101", "Probability and Statistics", 3),
    ("CS102", "Data Structures", 3),
    ("DB201", "Databases", 3),
    ("VIZ201", "Data Visualization", 2),
    ("ML201", "Machine Learning", 4),
    ("DE301", "Data Engineering", 3),
    ("DB301", "NoSQL Databases", 3),
    ("DL301", "Deep Learning", 4),
    ("NLP401", "Natural Language Processing", 3),
    ("CAP401", "Capstone Project", 6),
]
# Dataset: 16 prerequisite relationships
# (course, prerequisite)
REQUIRES = [
    ("MATH102", "MATH101"),
    ("STAT101", "MATH101"),
    ("CS102", "CS101"),
    ("DB201", "CS102"),
    ("VIZ201", "CS101"),
    ("VIZ201", "STAT101"),
    ("ML201", "CS102"),
    ("ML201", "MATH102"),
    ("ML201", "STAT101"),
    ("DE301", "DB201"),
    ("DE301", "CS102"),
    ("DB301", "DB201"),
    ("DL301", "ML201"),
    ("NLP401", "DL301"),
    ("CAP401", "DB301"),
    ("CAP401", "ML201"),
]
# Dataset: 10 students
# (id, name, year)
STUDENTS = [
    ("S01", "An", 3),
    ("S02", "Binh", 2),
    ("S03", "Chi", 3),
    ("S04", "Dung", 1),
    ("S05", "Giang", 2),
    ("S06", "Hoa", 3),
    ("S07", "Khoa", 2),
    ("S08", "Lan", 1),
    ("S09", "Minh", 3),
    ("S10", "Phuong", 2),
]
PASSED = {  # student -> {course: grade}
    "S01": {"CS101": 8.5, "MATH101": 7.0, "CS102": 8.0, "MATH102": 6.5, "STAT101": 7.5, "DB201": 9.0},
    "S02": {"CS101": 7.0, "MATH101": 8.0, "STAT101": 8.5, "VIZ201": 9.0},
    "S03": {"CS101": 9.0, "MATH101": 9.5, "MATH102": 9.0, "STAT101": 8.0, "CS102": 8.5, "ML201": 9.0, "DB201": 7.5},
    "S04": {"CS101": 6.5, "MATH101": 7.5},
    "S05": {"CS101": 8.0, "CS102": 7.5, "DB201": 8.0, "MATH101": 6.0},
    "S06": {"CS101": 9.5, "MATH101": 8.5, "MATH102": 8.0, "STAT101": 9.0, "CS102": 9.0, "DB201": 8.5, "DB301": 9.0, "ML201": 8.0},
    "S07": {"CS101": 7.5, "MATH101": 7.0, "STAT101": 6.5, "CS102": 7.0},
    "S08": {"CS101": 8.0},
    "S09": {"CS101": 8.0, "MATH101": 8.0, "MATH102": 7.5, "STAT101": 7.0, "CS102": 8.0, "DB201": 8.0, "ML201": 7.5, "DL301": 8.5, "VIZ201": 8.0},
    "S10": {"CS101": 9.0, "MATH101": 9.0, "STAT101": 8.0, "VIZ201": 8.5, "CS102": 7.5},
}
# Dataset: 11 friendships
# Store each friendship once; queries can traverse both directions.
FRIENDS = [
    ("S01", "S02"),
    ("S01", "S05"),
    ("S02", "S04"),
    ("S04", "S08"),
    ("S05", "S07"),
    ("S07", "S10"),
    ("S03", "S06"),
    ("S03", "S09"),
    ("S06", "S09"),
    ("S09", "S10"),
    ("S08", "S10"),
]

def setup():
    """Clear database, create constraints and load dataset."""
    q = lambda cypher, **params: driver.execute_query(
        cypher, parameters_=params
    )

    q("MATCH (n) DETACH DELETE n")

    q("""
    CREATE CONSTRAINT student_id IF NOT EXISTS
    FOR (s:Student) REQUIRE s.id IS UNIQUE
    """)

    q("""
    CREATE CONSTRAINT course_code IF NOT EXISTS
    FOR (c:Course) REQUIRE c.code IS UNIQUE
    """)

    q("""
    UNWIND $rows AS r
    MERGE (c:Course {code: r[0]})
    SET c.title = r[1], c.credits = r[2]
    """, rows=[list(c) for c in COURSES])

    q("""
    UNWIND $rows AS r
    MATCH (c:Course {code: r[0]})
    MATCH (p:Course {code: r[1]})
    MERGE (c)-[:REQUIRES]->(p)
    """, rows=[list(r) for r in REQUIRES])

    q("""
    UNWIND $rows AS r
    MERGE (s:Student {id: r[0]})
    SET s.name = r[1], s.year = r[2]
    """, rows=[list(s) for s in STUDENTS])

    q("""
    UNWIND $rows AS r
    MATCH (s:Student {id: r.sid})
    MATCH (c:Course {code: r.code})
    MERGE (s)-[p:PASSED]->(c)
    SET p.grade = r.grade
    """, rows=[
        {"sid": sid, "code": code, "grade": grade}
        for sid, courses in PASSED.items()
        for code, grade in courses.items()
    ])

    q("""
    UNWIND $rows AS r
    MATCH (a:Student {id: r[0]})
    MATCH (b:Student {id: r[1]})
    MERGE (a)-[:FRIEND]->(b)
    """, rows=[list(f) for f in FRIENDS])

    result = driver.execute_query("""
        MATCH (n)
        RETURN labels(n)[0] AS label, count(*) AS n
        ORDER BY label
    """)

    print("Loaded:", {
        r["label"]: r["n"] for r in result.records
    })

def passed_courses(student_id):
    records, _, _ = driver.execute_query("""
        MATCH (s:Student {id: $student_id})
              -[p:PASSED]->(c:Course)
        RETURN c.code AS code, p.grade AS grade
        ORDER BY grade DESC, code ASC
    """, student_id=student_id)

    return [(r["code"], r["grade"]) for r in records]

def prerequisite_chain(course_code):
    records, _, _ = driver.execute_query("""
        MATCH (c:Course {code: $code})
              -[:REQUIRES*1..]->(pre:Course)
        WITH pre, min(length(
            shortestPath(
                (c)-[:REQUIRES*1..]->(pre)
            )
        )) AS depth
        RETURN pre.code AS code, depth
        ORDER BY depth ASC, code ASC
    """, code=course_code)

    return [(r["code"], r["depth"]) for r in records]

def eligible_courses(student_id):
    records, _, _ = driver.execute_query("""
        MATCH (s:Student {id: $student_id})
        MATCH (c:Course)
        WHERE NOT EXISTS {
            MATCH (s)-[:PASSED]->(c)
        }
        AND NOT EXISTS {
            MATCH (c)-[:REQUIRES]->(pre:Course)
            WHERE NOT EXISTS {
                MATCH (s)-[:PASSED]->(pre)
            }
        }
        RETURN c.code AS code
        ORDER BY code ASC
    """, student_id=student_id)

    return [r["code"] for r in records]

def suggest_friends(student_id):
    records, _, _ = driver.execute_query("""
        MATCH (s:Student {id: $student_id})
              -[:PASSED]->(c:Course)<-[:PASSED]-(other:Student)
        WHERE other <> s
          AND NOT EXISTS {
              MATCH (s)-[:FRIEND]-(other)
          }
        WITH other, count(DISTINCT c) AS shared_courses
        RETURN other.name AS name, shared_courses
        ORDER BY shared_courses DESC, name ASC
	LIMIT 3
    """, student_id=student_id)

    return [
        (r["name"], r["shared_courses"])
        for r in records
    ]

def connection(student_a, student_b):
    records, _, _ = driver.execute_query("""
        MATCH (a:Student {id: $student_a})
        MATCH (b:Student {id: $student_b})
        OPTIONAL MATCH p = shortestPath(
            (a)-[:FRIEND*]-(b)
        )
        RETURN [n IN nodes(p) | n.name] AS names
    """, student_a=student_a, student_b=student_b)

    if not records or records[0]["names"] is None:
        return []

    return records[0]["names"]

def bottleneck_courses():
    records, _, _ = driver.execute_query("""
        MATCH (dependent:Course)-[:REQUIRES*1..]->(pre:Course)
        WITH pre, count(DISTINCT dependent) AS total
        RETURN pre.code AS code, total
        ORDER BY total DESC, code ASC
        LIMIT 3
    """)

    return [(r["code"], r["total"]) for r in records]

def _record_pass_tx(tx, student_id, course_code, grade):
    # Check student and course existence
    record = tx.run("""
        OPTIONAL MATCH (s:Student {id: $sid})
        OPTIONAL MATCH (c:Course {code: $code})
        RETURN s IS NOT NULL AS student_exists,
               c IS NOT NULL AS course_exists
    """, sid=student_id, code=course_code).single()

    if not record["student_exists"] or not record["course_exists"]:
        raise ValueError("unknown student or course")

    # Check missing direct prerequisites
    missing = tx.run("""
        MATCH (c:Course {code: $code})-[:REQUIRES]->(pre:Course)
        WHERE NOT EXISTS {
            MATCH (:Student {id: $sid})-[:PASSED]->(pre)
        }
        RETURN pre.code AS code
        ORDER BY code
    """, sid=student_id, code=course_code).value()

    if missing:
        raise ValueError(f"missing prerequisites: {missing}")

    # Create or update the grade
    tx.run("""
        MATCH (s:Student {id: $sid})
        MATCH (c:Course {code: $code})
        MERGE (s)-[p:PASSED]->(c)
        SET p.grade = $grade
    """, sid=student_id, code=course_code, grade=grade).consume()


def record_pass(student_id, course_code, grade):
    with driver.session() as session:
        session.execute_write(
            _record_pass_tx, student_id, course_code, grade
        )

def check():
    setup()

    assert passed_courses("S04") == [
        ("MATH101", 7.5),
        ("CS101", 6.5)
    ]
    print("PASS 1 passed_courses")

    assert prerequisite_chain("DE301") == [
        ("CS102", 1),
        ("DB201", 1),
        ("CS101", 2)
    ]
    print("PASS 2 prerequisite_chain")

    assert eligible_courses("S04") == [
        "CS102", "MATH102", "STAT101"
    ]
    print("PASS 3 eligible_courses")

    assert suggest_friends("S02") == [
        ("Minh", 4),
        ("Phuong", 4),
        ("Chi", 3)
    ]
    print("PASS 4 suggest_friends")

    assert connection("S01", "S08") == [
        "An", "Binh", "Dung", "Lan"
    ]
    print("PASS 5 connection")

    assert bottleneck_courses() == [
        ("CS101", 9),
        ("CS102", 7),
        ("MATH101", 7)
    ]
    print("PASS 6 bottleneck_courses")

    try:
        record_pass("S04", "ML201", 8.0)
        raise AssertionError("Expected ValueError")
    except ValueError as e:
        assert str(e) == (
            "missing prerequisites: "
            "['CS102', 'MATH102', 'STAT101']"
        )
    print("PASS 7a record_pass refuses")

    record_pass("S08", "CS102", 7.0)
    record_pass("S08", "CS102", 8.0)

    records, _, _ = driver.execute_query("""
        MATCH (:Student {id: "S08"})
              -[p:PASSED]->
              (:Course {code: "CS102"})
        RETURN count(p) AS total,
               max(p.grade) AS grade
    """)

    assert records[0]["total"] == 1
    assert records[0]["grade"] == 8.0
    print("PASS 7b record_pass writes")







if __name__ == "__main__":
    driver.verify_connectivity()

    if len(sys.argv) > 1 and sys.argv[1] == "setup":
        setup()
    elif len(sys.argv) > 1 and sys.argv[1] == "task1":
       print(passed_courses("S04"))
    elif len(sys.argv) > 1 and sys.argv[1] == "task2":
       print(prerequisite_chain("DE301"))
       print(prerequisite_chain("CAP401"))
    elif len(sys.argv) > 1 and sys.argv[1] == "task3":
       print(eligible_courses("S01"))
       print(eligible_courses("S04"))
    elif len(sys.argv) > 1 and sys.argv[1] == "task4":
       print(suggest_friends("S02"))
    elif len(sys.argv) > 1 and sys.argv[1] == "task5":
       print(connection("S01", "S08"))
       print(connection("S03", "S05"))
    elif len(sys.argv) > 1 and sys.argv[1] == "task6":
       print(bottleneck_courses())

    elif len(sys.argv) > 1 and sys.argv[1] == "task7":
       try:
            record_pass("S04", "ML201", 8.0)
       except ValueError as e:
            print("ValueError:", e)

       record_pass("S08", "CS102", 7.0)
       print("PASS: record_pass writes")

       print("Eligible courses:", eligible_courses("S08"))
    elif len(sys.argv) > 1 and sys.argv[1] == "check":
        check()

    else:
        print("Usage: python campus.py setup")

    driver.close()

