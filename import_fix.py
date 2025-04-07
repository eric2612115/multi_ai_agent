#\!/usr/bin/env python3
import os
import sys
import re

def fix_imports(root_dir="src"):
    pattern = re.compile(r'from\s+(ai|forest|storage|common|api|services|dependencies)\.', re.MULTILINE)
    
    for dirpath, dirnames, filenames in os.walk(root_dir):
        for filename in [f for f in filenames if f.endswith('.py')]:
            filepath = os.path.join(dirpath, filename)
            
            with open(filepath, 'r') as file:
                content = file.read()
            
            # Skip if already has src in imports
            if 'from src.' in content:
                continue
                
            modified_content = pattern.sub(r'from src.\1.', content)
            
            if content != modified_content:
                print(f"Fixing imports in {filepath}")
                with open(filepath, 'w') as file:
                    file.write(modified_content)

if __name__ == "__main__":
    fix_imports()
    print("Import fixing complete\!")
