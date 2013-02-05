
@celery.task
def QUEUE_NAME(headers, args, retry_dict, name=""):
  """ Executes a task to a url with the given args. 
    
  Args:
    headers: A dictionary of headers for the task.
    args: A dictionary of arguments for the request.
          Contains the task body.
    retry_dict: A dictionary with retry parameters.
    name: The name of the task.
  Raises:
    The current function to retry.
  """
  logger.info("Running task with %s %s %s %s" % \
      (str(headers), str(args), str(retry_dict), name))
  connection_host = args['host']
  method = args['method']
  url = args['url']
  connection = httplib.HTTPConnection(connection_host)
  connection.putrequest(method, 
                        url,
                        skip_host='host' in headers,
                        skip_accept_encoding='accept-encoding' in headers) 
  for header in headers:
    connection.putheader(header, headers[header]) 
  connection.endheaders()
  if args["body"]:
    connection.send(base64.b64decode(args['body']))
  response = connection.getresponse()
  response.read()
  response.close()
  logger.info("Response status %d: % response.status")
  if 200 <= response.status < 300:
    pass
    # Success
    # Update the database with the done status
  else:
    # Fail
    # Update the database with the failed status 
    # Retry
    #countdown = retry_time
    raise QUEUE_NAME.retry(countdown=60)
