# Flask Taxonomies

[![](https://img.shields.io/github/license/oarepo/flask-taxonomies.svg)](https://github.com/oarepo/flask-taxonomies/blob/master/LICENSE)
[![](https://img.shields.io/travis/oarepo/flask-taxonomies.svg)](https://travis-ci.org/oarepo/flask-taxonomies)
[![](https://img.shields.io/coveralls/oarepo/flask-taxonomies.svg)](https://coveralls.io/r/oarepo/flask-taxonomies)
[![](https://img.shields.io/pypi/v/flask-taxonomies.svg)](https://pypi.org/pypi/flask-taxonomies)

<!--TOC-->

- [Flask Taxonomies](#flask-taxonomies)
  - [Installation](#installation)
  - [Terminology](#terminology)
  - [REST API](#rest-api)
    - [Retrieving resources](#retrieving-resources)
      - [``Prefer`` HTTP header](#prefer-http-header)
        - [Returned representation](#returned-representation)
        - [Includes and excludes](#includes-and-excludes)
          - [Including extra data](#including-extra-data)
          - [Excluding data](#excluding-data)
      - [Query parameters](#query-parameters)
      - [Selecting subset of term data](#selecting-subset-of-term-data)
      - [Pagination](#pagination)
    - [Taxonomy](#taxonomy)
      - [Creating](#creating)
      - [Updating](#updating)
        - [Replacing via HTTP PUT](#replacing-via-http-put)
        - [Patching with HTTP POST](#patching-with-http-post)
      - [Deleting](#deleting)
    - [Taxonomy Term](#taxonomy-term)
      - [Creating](#creating-1)
      - [Updating](#updating-1)
      - [Deleting](#deleting-1)
      - [Un-Deleting](#un-deleting)
      - [Moving](#moving)
      - [Renaming](#renaming)
  - [Configuration](#configuration)
    - [Configuration Variables](#configuration-variables)
    - [Security](#security)
      - [Recommended initial settings](#recommended-initial-settings)
  - [Python API](#python-api)
    - [Signals](#signals)

<!--TOC-->

## Installation

```bash
pip install flask-taxonomies
```

```python
from flask_taxonomies.ext import FlaskTaxonomies
from flask_taxonomies.views import blueprint
from flask import Flask
from flask_principal import Principal

app = Flask('__test__')

FlaskTaxonomies(app)
Principal(app)
app.register_blueprint(blueprint, url_prefix=app.config['FLASK_TAXONOMIES_URL_PREFIX'])

db = ...
from flask_taxonomies.models import Base
Base.metadata.create_all(db.engine)
```

## Terminology

**Taxonomy** is a tree of taxonomy terms. It is represented as a database object identified by
*code*. A taxonomy may contain its original url (in case the taxonomy is defined elsewhere)
and additional metadata as a json object (containing, for example, taxonomy title). It may also
contain a default set of selectors for filtering metadata.

**TaxonomyTerm** represents a single node in a taxonomy. It is identified by its *slug* 
and may contain additional metadata as json object. A term can contain children to represent
hierarchy of taxonomy terms. Term does not define ordering within children, it is up to 
application logic to define any ordering.   

## REST API

The rest API sits on the ``app.config['FLASK_TAXONOMIES_URL_PREFIX']`` url, implicitly 
``/api/2.0/taxonomies/``. It follows the REST API principles with pagination inspired
by GitHub API. 

### Retrieving resources

#### ``Prefer`` HTTP header

Implicitly, the API returns rather minimal representation. The amount of the returned metadata
can be changed via HTTP ``prefer`` header or alternatively by query parameters.

##### Returned representation

The ``prefer`` header is a standard way of telling what you expect to get
as a response to the request. It is defined in [rfc7240](https://tools.ietf.org/html/rfc7240).

If the header is not present, ``return=representation`` is assumed. One can specify ``return=minimal``
to obtain minimal dataset, or other return types (even your own) defined in ``FLASK_TAXONOMIES_REPRESENTATION`` 
config.

**return=minimal**

returns the minimal representation. Mostly not usable directly as it does not return any metadata,
just the code/slug.

*Listing:*
```console
$ curl -i -H "Prefer: return=minimal" http://127.0.0.1:5000/api/2.0/taxonomies/

HTTP/1.0 200 OK
Link: <http://127.0.0.1:5000/api/2.0/taxonomies/>; rel=self

[
  {
    "code": "country"
  }
]
```

*Get taxonomy:*
```console
$ curl -i -H "Prefer: return=minimal" http://127.0.0.1:5000/api/2.0/taxonomies/country

HTTP/1.0 200 OK
Content-Type: application/json

{
  "code": "country"
}
```

*Get term:*
```console
$ curl -i -H "Prefer: return=minimal" http://127.0.0.1:5000/api/2.0/taxonomies/country/europe

HTTP/1.0 200 OK
Link: <http://127.0.0.1:5000/api/2.0/taxonomies/country/europe>; rel=self
Link: <http://127.0.0.1:5000/api/2.0/taxonomies/country/europe?representation:include=dsc>; rel=tree

{
  "slug": "europe"
}
```

**return=representation**

this is the default return type. Returns all user data declared on taxonomy/term together with
ancestor and urls. For example:

*Listing:*
```console
$ curl -i http://127.0.0.1:5000/api/2.0/taxonomies/
HTTP/1.0 200 OK
Link: <http://127.0.0.1:5000/api/2.0/taxonomies/>; rel=self

[
  {
    "code": "country", 
    "links": {
      "custom": "https://www.kaggle.com/nikitagrec/world-capitals-gps/data", 
      "self": "http://127.0.0.1:5000/api/2.0/taxonomies/country/"
    }, 
    "title": "List of countries"
  }
]
```

*Get term:*
```console
$ curl -i http://127.0.0.1:5000/api/2.0/taxonomies/country/europe/cz
HTTP/1.0 200 OK
Link: <http://127.0.0.1:5000/api/2.0/taxonomies/country/europe/cz>; rel=self
Link: <http://127.0.0.1:5000/api/2.0/taxonomies/country/europe/cz?representation:include=dsc>; rel=tree

{
  "CapitalLatitude": "50.083333333333336", 
  "CapitalLongitude": "14.466667", 
  "CapitalName": "Prague", 
  "ContinentName": "Europe", 
  "CountryCode": "CZ", 
  "CountryName": "Czech Republic", 
  "ancestors": [
    {
      "links": {
        "self": "http://127.0.0.1:5000/api/2.0/taxonomies/country/europe"
      }
    }
  ], 
  "links": {
    "self": "http://127.0.0.1:5000/api/2.0/taxonomies/country/europe/cz"
  }
}
```

``Europe`` has no user data, so it contains only the ``links`` section.

##### Includes and excludes

The returned representation can be modified by specifying which metadata should be included/excluded. 
Currently supported includes/excludes are:

```python
INCLUDE_URL = 'url'
INCLUDE_DESCENDANTS_URL = 'drl'
INCLUDE_DESCENDANTS_COUNT = 'dcn'
INCLUDE_ANCESTORS_HIERARCHY = 'anh'
INCLUDE_ANCESTORS = 'anc'
INCLUDE_ANCESTOR_LIST = 'anl'
INCLUDE_DATA = 'data'
INCLUDE_ID = 'id'
INCLUDE_DESCENDANTS = 'dsc'
INCLUDE_ENVELOPE='env'
INCLUDE_DELETED = 'del'
INCLUDE_SLUG = 'slug'
INCLUDE_LEVEL = 'lvl'
INCLUDE_STATUS = 'sta'
```

###### Including extra data

Examples:

**Include record url in response**

```console
$ curl -i -H "Prefer: return=minimal; include=url" \
  http://127.0.0.1:5000/api/2.0/taxonomies/country/europe

HTTP/1.0 200 OK
Link: <http://127.0.0.1:5000/api/2.0/taxonomies/country/europe>; rel=self
Link: <http://127.0.0.1:5000/api/2.0/taxonomies/country/europe?representation:include=dsc>; rel=tree

{
  "links": {
    "self": "http://127.0.0.1:5000/api/2.0/taxonomies/country/europe"
  }, 
  "slug": "europe"
}
```

Adds a ``links`` section to payload with record url (``"self":``)

**Include descendants url in response**

```console
$ curl -i -H "Prefer: return=minimal; include=url drl" \
  http://127.0.0.1:5000/api/2.0/taxonomies/country/europe

HTTP/1.0 200 OK
Link: <http://127.0.0.1:5000/api/2.0/taxonomies/country/europe>; rel=self
Link: <http://127.0.0.1:5000/api/2.0/taxonomies/country/europe?representation:include=dsc>; rel=tree

{
  "links": {
    "self": "http://127.0.0.1:5000/api/2.0/taxonomies/country/europe", 
    "tree": "http://127.0.0.1:5000/api/2.0/taxonomies/country/europe?representation:include=dsc"
  }, 
  "slug": "europe"
}
```

Adds a ``links`` section to payload with recoord url with descendants (``"tree":``)

**Include descendants count in response**

```console
$ curl -i -H "Prefer: return=minimal; include=dcn" \
  http://127.0.0.1:5000/api/2.0/taxonomies/country/europe

HTTP/1.0 200 OK
Link: <http://127.0.0.1:5000/api/2.0/taxonomies/country/europe>; rel=self
Link: <http://127.0.0.1:5000/api/2.0/taxonomies/country/europe?representation:include=dsc>; rel=tree

{
  "slug": "europe",
  "descendants_count": 58
}
```

Adds a ``descendant_count`` with a number of descendant terms under the term. The value is 0
if the term is a leaf term.

On taxonomy, returns the total number of terms in taxonomy:

```console
$ curl -i -H "Prefer: return=minimal; include=dcn" \
  http://127.0.0.1:5000/api/2.0/taxonomies/country

HTTP/1.0 200 OK
Link: <http://127.0.0.1:5000/api/2.0/taxonomies/country>; rel=self
Link: <http://127.0.0.1:5000/api/2.0/taxonomies/country?representation:include=dsc>; rel=tree

{
  "code": "country",
  "descendants_count": 253
}
```

**Include ancestors with hierarchy in response**

```console
$ curl -i -H "Prefer: return=minimal; include=anh url" \
  http://127.0.0.1:5000/api/2.0/taxonomies/country/europe/cz

{
  "children": [
    {
      "links": {
        "self": "http://127.0.0.1:5000/api/2.0/taxonomies/country/europe/cz"
      }, 
      "slug": "europe/cz"
    }
  ], 
  "links": {
    "self": "http://127.0.0.1:5000/api/2.0/taxonomies/country/europe"
  }, 
  "slug": "europe",
  "ancestor": true
}
```

If the term has ancestors, they are serialized and the term is included as their
child. This is useful for example when showing the taxonomy in tree form - the
rendering mechanism for the tree will stay the same. All ancestor terms are marked
with ``ancestor=true`` flag to help with ui rendering (for example to gray ancestors).

Adding url as well is recommended to get urls of ancestors.

**Include ancestors without hierarchy in response**

```console
$ curl -i -H "Prefer: return=minimal; include=anc url" \
  http://127.0.0.1:5000/api/2.0/taxonomies/country/europe/cz

HTTP/1.0 200 OK
Link: <http://127.0.0.1:5000/api/2.0/taxonomies/country/europe/cz>; rel=self
Link: <http://127.0.0.1:5000/api/2.0/taxonomies/country/europe/cz?representation:include=dsc>; rel=tree

{
  "ancestors": [
    {
      "links": {
        "self": "http://127.0.0.1:5000/api/2.0/taxonomies/country/europe"
      }, 
      "slug": "europe"
    }
  ], 
  "links": {
    "self": "http://127.0.0.1:5000/api/2.0/taxonomies/country/europe/cz"
  }, 
  "slug": "europe/cz"
}
```
The ancestors are rendered inside the ``ancestors`` element. Adding url as well 
is recommended to get urls of ancestors.

**Include ancestor list in response**

```console
$ curl -i -H "Prefer: return=representation; include=anl ant par" \
  http://127.0.0.1:5000/api/2.0/taxonomies/country/europe/cz

HTTP/1.0 200 OK
Link: <http://127.0.0.1:5000/api/2.0/taxonomies/country/europe/cz>; rel=self
Link: <http://127.0.0.1:5000/api/2.0/taxonomies/country/europe/cz?representation:include=dsc>; rel=tree

[
  {
    "links": {
      "self": "http://127.0.0.1:5000/api/2.0/taxonomies/country/europe"
    },
    "is_ancestor": true
  }, 
  {
    "CapitalLatitude": "50.083333333333336", 
    "CapitalLongitude": "14.466667", 
    "CapitalName": "Prague", 
    "ContinentName": "Europe", 
    "CountryCode": "CZ", 
    "CountryName": "Czech Republic", 
    "links": {
      "self": "http://127.0.0.1:5000/api/2.0/taxonomies/country/europe/cz",
      "parent": "http://127.0.0.1:5000/api/2.0/taxonomies/country/europe"
    },
    "is_ancestor": false
  }
]
```
The ancestors are rendered on the same level as the term. This rendering might be used
for example when serializing the taxonomy term to elasticsearch - this way all the 
ancestors are serialized within one array and indexed into one object in ES.

Note also the:
   * ``ant`` - adds ``ancestor`` field (``false`` if this is the term that has been queried), 
     ``true`` for ancestor term
   * ``parent`` - adds link to the parent within ``links`` section

Even one-term result is rendered as array:

```console
$ curl -i -H "Prefer: return=representation; include=anl ant par" \
  http://127.0.0.1:5000/api/2.0/taxonomies/country/europe

HTTP/1.0 200 OK
Link: <http://127.0.0.1:5000/api/2.0/taxonomies/country/europe>; rel=self
Link: <http://127.0.0.1:5000/api/2.0/taxonomies/country/europe?representation:include=dsc>; rel=tree

[
  {
    "links": {
      "self": "http://127.0.0.1:5000/api/2.0/taxonomies/country/europe"
    },
    "is_ancestor": false
  }
]
```

**Include data in response**

This is the default setting unless ``minimal`` representation is selected. In this case,
pass ``include=data`` to have data included.

```console
$ curl -i -H "Prefer: return=minimal; include=data" \
  http://127.0.0.1:5000/api/2.0/taxonomies/country/europe/cz

HTTP/1.0 200 OK
Link: <http://127.0.0.1:5000/api/2.0/taxonomies/country/europe/cz>; rel=self
Link: <http://127.0.0.1:5000/api/2.0/taxonomies/country/europe/cz?representation:include=dsc>; rel=tree

{
  "CapitalLatitude": "50.083333333333336", 
  "CapitalLongitude": "14.466667", 
  "CapitalName": "Prague", 
  "ContinentName": "Europe", 
  "CountryCode": "CZ", 
  "CountryName": "Czech Republic", 
  "slug": "europe/cz"
}
```

**Include id in response**

Use ``include=id`` to get the internal id included. This is rarely needed as API does not accept
this id at all.

**Include descendant terms in response**

To serialize descendants into the response, use ``include=dsc``:

```console
$ curl -i -H "Prefer: return=minimal; include=dsc" \
  http://127.0.0.1:5000/api/2.0/taxonomies/country/europe

HTTP/1.0 200 OK
Link: <http://127.0.0.1:5000/api/2.0/taxonomies/country/europe>; rel=self
Link: <http://127.0.0.1:5000/api/2.0/taxonomies/country/europe?representation:include=dsc>; rel=tree

{
  "children": [
    {
      "slug": "europe/ad"
    }, 
    {
      "slug": "europe/al"
    }, 
    ...
    {
      "slug": "europe/va"
    }
  ],
  "slug": "europe"
}
```

**Include slug in response**

Adds ``slug`` to response. In the ``minimal`` mode the slug is added automatically, use this tag to 
add it in ``return=representation``:

```console
$ curl -i -H "Prefer: return=representation; include=slug" \
  http://127.0.0.1:5000/api/2.0/taxonomies/country/europe/cz

HTTP/1.0 200 OK
Link: <http://127.0.0.1:5000/api/2.0/taxonomies/country/europe/cz>; rel=self
Link: <http://127.0.0.1:5000/api/2.0/taxonomies/country/europe/cz?representation:include=dsc>; rel=tree

{
  "CapitalLatitude": "50.083333333333336", 
  "CapitalLongitude": "14.466667", 
  "CapitalName": "Prague", 
  "ContinentName": "Europe", 
  "CountryCode": "CZ", 
  "CountryName": "Czech Republic", 
  "ancestors": [
    {
      "links":{"self":"http://127.0.0.1:5000/api/2.0/taxonomies/country/europe"},
      "slug": "europe"
    }
  ], 
  "links":{"self":"http://127.0.0.1:5000/api/2.0/taxonomies/country/europe/cz"},
  "slug": "europe/cz"
}
```

**Include hierarchy level in response**

Adds hierarchy level to taxonomy term. Top-level terms have ``level=1``, taxonomy ``0``.

```console
$ curl -i -H "Prefer: return=minimal; include=lvl" \
  http://127.0.0.1:5000/api/2.0/taxonomies/country/europe/cz

HTTP/1.0 200 OK
Link: <http://127.0.0.1:5000/api/2.0/taxonomies/country/europe/cz>; rel=self
Link: <http://127.0.0.1:5000/api/2.0/taxonomies/country/europe/cz?representation:include=dsc>; rel=tree

{
  "level": 2, 
  "slug": "europe/cz"
}
```

**Include deleted terms in response**

Let's delete a country from Europe:

```console
$ curl -X DELETE -i http://127.0.0.1:5000/api/2.0/taxonomies/country/europe/gb

HTTP/1.0 200 OK
Content-Type: application/json

{
  "CapitalLatitude": "51.5", 
  "CapitalLongitude": "-0.083333", 
  "CapitalName": "London", 
  "ContinentName": "Europe", 
  "CountryCode": "GB", 
  "CountryName": "United Kingdom",
  "links":{"self":"http://127.0.0.1:5000/api/2.0/taxonomies/country/europe/gb"}
}
```

United Kingdom has indeed been removed from Europe:

```console
$ curl -i http://127.0.0.1:5000/api/2.0/taxonomies/country/europe/gb
HTTP/1.0 410 GONE

{
  "message": "http://127.0.0.1:5000/api/2.0/taxonomies/country/europe/gb was not found on the server",
  "reason": "deleted"
}
```

Now run the GET again with removed terms included:

```console
$ curl -i -H "Prefer: return=minimal; include=del sta" \
  http://127.0.0.1:5000/api/2.0/taxonomies/country/europe/gb

HTTP/1.0 200 OK
Link: <http://127.0.0.1:5000/api/2.0/taxonomies/country/europe/gb>; rel=self
Link: <http://127.0.0.1:5000/api/2.0/taxonomies/country/europe/gb?representation:include=dsc>; rel=tree

{
  "slug": "europe/gb", 
  "status": "deleted",
  "busy_count":0,
  "descendants_busy_count":0
}
```

**Include term status**

Including the status will add the following metadata:
  * ``status`` of the term (alive, delete_pending, deleted, moved)
  * ``busy_count`` - an integer saying how "busy" the term is. Being busy means
    that a potentially destructive operation (such as deleting, moving or renaming slug)
    is in progress. 
  * ``descendants_busy_count`` - a number of descendants that are busy
  
```console
$ curl -i -H "Prefer: return=minimal; include=del sta dsc" \
  http://127.0.0.1:5000/api/2.0/taxonomies/country/europe

HTTP/1.0 200 OK
Link: <http://127.0.0.1:5000/api/2.0/taxonomies/country/europe>; rel=self
Link: <http://127.0.0.1:5000/api/2.0/taxonomies/country/europe?representation:include=dsc>; rel=tree

{
  "busy_count":0,
  "children": [
    {
      "busy_count":0,
      "descendants_busy_count":0,
      "slug": "europe/ad", 
      "status": "alive"
    }, 
    ...
    {
      "busy_count":0,
      "descendants_busy_count":0,
      "slug": "europe/gb", 
      "status": "deleted"
    }, 
    ...
    {
      "busy_count":0,
      "descendants_busy_count":0,
      "slug": "europe/va", 
      "status": "alive"
    }
  ], 
  "descendants_busy_count":0,
  "slug": "europe", 
  "status": "alive"
}
```

###### Excluding data

To exclude data from the representation, use ``exclude=...`` in prefer header.

#### Query parameters

Values from the ``prefer`` header can be used as query parameters:

```
curl -i -H "Prefer: return=minimal;" \
  "http://127.0.0.1:5000/api/2.0/taxonomies/country/europe?
     representation:include=sta,url&representation:exclude=slug"

HTTP/1.0 200 OK
Link: <http://127.0.0.1:5000/api/2.0/taxonomies/country/europe>; rel=self
Link: <http://127.0.0.1:5000/api/2.0/taxonomies/country/europe?representation:include=dsc>; rel=tree

{
  "links": {
    "self": "http://127.0.0.1:5000/api/2.0/taxonomies/country/europe"
  }, 
  "status": "alive"
}
```

#### Selecting subset of term data

Use ``select=<json pointer> <json pointer>...`` in ``prefer`` header or ``representation:select=`` query parameter
to select just part of user data:

```console
$ curl -i -H "Prefer: return=representation;select=/CapitalName /CountryCode" \ 
    "http://127.0.0.1:5000/api/2.0/taxonomies/country/europe/cz"

HTTP/1.0 200 OK
Link: <http://127.0.0.1:5000/api/2.0/taxonomies/country/europe/cz>; rel=self
Link: <http://127.0.0.1:5000/api/2.0/taxonomies/country/europe/cz?representation:include=dsc>; rel=tree

{
  "CapitalName": "Prague", 
  "CountryCode": "CZ", 
  "ancestors": [
    {
      "links": {
        "self": "http://127.0.0.1:5000/api/2.0/taxonomies/country/europe"
      }
    }
  ], 
  "links": {
    "self": "http://127.0.0.1:5000/api/2.0/taxonomies/country/europe/cz"
  }
}
```

#### Maximum levels

When descendants are selected, a maximum level of descendants can be specified via
``levels=<n>`` part of ``prefer`` header (or representation:levels=n in the query).

Example:

 ```console
$ curl -i -H "Prefer: return=representation; levels=1" \ 
    "http://127.0.0.1:5000/api/2.0/taxonomies/country"

HTTP/1.0 200 OK
Link: <http://127.0.0.1:5000/api/2.0/taxonomies/country>; rel=self
Link: <http://127.0.0.1:5000/api/2.0/taxonomies/country?representation:include=dsc>; rel=tree

{
        'children': [
            {'slug': 'africa'},
            {'slug': 'antarctica'},
            {'slug': 'asia'},
            {'slug': 'australia'},
            {'slug': 'central-america'},
            {'slug': 'europe'},
            {'slug': 'north-america'},
            {'slug': 'south-america'}
        ],
        'code': 'country',
        'title': 'List of countries'
}
```

#### Pagination

If descendants are requested without further arguments the whole tree is returned (well, in fact 
at most FLASK_TAXONOMIES_MAX_RESULTS_RETURNED terms to prevent server crash). This leads to high amount 
of data transferred and possibly a client crash. To prevent this, pagination should be used on larger
taxonomies.

Specify ``size`` argument to have at most this number of taxonomy terms returned. For example:

```console
$ curl -i -H "Prefer: return=minimal;" \
  "http://127.0.0.1:5000/api/2.0/taxonomies/country/europe?representation:include=dsc&size=5"

HTTP/1.0 200 OK
Link: <http://127.0.0.1:5000/api/2.0/taxonomies/country/europe>; rel=self
Link: <http://127.0.0.1:5000/api/2.0/taxonomies/country/europe?representation:include=dsc>; rel=tree
X-Page: 1
X-PageSize: 5
X-Total: 58

{
  "children": [
    {
      "slug": "europe/ad"
    }, 
    {
      "slug": "europe/al"
    }, 
    {
      "slug": "europe/am"
    }, 
    {
      "slug": "europe/at"
    }
  ], 
  "slug": "europe"
}
```

This returns 5 terms - europe and 4 children. To return the next page, add ``page=2`` argument:

```console
$ curl -i -H "Prefer: return=minimal;" \
  "http://127.0.0.1:5000/api/2.0/taxonomies/country/europe?representation:include=dsc&size=5&page=4"

HTTP/1.0 200 OK
Link: <http://127.0.0.1:5000/api/2.0/taxonomies/country/europe/dk>; rel=self
Link: <http://127.0.0.1:5000/api/2.0/taxonomies/country/europe/dk?representation:include=dsc>; rel=tree
X-Page: 4
X-PageSize: 5
X-Total: 58

[
  {
    "slug": "europe/dk"
  }, 
  {
    "slug": "europe/ee"
  }, 
  {
    "slug": "europe/es"
  }, 
  {
    "slug": "europe/fi"
  }, 
  {
    "slug": "europe/fo"
  }
]
```

Note that the first page contains the root element and the second does not. To fix it, either use ``include=anh``
to always get hierarchical representation:

```console
$ curl -i -H "Prefer: return=minimal;" \
  "http://127.0.0.1:5000/api/2.0/taxonomies/country/europe?representation:include=dsc,anh&size=5&page=2"

HTTP/1.0 200 OK
Link: <http://127.0.0.1:5000/api/2.0/taxonomies/country/europe/ax>; rel=self
Link: <http://127.0.0.1:5000/api/2.0/taxonomies/country/europe/ax?representation:include=dsc>; rel=tree
X-Page: 2
X-PageSize: 5
X-Total: 58

{
  "ancestor": true, 
  "children": [
    {
      "slug": "europe/ax"
    }, 
    {
      "slug": "europe/az"
    }, 
    {
      "slug": "europe/ba"
    }, 
    {
      "slug": "europe/be"
    }
  ], 
  "slug": "europe"
}
```

or, if interested only in descendants and not the node itself, ``exclude=self``

```console
$ curl -i -H "Prefer: return=minimal;" \
  "http://127.0.0.1:5000/api/2.0/taxonomies/country/europe?
     representation:include=dsc&representation:exclude=self&size=5&page=1"

HTTP/1.0 200 OK
Link: <http://127.0.0.1:5000/api/2.0/taxonomies/country/europe/ad>; rel=self
Link: <http://127.0.0.1:5000/api/2.0/taxonomies/country/europe/ad?representation:include=dsc>; rel=tree
X-Page: 1
X-PageSize: 5
X-Total: 58

[
  {
    "slug": "europe/ad"
  }, 
  {
    "slug": "europe/al"
  }, 
  {
    "slug": "europe/am"
  }, 
  {
    "slug": "europe/at"
  }, 
  {
    "slug": "europe/ax"
  }
]
```

#### Searching

Use ``q=`` parameter to search within terms. Returns all the resources
whose ``metadata`` contain the expression in q.

##### Simple query

If ``q`` is a simple string not containing ':' or string in quotes,
it is interpreted as a string that must be present in any of 
values inside the json.

The current implementation is dependent on the database backend
and might perform sub-optimal ``ilike %x%`` query on textified json.

```console
$ curl -i -H "Prefer: return=minimal; include=data dsc; exclude=self" \
  http://127.0.0.1:5000/api/2.0/taxonomies/country/europe?q=Prague

HTTP/1.0 200 OK
Link: <http://127.0.0.1:5000/api/2.0/taxonomies/country/europe>; rel=self
Link: <http://127.0.0.1:5000/api/2.0/taxonomies/country/europe?representation:include=dsc>; rel=tree

[
    {
      "CapitalLatitude": "50.083333333333336", 
      "CapitalLongitude": "14.466667", 
      "CapitalName": "Prague", 
      "ContinentName": "Europe", 
      "CountryCode": "CZ", 
      "CountryName": "Czech Republic", 
      "slug": "europe/cz"
    }
]
```

##### Lucene-like query

If the ``q`` contains a ':' character not enclosed in quotes,
it is parsed as a query in lucene syntax, with the following
allowed constructs:

   * path:value for matching value at the given path
   * a.b.c:value for representing nested paths 
   * AND, OR, NOT, brackets
   
The query will be executed if the database or search backend support
it. If not supported, HTTP 501 will be returned.

### Taxonomy
#### Creating

To create a taxonomy, either use HTTP PUT:

```console
$ curl -i -X PUT 'http://127.0.0.1:5000/api/2.0/taxonomies/test' \
-H 'Content-Type: application/json' \
--data-raw '{
    "title": "Test taxonomy"
}'

HTTP/1.0 201 CREATED
Link: <http://127.0.0.1:5000/api/2.0/taxonomies/test/>; rel=self
Link: <http://127.0.0.1:5000/api/2.0/taxonomies/test/?representation:include=dsc>; rel=tree
Location: http://127.0.0.1:5000/api/2.0/taxonomies/test/

{
  "code": "test", 
  "links": {
    "self": "http://127.0.0.1:5000/api/2.0/taxonomies/test/"
  }, 
  "title": "Test taxonomy"
}
```

Or HTTP POST with ``code`` in the payload

```console
$ curl -i -X POST 'http://127.0.0.1:5000/api/2.0/taxonomies/' \
    -H 'Content-Type: application/json' --data-raw '{
    "title": "Test taxonomy 1", "code": "test1"
}'

HTTP/1.0 201 CREATED
Link: <http://127.0.0.1:5000/api/2.0/taxonomies/test1/>; rel=self
Link: <http://127.0.0.1:5000/api/2.0/taxonomies/test1/?representation:include=dsc>; rel=tree
Location: http://127.0.0.1:5000/api/2.0/taxonomies/test1/

{
  "code": "test1", 
  "links": {
    "self": "http://127.0.0.1:5000/api/2.0/taxonomies/test1/"
  }, 
  "title": "Test taxonomy 1"
}
```


#### Updating

##### Replacing via HTTP PUT

```console
$ curl -i -X PUT 'http://127.0.0.1:5000/api/2.0/taxonomies/test' \
  --header 'Content-Type: application/json' --data-raw '{
    "title": "Test taxonomy updated"
}'

HTTP/1.0 200 OK
Link: <http://127.0.0.1:5000/api/2.0/taxonomies/test/>; rel=self
Link: <http://127.0.0.1:5000/api/2.0/taxonomies/test/?representation:include=dsc>; rel=tree

{
  "code": "test", 
  "links": {
    "self": "http://127.0.0.1:5000/api/2.0/taxonomies/test/"
  }, 
  "title": "Test taxonomy updated"
}
```

Note that terms are not updated nor removed when taxonomy metadata are updated.

##### Patching with HTTP PATCH

```console
$ curl -i -X PATCH 'http://127.0.0.1:5000/api/2.0/taxonomies/test' \
  --header 'Content-Type: application/json' --data-raw '[{
    "op": "replace", "path": "/title", "value": "Test taxonomy updated via patch"
}]'

HTTP/1.0 200 OK
Link: <http://127.0.0.1:5000/api/2.0/taxonomies/test/>; rel=self
Link: <http://127.0.0.1:5000/api/2.0/taxonomies/test/?representation:include=dsc>; rel=tree

{
  "code": "test", 
  "links": {
    "self": "http://127.0.0.1:5000/api/2.0/taxonomies/test/"
  }, 
  "title": "Test taxonomy updated via patch"
}
```

#### Deleting

```console
$ curl -i -X DELETE 'http://127.0.0.1:5000/api/2.0/taxonomies/test1'

HTTP/1.0 204 NO CONTENT
Content-Type: text/html; charset=utf-8
```

### Taxonomy Term
#### Creating

As in creating taxonomy, term can be created either via HTTP PUT:

```console
$ curl -i -X PUT 'http://127.0.0.1:5000/api/2.0/taxonomies/test/term' \
  --header 'Content-Type: application/json' --data-raw '{
    "title": "Test Term"
}'

HTTP/1.0 201 CREATED
Link: <http://127.0.0.1:5000/api/2.0/taxonomies/test/term>; rel=self
Link: <http://127.0.0.1:5000/api/2.0/taxonomies/test/term?representation:include=dsc>; rel=tree
Location: http://127.0.0.1:5000/api/2.0/taxonomies/test/term

{
  "links": {
    "self": "http://127.0.0.1:5000/api/2.0/taxonomies/test/term"
  }, 
  "title": "Test Term"
}
```

or POST:

```console
$ curl -i -X POST 'http://127.0.0.1:5000/api/2.0/taxonomies/test' \
  --header 'Content-Type: application/json' --data-raw '{
    "title": "Test term 1", "slug": "term1"
}'

HTTP/1.0 201 CREATED
Link: <http://127.0.0.1:5000/api/2.0/taxonomies/test/term1>; rel=self
Link: <http://127.0.0.1:5000/api/2.0/taxonomies/test/term1?representation:include=dsc>; rel=tree
Location: http://127.0.0.1:5000/api/2.0/taxonomies/test/term1

{
  "links": {
    "self": "http://127.0.0.1:5000/api/2.0/taxonomies/test/term1"
  }, 
  "title": "Test term 1"
}
``` 
 
As PUT/POST operation also mean updating term if slug exists, to be sure
that you are creating a new one use ``If-None-Match: '*'`` header:

```console
$ curl -i -X PUT 'http://127.0.0.1:5000/api/2.0/taxonomies/test/term' \
  --header 'Content-Type: application/json' \
  --header 'If-None-Match: '*'' \
  --data-raw '{
    "title": "Test Term"
}'

HTTP/1.0 412 Precondition Failed

{
     "message": "The taxonomy already contains a term on this slug. As If-None-Match: '*' has been requested, not modifying the term",
     "reason": "term-exists"
}
```
 
Terms can be created within terms via HTTP PUT:

```console
$ curl -i -X PUT 'http://127.0.0.1:5000/api/2.0/taxonomies/test/term/nested' \
  --header 'Content-Type: application/json' --data-raw '{
    "title": "Nested Term"
}'

HTTP/1.0 201 CREATED
Link: <http://127.0.0.1:5000/api/2.0/taxonomies/test/term/nested>; rel=self
Link: <http://127.0.0.1:5000/api/2.0/taxonomies/test/term/nested?representation:include=dsc>; rel=tree
Location: http://127.0.0.1:5000/api/2.0/taxonomies/test/term/nested

{
  "ancestors":[
     {
       "links":{
         "self":"http://127.0.0.1:5000/api/2.0/taxonomies/test/term"
       },
       "title":"Test Term"
     }
  ],
  "links": {
    "self": "http://127.0.0.1:5000/api/2.0/taxonomies/test/term/nested"
  }, 
  "title": "Nested Term"
}
```

or POST:

```console
$ curl -i -X POST 'http://127.0.0.1:5000/api/2.0/taxonomies/test/term1' \
  --header 'Content-Type: application/json' --data-raw '{
    "title": "Test nested term 1", "slug": "nested1"
}'

HTTP/1.0 201 CREATED
Link: <http://127.0.0.1:5000/api/2.0/taxonomies/test/term1/nested1>; rel=self
Link: <http://127.0.0.1:5000/api/2.0/taxonomies/test/term1/nested1?representation:include=dsc>; rel=tree
Location: http://127.0.0.1:5000/api/2.0/taxonomies/test/term1/nested1

{
  "ancestors":[
     {
       "links":{
         "self":"http://127.0.0.1:5000/api/2.0/taxonomies/test/term1"
       },
       "title":"Test term 1"
     }
  ],
  "links": {
    "self": "http://127.0.0.1:5000/api/2.0/taxonomies/test/term1/nested1"
  }, 
  "title": "Test nested term 1"
}
``` 

#### Updating

As for taxonomy, use HTTP ``PUT``:

```console
$ curl -i -X PUT 'http://127.0.0.1:5000/api/2.0/taxonomies/test/term' \
    --header 'Content-Type: application/json' --data-raw '{
    "title": "Test Term updated"                 
}'

HTTP/1.0 200 OK
Link: <http://127.0.0.1:5000/api/2.0/taxonomies/test/term>; rel=self
Link: <http://127.0.0.1:5000/api/2.0/taxonomies/test/term?representation:include=dsc>; rel=tree

{
  "links": {
    "self": "http://127.0.0.1:5000/api/2.0/taxonomies/test/term"
  }, 
  "title": "Test Term updated"
}
```

or ``PATCH``:

```console
$ curl -i -X PATCH 'http://127.0.0.1:5000/api/2.0/taxonomies/test/term' \
  --header 'Content-Type: application/json' --data-raw '[{
    "op": "replace", "path": "/title", "value": "Test taxonomy term updated via patch"
}]'

HTTP/1.0 200 OK
Link: <http://127.0.0.1:5000/api/2.0/taxonomies/test/term>; rel=self
Link: <http://127.0.0.1:5000/api/2.0/taxonomies/test/term?representation:include=dsc>; rel=tree

{
  "links": {
    "self": "http://127.0.0.1:5000/api/2.0/taxonomies/test/term"
  }, 
  "title": "Test taxonomy term updated via patch"
}
```

As PUT operation also means creating term if slug does not exist, to be sure
that you are just updating use ``If-Match: '*'`` header:

```console
$ curl -i -X PUT 'http://127.0.0.1:5000/api/2.0/taxonomies/test/unknown' \
  --header 'Content-Type: application/json' \
  --header 'If-Match: '*'' \
  --data-raw '{
    "title": "Test Term"
}'

HTTP/1.0 412 Precondition Failed

{
         "message": "The taxonomy does not contain a term on this slug. As If-Match: '*' has been requested, not creating a new term",
         "reason": "term-does-not-exist"
}
```


#### Deleting

Use HTTP delete to remove a term. The removed term will be returned in the response:

```console
$ curl -i -X DELETE 'http://127.0.0.1:5000/api/2.0/taxonomies/test/term1'

HTTP/1.0 200 OK
Content-Type: application/json

{
  "links": {
    "self": "http://127.0.0.1:5000/api/2.0/taxonomies/test/term1"
  }, 
  "title": "Test term 1"
}
```

Subsequent GET returns 410:

```console
$ curl -i 'http://127.0.0.1:5000/api/2.0/taxonomies/test/term1'

HTTP/1.0 410 GONE

{
  "message": "http://127.0.0.1:5000/api/2.0/taxonomies/test/term1 was not found on the server",
  "reason": "deleted"
}
```

But the term stays on the server:

```console
$ curl -i 'http://127.0.0.1:5000/api/2.0/taxonomies/test/term?representation:include=del'
HTTP/1.0 200 OK
Link: <http://127.0.0.1:5000/api/2.0/taxonomies/test/term>; rel=self
Link: <http://127.0.0.1:5000/api/2.0/taxonomies/test/term?representation:include=dsc>; rel=tree

{
  "links": {
    "self": "http://127.0.0.1:5000/api/2.0/taxonomies/test/term"
  }, 
  "title": "Test taxonomy term updated via patch"
}
```

#### Un-Deleting

To salvage a deleted term, update it via PATCH, with an empty set of operations to keep it unmodified:

```console
$ curl -i -X PATCH -H "Prefer: return=minimal; include=del" \
   'http://127.0.0.1:5000/api/2.0/taxonomies/test/term' \
    --header 'Content-Type: application/json' --data-raw '[]'

HTTP/1.0 200 OK
Link: <http://127.0.0.1:5000/api/2.0/taxonomies/test/term>; rel=self
Link: <http://127.0.0.1:5000/api/2.0/taxonomies/test/term?representation:include=dsc>; rel=tree

{
  "slug": "term"
}
```

#### Moving

Use HTTP post with content type ``application/vnd.move`` and ``Destination`` header:

```console
$ curl -i -X POST \
   -H 'Content-Type: application/vnd.move' \
   -H "Destination: /" \
  'http://127.0.0.1:5000/api/2.0/taxonomies/test/term/nested'

HTTP/1.0 200 OK

{
    "links":{
        "self":"http://127.0.0.1:5000/api/2.0/taxonomies/test/nested"
    },
    "title":"Nested Term"
}
```

The original url returns 301:

```console
$ curl -i 'http://127.0.0.1:5000/api/2.0/taxonomies/test/term/nested'

HTTP/1.0 301 MOVED PERMANENTLY
Location: http://127.0.0.1:5000/api/2.0/taxonomies/test/nested
Link: <http://localhost/api/2.0/taxonomies/test/term/nested>; rel=self
Link: <http://localhost/api/2.0/taxonomies/test/nested>; rel=obsoleted_by

{
    "links": {
        "self": "http://localhost/api/2.0/taxonomies/test/term/nested", 
        "obsoleted_by": "http://localhost/api/2.0/taxonomies/test/nested"
    }, 
    "status": "moved"
}
```

#### Renaming

Use HTTP post with content type ``application/vnd.move`` and ``Rename`` header:

```console
$ curl -i -X POST \
   -H 'Content-Type: application/vnd.move' \
   -H "Rename: renamed-nested" \
  'http://127.0.0.1:5000/api/2.0/taxonomies/test/nested'

HTTP/1.0 200 OK

{
    "links":{
        "self":"http://127.0.0.1:5000/api/2.0/taxonomies/test/renamed-nested"
    },
    "title":"Nested Term"
}
```


The original url returns 301:

```console
$ curl -i 'http://127.0.0.1:5000/api/2.0/taxonomies/test/nested'

HTTP/1.0 301 MOVED PERMANENTLY
Location: http://127.0.0.1:5000/api/2.0/taxonomies/test/renamed-nested
Link: <http://localhost/api/2.0/taxonomies/test/nested>; rel=self
Link: <http://localhost/api/2.0/taxonomies/test/renamed-nested>; rel=obsoleted_by

{
    "links": {
        "self": "http://localhost/api/2.0/taxonomies/test/nested", 
        "obsoleted_by": "http://localhost/api/2.0/taxonomies/test/renamed-nested"
    }, 
    "status": "moved"
}
```


## Configuration

### Configuration Variables

``FLASK_TAXONOMIES_SERVER_NAME``

Server name hosting the taxonomies. If not set, SERVER_NAME is used.

``FLASK_TAXONOMIES_SERVER_SCHEME``

Scheme to use in generated urls, defaults to ``https``

``FLASK_TAXONOMIES_URL_PREFIX``

A prefix on which taxonomies are served, defaults to ``/api/2.0/taxonomies/``

``FLASK_TAXONOMIES_REPRESENTATION``

Values for ``Prefer: return=`` header. ``minimal`` and ``representation`` are obligatory,
you are free to add other return representations. 

```python
from flask_taxonomies.constants import *

FLASK_TAXONOMIES_REPRESENTATION = {
    'minimal': {
        'include': [INCLUDE_SLUG, INCLUDE_SELF],
        'exclude': [],
        'select': None,
        'options': {}
    },
    'representation': {
        'include': [INCLUDE_DATA, INCLUDE_ANCESTORS, 
                    INCLUDE_URL, INCLUDE_SELF],
        'exclude': [],
        'select': None,
        'options': {}
    },
    'full': {
        'include': [INCLUDE_DATA, INCLUDE_ANCESTORS, INCLUDE_URL, 
                    INCLUDE_DESCENDANTS_URL, INCLUDE_SELF],
        'exclude': [],
        'select': None,
        'options': {}
    }
}
```

``FLASK_TAXONOMIES_MAX_RESULTS_RETURNED``

Specifies max results returned when pagination is not used. Defaults to ``10000``.

### Security

Flask taxonomies uses ``flask-principal`` to handle security. The default permissions are
that everyone is allowed to read/create/update/delete/move all taxonomies and terms.

To restrict the access, specify permission factories (a function that returns a list of permission)
for each operation.

``FLASK_TAXONOMIES_PERMISSION_FACTORIES``

A dictionary of operation to a list of permissions.

```
FLASK_TAXONOMIES_PERMISSION_FACTORIES = {
    'taxonomy_list':   request -> List[Permission]
    'taxonomy_read':   request, taxonomy -> List[Permission]
    'taxonomy_create': request, code -> List[Permission]
    'taxonomy_update': request, taxonomy -> List[Permission]
    'taxonomy_delete': request, taxonomy -> List[Permission],

    'taxonomy_term_read':   request, taxonomy, slug -> List[Permission]
    'taxonomy_term_create': request, taxonomy, slug -> List[Permission]
    'taxonomy_term_update': request, taxonomy, term -> List[Permission]
    'taxonomy_term_delete': request, taxonomy, term -> List[Permission],
    'taxonomy_term_move': request, taxonomy, term, destination, rename -> List[Permission],
}
```
The right-hand side can be either a list/tuple of permissions, function with the above-mentioned
signatures or a string pointing to the implementation. The string form is resolved on 
the first request. 

If ``.can`` on any of the permissions returns True or the list is empty, access is granted.

#### Recommended initial settings

The recommended initial settings are read-only for everyone except admin role:

```python
from flask_principal import RoleNeed

FLASK_TAXONOMIES_PERMISSION_FACTORIES = {
    'taxonomy_create': [RoleNeed('admin')],
    'taxonomy_update': [RoleNeed('admin')],
    'taxonomy_delete': [RoleNeed('admin')],

    'taxonomy_term_create': [RoleNeed('admin')],
    'taxonomy_term_update': [RoleNeed('admin')],
    'taxonomy_term_delete': [RoleNeed('admin')],
    'taxonomy_term_move': [RoleNeed('admin')]
}
```

## Python API

The calls below use ``session`` as an optional parameter. If not supplied, session from
current_app is used. 

``TermIdentification`` is a class to identify taxonomy term, binding taxonomy (or its code),
slug or a term instance. See [flask_taxonomies/term_identification.py](./flask_taxonomies/term_identification.py)
for details.

```python
from flask_taxonomies.proxies import current_flask_taxonomies

# returns a taxonomy list
current_flask_taxonomies.list_taxonomies(session=None)

# returns a taxonomy with the given code. Fails by default if not found
current_flask_taxonomies.get_taxonomy(code, fail=True, session=None)

# creates a new taxonomy
current_flask_taxonomies.create_taxonomy(code, extra_data=None, url=None, 
    select=None, session=None)

# updates a taxonomy
current_flask_taxonomies.update_taxonomy(
    taxonomy: [Taxonomy, str], extra_data, 
    url=MISSING, select=MISSING,
    session=None)

# deletes a taxonomy
current_flask_taxonomies.delete_taxonomy(taxonomy: Taxonomy, session=None)

# lists terms within the taxonomy. 
current_flask_taxonomies.list_taxonomy(taxonomy: [Taxonomy, str], levels=None,
    status_cond=TaxonomyTerm.status == TermStatusEnum.alive,
    order=True, session=None)

# creates a new term inside a taxonomy
current_flask_taxonomies.create_term(ti: TermIdentification, 
    extra_data=None, session=None)

# updates a term, setting or patching extra_data
current_flask_taxonomies.update_term(ti: [TaxonomyTerm, TermIdentification],
    status_cond=TaxonomyTerm.status == TermStatusEnum.alive,
    extra_data=None, patch=False, status=MISSING, session=None)

# returns all descendants of a term
current_flask_taxonomies.descendants(ti: TermIdentification, levels=None,
    status_cond=TaxonomyTerm.status == TermStatusEnum.alive,
    order=True, session=None)

# returns a term and its descendants
current_flask_taxonomies.descendants_or_self(ti: TermIdentification, levels=None,
    status_cond=TaxonomyTerm.status == TermStatusEnum.alive,
    order=True, session=None)

# returns all ancestors of a term
current_flask_taxonomies.ancestors(ti: TermIdentification, 
    status_cond=TaxonomyTerm.status == TermStatusEnum.alive, session=None)

# returns term and its ancestors
current_flask_taxonomies.ancestors_or_self(ti: TermIdentification,
    status_cond=TaxonomyTerm.status == TermStatusEnum.alive, session=None)

# removes a term
current_flask_taxonomies.delete_term(ti: TermIdentification, 
    remove_after_delete=True, session=None)

# renames term's slug
current_flask_taxonomies.rename_term(ti: TermIdentification, new_slug=None,
    remove_after_delete=True, session=None)

# moves term into a new parent within the same taxonomy
current_flask_taxonomies.move_term(ti: TermIdentification, new_parent=None,
    remove_after_delete=True, session=None)
```

### Signals

See [flask_taxonomies/signals.py](flask_taxonomies/signals.py) for details