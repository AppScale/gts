from cassandra.policies import (FallthroughRetryPolicy,
                                RetryPolicy)

# The number of times to retry idempotent statements.
BASIC_RETRY_COUNT = 5


class IdempotentRetryPolicy(RetryPolicy):
  """ A policy used for retrying idempotent statements. """
  def on_read_timeout(self, query, consistency, required_responses,
                      received_responses, data_retrieved, retry_num):
    """ This is called when a ReadTimeout occurs.

    Args:
      query: A statement that timed out.
      consistency: The consistency level of the statement.
      required_responses: The number of responses required.
      received_responses: The number of responses received.
      data_retrieved: Indicates whether any responses contained data.
      retry_num: The number of times the statement has been tried.
    """
    if retry_num >= BASIC_RETRY_COUNT:
      return self.RETHROW, None
    else:
      return self.RETRY, consistency

  def on_write_timeout(self, query, consistency, write_type,
                       required_responses, received_responses, retry_num):
    """ This is called when a WriteTimeout occurs.

    Args:
      query: A statement that timed out.
      consistency: The consistency level of the statement.
      required_responses: The number of responses required.
      received_responses: The number of responses received.
      data_retrieved: Indicates whether any responses contained data.
      retry_num: The number of times the statement has been tried.
      """
    if retry_num >= BASIC_RETRY_COUNT:
      return self.RETHROW, None
    else:
      return self.RETRY, consistency


# A basic policy that retries idempotent operations.
BASIC_RETRIES = IdempotentRetryPolicy()

# A retry policy that never retries operations.
NO_RETRIES = FallthroughRetryPolicy()
