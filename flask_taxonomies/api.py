import logging
from dataclasses import MISSING

import jsonpatch
import jsonpointer
import sqlalchemy
from flask import current_app
from flask_sqlalchemy import get_state
from slugify import slugify
from sqlalchemy import func
from sqlalchemy.orm import Session, aliased
from sqlalchemy.orm.attributes import flag_modified
from sqlalchemy.orm.exc import NoResultFound
from sqlalchemy.util import deprecated
from werkzeug.utils import cached_property, import_string

from .constants import INCLUDE_DATA, INCLUDE_DESCENDANTS
from .models import (
    Taxonomy,
    TaxonomyError,
    TaxonomyTerm,
    TaxonomyTermBusyError,
    TermStatusEnum,
)
from .signals import (
    after_taxonomy_created,
    after_taxonomy_deleted,
    after_taxonomy_term_created,
    after_taxonomy_term_deleted,
    after_taxonomy_term_moved,
    after_taxonomy_term_updated,
    after_taxonomy_updated,
    before_taxonomy_created,
    before_taxonomy_deleted,
    before_taxonomy_term_created,
    before_taxonomy_term_deleted,
    before_taxonomy_term_moved,
    before_taxonomy_term_updated,
    before_taxonomy_updated,
)
from .term_identification import TermIdentification, _coerce_ti
from .views.perms import PermsEnforcer

log = logging.getLogger(__name__)


class Api:
    def __init__(self, app=None):
        self.app = app
        self.permissions = PermsEnforcer(app)

    @property
    def session(self):
        db = get_state(self.app).db
        return db.session

    def list_taxonomies(self, session=None, return_descendants_count=False,
                        return_descendants_busy_count=False):
        """Return a list of all available taxonomies."""
        session = session or self.session

        query_parts = [Taxonomy]
        if return_descendants_count:
            aliased_descendant = aliased(TaxonomyTerm, name='aliased_descendant')
            stmt = session.query(func.count(aliased_descendant.id))
            stmt = stmt.filter(aliased_descendant.taxonomy_id == Taxonomy.id)
            stmt = stmt.label('descendants_count')
            query_parts.append(stmt)

        if return_descendants_busy_count:
            aliased_descendant = aliased(TaxonomyTerm, name='aliased_abc_descendant')
            stmt = session.query(func.count(aliased_descendant.id))
            stmt = stmt.filter(aliased_descendant.taxonomy_id == Taxonomy.id)
            stmt = stmt.filter(aliased_descendant.busy_count > 0)
            stmt = stmt.label('descendants_busy_count')
            query_parts.append(stmt)

        ret = session.query(*query_parts)

        return ret

    @deprecated(version='7.0.0')
    def taxonomy_list(self):
        return self.list_taxonomies()  # pragma: no cover

    def filter_taxonomy(self, code, session=None, return_descendants_count=False,
                        return_descendants_busy_count=False):
        ret = self.list_taxonomies(session=session, return_descendants_count=return_descendants_count,
                                   return_descendants_busy_count=return_descendants_busy_count)
        return ret.filter(Taxonomy.code == code)

    def get_taxonomy(self, code, fail=True, session=None, return_descendants_count=False,
                     return_descendants_busy_count=False):
        ret = self.filter_taxonomy(code, session, return_descendants_count=return_descendants_count,
                                   return_descendants_busy_count=return_descendants_busy_count)
        if fail:
            return ret.one()
        else:
            return ret.one_or_none()

    def create_taxonomy(self, code, extra_data=None, url=None, select=None, session=None) -> Taxonomy:
        """Creates a new taxonomy.
        :param code: taxonomy code
        :param extra_data: taxonomy metadata
        :param session: use a different db session
        :raises IntegrityError
        :returns Taxonomy
        """
        session = session or self.session
        with session.begin_nested():
            before_taxonomy_created.send(self, code=code, extra_data=extra_data)
            created = Taxonomy(code=code, url=url, extra_data=extra_data, select=select)
            session.add(created)
            after_taxonomy_created.send(created)
        return created

    def update_taxonomy(self, taxonomy: [Taxonomy, str], extra_data, url=MISSING, select=MISSING,
                        session=None) -> Taxonomy:
        """Updates a taxonomy.
        :param taxonomy: taxonomy instance to be updated
        :param extra_data: new taxonomy metadata
        :param session: use a different db session
        :return Taxonomy: updated taxonomy
        """
        session = session or self.session
        if isinstance(taxonomy, str):
            taxonomy = session.query(Taxonomy).filter(Taxonomy.code == taxonomy).one()
        with session.begin_nested():
            before_taxonomy_updated.send(taxonomy, taxonomy=taxonomy, extra_data=extra_data)
            taxonomy.extra_data = extra_data
            flag_modified(taxonomy, "extra_data")
            if url is not MISSING:
                taxonomy.url = url
                flag_modified(taxonomy, "url")
            if select is not MISSING:
                taxonomy.select = select
                flag_modified(taxonomy, "select")
            session.add(taxonomy)
            after_taxonomy_updated.send(taxonomy, taxonomy=taxonomy)
        return taxonomy

    def delete_taxonomy(self, taxonomy: Taxonomy, session=None):
        """Delete a taxonomy.
        :param taxonomy: taxonomy instance to be deleted
        :param session: use a different db session
        :raise TaxonomyError
        """
        session = session or self.session
        with session.begin_nested():
            before_taxonomy_deleted.send(taxonomy, taxonomy=taxonomy)
            session.delete(taxonomy)
            after_taxonomy_deleted.send(taxonomy)

    def list_taxonomy(self, taxonomy: [Taxonomy, str], levels=None,
                      status_cond=TaxonomyTerm.status == TermStatusEnum.alive,
                      order=True, session=None, return_descendants_count=False,
                      return_descendants_busy_count=False):
        session = session or self.session

        query_parts = [TaxonomyTerm]
        if return_descendants_count:
            aliased_descendant = aliased(TaxonomyTerm, name='aliased_descendant')
            stmt = session.query(func.count(aliased_descendant.id))
            stmt = stmt.filter(aliased_descendant.slug.descendant_of(TaxonomyTerm.slug))
            stmt = stmt.filter(aliased_descendant.slug != TaxonomyTerm.slug)
            stmt = stmt.label('descendants_count')
            query_parts.append(stmt)

        if return_descendants_busy_count:
            aliased_descendant = aliased(TaxonomyTerm, name='aliased_abc_descendant')
            stmt = session.query(func.count(aliased_descendant.id))
            stmt = stmt.filter(aliased_descendant.slug.descendant_of(TaxonomyTerm.slug))
            stmt = stmt.filter(aliased_descendant.slug != TaxonomyTerm.slug)
            stmt = stmt.filter(aliased_descendant.busy_count > 0)
            stmt = stmt.label('descendants_busy_count')
            query_parts.append(stmt)

        query = session.query(*query_parts)

        if isinstance(taxonomy, Taxonomy):
            query = query.filter(TaxonomyTerm.taxonomy_id == taxonomy.id)
        else:
            query = query.join(Taxonomy).filter(Taxonomy.code == taxonomy)

        if status_cond is not None:
            query = query.filter(status_cond)
        if levels is not None:
            query = query.filter(TaxonomyTerm.level < levels)
        if order:
            query = query.order_by(TaxonomyTerm.slug)
        return query

    def taxonomy_url(self, taxonomy: [Taxonomy, str], descendants=False):
        proto = (
                current_app.config.get('FLASK_TAXONOMIES_SERVER_SCHEME') or
                current_app.config.get('PREFERRED_URL_SCHEME') or
                'https'
        )
        prefix = current_app.config.get('FLASK_TAXONOMIES_URL_PREFIX')
        base = current_app.config.get('FLASK_TAXONOMIES_SERVER_NAME')
        if not base:
            base = current_app.config.get('SERVER_NAME')
        if not base:
            log.error('Error retrieving taxonomies, FLASK_TAXONOMIES_SERVER_NAME nor SERVER_NAME set')
            base = 'localhost'
        ret = '{}://{}{}{}/'.format(
            proto,
            base,
            prefix,
            taxonomy.code if isinstance(taxonomy, Taxonomy) else taxonomy
        )
        if descendants:
            ret = ret + '?representation:include=' + INCLUDE_DESCENDANTS
        return ret

    def taxonomy_term_url(self, taxonomy_term: TaxonomyTerm, descendants=False):
        taxonomy_url = self.taxonomy_url(taxonomy_term.taxonomy_code)
        ret = taxonomy_url + taxonomy_term.slug
        if descendants:
            ret = ret + '?representation:include=' + INCLUDE_DESCENDANTS
        return ret

    def taxonomy_term_parent_url(self, taxonomy_term: TaxonomyTerm, descendants=False):
        if '/' not in taxonomy_term.slug:
            return None
        taxonomy_url = self.taxonomy_url(taxonomy_term.taxonomy_code)
        ret = taxonomy_url + taxonomy_term.slug.rsplit('/', maxsplit=1)[0]
        if descendants:
            ret = ret + '?representation:include=' + INCLUDE_DESCENDANTS
        return ret

    def create_term(self, ti: TermIdentification, extra_data=None, session=None):
        """Creates a taxonomy term identified by term identification
        """
        ti = _coerce_ti(ti)
        session = session or self.session
        with session.begin_nested():
            parent_identification = ti.parent_identification()
            if parent_identification:
                parent = parent_identification.term_query(session).one()
                if parent.status != TermStatusEnum.alive:
                    raise TaxonomyError('Can not create term inside inactive parent')
            else:
                parent = None

            slug = self._slugify(parent.slug if parent else None, ti.leaf_slug)
            taxonomy = ti.get_taxonomy(session)
            before_taxonomy_term_created.send(taxonomy, slug=slug, extra_data=extra_data)

            parent = TaxonomyTerm(slug=slug,
                                  extra_data=extra_data,
                                  level=(parent.level + 1) if parent else 0,
                                  parent_id=parent.id if parent else None,
                                  taxonomy_id=taxonomy.id,
                                  taxonomy_code=taxonomy.code)
            session.add(parent)
            after_taxonomy_term_created.send(parent, taxonomy=taxonomy, term=parent)
            return parent

    def filter_term(self, ti: TermIdentification,
                    status_cond=TaxonomyTerm.status == TermStatusEnum.alive,
                    return_descendants_count=False,
                    return_descendants_busy_count=False,
                    session=None):
        ti = _coerce_ti(ti)
        session = session or self.session
        return ti.term_query(session, return_descendants_count=return_descendants_count,
                             return_descendants_busy_count=return_descendants_busy_count).filter(status_cond)

    def update_term(self, ti: [TaxonomyTerm, TermIdentification],
                    status_cond=TaxonomyTerm.status == TermStatusEnum.alive,
                    extra_data=None, patch=False, status=MISSING, session=None):
        ti = _coerce_ti(ti)
        session = session or self.session
        with session.begin_nested():
            term = self.filter_term(ti, status_cond=status_cond, session=session).one()

            before_taxonomy_term_updated.send(term, term=term, taxonomy=term.taxonomy,
                                              extra_data=extra_data)
            if patch:
                # apply json patch
                term.extra_data = jsonpatch.apply_patch(
                    term.extra_data or {}, extra_data, in_place=True)
            else:
                term.extra_data = extra_data
            flag_modified(term, "extra_data")
            if status is not MISSING and status != term.status:
                term.status = status
                flag_modified(term, "status")
            session.add(term)
            after_taxonomy_term_updated.send(term, term=term, taxonomy=term.taxonomy)
            return term

    def descendants(self, ti: TermIdentification, levels=None,
                    status_cond=TaxonomyTerm.status == TermStatusEnum.alive,
                    order=True, session=None, return_descendants_count=False,
                    return_descendants_busy_count=False):
        ret = self._descendants(ti, levels=levels, return_term=False,
                                status_cond=status_cond, session=session,
                                return_descendants_count=return_descendants_count,
                                return_descendants_busy_count=return_descendants_busy_count)
        if order:
            return ret.order_by(TaxonomyTerm.slug)
        return ret  # pragma: no cover

    def descendants_or_self(self, ti: TermIdentification, levels=None,
                            status_cond=TaxonomyTerm.status == TermStatusEnum.alive,
                            order=True, session=None, return_descendants_count=False,
                            return_descendants_busy_count=False):
        ret = self._descendants(ti, levels=levels, return_term=True,
                                status_cond=status_cond, session=session,
                                return_descendants_count=return_descendants_count,
                                return_descendants_busy_count=return_descendants_busy_count)
        if order:
            return ret.order_by(TaxonomyTerm.slug)
        return ret

    def _descendants(self, ti: TermIdentification, levels=None,
                     return_term=True, status_cond=None, session=None,
                     return_descendants_count=False,
                     return_descendants_busy_count=False):
        ti = _coerce_ti(ti)
        session = session or self.session
        query = ti.descendant_query(session,
                                    return_descendants_count=return_descendants_count,
                                    return_descendants_busy_count=return_descendants_busy_count)
        if levels is not None:
            query = query.filter(TaxonomyTerm.level <= ti.level + levels)
        if not return_term:
            query = query.filter(TaxonomyTerm.level > ti.level)
        if status_cond is not None:
            query = query.filter(status_cond)
        return query

    def ancestors(self, ti: TermIdentification, status_cond=TaxonomyTerm.status == TermStatusEnum.alive, session=None,
                  return_descendants_count=False, return_descendants_busy_count=False):
        return self._ancestors(ti, return_term=False, status_cond=status_cond, session=session,
                               return_descendants_count=return_descendants_count,
                               return_descendants_busy_count=return_descendants_busy_count)

    def ancestors_or_self(self, ti: TermIdentification,
                          status_cond=TaxonomyTerm.status == TermStatusEnum.alive, session=None,
                          return_descendants_count=False,
                          return_descendants_busy_count=False):
        return self._ancestors(ti, return_term=True, status_cond=status_cond, session=session,
                               return_descendants_count=return_descendants_count,
                               return_descendants_busy_count=return_descendants_busy_count)

    def _ancestors(self, ti: TermIdentification, return_term=True, status_cond=None, session=session,
                   return_descendants_count=False, return_descendants_busy_count=False):
        ti = _coerce_ti(ti)
        session = session or self.session
        query = ti.ancestor_query(session,
                                  return_descendants_count=return_descendants_count,
                                  return_descendants_busy_count=return_descendants_busy_count)
        if status_cond is not None:
            query = query.filter(status_cond)
        if not return_term:
            query = query.filter(TaxonomyTerm.level < ti.level)
        return query

    def delete_term(self, ti: TermIdentification, remove_after_delete=True, session=None):
        ti = _coerce_ti(ti)
        session = session or self.session
        with session.begin_nested():
            terms = self.descendants_or_self(ti,
                                             order=False, status_cond=sqlalchemy.sql.true())
            locked_terms = [r[0] for r in
                            terms.with_for_update().values(TaxonomyTerm.id)]  # get ids to actually lock the terms

            if terms.filter(TaxonomyTerm.busy_count > 0).count():
                raise TaxonomyTermBusyError('Can not delete busy terms')

            if self._in_busy_tree(ti, session):
                raise TaxonomyTermBusyError('Can not move to locked parent %s' % ti.slug)

            term = terms.first()
            if not term:
                raise NoResultFound('TaxonomyTerm %s not found' % ti)
            self.mark_busy(locked_terms,
                           TermStatusEnum.delete_pending if remove_after_delete else TermStatusEnum.deleted,
                           session=session)
            # can call mark_busy if the deletion should be postponed
            taxonomy = term.taxonomy
            before_taxonomy_term_deleted.send(term, taxonomy=taxonomy, term=term, terms=terms,
                                              locked_terms=locked_terms)
            self.unmark_busy(locked_terms, session=session)
            after_taxonomy_term_deleted.send(term, taxonomy=taxonomy, term=term)
            return term

    def mark_busy(self, term_ids, status=None, session=None):
        session = session or self.session
        with session.begin_nested():
            terms = session.query(TaxonomyTerm).filter(TaxonomyTerm.id.in_(term_ids))
            if status:
                terms.update({
                    TaxonomyTerm.busy_count: TaxonomyTerm.busy_count + 1,
                    TaxonomyTerm.status: status
                }, synchronize_session=False)
            else:
                terms.update({TaxonomyTerm.busy_count: TaxonomyTerm.busy_count + 1},
                             synchronize_session=False)
        session.expire_all()

    def unmark_busy(self, term_ids, session=None):
        session = session or self.session
        with session.begin_nested():
            terms = session.query(TaxonomyTerm).filter(TaxonomyTerm.id.in_(term_ids))
            terms.update({TaxonomyTerm.busy_count: TaxonomyTerm.busy_count - 1},
                         synchronize_session=False)
            # delete those that are marked as 'delete_pending'
            terms.filter(
                TaxonomyTerm.busy_count <= 0,
                TaxonomyTerm.status == TermStatusEnum.delete_pending).delete(
                synchronize_session=False
            )
        session.expire_all()

    def rename_term(self, ti: TermIdentification, new_slug=None,
                    remove_after_delete=True, session=None):
        ti = _coerce_ti(ti)
        elements = self.descendants_or_self(ti, status_cond=sqlalchemy.sql.true(), order=False)
        return self._rename_or_move(elements, parent_query=None, slug=new_slug,
                                    remove_after_delete=remove_after_delete, session=session)

    def move_term(self, ti: TermIdentification, new_parent=None,
                  remove_after_delete=True, session=None):
        session = session or self.session
        ti = _coerce_ti(ti)
        if new_parent:
            new_parent = _coerce_ti(new_parent)
            if ti.contains(new_parent):
                raise TaxonomyError('Can not move inside self')
            new_parent = self.filter_term(new_parent, session=session)
        elements = self.descendants_or_self(ti, status_cond=sqlalchemy.sql.true(), order=False, session=session)
        return self._rename_or_move(elements, parent_query=new_parent,
                                    remove_after_delete=remove_after_delete, session=session)

    def extract_data(self, representation, obj):
        data = obj.extra_data or {}
        if INCLUDE_DATA not in representation:
            return {}
        if representation.select is None:
            # include everything
            return data

        # include selected data
        ret = {}
        for sel in representation.select:
            if not sel.startswith('/'):
                sel = '/' + sel
            ptr = jsonpointer.JsonPointer(sel)
            selected_data = ptr.resolve(data)
            if selected_data:
                ret[ptr.parts[-1]] = selected_data
        return ret

    def _rename_or_move(self, elements, parent_query=None, slug=None,
                        remove_after_delete=False, session=None):
        for el in elements:
            if el.busy_count:
                raise TaxonomyTermBusyError('Element %s is locked, can not move or rename it' % el.slug)

        session = session or self.session
        with session.begin_nested():
            if slug and '/' in slug:
                raise TaxonomyError('/ is not allowed when renaming term')
            root = elements.order_by(TaxonomyTerm.slug).first()

            if slug:
                if not parent_query and root.parent_id:
                    parent_query = session.query(TaxonomyTerm).filter(TaxonomyTerm.id == root.parent_id)

            parent = None
            if parent_query:
                parent = parent_query.with_for_update().one()

            if slug:
                if parent:
                    target_path = parent.slug + '/' + slug
                else:
                    target_path = slug
            elif parent:
                target_path = parent.slug + '/' + self._last_slug_element(root.slug)
            else:
                target_path = self._last_slug_element(root.slug)

            if parent:
                if self._in_busy_tree(parent, session):
                    raise TaxonomyTermBusyError('Can not move to locked parent %s' % parent.slug)

            locked_terms = [r[0] for r in
                            elements.with_for_update().values(TaxonomyTerm.id)]  # get ids to actually lock the terms

            self.mark_busy(locked_terms,
                           status=(
                               TermStatusEnum.delete_pending
                               if remove_after_delete else TermStatusEnum.deleted
                           ))
            before_taxonomy_term_moved.send(root, target_path=target_path, terms=elements, locked_terms=locked_terms)
            target_root = self._copy(root, parent, target_path, session)
            self.unmark_busy(locked_terms)
            if not remove_after_delete:
                session.refresh(root)
                root.obsoleted_by_id = target_root.id
                session.add(root)
            after_taxonomy_term_moved.send(root, term=root, new_term=target_root)
            return root, target_root

    def _in_busy_tree(self, el, session):
        return self.ancestors_or_self(el, session=session). \
                   filter(TaxonomyTerm.busy_count > 0).count() > 0

    def _copy(self, term: TaxonomyTerm, parent, target_path, session):
        new_term = TaxonomyTerm(
            taxonomy_id=term.taxonomy_id,
            taxonomy_code=term.taxonomy_code,
            parent_id=parent.id if parent else None,
            slug=target_path,
            level=parent.level + 1 if parent else 0,
            extra_data=term.extra_data
        )
        session.add(new_term)
        session.flush()
        assert new_term.id > 0
        term.obsoleted_by_id = new_term.id
        session.add(term)
        for child in term.children:
            self._copy(child, new_term,
                       target_path + '/' + self._last_slug_element(child.slug),
                       session)
        return new_term

    @staticmethod
    def _slugify(parent_path, slug):
        slug = slugify(slug)
        if parent_path:
            return parent_path + '/' + slug
        return slug

    @staticmethod
    def _last_slug_element(slug):
        return slug.split('/')[-1]

    @cached_property
    def query_parser(self):
        parser_or_import = self.app.config.get('FLASK_TAXONOMIES_QUERY_PARSER',
                                               'flask_taxonomies.query.default_query_parser')
        if isinstance(parser_or_import, str):
            return import_string(parser_or_import)
        return parser_or_import

    @cached_property
    def query_executor(self):
        executor_or_import = self.app.config.get('FLASK_TAXONOMIES_QUERY_EXECUTOR',
                                                 'flask_taxonomies.query.default_query_executor')
        if isinstance(executor_or_import, str):
            return import_string(executor_or_import)
        return executor_or_import

    def apply_taxonomy_query(self, sqlalchemy_query, query_string, session=None):
        session = session or self.session
        return self.query_executor(session, sqlalchemy_query, Taxonomy, self.query_parser(query_string))

    def apply_term_query(self, sqlalchemy_query, query_string, taxonomy_code, session=None):
        session = session or self.session
        return self.query_executor(session, sqlalchemy_query, TaxonomyTerm,
                                   self.query_parser(query_string, taxonomy_code=taxonomy_code))

    def commit(self, session=None):
        session = session or self.session
        session.commit()
