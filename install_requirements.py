
#!/usr/bin/env python
"""
安裝必要依賴
"""
import sys
import subprocess
from importlib.util import find_spec

def check_module(module_name):
    """檢查模組是否已安裝"""
    return find_spec(module_name) is not None

def install_module(module_name):
    """安裝模組"""
    print(f"安裝 {module_name}...")
    subprocess.check_call([sys.executable, "-m", "pip", "install", module_name])
    print(f"{module_name} 安裝完成!")

def main():
    """主函數"""
    # 檢查核心依賴
    core_modules = [
        "pymongo",
        "motor"
    ]
    
    for module in core_modules:
        if not check_module(module):
            print(f"{module} 未安裝，正在安裝...")
            install_module(module)
        else:
            print(f"{module} 已安裝")
    
    print("\n所有必要的依賴都已安裝!")

if __name__ == "__main__":
    main()
