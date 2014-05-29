
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
  logger.info("Running task with %s %s %s" % \
      (str(headers), str(args), args['task_name']))
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
    min_backoff_seconds = int(args['min_backoff_sec'])
    max_doublings = int(args['max_doublings'])
    max_backoff_seconds = int(args['max_backoff_sec'])
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

      item = TaskName.get_by_key_name(args['task_name'])
      item.state = TASK_STATES.EXPIRED
      item.endtime = datetime.datetime.now()
      item.put()
      logger.error("Task %s with id %s has expired with expiration date %s" % \
                   (args['task_name'], QUEUE_NAME.request.id, args['expires']))
      celery.control.revoke(QUEUE_NAME.request.id)
      return

    if QUEUE_NAME.request.retries >= args['max_retries'] and \
           args['max_retries'] != 0:
      logger.error("Task %s with id %s has exceeded retries: %s" % \
                   (args['task_name'], QUEUE_NAME.request.id, args['max_retries']))

      item = TaskName.get_by_key_name(args['task_name'])
      item.state = TASK_STATES.FAILED
      item.endtime = datetime.datetime.now()
      item.put()
      celery.control.revoke(QUEUE_NAME.request.id)
      return

    if url.scheme == 'http':
      connection = httplib.HTTPConnection(url.hostname, url.port)
    elif url.scheme == 'https':
      connection = httplib.HTTPSConnection(url.hostname, url.port)
    else:
      logger.error("Task %s tried to use url scheme %s, which is not supported." % (args['task_name'], url.scheme))

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

    content_length = "0"
    if args["body"]:
      content_length = str(len(args['body']))

    if 'content-type' not in headers or 'Content-Type' not in headers:
      if url.query:
        connection.putheader('content-type', 'application/octet-stream')
      else:
        connection.putheader('content-type', 'application/x-www-form-urlencoded')

    connection.putheader("Content-Length", content_length)
    connection.endheaders()
    if args["body"]:
      connection.send(args['body'])
    response = connection.getresponse()
    payload = response.read()
    response.close()
    retries = int(QUEUE_NAME.request.retries) + 1
    if 200 <= response.status < 300:
      # Mark the task as a success.
      item = TaskName.get_by_key_name(args['task_name'])
      item.state = TASK_STATES.SUCCESS
      item.endtime = datetime.datetime.now()
      item.put()
      return response.status
    elif response.status == 302:
      redirect_url = response.getheader('Location')
      logger.info("Task %s asked us to redirect to %s, so retrying there." % (args['task_name'], redirect_url))
      url = urlparse(redirect_url)
      if redirects_left == 0:
        raise QUEUE_NAME.retry(countdown=get_wait_time(retries, args))
      redirects_left -= 1
    else:
      # Fail
      # TODO: Update the database with the failed status
      wait_time = get_wait_time(retries, args)
      logger.warning("Task %s will retry in %d seconds. Got response of %d when doing a %s on %s" % \
                      (args['task_name'], wait_time, response.status, method, args['url']))
      raise QUEUE_NAME.retry(countdown=wait_time)
