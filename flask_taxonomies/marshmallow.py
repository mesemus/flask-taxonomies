import re

from marshmallow import utils, Schema, EXCLUDE
from marshmallow.fields import Field
from werkzeug.http import parse_options_header

from flask_taxonomies.models import Representation, DEFAULT_REPRESENTATION

RETURN_PREFIX = 'return='


class PreferHeaderField(Field):
    default_error_messages = {
        "invalid": "Not a valid string.",
        "invalid_utf8": "Not a valid utf-8 string.",
    }

    def _serialize(self, value, attr, obj, **kwargs):
        raise NotImplementedError()

    def _deserialize(self, value, attr, data, **kwargs) -> [Representation, None]:
        if not isinstance(value, (str, bytes)):
            raise self.make_error("invalid")
        try:
            value = utils.ensure_text_type(value)
        except UnicodeDecodeError as error:
            raise self.make_error("invalid_utf8") from error
        value = parse_options_header(value)
        command, options = value
        if not command.startswith(RETURN_PREFIX):
            return None
        representation = command[len(RETURN_PREFIX):]
        options = {
            k: set((v or '').split()) for k, v in options.items()
        }
        return Representation(
            representation,
            include=options.get('include', None),
            exclude=options.get('exclude', None),
            selectors=options.get('selectors', None)
        )


class PreferQueryField(Field):
    default_error_messages = {
        "invalid": "Not a valid string.",
        "invalid_utf8": "Not a valid utf-8 string.",
    }

    def __init__(self, type=None, **kwargs):
        super().__init__(**kwargs)
        self.repr_type = type

    def _serialize(self, value, attr, obj, **kwargs):
        raise NotImplementedError()

    def _deserialize(self, value, attr, data, **kwargs) -> [Representation, None]:
        if not isinstance(value, (str, bytes)):
            raise self.make_error("invalid")
        try:
            value = utils.ensure_text_type(value)
        except UnicodeDecodeError as error:
            raise self.make_error("invalid_utf8") from error
        value = [x.strip() for x in re.split(r'[ ,]', value)]
        return Representation(
            'representation',
            **{self.repr_type:value}
        )


class HeaderSchema(Schema):
    prefer = PreferHeaderField(missing=DEFAULT_REPRESENTATION)

    class Meta:
        unknown = EXCLUDE


class QuerySchema(Schema):
    include = PreferQueryField(type='include', missing=None, data_key='representation:include')
    exclude = PreferQueryField(type='exclude', missing=None, data_key='representation:exclude')
    selectors = PreferQueryField(type='selectors', missing=None, data_key='representation:selectors')

    class Meta:
        unknown = EXCLUDE