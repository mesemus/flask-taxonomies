import enum
import logging
from collections import namedtuple

import sqlalchemy.dialects
from flask import current_app
from sqlalchemy import (
    JSON,
    Column,
    Enum,
    ForeignKey,
    Index,
    Integer,
    String,
    UniqueConstraint,
)
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship
from werkzeug.utils import cached_property

from flask_taxonomies.constants import *
from flask_taxonomies.fields import PostgresSlugType, SlugType
from flask_taxonomies.proxies import current_flask_taxonomies

logger = logging.getLogger('taxonomies')


class TaxonomyError(Exception):
    pass


Base = declarative_base()


def _cast_set(x, return_none=False):
    if x is None and return_none:
        return None
    if not x:
        return set()
    return set(x)


class Representation:
    KNOWN_FEATURES = {
        PRETTY_PRINT,
        INCLUDE_ANCESTORS_HIERARCHY,
        INCLUDE_ANCESTORS,
        INCLUDE_ANCESTOR_LIST,
        INCLUDE_URL,
        INCLUDE_DATA,
        INCLUDE_ID,
        INCLUDE_DESCENDANTS,
        INCLUDE_DESCENDANTS_COUNT,
        INCLUDE_ENVELOPE,
        INCLUDE_LEVEL
    }

    def __init__(self, representation, include=None, exclude=None, select=None, options=None):
        self.representation = representation

        self._include = include
        self._exclude = exclude
        self._select = select
        self._options = options

    @property
    def has_include(self):
        return self._include is not None

    @property
    def has_exclude(self):
        return self._exclude is not None

    @property
    def has_select(self):
        return self._select is not None

    @cached_property
    def include(self):
        return _cast_set(self._include) | _cast_set(self._config['include'])

    @cached_property
    def exclude(self):
        return _cast_set(self._exclude) | _cast_set(self._config['exclude'])

    @cached_property
    def select(self):
        config_select = _cast_set(self._config['select'], return_none=True)
        self_select = _cast_set(self._select, return_none=True)

        if config_select is not None:
            if self_select is not None:
                return self_select | config_select
            else:
                return config_select
        elif self_select is not None:
            return self_select

    @cached_property
    def options(self):
        return self._options or self._config['options'] or {}

    @cached_property
    def _config(self):
        return current_app.config['FLASK_TAXONOMIES_REPRESENTATION'].get(
            self.representation, {
                'include': set(),
                'exclude': set(),
                'select': None,
                'options': {}
            })

    def __contains__(self, item):
        return item in self.include and item not in self.exclude

    def as_query(self):
        ret = {
            'representation:representation': self.representation,
        }
        if self.include:
            ret['representation:include'] = list(self.include)
        if self.exclude:
            ret['representation:exclude'] = list(self.exclude)
        if self.select:
            ret['representation:select'] = list(self.select)
        if self.options:
            for k, v in self.options.items():
                ret['representation:' + k] = str(v)
        return ret

    def copy(self, representation=None, include=None, exclude=None, select=None, options=None):
        return Representation(representation or self.representation,
                              include or self.include, exclude or self.exclude,
                              select or self.select,
                              options or self.options)

    def extend(self, include=None, exclude=None, select=None, options=None):
        if include:
            include = self.include | set(include)
        else:
            include = self.include
        if exclude:
            exclude = self.exclude | set(exclude)
        else:
            exclude = self.exclude
        if select:
            select = set(self.select or []) | set(select)
        else:
            select = self.select
        if options:
            options = {**self.options, **options}
        else:
            options = {**self.options}
        return Representation(self.representation, include, exclude, select, options)


DEFAULT_REPRESENTATION = Representation('representation')
PRETTY_REPRESENTATION = Representation('representation', include=[PRETTY_PRINT])

EnvelopeLinks = namedtuple('EnvelopeLinks', 'envelope headers')


class Taxonomy(Base):
    __tablename__ = 'taxonomy_taxonomy'

    id = Column(Integer, primary_key=True, autoincrement=True)
    code = Column(String(256), unique=True, index=True)
    url = Column(String(1024), unique=True, index=True)
    """
    Custom url of the taxonomy. If not set, the url is supposed to be
    <FLASK_TAXONOMIES_SERVER_NAME or SERVER_NAME>/api/2.0/taxonomies/<name>
    """
    extra_data = Column(JSON().with_variant(
        sqlalchemy.dialects.postgresql.JSONB, 'postgresql'))
    terms = relationship("TaxonomyTerm", cascade="all, delete", lazy="dynamic")

    select = Column(JSON().with_variant(
        sqlalchemy.dialects.postgresql.JSONB, 'postgresql'), nullable=True)

    def __str__(self):
        return 'Taxonomy[{}]'.format(self.code)

    def __repr__(self):
        return str(self)

    def links(self, representation=DEFAULT_REPRESENTATION) -> EnvelopeLinks:
        links = {}
        all_links = {}
        self_link = current_flask_taxonomies.taxonomy_url(self)
        all_links['self'] = self_link
        if self.url:
            all_links['custom'] = self.url
        if INCLUDE_URL in representation:
            links['self'] = self_link
            if self.url:
                links['custom'] = self.url

        descendants_link = current_flask_taxonomies.taxonomy_url(self, descendants=True)
        all_links['tree'] = descendants_link
        if INCLUDE_DESCENDANTS_URL in representation:
            links['tree'] = descendants_link

        return EnvelopeLinks(headers=all_links, envelope=links)

    def json(self, representation=DEFAULT_REPRESENTATION):
        """
        Returns a tuple of (json, links)
        :param representation:
        :return:
        """
        resp = {
            'code': self.code,
        }

        if INCLUDE_ID in representation:
            resp['id'] = self.id
        if INCLUDE_LEVEL in representation:
            resp['level'] = 0
        if INCLUDE_DATA in representation and self.extra_data:
            representation = self.merge_select(representation)
            resp.update(current_flask_taxonomies.extract_data(representation, self))
        if INCLUDE_DESCENDANTS_COUNT in representation and hasattr(self, 'descendants_count'):
            resp['descendants_count'] = self.descendants_count
        if INCLUDE_ENVELOPE in representation:
            resp = {
                'data': resp
            }

        if INCLUDE_URL in representation or INCLUDE_DESCENDANTS_URL in representation:
            resp['links'] = self.links(representation).envelope

        return resp

    def merge_select(self, representation: Representation):
        if self.select is not None and not representation.has_select:
            return representation.copy(select=self.select)
        return representation


class TermStatusEnum(enum.Enum):
    alive = 'A'
    """
    Alive taxonomy terms
    """

    deleted = 'D'
    """
    Taxonomy terms that have been deleted but should be kept in the database
    """

    delete_pending = 'd'
    """
    Taxonomy term that is in process of deletion. When its busy_count reaches 0,
    it will be permanently removed from the database
    """


class TaxonomyTerm(Base):
    __tablename__ = 'taxonomy_term'

    id = Column(Integer, primary_key=True, autoincrement=True)
    slug = Column(SlugType(1024).with_variant(PostgresSlugType(), 'postgresql'),
                  unique=False, index=True)
    extra_data = Column(JSON().with_variant(
        sqlalchemy.dialects.postgresql.JSONB, 'postgresql'))
    level = Column(Integer)

    parent_id = Column(Integer, ForeignKey(__tablename__ + '.id'))
    parent = relationship("TaxonomyTerm", back_populates="children",
                          remote_side=id, foreign_keys=parent_id)
    children = relationship("TaxonomyTerm", back_populates="parent",
                            lazy="dynamic", foreign_keys=parent_id,
                            order_by=slug)

    taxonomy_id = Column(Integer, ForeignKey(Taxonomy.__tablename__ + '.id'))
    taxonomy = relationship("Taxonomy", back_populates="terms")
    taxonomy_code = Column(String(256))

    busy_count = Column(Integer, default=0)
    obsoleted_by_id = Column(Integer, ForeignKey(__tablename__ + '.id'))
    obsoleted_by = relationship("TaxonomyTerm", back_populates="obsoletes",
                                remote_side=id, foreign_keys=obsoleted_by_id)
    obsoletes = relationship("TaxonomyTerm", back_populates="obsoleted_by",
                             lazy="dynamic", foreign_keys=obsoleted_by_id)
    status = Column(Enum(TermStatusEnum), default=TermStatusEnum.alive, nullable=False)

    __table_args__ = (
        Index('index_term_slug', slug, postgresql_using="gist"),
        UniqueConstraint(taxonomy_id, slug, name='unique_taxonomy_slug')
    )

    @property
    def parent_slug(self):
        if '/' in self.slug:
            return self.slug.rsplit('/')[0]
        return None

    def __str__(self):
        return 'TaxonomyTerm[tax {}, lev {}, slug {}]'.format(
            self.taxonomy.code, self.level, self.slug)

    def __repr__(self):
        return str(self)

    def json(self, representation=DEFAULT_REPRESENTATION):
        """
        Return a tuple of (json_response, links)

        :param representation:
        :return:
        """
        resp = {}
        if INCLUDE_SLUG in representation:
            resp['slug'] = self.slug
        if INCLUDE_LEVEL in representation:
            resp['level'] = self.level

        if INCLUDE_ID in representation:
            resp['id'] = self.id
        if INCLUDE_LEVEL in representation:
            resp['level'] = self.level + 1
        if INCLUDE_STATUS in representation:
            if self.status in (TermStatusEnum.deleted, TermStatusEnum.delete_pending) and self.obsoleted_by_id:
                resp['status'] = 'moved'
            else:
                resp['status'] = self.status.name if self.status else None
        if INCLUDE_DATA in representation and self.extra_data:
            resp.update(current_flask_taxonomies.extract_data(representation, self))
        if INCLUDE_DESCENDANTS_COUNT in representation and hasattr(self, 'descendants_count'):
            resp['descendants_count'] = self.descendants_count

        if INCLUDE_ENVELOPE in representation:
            resp = {
                'data': resp
            }
        if INCLUDE_URL in representation or INCLUDE_DESCENDANTS_URL in representation:
            resp['links'] = self.links(representation).envelope

        return resp

    def links(self, representation=DEFAULT_REPRESENTATION) -> EnvelopeLinks:
        links = {}
        all_links = {}
        self_link = current_flask_taxonomies.taxonomy_term_url(self)
        all_links['self'] = self_link
        if INCLUDE_URL in representation:
            links['self'] = self_link

        if self.obsoleted_by_id:
            obslinks = self.obsoleted_by.links(representation)
            all_links['obsoleted_by'] = obslinks.envelope['self']
            if INCLUDE_URL in representation:
                links['obsoleted_by'] = obslinks.envelope['self']

        descendants_link = current_flask_taxonomies.taxonomy_term_url(self, descendants=True)
        all_links['tree'] = descendants_link
        if INCLUDE_DESCENDANTS_URL in representation:
            links['tree'] = descendants_link

        return EnvelopeLinks(envelope=links, headers=all_links)
