"""
Unit tests for common/security.py

bcrypt and hashlib are stable, deterministic dependencies — they are the
units under test here, so they are NOT mocked.  No volatile I/O exists in
this module, making it the one file where no patching is required.
"""

import hashlib
import unittest

from common.security import hash_password, verify_password


class HashPasswordShould(unittest.TestCase):

    def test_returns_a_string(self):
        result = hash_password("mysecretpassword")
        self.assertIsInstance(result, str)

    def test_output_is_not_the_plain_text(self):
        plain = "mysecretpassword"
        self.assertNotEqual(hash_password(plain), plain)

    def test_output_starts_with_bcrypt_prefix(self):
        # passlib always produces a $2b$ prefixed hash
        self.assertTrue(hash_password("anypass").startswith("$2b$"))

    def test_same_input_produces_different_hashes(self):
        self.assertNotEqual(hash_password("anypass"), hash_password("anypass"))

    def test_different_inputs_produce_different_hashes(self):
        self.assertNotEqual(hash_password("anypass"), hash_password("pass"))

    def test_empty_string_is_hashable(self):
        result = hash_password("")
        self.assertIsInstance(result, str)
        self.assertGreater(len(result), 0)


class VerifyPasswordShoud(unittest.TestCase):

    def test_correct_password_returns_true(self):
        plain = "anypass"
        self.assertTrue(verify_password(plain, hash_password(plain)))

    def test_wrong_password_returns_false(self):
        hashed = hash_password("anypass")
        self.assertFalse(verify_password("wrong password", hashed))

    def test_empty_password_matches_empty_hash(self):
        self.assertTrue(verify_password("", hash_password("")))

    def test_empty_password_does_not_match_non_empty_hash(self):
        self.assertFalse(verify_password("", hash_password("non_empty")))

    def test_verification_is_case_sensitive(self):
        hashed = hash_password("Anypass")
        self.assertFalse(verify_password("anypass", hashed))
        self.assertFalse(verify_password("ANYPASS", hashed))
        self.assertTrue(verify_password("Anypass", hashed))

    def test_sha256_pre_hash_layer_cannot_be_bypassed(self):
        """
        Security test: passing the raw SHA-256 hex digest directly must NOT
        satisfy verification.  The caller must always supply the original
        plaintext — the pre-hashing step is an internal implementation detail.
        """
        plain = "anypass"
        sha_hex = hashlib.sha256(plain.encode("utf-8")).hexdigest()
        hashed = hash_password(plain)

        self.assertFalse(verify_password(sha_hex, hashed))
        self.assertTrue(verify_password(plain, hashed))


if __name__ == "__main__":
    unittest.main()
