import unittest

from appscale.datastore import utils


class TestUtils(unittest.TestCase):
  def test_decode_path(self):
    # Test an entity name.
    path = utils.decode_path('Project:Hadoop\x01')
    self.assertEqual(path.element_size(), 1)
    self.assertEqual(path.element(0).type(), 'Project')
    self.assertEqual(path.element(0).name(), 'Hadoop')

    # Test a path with more than one element.
    path = utils.decode_path('Org:Apache\x01Project:Hadoop\x01')
    self.assertEqual(path.element_size(), 2)
    self.assertEqual(path.element(0).type(), 'Org')
    self.assertEqual(path.element(0).name(), 'Apache')
    self.assertEqual(path.element(1).type(), 'Project')
    self.assertEqual(path.element(1).name(), 'Hadoop')

    # Test an entity ID.
    path = utils.decode_path('Greeting:0000000000000002\x01')
    self.assertEqual(path.element_size(), 1)
    self.assertEqual(path.element(0).type(), 'Greeting')
    self.assertEqual(path.element(0).id(), 2)
