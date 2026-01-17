import os

import yaml
from redis.sentinel import Sentinel

__all__ = ["get_redis_client"]


HDFLOW_REDIS_HOOK_CONFIG_PATH = os.path.expanduser("~/.hdflow/redis_hook.yaml")


class RedisConfig:
    HOST = "http://redis-hook-service.test.com"
    DB = 0
    REDIS_HOOK_API = f"{HOST}/redis_hook"
    NOTIFY_TRAINING_PIPELINE_API = f"{HOST}/notify_training_pipeline"
    ADDRS = ["11.11.11.2:26380", "11.11.11.3:26380", "11.11.11.4:26380"]
    SENTINEL_MASTER = "mymaster"
    PASSWORD = ""


def load_config(path=HDFLOW_REDIS_HOOK_CONFIG_PATH):
    if not os.path.exists(path):
        return dict(
            db=RedisConfig.DB,
            addrs=RedisConfig.ADDRS,
            sentinel_master=RedisConfig.SENTINEL_MASTER,
            password=RedisConfig.PASSWORD,
        )
    else:
        return yaml.safe_load(open(path, "r"))


def get_redis_client():
    """Get a redis client.

    Returns:
        redis.StrictRedis: a redis client
    """
    config = load_config()
    addrs = parse_address(config["addrs"])
    sentinel = Sentinel([(addr.host, addr.port) for addr in addrs])
    return sentinel.master_for(
        config["sentinel_master"],
        password=config["password"],
        db=config["db"],
    )
