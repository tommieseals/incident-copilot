#!/usr/bin/env python3
"""Fix broken string literals in Python files."""
import re
import sys
from pathlib import Path

def fix_file(filepath):
    with open(filepath, "r") as f:
        content = f.read()
    original = content
    
    # Fix Enum values: VALUE = word -> VALUE = "word"
    content = re.sub(r'^(\s+[A-Z_]+) = ([a-z_]+)$', r'\1 = "\2"', content, flags=re.MULTILINE)
    
    # Fix dictionary keys: {key: -> {"key":
    def fix_dict_keys(match):
        inside = match.group(1)
        fixed = re.sub(r'(?<=[{,\s])([a-z_][a-z0-9_]*)\s*:', r'"\1":', inside)
        return "{" + fixed + "}"
    content = re.sub(r'\{([^{}]+)\}', fix_dict_keys, content)
    
    # Fix .get(word, and .get(word) patterns
    content = re.sub(r'\.get\(([a-z_][a-z0-9_]*),', r'.get("\1",', content)
    content = re.sub(r'\.get\(([a-z_][a-z0-9_]*)\)', r'.get("\1")', content)
    
    # Fix empty strings: = ") -> = "")
    content = re.sub(r'= "\)', r'= "")', content)
    content = re.sub(r', "\)', r', "")', content)
    
    # Fix string defaults after .get: .get("key", word) -> .get("key", "word")
    content = re.sub(r'\.get\("([^"]+)",\s*([a-z][a-z0-9_]*)\)', r'.get("\1", "\2")', content)
    
    # Fix source=word -> source="word"
    content = re.sub(r'source=([a-z]+),', r'source="\1",', content)
    content = re.sub(r'source=([a-z]+)\)', r'source="\1")', content)
    
    # Fix level=word -> level="word" for log levels
    content = re.sub(r'level=([a-z]+),', r'level="\1",', content)
    content = re.sub(r'level=([a-z]+)\)', r'level="\1")', content)
    
    if content != original:
        with open(filepath, "w") as f:
            f.write(content)
        print(f"Fixed: {filepath}")
    else:
        print(f"No changes: {filepath}")

if __name__ == "__main__":
    src_dir = Path(sys.argv[1] if len(sys.argv) > 1 else "src")
    for py_file in src_dir.glob("*.py"):
        fix_file(py_file)
