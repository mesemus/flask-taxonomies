from setuptools import setup

requires = [
    'flask',
    'flask-sqlalchemy',
    'blinker',
    'sqlalchemy-utils',
    'python-slugify',
    'jsonpatch',
    'flask-migrate',
    'webargs',
    'jsonpointer',
    'LinkHeader',
    'jsonpatch',
    'flask-principal',
    'luqum'
]

tests_require = [
    'pytest>=5.4',
    'pytest-flask-sqlalchemy',
    'md-toc',
    'isort',
    'check-manifest',
    'pytest-coverage',
    'pytest-pep8'
]

setup(
    name='flask-taxonomies',
    version='7.0.0a11',
    packages=['flask_taxonomies', 'flask_taxonomies.alembic', 'flask_taxonomies.views'],
    install_requires=requires,
    tests_require=tests_require,
    extras_require={
        'tests': tests_require,
        'postgresql': ['psycopg2'],
        'sqlite': []
    },
    license='Creative Commons Attribution-Noncommercial-Share Alike license',
    long_description=open('README.md').read(),
    long_description_content_type="text/markdown"
)
