# See license.txt for license details.
# Copyright (c) 2023 onwards Chris Withers

import os

from setuptools import setup, find_packages

base_dir = os.path.dirname(__file__)

setup(
    name='testservices',
    version='0.3.0',
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
    ],
    packages=find_packages(exclude=["tests"]),
    zip_safe=False,
    include_package_data=True,
    python_requires=">=3.11",
    install_requires=[
        # If good non-container use cases appear, this should move
        # to an extra:
        'docker',
    ],
    extras_require=dict(
        test=[
            'PyMySQL',
            'clickhouse-driver',
            'mypy',
            'psycopg[binary]',
            'pytest',
            'pytest-cov',
            'sybil',
            'testfixtures',
            'psycopg',
            'sqlalchemy',
        ],
        build=[
            'furo',
            'setuptools',
            'setuptools-git',
            'sphinx',
            'twine',
            'wheel'
        ]
    ),
)
