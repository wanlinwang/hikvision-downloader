import os


def validate_path(file_path, base_path):
    """
    Validate that the resolved file path is within the expected base directory.
    This prevents path traversal attacks.
    """
    # Resolve absolute paths
    abs_base = os.path.abspath(base_path)
    abs_file = os.path.abspath(file_path)
    
    # Check that the file path starts with the base path
    return abs_file.startswith(abs_base + os.sep) or abs_file == abs_base


def sanitize_filename(filename):
    """
    Sanitize a filename by removing or replacing potentially dangerous characters.
    """
    # Remove any path separators and null bytes
    dangerous_chars = ['..', '/', '\\', '\x00']
    result = filename
    for char in dangerous_chars:
        result = result.replace(char, '_')
    return result


def create_directory_for(file_path):
    directory = os.path.dirname(file_path)
    if not os.path.exists(directory):
        os.makedirs(directory)
