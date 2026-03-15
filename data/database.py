import os
from mariadb import connect
from mariadb.connections import Connection
from dotenv import load_dotenv


load_dotenv()


def _get_connection() -> Connection:
    user = os.getenv("DB_USER")
    password = os.getenv("DB_PASSWORD")
    host = os.getenv("DB_HOST")
    database = os.getenv("DB_NAME")

    if not all([user, password, host, database]):
        raise RuntimeError("Missing one or more required database environment variables")

    return connect(
        user=user,
        password=password,
        host=host,
        port=int(os.getenv("DB_PORT", "3306")),
        database=database,
    )


def read_query(sql: str, sql_params=()) -> list:
    with _get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(sql, sql_params)

        return list(cursor)


def insert_query(sql: str, sql_params=()) -> int:
    with _get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(sql, sql_params)
        conn.commit()

        return cursor.lastrowid or 0


def update_query(sql: str, sql_params=()) -> bool:
    with _get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(sql, sql_params)
        conn.commit()

    return cursor.rowcount > 0


def delete_query(sql: str, sql_params=()) -> bool:
    with _get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(sql, sql_params)
        conn.commit()

    return cursor.rowcount > 0
