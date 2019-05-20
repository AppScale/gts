""" Implements the datastore viewer interface. """
import math
import urllib

from app_dashboard import AppDashboard
from datastore_location import DATASTORE_LOCATION

from google.appengine.api import api_base_pb
from google.appengine.api import datastore
from google.appengine.api import memcache
from google.appengine.api.datastore_distributed import DatastoreDistributed
from google.appengine.datastore import datastore_pb
from google.appengine.ext import gql
from google.appengine.tools.devappserver2.admin.datastore_viewer import (
  DataType)


def _format_datastore_key(key):
  """Return a nicely formatted decomposition of a datastore key.

  Args:
    key: The datastore_types.Key object to format.

  Returns:
    A string or Unicode object containing nicely formatted information about
    the given key e.g. "ParentKind: name=Animal > ChildKind: id=123".
  """
  path = key.to_path()  # [kind, id/name, kind, id/name, ...]
  parts = []
  for i in range(0, len(path)//2):
    kind = path[i*2]
    value = path[i*2 + 1]
    if isinstance(value, (int, long)):
      parts.append('%s: id=%d' % (kind, value))
    else:
      parts.append('%s: name=%s' % (kind, value))
  return ' > '.join(parts)


def _property_name_to_values(entities):
  """Returns a mapping of entity property names to a list of their values.

  For example:
    _property_name_to_values([{'cat': 5, 'dog': 10},
                              {'dog': 15, 'mouse': 'happy'}])
    => {'cat': [5], 'dog': [10, 15], 'mouse': ['happy']}

  Args:
    entities: A sequence of mappings (i.e. datastore.Entity) that represent
        datastore properties and their values.

  Returns:
    A dict whose keys are the union of the keys of the given entities and
    whose values are the list of values for those keys.
  """
  property_name_to_values = {}
  for entity in entities:
    for property_name, value in entity.iteritems():
      property_name_to_values.setdefault(property_name, []).append(value)

  return property_name_to_values


def _delete_entities(ds_access, entity_keys):
  """ Deletes a list of datastore entities.

  Args:
    ds_access: A DatastoreDistributed client.
    entity_keys: A list of datastore.Key objects.
  Raises:
    ApplicationError if unable to delete entities.
  """
  request = datastore_pb.DeleteRequest()
  for entity_key in entity_keys:
    key = request.add_key()
    key.CopyFrom(entity_key._ToPb())

  response = datastore_pb.DeleteResponse()
  ds_access._Dynamic_Delete(request, response)


def _get_entity_by_key(ds_access, entity_key):
  """ Fetches an entity.

  Args:
    ds_access: A DatastoreDistributed client.
    entity_key: A datastore.Key object.
  Returns:
    A datastore.Entity object.
  Raises:
    ApplicationError if unable to fetch entity.
  """
  reference = entity_key._ToPb()
  request = datastore_pb.GetRequest()
  key = request.add_key()
  key.CopyFrom(reference)

  response = datastore_pb.GetResponse()
  ds_access._Dynamic_Get(request, response)
  entity = datastore.Entity.FromPb(response.entity(0).entity())
  return entity


def _put_entity(ds_access, entity):
  """ Updates or creates an entity.

  Args:
    ds_access: A DatastoreDistributed client.
    entity: A datastore.Entity object.
  Raises:
    ApplicationError if unable to put entity.
  """
  request = datastore_pb.PutRequest()
  new_entity = request.add_entity()
  new_entity.CopyFrom(entity.ToPb())

  response = datastore_pb.PutResponse()
  ds_access._Dynamic_Put(request, response)


def _get_entities(ds_access, kind, namespace, order, start, count):
  """Returns a list and a count of entities of the given kind.

  Args:
    kind: A string representing the name of the kind of the entities to
        return.
    namespace: A string representing the namespace of the entities to return.
    order: A string containing the name of the property to sorted the results
        by. A "-" prefix indicates descending order e.g. "-age".
    start: The number of initial entities to skip in the result set.
    count: The maximum number of entities to return.

  Returns:
    A tuple of (list of datastore.Entity, total entity count).
  """
  query = datastore_pb.Query()
  query.set_name_space(namespace)
  query.set_app(ds_access.project_id)
  query.set_kind(kind)
  query.set_compile(True)

  if order:
    query_order = query.add_order()
    if order.startswith('-'):
      query_order.set_direction(datastore_pb.Query_Order.DESCENDING)
      query_order.set_property(order[1:])
    else:
      query_order.set_direction(datastore_pb.Query_Order.ASCENDING)
      query_order.set_property(order)

  # Count queries just take note of the skipped results.
  count_query = datastore_pb.Query()
  count_query.CopyFrom(query)
  count_query.set_offset(1000)
  count_query.set_limit(0)
  result = datastore_pb.QueryResult()
  ds_access._Dynamic_RunQuery(count_query, result)
  total = result.skipped_results()

  query.set_limit(count)
  query.set_offset(start)
  result = datastore_pb.QueryResult()
  ds_access._Dynamic_RunQuery(query, result)
  entities = [datastore.Entity.FromPb(entity_pb)
              for entity_pb in result.result_list()]

  return entities, total


class DatastoreViewerPage(AppDashboard):
  """ A base class for datastore viewer pages. """
  def ensure_user_has_admin(self, project_id):
    """ Returns an error page if user does not have project permissions.

    Args:
      project_id: A string specifying a project ID.
    """
    if self.helper.is_user_cloud_admin():
      version_keys = self.helper.get_version_info().keys()
      owned_projects = list({version.split('_')[0]
                             for version in version_keys})
    else:
      owned_projects = self.helper.get_owned_apps()

    if project_id not in owned_projects:
      self.response.write(
        'You do not have permission to view data for {}.'.format(project_id))
      self.abort(403)


class DatastoreViewerSelector(AppDashboard):
  """ Handles requests for the Datastore Viewer project selection page. """
  TEMPLATE = 'datastore/project_selector.html'

  def get(self):
    """ Presents a list of projects to view data for. """
    if self.helper.is_user_cloud_admin():
      version_keys = self.helper.get_version_info().keys()
      owned_projects = list({version.split('_')[0] for version in version_keys
                             if version.split('_')[0] != self.PROJECT_ID})
    else:
      owned_projects = self.helper.get_owned_apps()

    context = {
      'page_content': self.TEMPLATE,
      'owned_projects': owned_projects,
    }
    self.render_app_page(page='datastore_viewer_selector', values=context)


class DatastoreViewer(DatastoreViewerPage):
  """ Handles requests for the Datastore Viewer page. """
  NUM_ENTITIES_PER_PAGE = 20

  TEMPLATE = 'datastore/viewer.html'

  @staticmethod
  def _calculate_writes_for_built_in_indices(entity):
    """ Estimates number of write operations for standard properties.

    Args:
      entity: A datastore.Entity object.
    Returns:
      An integer specifying the number of datastore write operations.
    """
    writes = 0
    for prop_name in entity.keys():
      if not prop_name in entity.unindexed_properties():
        # 2 writes per property value, one for EntitiesByProperty and one for
        # EntitiesbyPropertyDesc
        prop_vals = entity[prop_name]
        if isinstance(prop_vals, (list)):
          num_prop_vals = len(prop_vals)
        else:
          num_prop_vals = 1
        writes += 2 * num_prop_vals
    return writes

  @staticmethod
  def _calculate_writes_for_composite_index(entity, index):
    """ Estimates the number of write operations for composite index entries.

    Args:
      entity: A datastore.Entity object.
    Returns:
      An integer specifying the number of datastore write operations.
    """
    composite_index_value_count = 1
    for prop_name, _ in index.Properties():
      if not prop_name in entity.keys() or (
          prop_name in entity.unindexed_properties()):
        return 0
      prop_vals = entity[prop_name]
      if isinstance(prop_vals, (list)):
        composite_index_value_count *= len(prop_vals)

    # If this is an ancestor index we're going to duplicate all these index
    # writes for every key in the hierarchy.  So if the entity key has no
    # parent we write the index values once, if the entity key has a depth of
    # 2 then we write the index values twice, and so on.
    ancestor_count = 1  # A key is its own ancestor.
    if index.HasAncestor():
      key = entity.key().parent()
      while key is not None:
        ancestor_count += 1
        key = key.parent()
    return composite_index_value_count * ancestor_count

  def _construct_url(self, remove=None, add=None):
    """Returns a URL referencing the current resource with the same params.

    For example, if the request URL is
    "http://foo/bar?animal=cat&color=redirect" then
    _construct_url(['animal'], {'vehicle': 'car'}) will return
    "http://foo/bar?vehicle=car&color=redirect"

    Args:
      remove: A sequence of query parameters to remove from the query string.
      add: A mapping of query parameters to add to the query string.

    Returns:
      A new query string suitable for use in "GET" requests.
    """
    remove = remove or []
    add = add or {}
    params = dict(self.request.params)
    for arg in remove:
      if arg in params:
        del params[arg]

    params.update(add)
    return str('%s?%s' % (self.request.path,
                          urllib.urlencode(sorted(params.iteritems()))))

  @classmethod
  def _format_entity_template_data(cls, ds_access, request_uri, entities,
                                   total_entities):
    """ Fetches template variables for datastore viewer page for a given kind.

    Args:
      ds_access: A DatastoreDistributed client.
      request_uri: A string specifying the current request location.
      entities: A list of datastore.Entity objects.
      total_entities: An integer specifying the total number of entities.
    Returns:
      A tuple containing headers, entities, and total entity count.
    """
    prop_names = sorted({prop for entity in entities for prop in entity})

    headers = [{'name': property_name}
               for property_name in prop_names]

    template_entities = []
    for entity in entities:
      attributes = []
      for property_name in prop_names:
        if property_name in entity:
          raw_value = entity[property_name]
          data_type = DataType.get(raw_value)
          value = data_type.format(raw_value)
          short_value = data_type.short_format(raw_value)
        else:
          value = ''
          short_value = ''
        attributes.append({'name': property_name,
                           'value': value,
                           'short_value': short_value,
                          })
      edit_uri = '/datastore_viewer/%s/edit/%s?next=%s' % (
          ds_access.project_id, entity.key(), urllib.quote(request_uri))
      template_entities.append(
          {'attributes': attributes,
           'edit_uri': edit_uri,
           'key': entity.key(),
           'key_id': entity.key().id(),
           'key_name': entity.key().name(),
           'shortened_key': str(entity.key())[:8] + '...',
           'write_ops': cls._get_write_ops(ds_access, entity)})
    return headers, template_entities, total_entities

  @classmethod
  def _get_indexes(cls, ds_access):
    """ Retrieves a list of composite indexes for a project.

    Args:
      ds_access: A DatastoreDistributed client.
    Returns:
      A list of datastore.Index objects.
    """
    request = api_base_pb.StringProto()
    request.set_value(ds_access.project_id)
    response = datastore_pb.CompositeIndices()
    ds_access._Dynamic_GetIndices(request, response)
    indexes = []
    for index in response.index_list():
      props = [(prop.name(), prop.direction())
               for prop in index.definition().property_list()]
      new_index = datastore.Index(index.id(), index.definition().entity_type(),
                                  index.definition().ancestor(), props)
      indexes.append(new_index)

    return indexes

  @classmethod
  def _get_kinds(cls, ds_access, namespace):
    """ Returns a sorted list of kind names present in the given namespace.

    Args:
      ds_access: A DatastoreDistributed client.
      namespace: A string specifying the datastore namespace.
    Returns:
      A list of string specifying kind names.
    """
    assert namespace is not None
    query = datastore_pb.Query()
    query.set_name_space(namespace)
    query.set_app(ds_access.project_id)
    query.set_kind('__kind__')
    result = datastore_pb.QueryResult()
    ds_access._Dynamic_RunQuery(query, result)
    kinds = [entity.entity_group().element(0).name()
             for entity in result.result_list()]
    return sorted(kinds)

  @classmethod
  def _get_write_ops(cls, ds_access, entity):
    """ Estimates the number of write operations for an entity.

    Args:
      ds_access: A DatastoreDistributed client.
      entity: A datastore.Entity object.
    Returns:
      An integer specifying the number of write operations.
    """
    # Minimum 2 writes, one for the entity and one for the EntitiesByKind index.
    writes = 2 + cls._calculate_writes_for_built_in_indices(entity)

    # Account for composite indices.
    for index in cls._get_indexes(ds_access):
      if index.Kind() != entity.kind():
        continue
      writes += cls._calculate_writes_for_composite_index(entity, index)
    return writes

  def get(self, project_id):
    """ Displays a list of entities for a given kind.

    Args:
      project_id: A string specifying the project ID.
    """
    self.ensure_user_has_admin(project_id)

    ds_access = DatastoreDistributed(project_id, DATASTORE_LOCATION,
                                     trusted=True)

    kind = self.request.get('kind', None)
    namespace = self.request.get('namespace', '')
    order = self.request.get('order', None)
    message = self.request.get('message', None)
    gql_string = self.request.get('gql', None)

    try:
      page = int(self.request.get('page', '1'))
    except ValueError:
      page = 1

    kinds = self._get_kinds(ds_access, namespace)

    if gql_string is not None:
      start = (page - 1) * self.NUM_ENTITIES_PER_PAGE

      total_entities = 0
      entities = []
      try:
        gql_query = gql.GQL(gql_string, _app=project_id, namespace=namespace)
        kind = gql_query.kind()
        query = gql_query.Bind([], {})

        total_entities = query.Count()
        entities = list(
          query.Run(limit=self.NUM_ENTITIES_PER_PAGE, offset=start))
      except datastore.datastore_errors.NeedIndexError as error:
        message = ('Error during GQL query: <pre>{}</pre> Note: Queries '
                   'requiring a composite index are not yet supported by the '
                   'AppScale datastore viewer.'.format(error))
      except datastore.datastore_errors.Error as error:
        message = 'Error during GQL query: <pre>{}</pre>'.format(error)

      headers, template_entities, total_entities = (
        self._format_entity_template_data(ds_access, self.request.uri,
                                          entities, total_entities))
      num_pages = int(math.ceil(float(total_entities) /
                                self.NUM_ENTITIES_PER_PAGE))
    else:
      if not kind and kinds:
        self.redirect(self._construct_url(add={'kind': kinds[0]}))
        return

      if kind:
        start = (page-1) * self.NUM_ENTITIES_PER_PAGE
        entities, total_entities = _get_entities(
          ds_access, kind, namespace, order, start, self.NUM_ENTITIES_PER_PAGE)
        headers, template_entities, total_entities = (
          self._format_entity_template_data(ds_access, self.request.uri,
                                            entities, total_entities))
        num_pages = int(math.ceil(float(total_entities) /
                                  self.NUM_ENTITIES_PER_PAGE))
      else:
        start = 0
        headers = []
        template_entities = []
        total_entities = 0
        num_pages = 0

    select_namespace_url = self._construct_url(
      remove=['message'],
      add={'namespace': self.request.get('namespace')})
    context = {
      'entities': template_entities,
      'gql_string': gql_string,
      'headers': headers,
      'kind': kind,
      'kinds': kinds,
      'message': message,
      'namespace': namespace,
      'num_pages': num_pages,
      'order': order,
      'order_base_url': self._construct_url(remove=['message', 'order']),
      'page': page,
      'page_content': self.TEMPLATE,
      'paging_base_url': self._construct_url(remove=['message', 'page']),
      'project_id': project_id,
      'request': self.request,
      'select_namespace_url': select_namespace_url,
      'show_namespace': self.request.get('namespace', None) is not None,
      'start': start,
      'total_entities': total_entities
    }
    self.render_app_page(page='datastore_viewer', values=context)

  def post(self, project_id):
    """ Handle modifying actions and redirect to a GET page.

    Args:
      project_id: A string specifyng the project ID.
    """
    self.ensure_user_has_admin(project_id)

    if self.request.get('action:flush_memcache'):
      if memcache.flush_all():
        message = 'Cache flushed, all keys dropped.'
      else:
        message = 'Flushing the cache failed. Please try again.'
      self.redirect(self._construct_url(remove=['action:flush_memcache'],
                                        add={'message': message}))
    elif self.request.get('action:delete_entities'):
      ds_access = DatastoreDistributed(project_id, DATASTORE_LOCATION,
                                       trusted=True)

      entity_keys = [datastore.Key(key)
                     for key in self.request.params.getall('entity_key')]
      _delete_entities(ds_access, entity_keys)
      self.redirect(self._construct_url(
          remove=['action:delete_entities'],
          add={'message': '%d entities deleted' % len(entity_keys)}))
    else:
      self.error(404)


class DatastoreEditRequestHandler(DatastoreViewerPage):
  """A handler that allows datastore entities to be created and edited."""
  TEMPLATE = 'datastore/edit.html'

  def get(self, project_id, entity_key_string=None):
    """ Displays the fields for a given entity.

    Args:
      project_id: A string specifying the project ID.
      entity_key_string: A string specifying the entity key.
    """
    self.ensure_user_has_admin(project_id)

    ds_access = DatastoreDistributed(project_id, DATASTORE_LOCATION,
                                     trusted=True)

    if entity_key_string:
      entity_key = datastore.Key(entity_key_string)
      entity_key_name = entity_key.name()
      entity_key_id = entity_key.id()
      namespace = entity_key.namespace()
      kind = entity_key.kind()
      entities = [_get_entity_by_key(ds_access, entity_key)]
      parent_key = entity_key.parent()
      if parent_key:
        parent_key_string = _format_datastore_key(parent_key)
      else:
        parent_key_string = None
    else:
      entity_key = None
      entity_key_string = None
      entity_key_name = None
      entity_key_id = None
      namespace = self.request.get('namespace')
      kind = self.request.get('kind')
      entities, _ = _get_entities(ds_access, kind, namespace, order=None,
                                  start=0, count=20)
      parent_key = None
      parent_key_string = None

      if not entities:
        params = urllib.urlencode(
          [('kind', kind),
           ('message', 'Cannot create the kind "%s" in the "%s" namespace '
                       'because no template entity '
                       'exists.' % (kind, namespace)),
           ('namespace', namespace)])
        self.redirect('/datastore_viewer/%s?%s' % (project_id, params))
        return

    property_name_to_values = _property_name_to_values(entities)
    fields = []
    for property_name, values in sorted(property_name_to_values.iteritems()):
      data_type = DataType.get(values[0])
      field = data_type.input_field('%s|%s' % (data_type.name(), property_name),
                                    values[0] if entity_key else None,
                                    values,
                                    self.request.uri)
      fields.append((property_name, data_type.name(), field))

    context = {
      'page_content': self.TEMPLATE,
      'project_id': project_id,
      'fields': fields,
      'key': entity_key_string,
      'key_id': entity_key_id,
      'key_name': entity_key_name,
      'kind': kind,
      'namespace': namespace,
      'next': self.request.get('next',
                               '/datastore_viewer/{}'.format(project_id)),
      'parent_key': parent_key,
      'parent_key_string': parent_key_string,
      'request': self.request
    }
    self.render_app_page(page='datastore_editor', values=context)

  def post(self, project_id, entity_key_string=None):
    """ Handles mutations to a given entity.

    Args:
      project_id: A string specifying the project ID.
      entity_key_string: A string specifying the entity key.
    """
    self.ensure_user_has_admin(project_id)

    ds_access = DatastoreDistributed(project_id, DATASTORE_LOCATION,
                                     trusted=True)

    if self.request.get('action:delete'):
      if entity_key_string:
        _delete_entities(ds_access, [datastore.Key(entity_key_string)])
        redirect_url = self.request.get(
          'next', '/datastore_viewer/{}'.format(project_id))
        self.redirect(str(redirect_url))
      else:
        self.response.set_status(400)
      return

    if entity_key_string:
      entity = _get_entity_by_key(ds_access, datastore.Key(entity_key_string))
    else:
      kind = self.request.get('kind')
      namespace = self.request.get('namespace', None)
      entity = datastore.Entity(kind, _namespace=namespace, _app=project_id)

    for arg_name in self.request.arguments():
      # Arguments are in <property_type>|<property_name>=<value> format.
      if '|' not in arg_name:
        continue
      data_type_name, property_name = arg_name.split('|')
      form_value = self.request.get(arg_name)
      data_type = DataType.get_by_name(data_type_name)
      if (entity and
          property_name in entity and
          data_type.format(entity[property_name]) == form_value):
        # If the property is unchanged then don't update it. This will prevent
        # empty form values from causing the property to be deleted if the
        # property was already empty.
        continue

      # TODO: Handle parse exceptions.
      entity[property_name] = data_type.parse(form_value)

    _put_entity(ds_access, entity)
    redirect_url = self.request.get(
      'next', '/datastore_viewer/{}'.format(project_id))
    self.redirect(str(redirect_url))
