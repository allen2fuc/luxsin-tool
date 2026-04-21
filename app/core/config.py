from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    # 数据库配置
    DB_URL: str
    DB_ECHO: bool = False

    # REDIS
    REDIS_URL: str

    # AI相关配置
    AI_BASE_URL: str
    AI_API_KEY: str
    AI_MODEL: str
    AI_MAX_TOKENS: int = 1024 * 8

    # 设置摘要的条数和token数
    SUMMARY_MAX_MESSAGES: int = 21
    SUMMARY_MAX_TOKENS: int = 10000
    

    # 优化EQ的最大token数
    OPTIMIZE_EQ_MAX_TOKENS: int = 1024 * 8

    # 等待前端回传结果的timeout
    WAIT_FOR_FRONTEND_RESULT_TIMEOUT: int = 30
    # 放入缓存的工具结果的timeout
    CACHE_TOOL_RESULT_TIMEOUT: int = 60

    model_config = {
        "env_file": ".env",
        "env_file_encoding": "utf-8",
    }

settings = Settings()