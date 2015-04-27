""" A test script to shut down cassandra. """
import os
import sys
sys.path.append(os.path.join(os.path.dirname(__file__), "../../backup"))
import cassandra_backup

cassandra_backup.shutdown_cassandra()
