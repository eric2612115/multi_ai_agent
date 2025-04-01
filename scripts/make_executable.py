#!/usr/bin/env python
"""
給所有測試腳本添加執行權限
"""
import os
import stat
import sys

def make_executable(file_path):
    """添加執行權限"""
    current_permissions = os.stat(file_path).st_mode
    os.chmod(file_path, current_permissions | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
    print(f"Added execute permission to {file_path}")

def main():
    """主函數"""
    script_dir = os.path.dirname(os.path.abspath(__file__))
    
    for filename in os.listdir(script_dir):
        if filename.endswith(".py") and not filename == os.path.basename(__file__):
            file_path = os.path.join(script_dir, filename)
            make_executable(file_path)
    
    print("Done! All Python scripts now have executable permissions.")

if __name__ == "__main__":
    main()
