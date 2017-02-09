
@celery.task(max_retries=10000)
def QUEUE_NAME(headers, args):
  """ Executes a task to a url with the given args. 
    
  Args:
    headers: A dictionary of headers for the task.
    args: A dictionary of arguments for the request.
          Contains the task body.
  Returns:
    The status code of the task fetch upon success.
  Raises:
    The current function to retry.
  """
  content_length = len(args['body'])

  loggable_args = {key: args[key] for key in args
                   if key not in ['task_name', 'body', 'payload']}
  loggable_args['body_length'] = content_length
  logger.info('Running {}\n'
              'Headers: {}\n'
              'Args: {}'.format(args['task_name'], headers, loggable_args))
  url = urlparse(args['url'])

  def get_wait_time(retries, args):
    """ Calculates how long we should wait to execute a failed task, based on
    how many times it's failed in the past.

    Args:
      retries: An int that indicates how many times this task has failed.
      args: A dict that contains information about when the user wants to retry
        the failed task.
    Returns:
      The amount of time, in seconds, that we should wait before executing this
      task again.
    """
    min_backoff_seconds = float(args['min_backoff_sec'])
    max_doublings = int(args['max_doublings'])
    max_backoff_seconds = float(args['max_backoff_sec'])
    max_doublings = min(max_doublings, retries)
    wait_time = 2**(max_doublings - 1) * min_backoff_seconds
    wait_time = min(wait_time, max_backoff_seconds)
    return wait_time

  redirects_left = 1
  while True:
    urlpath = url.path
    if url.query:
      urlpath += "?" + url.query

    method = args['method']
    if args['expires'] <= datetime.datetime.now():
      # We do this check because the expires attribute in
      # celery is not passed to retried tasks. This is a
      # documented bug in celery.
      logger.error("Task %s with id %s has expired with expiration date %s" % (
                   args['task_name'], QUEUE_NAME.request.id, args['expires']))
      item = TaskName.get_by_key_name(args['task_name'])
      celery.control.revoke(QUEUE_NAME.request.id)
      db.delete(item)
      return

    if (args['max_retries'] != 0 and
        QUEUE_NAME.request.retries >= args['max_retries']):
      logger.error("Task %s with id %s has exceeded retries: %s" % (
                   args['task_name'], QUEUE_NAME.request.id,
                   args['max_retries']))
      item = TaskName.get_by_key_name(args['task_name'])
      celery.control.revoke(QUEUE_NAME.request.id)
      db.delete(item)
      return

    if url.scheme == 'http':
      connection = httplib.HTTPConnection(PUBLIC_IP, url.port)
    elif url.scheme == 'https':
      connection = httplib.HTTPSConnection(PUBLIC_IP, url.port)
    else:
      logger.error("Task %s tried to use url scheme %s, "
                   "which is not supported." % (args['task_name'], url.scheme))

    skip_host = False
    if 'host' in headers or 'Host' in headers:
      skip_host = True
    skip_accept_encoding = False
    if 'accept-encoding' in headers or 'Accept-Encoding' in headers:
      skip_accept_encoding = True
    connection.putrequest(method,
                          urlpath,
                          skip_host=skip_host,
                          skip_accept_encoding=skip_accept_encoding)

    # Update the task headers
    headers['X-AppEngine-TaskRetryCount'] = str(QUEUE_NAME.request.retries)
    headers['X-AppEngine-TaskExecutionCount'] = str(QUEUE_NAME.request.retries)

    for header in headers:
      connection.putheader(header, headers[header])

    if 'content-type' not in headers or 'Content-Type' not in headers:
      if url.query:
        connection.putheader('content-type', 'application/octet-stream')
      else:
        connection.putheader('content-type',
                             'application/x-www-form-urlencoded')

    connection.putheader("Content-Length", str(content_length))

    retries = int(QUEUE_NAME.request.retries) + 1
    wait_time = get_wait_time(retries, args)

    try:
      connection.endheaders()
      if args["body"]:
        connection.send(args['body'])

      response = connection.getresponse()
      response.read()
      response.close()
    except (BadStatusLine, SocketError):
      logger.warning(
        '{task} failed before receiving response. It will retry in {wait} '
        'seconds.'.format(task=args['task_name'], wait=wait_time))
      raise QUEUE_NAME.retry(countdown=wait_time)

    if 200 <= response.status < 300:
      # Task successful.
      item = TaskName.get_by_key_name(args['task_name'])
      db.delete(item)
      logger.info(
        '{task} received status {status} from {url}'.format(
          task=args['task_name'], status=response.status, url=url))
      return response.status
    elif response.status == 302:
      redirect_url = response.getheader('Location')
      logger.info("Task %s asked us to redirect to %s, so retrying there." % (
        args['task_name'], redirect_url))
      url = urlparse(redirect_url)
      if redirects_left == 0:
        raise QUEUE_NAME.retry(countdown=wait_time)
      redirects_left -= 1
    else:
      logger.warning("Task %s will retry in %d seconds. "
                     "Got response of %d when doing a %s on %s" % \
                      (args['task_name'],
                      wait_time,
                      response.status,
                      method, args['url']))
      raise QUEUE_NAME.retry(countdown=wait_time)
