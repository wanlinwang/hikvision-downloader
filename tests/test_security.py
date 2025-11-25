import unittest
import os
import tempfile
import shutil

from src.utils import validate_path, sanitize_filename


class TestSecurityUtils(unittest.TestCase):
    def setUp(self):
        # Create a temporary directory for testing
        self.test_dir = tempfile.mkdtemp()
    
    def tearDown(self):
        # Clean up the temporary directory
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def test_validate_path_valid(self):
        """Test that valid paths within base directory are accepted."""
        base_path = self.test_dir
        valid_path = os.path.join(base_path, 'subdir', 'file.txt')
        self.assertTrue(validate_path(valid_path, base_path))

    def test_validate_path_traversal_attack(self):
        """Test that path traversal attempts are rejected."""
        base_path = self.test_dir
        # Attempt to escape the base directory
        malicious_path = os.path.join(base_path, '..', '..', 'etc', 'passwd')
        self.assertFalse(validate_path(malicious_path, base_path))

    def test_validate_path_absolute_path_attack(self):
        """Test that absolute paths outside base directory are rejected."""
        base_path = self.test_dir
        malicious_path = '/etc/passwd'
        self.assertFalse(validate_path(malicious_path, base_path))

    def test_sanitize_filename_removes_path_traversal(self):
        """Test that path traversal characters are removed."""
        malicious = '../../../etc/passwd'
        sanitized = sanitize_filename(malicious)
        self.assertNotIn('..', sanitized)
        self.assertNotIn('/', sanitized)
        # Should extract just 'passwd' as the basename
        self.assertEqual('passwd', sanitized)

    def test_sanitize_filename_removes_backslash(self):
        """Test that backslashes are removed (Windows path traversal)."""
        malicious = '..\\..\\windows\\system32'
        sanitized = sanitize_filename(malicious)
        self.assertNotIn('..', sanitized)
        self.assertNotIn('\\', sanitized)

    def test_sanitize_filename_removes_null_bytes(self):
        """Test that null bytes are removed."""
        malicious = 'file\x00.txt'
        sanitized = sanitize_filename(malicious)
        self.assertNotIn('\x00', sanitized)

    def test_sanitize_filename_preserves_valid_names(self):
        """Test that valid filenames are preserved."""
        valid_name = '2020-04-15_10_30_00'
        sanitized = sanitize_filename(valid_name)
        self.assertEqual(valid_name, sanitized)

    def test_sanitize_filename_handles_url_encoded_slash(self):
        """Test that URL-encoded path separators are handled."""
        # %2F is URL-encoded forward slash
        malicious = 'file%2F..%2F..%2Fetc%2Fpasswd'
        sanitized = sanitize_filename(malicious)
        self.assertNotIn('/', sanitized)
        # After URL decoding and basename extraction, should get 'passwd'
        self.assertEqual('passwd', sanitized)

    def test_sanitize_filename_handles_url_encoded_backslash(self):
        """Test that URL-encoded backslashes are handled."""
        # %5C is URL-encoded backslash
        malicious = 'file%5C..%5C..%5Cwindows%5Csystem32'
        sanitized = sanitize_filename(malicious)
        self.assertNotIn('\\', sanitized)

    def test_sanitize_filename_empty_result_returns_default(self):
        """Test that empty results after sanitization return a default value."""
        # Edge case: just '..' becomes '_' after sanitization
        result = sanitize_filename('..')
        self.assertNotIn('..', result)
        
        # Edge case: just '.' returns 'unknown'
        result = sanitize_filename('.')
        self.assertEqual('unknown', result)


if __name__ == '__main__':
    unittest.main()
