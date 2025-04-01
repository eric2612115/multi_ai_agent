
try:
    import pymongo
    print(f"PyMongo已安裝，版本: {pymongo.__version__}")
except ImportError:
    print("PyMongo未安裝，無法使用MongoDB功能")

# 嘗試連接到MongoDB
try:
    from pymongo import MongoClient
    client = MongoClient("mongodb://localhost:27017/", serverSelectionTimeoutMS=5000)
    # 測試連接
    client.server_info()
    print("成功連接到MongoDB服務器")
    
    # 列出所有數據庫
    print("可用的數據庫:")
    for db in client.list_database_names():
        print(f"  - {db}")
except Exception as e:
    print(f"MongoDB連接失敗: {e}")
