"""用戶計劃和角色配置."""

# 用戶計劃和配額
USER_PLANS = {
    "free": {
        "daily_api_limit": 50,
        "concurrent_tasks": 1,
        "max_messages_per_conversation": 50,
        "max_conversations": 5,
        "advanced_models": False
    },
    "basic": {
        "daily_api_limit": 200,
        "concurrent_tasks": 3,
        "max_messages_per_conversation": 200,
        "max_conversations": 20,
        "advanced_models": False
    },
    "pro": {
        "daily_api_limit": 1000,
        "concurrent_tasks": 10,
        "max_messages_per_conversation": 500,
        "max_conversations": 100,
        "advanced_models": True
    }
}

# 角色定義
ROLES = {
    "user": 0,
    "manager": 10,
    "admin": 20,
    "superadmin": 30
}
