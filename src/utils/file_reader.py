"""
Utility to read files.
"""
def read_file(path):
    with open(path, 'r', encoding='utf-8') as f:
        return f.read()