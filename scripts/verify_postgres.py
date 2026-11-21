import getpass
import psycopg

database = input("PostgreSQL database name: ")
username = input("PostgreSQL username: ")
password = getpass.getpass("PostgreSQL password: ")

try:
    with psycopg.connect(
        host="10.97.0.141",
        port=15432,
        dbname=database,
        user=username,
        password=password,
        connect_timeout=5,
    ) as connection:
        with connection.cursor() as cursor:
            cursor.execute("""
                SELECT
                    current_database(),
                    current_user,
                    current_setting('server_version')
            """)
            result = cursor.fetchone()

    print("\nPostgreSQL authentication successful!")
    print(f"Database: {result[0]}")
    print(f"User: {result[1]}")
    print(f"Server version: {result[2]}")

except psycopg.OperationalError as error:
    print("\nPostgreSQL connection failed.")
    print(f"Reason: {error}")
    raise SystemExit(1)
