# encoding: utf-8

import datetime
from sqlalchemy.orm import class_mapper
import sqlalchemy


from ckan.model.core import State

try:
    RowProxy = sqlalchemy.engine.result.RowProxy
except AttributeError:
    RowProxy = sqlalchemy.engine.base.RowProxy

try:
    long        # Python 2
except NameError:
    long = int  # Python 3


# NOTE
# The functions in this file contain very generic methods for dictizing objects
# and saving dictized objects. If a specialised use is needed please do NOT extend
# these functions.  Copy code from here as needed.

legacy_dict_sort = lambda x: (len(x), dict.items(x))

def table_dictize(obj, context, **kw):
    '''Get any model object and represent it as a dict'''

    result_dict = {}

    if isinstance(obj, RowProxy):
        fields = obj.keys()
    else:
        ModelClass = obj.__class__
        table = class_mapper(ModelClass).persist_selectable
        fields = [field.name for field in table.c]

    for field in fields:
        name = field
        if name in ('current', 'expired_timestamp', 'expired_id'):
            continue
        if name in ('continuity_id', 'revision_id'):
            continue
        value = getattr(obj, name)
        if value is None:
            result_dict[name] = value
        elif isinstance(value, dict):
            result_dict[name] = value
        elif isinstance(value, int):
            result_dict[name] = value
        elif isinstance(value, long):
            result_dict[name] = value
        elif isinstance(value, datetime.datetime):
            result_dict[name] = value.isoformat()
        elif isinstance(value, list):
            result_dict[name] = value
        else:
            result_dict[name] = str(value)

    result_dict.update(kw)

    ##HACK For optimisation to get metadata_modified created faster.

    context['metadata_modified'] = max(result_dict.get('revision_timestamp', ''),
                                       context.get('metadata_modified', ''))

    return result_dict


def obj_list_dictize(obj_list, context, sort_key=legacy_dict_sort):
    '''Get a list of model object and represent it as a list of dicts'''

    result_list = []
    active = context.get('active', True)

    for obj in obj_list:
        if context.get('with_capacity'):
            obj, capacity = obj
            dictized = table_dictize(obj, context, capacity=capacity)
        else:
            dictized = table_dictize(obj, context)
        if active and obj.state != 'active':
            continue
        result_list.append(dictized)

    return sorted(result_list, key=sort_key)

def obj_dict_dictize(obj_dict, context, sort_key=lambda x:x):
    '''Get a dict whose values are model objects
    and represent it as a list of dicts'''

    result_list = []

    for key, obj in obj_dict.items():
        result_list.append(table_dictize(obj, context))

    return sorted(result_list, key=sort_key)


def get_unique_constraints(table, context):
    '''Get a list of unique constraints for a sqlalchemy table'''

    list_of_constraints = []

    for contraint in table.constraints:
        if isinstance(contraint, sqlalchemy.UniqueConstraint):
            columns = [column.name for column in contraint.columns]
            list_of_constraints.append(columns)

    return list_of_constraints

def table_dict_save(table_dict, ModelClass, context, extra_attrs=()):
    '''Given a dict and a model class, update or create a sqlalchemy object.
    This will use an existing object if "id" is supplied OR if any unique
    constraints are met. e.g supplying just a tag name will get out that tag obj.
    '''

    model = context["model"]
    session = context["session"]

    table = class_mapper(ModelClass).persist_selectable

    obj = None

    id = table_dict.get("id")

    if id:
        obj = session.query(ModelClass).get(id)

    if not obj:
        unique_constraints = get_unique_constraints(table, context)
        for constraint in unique_constraints:
            params = dict((key, table_dict.get(key)) for key in constraint)
            obj = session.query(ModelClass).filter_by(**params).first()
            if obj:
                if 'name' in params and getattr(obj, 'state', None) == State.DELETED:
                    obj.name = obj.id
                    obj = None
                else:
                    break

    if not obj:
        obj = ModelClass()

    obj.from_dict(table_dict)
    for a in extra_attrs:
        if a in table_dict:
            setattr(obj, a, table_dict[a])

    session.add(obj)

    return obj
