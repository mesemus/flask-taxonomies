# -*- coding: utf-8 -*-
"""User models."""
import wrapt
from blinker import Namespace
from flask import url_for
from invenio_db import db
from sqlalchemy import asc
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from sqlalchemy_mptt import BaseNestedSets, mptt_sessionmaker

taxonomy_signals = Namespace()

# signals emitted by REST methods
before_taxonomy_created = taxonomy_signals.signal('before-taxonomy-created')
after_taxonomy_created = taxonomy_signals.signal('after-taxonomy-created')

before_taxonomy_updated = taxonomy_signals.signal('before-taxonomy-updated')
after_taxonomy_updated = taxonomy_signals.signal('after-taxonomy-updated')

before_taxonomy_deleted = taxonomy_signals.signal('before-taxonomy-deleted')
after_taxonomy_deleted = taxonomy_signals.signal('after-taxonomy-deleted')

before_taxonomy_term_created = taxonomy_signals.signal('before-taxonomy-term-created')
after_taxonomy_term_created = taxonomy_signals.signal('after-taxonomy-term-created')

before_taxonomy_term_updated = taxonomy_signals.signal('before-taxonomy-term-updated')
after_taxonomy_term_updated = taxonomy_signals.signal('after-taxonomy-term-updated')

before_taxonomy_term_deleted = taxonomy_signals.signal('before-taxonomy-term-deleted')
after_taxonomy_term_deleted = taxonomy_signals.signal('after-taxonomy-term-deleted')

before_taxonomy_term_moved = taxonomy_signals.signal('before-taxonomy-term-moved')
after_taxonomy_term_moved = taxonomy_signals.signal('after-taxonomy-term-moved')


class TaxonomyTerm(db.Model, BaseNestedSets):
    """TaxonomyTerm adjacency list model."""
    __tablename__ = "taxonomy_term"
    __table_args__ = (
        db.UniqueConstraint('slug', 'parent_id', name='uq_taxonomy_term_slug_parent'),
        db.UniqueConstraint('slug', 'tree_id', name='uq_taxonomy_term_slug_tree'),
    )

    id = db.Column(db.Integer, primary_key=True)
    slug = db.Column(db.String(64), unique=False, index=True)
    extra_data = db.Column(db.JSON)

    def update(self, extra_data: dict = None):
        """Update Taxonomy Term data."""
        self.extra_data = extra_data

        session = mptt_sessionmaker(db.session)
        session.add(self)
        session.commit()

    def __init__(self,
                 slug: str,
                 extra_data: dict = None,
                 parent=None,
                 tree_id=None):
        """Taxonomy Term constructor."""
        self.slug = slug
        self.extra_data = extra_data
        self.parent = parent
        self.tree_id = tree_id

    def append(self, term, order=-1):

        if term.parent == self:
            # moving seems to be broken, so remove it from the tree and unfortunately commit
            term.parent = None
            session = Session.object_session(term)
            session.add(term)
            session.commit()

            # get it back and reinsert it into the tree
            term = TaxonomyTerm.query.get(term.id)

        # add to the end of the term
        session = mptt_sessionmaker(Session.object_session(self))
        if not session:
            if term.parent_id:
                term.move_inside(self.id)
            else:
                term.parent = self
            return

        # if no children, add to the end of the term regardless the order
        children = list(x.id for x in self.children)

        if not children:
            if term.parent_id:
                term.move_inside(self.id)
            else:
                term.parent = self
            return

        if not term.parent_id:
            term.parent = self
            session.add(term)

        # fix order to interval [0, len(children)] inclusive and move to the correct position
        order = order % (len(children) + 1)

        if order > 0:
            if hasattr(term, 'mptt_move_before'):
                delattr(term, 'mptt_move_before')
            term.move_after(children[order - 1])
        else:
            if hasattr(term, 'mptt_move_after'):
                delattr(term, 'mptt_move_after')
            term.move_before(children[0])

    def move_to(self, target_path, order=-1):
        if self.parent_id is None:
            raise AttributeError('Can not move taxonomy into another taxonomy')
        taxonomy, target_term = Taxonomy.find_taxonomy_and_term(target_path)
        session = mptt_sessionmaker(db.session)
        target_term.append(self, order)
        session.add(self)
        session.add(target_term)
        session.commit()

    @property
    def descendants(self):
        return TaxonomyTerm.query.filter(
            TaxonomyTerm.tree_id == self.tree_id,
            TaxonomyTerm.left > self.left,
            TaxonomyTerm.right < self.right).order_by('lft')

    @property
    def descendants_or_self(self):
        return TaxonomyTerm.query.filter(
            TaxonomyTerm.tree_id == self.tree_id,
            TaxonomyTerm.left >= self.left,
            TaxonomyTerm.right <= self.right).order_by('lft')

    @property
    def link_self(self):
        taxonomy_code, term_path = self.tree_path.lstrip('/').split('/', 1)

        return url_for(
            "taxonomies.taxonomy_get_term",
            taxonomy_code=taxonomy_code,
            term_path=term_path,
            _external=True,
        )

    @property
    def link_tree(self):
        taxonomy_code, term_path = self.tree_path.lstrip('/').split('/', 1)

        return url_for(
            "taxonomies.taxonomy_get_term",
            taxonomy_code=taxonomy_code,
            term_path=term_path,
            drilldown=True,
            _external=True,
        )

    @property
    def tree_path(self) -> str:
        """Get path in a taxonomy tree."""
        return "/{path}".format(
            path="/".join([t.slug for t in self.path_to_root(order=asc).all()]),  # noqa
        )

    def __repr__(self):
        """Represent taxonomy term instance as a unique string."""
        return "<TaxonomyTerm({slug}:{path})>" \
            .format(slug=self.slug, path=self.id)


class Taxonomy(wrapt.ObjectProxy):

    def __init__(self, node):
        super().__init__(node)

    @classmethod
    def create_taxonomy(cls, code, extra_data: dict = None):
        if TaxonomyTerm.query.filter_by(parent=None, slug=code).count() > 0:
            raise IntegrityError('Error creating taxonomy - duplicated code', '', [], None)
        return cls(TaxonomyTerm(slug=code, extra_data=extra_data, parent=None, tree_id=code))

    @property
    def code(self):
        return self.slug

    @property
    def terms(self):
        return self.descendants

    @property
    def roots(self):
        return self.children

    @property
    def link_self(self):
        return url_for(
            "taxonomies.taxonomy_get_roots",
            taxonomy_code=self.code,
            _external=True,
        )

    @property
    def link_tree(self):
        return url_for(
            "taxonomies.taxonomy_get_roots",
            taxonomy_code=self.code,
            drilldown=True,
            _external=True,
        )

    @classmethod
    def taxonomies(cls, _filter=None):
        terms = TaxonomyTerm.query.filter_by(parent=None)
        if _filter:
            terms = _filter(terms)
        for term in terms:
            yield cls(term)

    @classmethod
    def get(cls, code, required=False):
        if required:
            tax = TaxonomyTerm.query.filter_by(parent=None, slug=code).one()
        else:
            tax = TaxonomyTerm.query.filter_by(parent=None, slug=code).one_or_none()
            if not tax:
                return None
        return cls(tax)

    @classmethod
    def find_taxonomy_and_term(cls, path):
        parts = _parse_path(path)
        taxonomy = Taxonomy.get(parts[0])
        if len(parts) > 1 and taxonomy:
            term = taxonomy.get_term(parts[-1], required=True)
        else:
            term = taxonomy
        return taxonomy, term

    def find_term(self, path):

        parts = _parse_path(path)
        if parts:
            slug = parts[-1]
            return self.get_term(slug)

        return self

    def get_term(self, slug, required=False):
        found = self.descendants_or_self.filter_by(slug=slug)
        if required:
            return found.one()
        return found.one_or_none()

    def create_term(self, parent_path=None, **kwargs):
        term = TaxonomyTerm(**kwargs)
        parts = _parse_path(parent_path)
        parent_term = self.get_term(parts[-1]) if parts else self
        if not parent_term:
            raise AttributeError('Term with slug %s not found in taxonomy %s' %
                                 (parts[-1], self.code))
        parent_term.append(term)
        session = mptt_sessionmaker(db.session)
        session.add(term)
        session.commit()
        return term


def _parse_path(path):
    path = (path or '').strip('/')
    return [x for x in path.split('/') if x]


__all__ = ('TaxonomyTerm', 'Taxonomy')
