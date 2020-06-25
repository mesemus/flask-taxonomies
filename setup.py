from distutils.core import setup

requires = [
    'flask',
    'flask-sqlalchemy',
    'blinker',
    'sqlalchemy-utils',
    'python-slugify',
    'jsonpatch',
    'flask-migrate',
    'webargs',
    'jsonpointer'
]

tests_require = [
    'pytest',
    'pytest-flask-sqlalchemy'
]

setup(
    name='flask-taxonomies',
    version='7.0.0dev',
    packages=['flask_taxonomies', ],
    install_Srequires=requires,
    tests_require=tests_require,
    license='Creative Commons Attribution-Noncommercial-Share Alike license',
    long_description=open('README.rst').read(),
)
