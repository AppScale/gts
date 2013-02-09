
@celery.task
def QUEUE_NAME(headers, args, name=""):
  """ Executes a task to a url with the given args. 
    
  Args:
    headers: A dictionary of headers for the task.
    args: A dictionary of arguments for the request.
          Contains the task body.
    name: The name of the task.
  Raises:
    The current function to retry.
  """
  logger.info("Running task with %s %s %s" % \
      (str(headers), str(args), name))
  url = urlparse(args['url'])
  method = args['method']
  print url
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
  print response.read()
  response.close()
  print response.status
  logger.info("Response status %d: % response.status")
  if 200 <= response.status < 300:
    pass
    # Success
    # Update the database with the done status
  else:
    # Fail
    # Update the database with the failed status 
    # Retry
    raise QUEUE_NAME.retry()
