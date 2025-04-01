
#!/usr/bin/env python
"""
測試MongoDB連接和存儲
"""
import os
import uuid
from datetime import datetime
from pymongo import MongoClient

def main():
    """主函數"""
    print("測試MongoDB連接和基本操作...")
    
    # 連接MongoDB
    try:
        client = MongoClient("mongodb://localhost:27017", serverSelectionTimeoutMS=5000)
        # 測試連接
        client.server_info()
        print("成功連接到MongoDB服務器!")
        
        # 選擇數據庫和集合
        db = client.research_db
        collection = db.research_reports
        
        # 創建測試文檔
        doc_id = str(uuid.uuid4())
        document = {
            "_id": doc_id,
            "topic": "MongoDB測試文檔",
            "content": "這是一個測試文檔，用於確認MongoDB存儲功能正常工作。",
            "created_at": datetime.now()
        }
        
        # 存入MongoDB
        print(f"正在保存測試文檔到 {db.name}.{collection.name}...")
        result = collection.insert_one(document)
        print(f"文檔保存成功，ID: {result.inserted_id}")
        
        # 檢索文檔
        print("檢索文檔...")
        retrieved = collection.find_one({"_id": doc_id})
        if retrieved:
            print("成功檢索文檔:")
            print(f"  主題: {retrieved['topic']}")
            print(f"  內容: {retrieved['content']}")
        else:
            print("無法檢索文檔")
        
        # 列出所有文檔
        print("\n數據庫中的所有文檔:")
        for doc in collection.find().limit(5):
            print(f"  - {doc.get('_id')}: {doc.get('topic', '未知主題')}")
        
        # 刪除測試文檔
        print(f"\n刪除測試文檔 {doc_id}...")
        collection.delete_one({"_id": doc_id})
        print("測試文檔已刪除")
        
        print("\nMongoDB測試完成，一切正常!")
    except Exception as e:
        print(f"MongoDB測試失敗: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()
