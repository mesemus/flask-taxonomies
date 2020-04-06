# -*- coding: utf-8 -*-
"""Setup module for flask taxonomy."""
import os

from setuptools import setup

readme = open('README.rst').read()

DATABASE = "postgresql"
OAREPO_VERSION = os.environ.get('OAREPO_VERSION', '3.1.1')

install_requires = [
    'python-slugify>=3.0.2',
    'webargs>=5.3.2,<7.0.0',
    'wrapt>=1.11.0',
    'openpyxl>=3.0.1',
    'oarepo-references>=1.4.0',
    'flatten-json'
]

tests_require = [
    'pytest>=4.6.3',
]

extras_require = {
    'postgresql': [
        'invenio-db[postgresql]>=1.0.0b3',
    ],
    'mysql': [
        'invenio-db[mysql]>=1.0.0b3',
    ],
    'sqlite': [
        'invenio-db>=1.0.0b3',
    ],
    'tests': [
        *tests_require,
        'oarepo[tests]~={version}'.format(
            version=OAREPO_VERSION)],
    'tests-es7': [
        *tests_require,
        'oarepo[tests-es7]~={version}'.format(
            version=OAREPO_VERSION)],
}

setup_requires = [
    'pytest-runner>=2.7',
]

g = {}
with open(os.path.join('flask_taxonomies', 'version.py'), 'rt') as fp:
    exec(fp.read(), g)
version = g['__version__']

setup(
    name="flask_taxonomies",
    version=version,
    url="https://github.com/oarepo/flask-taxonomies",
    license="MIT",
    author="Miroslav Bauer",
    author_email="bauer@cesnet.cz",
    description="Taxonomy Term trees REST API for Invenio Applications",
    zip_safe=False,
    packages=['flask_taxonomies'],
    entry_points={
        'invenio_db.models': [
            'flask_taxonomies = flask_taxonomies.models',
        ],
        'invenio_db.alembic': [
            'flask_taxonomies = flask_taxonomies:alembic',
        ],
        'invenio_base.api_blueprints': [
            'flask_taxonomies = flask_taxonomies.views:blueprint',
        ],
        'invenio_base.apps': [
            'flask_taxonomies = flask_taxonomies.ext:FlaskTaxonomies',
            'flask_taxonomies_redis = flask_taxonomies.redis.ext:FlaskTaxonomiesRedis',
        ],
        'invenio_base.api_apps': [
            'flask_taxonomies = flask_taxonomies.ext:FlaskTaxonomies',
            'flask_taxonomies_redis = flask_taxonomies.redis.ext:FlaskTaxonomiesRedis',
        ],
        'invenio_jsonschemas.schemas': [
            'flask_taxonomies = flask_taxonomies.jsonschemas'
        ],
        'invenio_oarepo_mapping_includes': [
            'flask_taxonomies=flask_taxonomies.included_mappings'
        ],
        'invenio_records.jsonresolver': [
            'flask_taxonomies = flask_taxonomies.jsonresolver'
        ],
        'invenio_access.actions': [
            # Taxonomy related permissions
            'taxonomy_create_all'
            ' = flask_taxonomies.permissions:taxonomy_create_all',
            'taxonomy_read_all'
            ' = flask_taxonomies.permissions:taxonomy_read_all',
            'taxonomy_update_all'
            ' = flask_taxonomies.permissions:taxonomy_update_all',
            'taxonomy_delete_all'
            ' = flask_taxonomies.permissions:taxonomy_delete_all',
            # Taxonomy term related permissions.
            'taxonomy_term_create_all'
            ' = flask_taxonomies.permissions:taxonomy_term_create_all',
            'taxonomy_term_read_all'
            ' = flask_taxonomies.permissions:taxonomy_term_read_all',
            'taxonomy_term_update_all'
            ' = flask_taxonomies.permissions:taxonomy_term_update_all',
            'taxonomy_term_delete_all'
            ' = flask_taxonomies.permissions:taxonomy_term_delete_all',
            'taxonomy_term_move_all'
            ' = flask_taxonomies.permissions:taxonomy_term_move_all',
        ],
        'flask.commands': [
            'taxonomies = flask_taxonomies.cli:taxonomies',
        ]
    },
    include_package_data=True,
    setup_requires=setup_requires,
    extras_require=extras_require,
    install_requires=install_requires,
    tests_require=tests_require,
    platforms='any',
    classifiers=[
        'Environment :: Web Environment',
        'Intended Audience :: Developers',
        'License :: OSI Approved :: MIT License',
        'Operating System :: OS Independent',
        'Programming Language :: Python',
        'Topic :: Internet :: WWW/HTTP :: Dynamic Content',
        'Topic :: Software Development :: Libraries :: Python Modules',
        'Programming Language :: Python :: 2',
        'Programming Language :: Python :: 2.7',
        'Programming Language :: Python :: 3',
        'Programming Language :: Python :: 3.5',
        'Development Status :: 4 - Beta',
    ],
)
