"""PostgreSQL connection pool: idle connections are reused, at most `size` are in use at once, and
callers wait for a free slot instead of failing. (psycopg2's own pool closes every returned
connection unless minconn is raised, which defeats the purpose.)

`transaction()` runs one transaction on a pooled connection. What a transaction needs before its
first statement (schema, workspace, isolation level) is supplied by the caller as `prepare`, so
every value is transaction-local and a connection is safe to hand to the next request.
"""
import collections
from contextlib import contextmanager
import os
import threading
import time

from fastapi import HTTPException
import psycopg2
from psycopg2 import extensions
from psycopg2.extras import RealDictCursor

POOL_SIZE = max(int(os.environ.get('DB_POOL_SIZE', '10')), 2)   # the background job needs a second connection
POOL_WAIT_SECONDS = 10
IDLE_SECONDS = 300
APPLICATION_NAME = 'zhixing-workspace'   # visible in pg_stat_activity


class Pool:
    def __init__(self, dsn, size):
        self.dsn = dsn
        self.slots = threading.BoundedSemaphore(size)
        self.idle = collections.deque()          # (connection, returned_at), most recent last

    def acquire(self):
        if not self.slots.acquire(timeout=POOL_WAIT_SECONDS):
            raise HTTPException(503, '数据库连接繁忙，请稍后重试。')
        try:
            while True:
                try:
                    connection, returned_at = self.idle.pop()
                except IndexError:
                    return psycopg2.connect(self.dsn, connect_timeout=5, application_name=APPLICATION_NAME)
                if connection.closed or time.monotonic() - returned_at > IDLE_SECONDS:
                    self.discard(connection)
                    continue
                return connection
        except BaseException:
            self.slots.release()
            raise

    @staticmethod
    def discard(connection):
        try:
            connection.close()
        except Exception:
            pass

    def release(self, connection, discard=False):
        try:
            if discard or connection.closed:
                self.discard(connection)
            else:
                if connection.info.transaction_status != extensions.TRANSACTION_STATUS_IDLE:
                    connection.rollback()
                self.idle.append((connection, time.monotonic()))
        except Exception:
            self.discard(connection)
        finally:
            self.slots.release()

    def close(self):
        while self.idle:
            self.discard(self.idle.pop()[0])


_pools = {}
_pools_lock = threading.Lock()


def get_pool(dsn):
    with _pools_lock:
        if dsn not in _pools:
            _pools[dsn] = Pool(dsn, POOL_SIZE)
        return _pools[dsn]


def close_pools():
    with _pools_lock:
        for item in _pools.values():
            item.close()
        _pools.clear()


def checkout(connection_pool, prepare):
    """Take a connection and prepare the transaction. A pooled connection may have gone stale
    (database restarted): discard it and try once with a fresh one. Failing to connect at all is
    reported immediately."""
    connection = connection_pool.acquire()
    try:
        prepare(connection)
        return connection
    except (psycopg2.OperationalError, psycopg2.InterfaceError):
        connection_pool.release(connection, discard=True)
    except BaseException:
        connection_pool.release(connection, discard=True)
        raise
    connection = connection_pool.acquire()
    try:
        prepare(connection)
        return connection
    except BaseException:
        connection_pool.release(connection, discard=True)
        raise


@contextmanager
def transaction(dsn, prepare):
    """Yield a dict cursor inside one transaction: commit on success, roll back on any exception."""
    connection_pool = get_pool(dsn)
    connection = checkout(connection_pool, prepare)
    broken = False
    try:
        try:
            with connection.cursor(cursor_factory=RealDictCursor) as cursor:
                yield cursor
            connection.commit()
        except BaseException as error:
            if isinstance(error, (psycopg2.OperationalError, psycopg2.InterfaceError)):
                broken = True
            try:
                connection.rollback()
            except Exception:
                broken = True
            raise
    finally:
        connection_pool.release(connection, discard=broken)
