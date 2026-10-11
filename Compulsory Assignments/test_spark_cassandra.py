"""Create fruit example data, then verify reading it through Spark."""

import os
import subprocess
import sys

from pyspark.sql import SparkSession


# Use the keyspace and CQL patterns from 3_Cassandra.ipynb.
# The Python driver's default connection cannot load in this Python 3.12 setup.
# Run the same CQL through the existing container's cqlsh; Spark reads independently.
example_rows = [(1, "apple", 10), (2, "pear", 8), (3, "apple", 15)]
# A replication factor of one matches this single-node learning environment.
# Preserve existing tables instead of dropping them when the test is repeated.
# Fixed primary keys update the same three rows on subsequent runs.
setup_cql = """
CREATE KEYSPACE IF NOT EXISTS my_first_keyspace
WITH REPLICATION = {'class': 'SimpleStrategy', 'replication_factor': 1};
CREATE TABLE IF NOT EXISTS my_first_keyspace.fruit_test
(id int PRIMARY KEY, fruit text, quantity int);
INSERT INTO my_first_keyspace.fruit_test (id, fruit, quantity)
VALUES (1, 'apple', 10);
INSERT INTO my_first_keyspace.fruit_test (id, fruit, quantity)
VALUES (2, 'pear', 8);
INSERT INTO my_first_keyspace.fruit_test (id, fruit, quantity)
VALUES (3, 'apple', 15);
"""
# Pass arguments directly, without a shell. A failed setup stops the test.
subprocess.run(
    ["docker", "exec", "-i", "cassandra", "cqlsh"],
    input=setup_cql,
    text=True,
    check=True,
    timeout=60,
)
print("Prepared three example rows in my_first_keyspace.fruit_test.", flush=True)


# Use this project's Python interpreter for both Spark's driver and workers.
os.environ["PYSPARK_PYTHON"] = sys.executable
os.environ["PYSPARK_DRIVER_PYTHON"] = sys.executable
os.environ["PYSPARK_HADOOP_VERSION"] = "without"

# Follow D2Dbook/2_Data_sources/2_Databases/4_Spark.ipynb,
# section "Spark and Cassandra". Java and Hadoop use existing environment paths.
spark = (
    SparkSession.builder.master("local[2]")
    .appName("IND320CassandraConnectionTest")
    .config(
        "spark.jars.packages",
        "com.datastax.spark:spark-cassandra-connector_2.12:3.5.1",
    )
    .config("spark.cassandra.connection.host", "localhost")
    .config("spark.cassandra.connection.port", "9042")
    .config(
        "spark.sql.extensions",
        "com.datastax.spark.connector.CassandraSparkExtensions",
    )
    .config(
        "spark.sql.catalog.mycatalog",
        "com.datastax.spark.connector.datasource.CassandraCatalog",
    )
    .getOrCreate()
)

try:
    spark.sparkContext.setLogLevel("WARN")

    # Read the example table using Spark and the DataStax connector.
    # collect() triggers execution: constructing a DataFrame alone is insufficient.
    rows = (
        spark.read.format("org.apache.spark.sql.cassandra")
        .options(keyspace="my_first_keyspace", table="fruit_test")
        .load()
        .select("id", "fruit", "quantity")
        .filter("id IN (1, 2, 3)")
        .orderBy("id")
        .collect()
    )
    # Compare actual values, not just a row count, to verify the complete read.
    actual_rows = [tuple(row) for row in rows]
    if actual_rows != example_rows:
        raise RuntimeError(f"Unexpected Cassandra data: {actual_rows!r}")

    print(f"Spark version: {spark.version}")
    for row in rows:
        print(row)
    print("PASS: Spark successfully read Cassandra through the DataStax connector.")
finally:
    # Release Spark resources after either success or a query failure.
    spark.stop()
