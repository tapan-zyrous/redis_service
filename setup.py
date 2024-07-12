# setup.py for redis-service
from setuptools import setup, find_packages


setup(
    name='redis-service',
    version='0.1',
    author="TP",
    author_email="tp@gmail.com",
    package_dir={"": "src"},
    packages=find_packages(where="src"),
    namespace_packages=["redis_service"],
    entry_points={"redis_service_plugins": ["cache = redis_service.cache"]},
    install_requires=[
        'redis',
        'strawberry-graphql[debug-server]'
        # other dependencies
    ],
)