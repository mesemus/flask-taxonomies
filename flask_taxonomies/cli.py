import click
from flask import current_app
from flask.cli import with_appcontext
from invenio_accounts.models import Role, User
from invenio_db import db
from invenio_access import ActionSystemRoles, any_user

#
# Taxonomies commands
#
from flask_taxonomies.permissions import taxonomy_read_all, taxonomy_term_read_all


@click.group()
def taxonomies():
    """Taxonomies commands."""


#
# Taxonomies subcommands
#
@taxonomies.command('all-read')
@with_appcontext
def all_read():
    """Set permissions for everyone to read all taxonomies and taxonomy terms."""
    db.session.add(ActionSystemRoles.allow(taxonomy_read_all, role=any_user))
    db.session.add(ActionSystemRoles.allow(taxonomy_term_read_all, role=any_user))
    db.session.commit()
