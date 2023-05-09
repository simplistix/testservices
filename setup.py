# See license.txt for license details.
# Copyright (c) 2023, Chris Withers

import os

from setuptools import setup, find_packages

base_dir = os.path.dirname(__file__)

setup(
    name='testservices',
    version='0.1.0',
    author='Chris Withers',
    author_email='chris@withers.org',
    license='MIT',
    description=(
        "Orchestrating services for testing and development."
    ),
    long_description=open('README.rst').read(),
    url='https://github.com/simplistix/testservices',
    classifiers=[
        'License :: OSI Approved :: MIT License',
        'Programming Language :: Python :: 3',
        'Programming Language :: Python :: 3.8',
        'Programming Language :: Python :: 3.11',
    ],
    packages=find_packages(exclude=["tests"]),
    zip_safe=False,
    include_package_data=True,
    python_requires=">=3.8",
    extras_require=dict(
        test=[
            'PyMySQL',
            'clickhouse-driver',
            'docker',
            'pytest',
            'pytest-cov',
            'sybil',
            'testfixtures',
            'psycopg',
            'sqlalchemy',
            # https://github.com/docker/docker-py/issues/3113
            'urllib3<2',
        ],
        build=[
            'furo',
            'sphinx',
            'setuptools-git',
            'twine',
            # https://github.com/docker/docker-py/issues/3113
            'urllib3<2',
            'wheel'
        ]
    ),
)
