# redis_cache.py
import asyncio
import codecs
import inspect
import logging
import os
import pickle  # noqa: S403
from concurrent.futures import Future
from typing import Any, Optional, Type, TypeVar, Union, Generic
from redis import Redis, RedisError
from strawberry.dataloader import AbstractCache

T = TypeVar('T')

class RedisCache(Generic[T], AbstractCache[Any, T]):
    _redis: Redis
    _item_ttl: int
    _item_prefix: str

    def __init__(self, item_type: Type[T], cache_ttl: int = None):
        redis_host = os.getenv('CACHE_REDIS_HOST', 'localhost')
        redis_port = int(os.getenv('CACHE_REDIS_PORT', '6379'))
        redis_db = int(os.getenv('CACHE_REDIS_DB', '0'))
        redis_username = os.getenv('CACHE_REDIS_USERNAME', None)
        redis_password = os.getenv('CACHE_REDIS_PASSWORD', None)
        self._redis = Redis(
            host=redis_host,
            port=redis_port,
            db=redis_db,
            username=redis_username,
            password=redis_password,
        )
        self._item_ttl = cache_ttl or int(os.getenv('CACHE_TTL', '600'))
        self._item_prefix = f'{item_type.__module__}.{item_type.__name__}'

    def get(self, key: Any) -> Optional[asyncio.Future[T]]:
        try:
            value = self._redis.get(self._get_cache_key(key))
            if value:
                future = asyncio.get_event_loop().create_future()
                logging.debug('Value found in cache for key: %s', key)
                decoded_value = pickle.loads(codecs.decode(value, 'base64'))  # noqa: S301
                logging.debug('Decoded value: %s', decoded_value)
                future.set_result(decoded_value)
                return future
            else:
                logging.debug('Value not found in cache for key: %s', key)
                return None
        except RedisError:
            logging.error('Error occurred while getting key %s', key)
        return None

    def set(self, key: Any, value: Future[T]) -> None:
        async def resolve_future(future: Union[Future[T], asyncio.Future[T]]):
            result = future
            while inspect.isawaitable(result):
                result = await result
            return result

        def set_cache_value(future: T | any):
            try:
                result = future.result()
                if result:
                    self._redis.set(
                        name=self._get_cache_key(key),
                        value=codecs.encode(pickle.dumps(result), 'base64'),
                        ex=self._item_ttl,
                    )
                    logging.debug('Set key: %s with value: %s', key, result)
                else:
                    logging.debug('Skipping set cache value for key: %s (no value returned)', key)
            except RedisError:
                logging.error('Error occurred while setting key %s', key)

        try:
            task = asyncio.create_task(resolve_future(value))
            task.add_done_callback(set_cache_value)
        except Exception:
            logging.error('Error occurred while resolving future for key %s', key)

    def delete(self, key: Any) -> None:
        try:
            self._redis.delete(self._get_cache_key(key))
            logging.debug('Deleted key: %s', key)
        except Exception:
            logging.error('Error occurred while deleting key %s: %s', key)

    def clear(self) -> None:
        try:
            self._redis.flushdb()
            logging.debug('Cleared all keys in the cache')
        except Exception:
            logging.error('Error occurred while clearing the cache')

    def _get_cache_key(self, key: any) -> str:
        return f'{self._item_prefix}:{key}'
