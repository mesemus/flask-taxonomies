import json

from link_header import parse, LinkHeader, Link


def links2dict(links):
    return {
        l.rel: l.href for l in links.links
    }


def term_move_to_root_test(api, client, sample_taxonomy):
    resp = client.post('/api/2.0/taxonomies/test/a/aa', headers={
        'Destination': '/',
        'Content-Type': 'application/vnd.move'
    })
    assert resp.status_code == 200
    exp = {
        'links': {
            'self': 'http://localhost/api/2.0/taxonomies/test/aa',
        },
        'title': 'AA'
    }
    assert json.loads(resp.data) == exp
    taxonomies = client.get('/api/2.0/taxonomies/test/aa')
    assert json.loads(taxonomies.data) == exp

    resp = client.get('/api/2.0/taxonomies/test/a/aa')
    assert resp.status_code == 301
    assert resp.headers['Location'] == 'http://localhost/api/2.0/taxonomies/test/aa'
    links = parse(resp.headers['Link'])
    assert links2dict(links) == {
        'self': 'http://localhost/api/2.0/taxonomies/test/a/aa',
        'obsoleted_by': 'http://localhost/api/2.0/taxonomies/test/aa'
    }
    assert resp.json == {
        'links': {
            'obsoleted_by': 'http://localhost/api/2.0/taxonomies/test/aa',
            'self': 'http://localhost/api/2.0/taxonomies/test/a/aa'
        },
        'status': 'moved'
    }


def term_move_to_element_test(api, client, sample_taxonomy):
    resp = client.post('/api/2.0/taxonomies/test/b', headers={
        'Destination': '/a',
        'Content-Type': 'application/vnd.move'
    })
    assert resp.status_code == 200
    exp = {
        'ancestors': [
            {
                'links': {'self': 'http://localhost/api/2.0/taxonomies/test/a'},
                'title': 'A'
            }
        ],
        'links': {
            'self': 'http://localhost/api/2.0/taxonomies/test/a/b',
        },
        'title': 'B'
    }
    assert json.loads(resp.data) == exp
    taxonomies = client.get('/api/2.0/taxonomies/test/a/b')
    assert json.loads(taxonomies.data) == exp

    resp = client.get('/api/2.0/taxonomies/test/b')
    assert resp.status_code == 301
    assert resp.headers['Location'] == 'http://localhost/api/2.0/taxonomies/test/a/b'
    assert resp.json == {
        'links': {
            'obsoleted_by': 'http://localhost/api/2.0/taxonomies/test/a/b',
            'self': 'http://localhost/api/2.0/taxonomies/test/b'
        },
        'status': 'moved'
    }
