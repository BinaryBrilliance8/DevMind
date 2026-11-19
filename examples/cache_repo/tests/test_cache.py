import unittest

from cache import TTLCache


class CacheTests(unittest.TestCase):
    def setUp(self):
        self.now = 10.0
        self.cache = TTLCache(lambda: self.now)

    def test_value_before_expiry(self):
        self.cache.put("key", "value", 5)
        self.now = 14.9
        self.assertEqual(self.cache.get("key"), "value")

    def test_expired_at_boundary(self):
        self.cache.put("key", "value", 5)
        self.now = 15.0
        self.assertIsNone(self.cache.get("key"))

    def test_expired_after_boundary(self):
        self.cache.put("key", "value", 5)
        self.now = 15.1
        self.assertIsNone(self.cache.get("key"))

    def test_zero_ttl(self):
        self.cache.put("key", "value", 0)
        self.assertIsNone(self.cache.get("key"))

    def test_negative_ttl_rejected(self):
        with self.assertRaises(ValueError):
            self.cache.put("key", "value", -1)

    def test_missing_key(self):
        self.assertIsNone(self.cache.get("missing"))
