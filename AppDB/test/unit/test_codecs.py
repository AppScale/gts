import sys
import unittest

from appscale.common.unpackaged import APPSCALE_PYTHON_APPSERVER
from appscale.datastore.fdb import codecs

sys.path.append(APPSCALE_PYTHON_APPSERVER)
from google.appengine.datastore import entity_pb


class TestCodecs(unittest.TestCase):
  def test_reverse_bits(self):
    original = b'guestbook'
    reversed = codecs.reverse_bits(original)
    self.assertEqual(original, codecs.reverse_bits(reversed))

  def test_int64(self):
    test_vals = [-9223372036854775807, -1099511627776, -1, 0, 1, 255, 256,
                 16777216]
    # Ensure original value survives an encoding and decoding transform.
    for test_val in test_vals:
      encoded = codecs.Int64.encode(test_val)
      decoded = codecs.Int64.decode(encoded[0], encoded, 1)[0]
      self.assertEqual(test_val, decoded)

      reverse_encoded = codecs.Int64.encode(test_val, reverse=True)
      reverse_decoded = codecs.Int64.decode(
        reverse_encoded[0], reverse_encoded, 1, reverse=True)[0]
      self.assertEqual(test_val, reverse_decoded)

    # Ensure encoded values are sorted properly.
    for index, test_val in enumerate(test_vals):
      if index == len(test_vals) - 1:
        break

      greater_val = test_vals[index + 1]
      encoded = codecs.Int64.encode(test_val)
      greater_encoded = codecs.Int64.encode(greater_val)
      self.assertLess(encoded, greater_encoded)

      reverse_encoded = codecs.Int64.encode(test_val, reverse=True)
      reverse_greater_encoded = codecs.Int64.encode(greater_val, reverse=True)
      self.assertGreater(reverse_encoded, reverse_greater_encoded)

    test_vals = [(0, 1), (255, 1), (256, 2)]
    for test_val, byte_count in test_vals:
      bare_encoded = codecs.Int64.encode_bare(test_val, byte_count)
      bare_decoded = codecs.Int64.decode_bare(bare_encoded)
      self.assertEqual(test_val, bare_decoded)

  def test_bytes(self):
    test_vals = [b'\x00', b'\x00\x00', b'\x00\xFF', b'guestbook', b'\xFF',
                 b'\xFF\xFF']
    # Ensure original value survives an encoding and decoding transform.
    for test_val in test_vals:
      encoded = codecs.Bytes.encode(test_val)
      decoded = codecs.Bytes.decode(encoded, 1)[0]
      self.assertEqual(test_val, decoded)

      reverse_encoded = codecs.Bytes.encode(test_val, reverse=True)
      reverse_decoded = codecs.Bytes.decode(
        reverse_encoded, 1, reverse=True)[0]
      self.assertEqual(test_val, reverse_decoded)

    # Ensure encoded values are sorted properly.
    for index, test_val in enumerate(test_vals):
      if index == len(test_vals) - 1:
        break

      greater_val = test_vals[index + 1]
      encoded = codecs.Bytes.encode(test_val)
      greater_encoded = codecs.Bytes.encode(greater_val)
      self.assertLess(encoded, greater_encoded)

      reverse_encoded = codecs.Bytes.encode(test_val, reverse=True)
      reverse_greater_encoded = codecs.Bytes.encode(greater_val, reverse=True)
      self.assertGreater(reverse_encoded, reverse_greater_encoded)

  def test_double(self):
    test_vals = [-4294967296.0, -3.14, -.6, -0.0, 0.0, .5, 3.14, 16777216.0]
    # Ensure original value survives an encoding and decoding transform.
    for test_val in test_vals:
      encoded = codecs.Double.encode(test_val)
      decoded = codecs.Double.decode(encoded, 1)[0]
      self.assertEqual(test_val, decoded)

      reverse_encoded = codecs.Double.encode(test_val, reverse=True)
      reverse_decoded = codecs.Double.decode(
        reverse_encoded, 1, reverse=True)[0]
      self.assertEqual(test_val, reverse_decoded)

    # Ensure encoded values are sorted properly.
    for index, test_val in enumerate(test_vals):
      if index == len(test_vals) - 1:
        break

      greater_val = test_vals[index + 1]
      encoded = codecs.Double.encode(test_val)
      greater_encoded = codecs.Double.encode(greater_val)
      self.assertLess(encoded, greater_encoded)

      reverse_encoded = codecs.Double.encode(test_val, reverse=True)
      reverse_greater_encoded = codecs.Double.encode(greater_val, reverse=True)
      self.assertGreater(reverse_encoded, reverse_greater_encoded)

  def test_point(self):
    test_vals = []
    test_tuples = [(-3.5, -1), (-3.5, -0.0), (-3.5, 0.0), (-3.5, 1), (-0.0, 1),
                   (0.0, 1.0), (3.5, 5)]
    for x, y in test_tuples:
      test_val = entity_pb.PropertyValue_PointValue()
      test_val.set_x(x)
      test_val.set_y(y)
      test_vals.append(test_val)

    # Ensure original value survives an encoding and decoding transform.
    for test_val in test_vals:
      encoded = codecs.Point.encode(test_val)
      decoded = codecs.Point.decode(encoded, 1)[0]
      self.assertTrue(test_val.Equals(decoded))

      reverse_encoded = codecs.Point.encode(test_val, reverse=True)
      reverse_decoded = codecs.Point.decode(
        reverse_encoded, 1, reverse=True)[0]
      self.assertTrue(test_val.Equals(reverse_decoded))

    # Ensure encoded values are sorted properly.
    for index, test_val in enumerate(test_vals):
      if index == len(test_vals) - 1:
        break

      greater_val = test_vals[index + 1]
      encoded = codecs.Point.encode(test_val)
      greater_encoded = codecs.Point.encode(greater_val)
      self.assertLess(encoded, greater_encoded)

      reverse_encoded = codecs.Point.encode(test_val, reverse=True)
      reverse_greater_encoded = codecs.Point.encode(greater_val, reverse=True)
      self.assertGreater(reverse_encoded, reverse_greater_encoded)

  def test_text(self):
    test_vals = [u'\x00', u'\x00\x00', u'guestbook', u'z', u'\u03b1']
    # Ensure original value survives an encoding and decoding transform.
    for test_val in test_vals:
      encoded = codecs.Text.encode(test_val)
      decoded = codecs.Text.decode(encoded, 0)[0]
      self.assertEqual(test_val, decoded)

      reverse_encoded = codecs.Text.encode(test_val, reverse=True)
      reverse_decoded = codecs.Text.decode(
        reverse_encoded, 0, reverse=True)[0]
      self.assertEqual(test_val, reverse_decoded)

    # Ensure encoded values are sorted properly.
    for index, test_val in enumerate(test_vals):
      if index == len(test_vals) - 1:
        break

      greater_val = test_vals[index + 1]
      encoded = codecs.Text.encode(test_val)
      greater_encoded = codecs.Text.encode(greater_val)
      self.assertLess(encoded, greater_encoded)

      reverse_encoded = codecs.Text.encode(test_val, reverse=True)
      reverse_greater_encoded = codecs.Text.encode(greater_val, reverse=True)
      self.assertGreater(reverse_encoded, reverse_greater_encoded)

  def test_user(self):
    test_vals = []
    test_tuples = [(u'a@a.com', u'a.com'),
                   (u'test@appscale.com', u'appscale.com'),
                   (u'test@appscale.com', u'example.com')]
    for email, auth_domain in test_tuples:
      test_val = entity_pb.PropertyValue_UserValue()
      test_val.set_email(email)
      test_val.set_auth_domain(auth_domain)
      test_vals.append(test_val)

    # Ensure original value survives an encoding and decoding transform.
    for test_val in test_vals:
      encoded = codecs.User.encode(test_val)
      decoded = codecs.User.decode(encoded, 1)[0]
      self.assertTrue(test_val.Equals(decoded))

      reverse_encoded = codecs.User.encode(test_val, reverse=True)
      reverse_decoded = codecs.User.decode(
        reverse_encoded, 1, reverse=True)[0]
      self.assertTrue(test_val.Equals(reverse_decoded))

    # Ensure encoded values are sorted properly.
    for index, test_val in enumerate(test_vals):
      if index == len(test_vals) - 1:
        break

      greater_val = test_vals[index + 1]
      encoded = codecs.User.encode(test_val)
      greater_encoded = codecs.User.encode(greater_val)
      self.assertLess(encoded, greater_encoded)

      reverse_encoded = codecs.User.encode(test_val, reverse=True)
      reverse_greater_encoded = codecs.User.encode(greater_val, reverse=True)
      self.assertGreater(reverse_encoded, reverse_greater_encoded)

  def test_path(self):
    test_tuples = [(u'Greet', u'test', u'Greeting', u'test'),
                   (u'Greeting', 1),
                   (u'Greeting', 2),
                   (u'Greeting', u'test'),
                   (u'Greeting', u'test', u'Author', 1),
                   (u'Greeting', u'test', u'Greeting', u'test'),
                   (u'Greeting2', u'test'),
                   (u'Greeting2', u'test', u'Greeting', u'test')]

    # Ensure original value survives an encoding and decoding transform.
    for path_tuple in test_tuples:
      encoded = codecs.Path.pack(path_tuple)
      decoded = codecs.Path.unpack(encoded, 0)[0]
      self.assertEqual(path_tuple, decoded)

      reverse_encoded = codecs.Path.pack(path_tuple, reverse=True)
      reverse_decoded = codecs.Path.unpack(
        reverse_encoded, 0, reverse=True)[0]
      self.assertEqual(path_tuple, reverse_decoded)

    # Ensure encoded values are sorted properly.
    for index, path_tuple in enumerate(test_tuples):
      if index == len(test_tuples) - 1:
        break

      greater_val = test_tuples[index + 1]
      encoded = codecs.Path.pack(path_tuple)
      greater_encoded = codecs.Path.pack(greater_val)
      self.assertLess(encoded, greater_encoded)

      reverse_encoded = codecs.Path.pack(path_tuple, reverse=True)
      reverse_greater_encoded = codecs.Path.pack(greater_val, reverse=True)
      self.assertGreater(reverse_encoded, reverse_greater_encoded)

  def test_reference(self):
    test_vals = []
    test_tuples = [
      (u'guest', u'', u'Greet', u'test', u'Greeting', u'test'),
      (u'guestbook', u'', u'Greet', u'test', u'Greeting', u'test'),
      (u'guestbook', u'', u'Greeting', 1),
      (u'guestbook', u'', u'Greeting', 2),
      (u'guestbook', u'', u'Greeting', u'test'),
      (u'guestbook', u'', u'Greeting', u'test', u'Author', 1),
      (u'guestbook', u'', u'Greeting', u'test', u'Greeting', u'test'),
      (u'guestbook', u'', u'Greeting2', u'test'),
      (u'guestbook', u'', u'Greeting2', u'test', u'Greeting', u'test'),
      (u'guestbook', u'ns1', u'Greeting2', u'test', u'Greeting', u'test'),
      (u'guestbook2', u'', u'Greet', u'test', u'Greeting', u'test')
    ]
    for test_tuple in test_tuples:
      ref_val = entity_pb.PropertyValue_ReferenceValue()
      ref_val.set_app(test_tuple[0])
      ref_val.set_name_space(test_tuple[1])
      flat_path = test_tuple[2:]
      for index in range(0, len(flat_path), 2):
        element = ref_val.add_pathelement()
        element.set_type(flat_path[index])
        id_or_name = flat_path[index + 1]
        if isinstance(id_or_name, int):
          element.set_id(id_or_name)
        else:
          element.set_name(id_or_name)

      test_vals.append(ref_val)

    # Ensure original value survives an encoding and decoding transform.
    for test_val in test_vals:
      encoded = codecs.Reference.encode(test_val)
      decoded = codecs.Reference.decode(encoded, 1)[0]
      self.assertTrue(test_val.Equals(decoded))

      reverse_encoded = codecs.Reference.encode(test_val, reverse=True)
      reverse_decoded = codecs.Reference.decode(
        reverse_encoded, 1, reverse=True)[0]
      self.assertTrue(test_val.Equals(reverse_decoded))

    # Ensure encoded values are sorted properly.
    for index, test_val in enumerate(test_vals):
      if index == len(test_vals) - 1:
        break

      greater_val = test_vals[index + 1]
      encoded = codecs.Reference.encode(test_val)
      greater_encoded = codecs.Reference.encode(greater_val)
      self.assertLess(encoded, greater_encoded)

      reverse_encoded = codecs.Reference.encode(test_val, reverse=True)
      reverse_greater_encoded = codecs.Reference.encode(
        greater_val, reverse=True)
      self.assertGreater(reverse_encoded, reverse_greater_encoded)

  def test_txid(self):
    scatter_val = 5
    commit_vs = b'\x00\x00\x00\xa4\x10\xaf\xd3\x0a\x00\x01'
    encoded = codecs.TransactionID.encode(scatter_val, commit_vs)
    decoded_scatter, decoded_commit_vs = codecs.TransactionID.decode(encoded)
    self.assertEqual(scatter_val, decoded_scatter)
    self.assertEqual(commit_vs, decoded_commit_vs)
