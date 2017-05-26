# Copyright (C) 2016 Nokia Corporation and/or its subsidiary(-ies).

from setuptools import setup, find_packages

import sys
if sys.version_info > (3, 0):
    sys.exit('Python 3 is not supported (yet ?)')


tests_require = [
    'nose',
    'freezegun',
    'mock'
]

install_requires = [
    'GitPython >= 2.1.3, < 3',
    'sqlalchemy >= 1.0, < 2',
    'ws4py >= 0.3.5',
    'enum34',
    'requests >= 2.6',
    'cherrypy >= 8.9, < 9',
    'bottle >= 0.12.9',
    'beanstalkc >= 0.4, < 0.5',
    'bottle_sqlalchemy',
    'marshmallow >= 2.13, < 3',
    'marshmallow_sqlalchemy',
    'bcrypt',
    'pyyaml'
    # You will need a SQLAlchemy compatible DB driver too
    # (see extras)
]

extras = [
    'pymysql'
]

setup(
    name='deployment',
    version='0.1',
    description='A simple web service to deploy projects from Git repositories.',
    author='Etienne Adam, Benoît Faucon',
    author_email='etienne.adam@withings.com, benoit.faucon@withings.com',
    license='Apache 2',
    packages=find_packages(),
    install_requires=install_requires,
    tests_require=tests_require,
    extras_require={
        'test': tests_require + install_requires,
        'full': tests_require + install_requires + extras
    },
    entry_points={
        'console_scripts': [
            'deployer = deployment.__main__:main'
        ]
    }
)
