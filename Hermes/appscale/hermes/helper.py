""" Helper functions for Hermes operations. """
import asyncio
import logging

from appscale.hermes.constants import SubprocessError

logger = logging.getLogger(__name__)


async def subprocess(command, timeout):
  process = await asyncio.create_subprocess_shell(
    command,
    stdout=asyncio.subprocess.PIPE,
    stderr=asyncio.subprocess.PIPE
  )
  logger.debug('Started subprocess `{}` (pid: {})'
               .format(command, process.pid))

  try:
    # Wait for the subprocess to finish
    stdout, stderr = await asyncio.wait_for(process.communicate(), timeout)
  except asyncio.TimeoutError:
    raise SubprocessError('Timed out waiting for subprocess `{}` (pid: {})'
                          .format(command, process.pid))

  output = stdout.decode()
  error = stderr.decode()
  if error:
    logger.warning(error)
  if process.returncode != 0:
    raise SubprocessError('Subprocess failed with return code {} ({})'
                          .format(process.returncode, error))

  return output, error
