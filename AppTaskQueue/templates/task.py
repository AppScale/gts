
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
  method = args['method']
  if args['expires'] <= datetime.datetime.now():
    # We do this check because the expires attribute in 
    # celery is not passed to retried tasks. This is a
    # documented bug in celery.
    logger.error("Task %s with id %s has expired with expiration date %s" % \
                 (args['task_name'], QUEUE_NAME.request.id, args['expires']))
    celery.control.revoke(QUEUE_NAME.request.id)
    return

  if QUEUE_NAME.request.retries >= args['max_retries'] and \
         args['max_retries'] != 0:
    logger.error("Task %s with id %s has exceeded retries: %s" % \
                 (args['task_name'], QUEUE_NAME.request.id, args['max_retries']))
    celery.control.revoke(QUEUE_NAME.request.id)
    return
 
  connection = httplib.HTTPConnection(url.hostname, url.port)
  connection.putrequest(method, 
                        url.path,
                        skip_host='host' in headers,
                        skip_accept_encoding='accept-encoding' in headers) 

  # Update the task headers
  headers['X-AppEngine-TaskRetryCount'] = str(QUEUE_NAME.request.retries)
  headers['X-AppEngine-TaskExecutionCount'] = str(QUEUE_NAME.request.retries)

  for header in headers:
    connection.putheader(header, headers[header]) 
  connection.endheaders()
  if args["body"]:
    connection.send(base64.b64decode(args['body']))
  response = connection.getresponse()
  response.close()
  logger.info("Response status %d: % response.status")
  if 200 <= response.status < 300:
    return response.status
    # Success
    # TODO: Update the database with the done status
  else:
    # Fail
    # TODO: Update the database with the failed status 
    # Retry logic
    # Calculate the countdown to run again.
    # http://goo.gl/aWDGi

    retries = int(QUEUE_NAME.request.retries) + 1
    min_backoff_seconds = int(args['min_backoff_sec'])
    max_doublings = int(args['max_doublings'])
    max_backoff_seconds = int(args['max_backoff_sec'])
    max_doublings = min(max_doublings, retries)
    wait_time = 2**(max_doublings - 1) * min_backoff_seconds
    wait_time = min(wait_time, max_backoff_seconds)
    logger.warning("Task %s will retry in %d seconds" % \
                    (args['task_name'], wait_time))
    raise QUEUE_NAME.retry(countdown=wait_time)
