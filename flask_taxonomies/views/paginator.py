from flask import current_app, jsonify
from link_header import Link, LinkHeader
from sqlalchemy.engine import result
from sqlalchemy.orm.exc import NoResultFound
from werkzeug.utils import cached_property

from flask_taxonomies.constants import (
    INCLUDE_ANCESTOR_LIST,
    INCLUDE_ANCESTORS_HIERARCHY,
    INCLUDE_ENVELOPE,
    INCLUDE_SELF,
)
from flask_taxonomies.models import EnvelopeLinks

from .common import enrich_data_with_computed


class Paginator:
    def __init__(self, representation, data, page, size,
                 json_converter=None, envelope_links=None,
                 allow_empty=True, single_result=False, has_query=False):
        self.data = data
        self.page = page
        self.size = size
        self.count = None
        self.use_envelope = INCLUDE_ENVELOPE in representation
        self.json_converter = json_converter or (lambda _data: [x.json(representation=representation) for x in _data])
        self.allow_empty = allow_empty
        self.single_result = single_result
        self._envelope_links = envelope_links or self._default_envelope_links
        self.representation = representation
        self.has_query = has_query

    @cached_property
    def _data(self):
        if not self.has_query:
            self_offset = 0 if INCLUDE_SELF in self.representation else 1
        else:
            self_offset = 0
        if self.size:
            data = self.data
            if isinstance(data, (list, tuple)):
                self.count = len(data)
            else:
                self.count = self.data.count()

            if self.page > 1 and INCLUDE_ANCESTORS_HIERARCHY in self.representation:
                # second page should have one element less
                size_offset = 1 if self.size > 1 else 0
                # -size_offset is to remove the parent that will get added automatically
                data = list(data[self_offset + (self.page - 1) * self.size:
                                 self_offset + self.page * self.size - size_offset])
            else:
                data = list(data[self_offset + (self.page - 1) * self.size: self_offset + self.page * self.size])
        else:
            max_items = current_app.config['FLASK_TAXONOMIES_MAX_RESULTS_RETURNED']
            data = list(self.data[self_offset:max_items])
        data = [enrich_data_with_computed(x) for x in data]
        if not self.allow_empty and not data:
            raise NoResultFound()
        return self.json_converter(data), data

    def set_children(self, children):
        self._data[0][0]['children'] = children

    @property
    def headers(self):
        data, original = self._data
        links = self.envelope_links(self.representation, data, original).headers
        headers = {
            'Link': str(LinkHeader([Link(v, rel=k) for k, v in links.items()]))
        }
        if self.size:
            headers.update({
                'X-Page': self.page,
                'X-PageSize': self.size,
                'X-Total': self.count,
            })

        return headers, links

    def check_single_result(self, data, original):
        if self.single_result and not INCLUDE_ANCESTOR_LIST in self.representation:
            if not data:
                raise NoResultFound()

            if len(data) == 1:
                data = data[0]
                if INCLUDE_ENVELOPE in self.representation and self.size:
                    if self.size:
                        data.update({
                            'page': self.page,
                            'size': self.size,
                            'total': self.count,
                        })
                return data

        if INCLUDE_ENVELOPE in self.representation:
            links = self.envelope_links(self.representation, data, original).envelope
            data = {
                'data': data,
            }
            if links:
                data['links'] = links
            if self.size:
                data.update({
                    'page': self.page,
                    'size': self.size,
                    'total': self.count,
                })

        return data

    @property
    def paginated_data(self):
        data, original = self._data
        return self.check_single_result(data, original)

    @property
    def paginated_data_without_envelope(self):
        data = self.paginated_data
        if INCLUDE_ENVELOPE in self.representation:
            return data['data']
        else:
            return data

    @property
    def no_pagination(self):
        return not self.size

    def jsonify(self, status_code=200):
        ret = jsonify(self.paginated_data)
        headers, links = self.headers
        ret.headers.extend(headers)
        ret.status_code = status_code
        if ret.status_code == 201 and 'self' in links:
            ret.headers['Location'] = links['self']
        ret.content_type = 'application/json'  # seems to be lost when status code is set
        return ret

    def envelope_links(self, representation, data, links) -> EnvelopeLinks:
        el = self._envelope_links
        if callable(el):
            el = el(representation, data, links)
        return el

    def _default_envelope_links(self, representation, data, original_data):
        if not data:
            return EnvelopeLinks({}, {})
        return original_data[0].links(representation)
