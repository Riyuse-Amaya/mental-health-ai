import logging
from logging.config import fileConfig

from flask import current_app
from alembic import context

# Alembic Config オブジェクト
config = context.config

# ロギング設定
fileConfig(config.config_file_name)
logger = logging.getLogger('alembic.env')

# Flask アプリケーションから SQLAlchemy のメタデータを取得
target_metadata = current_app.extensions['migrate'].db.metadata

# DB 接続設定
def run_migrations_offline():
    """オフラインモードでマイグレーションを実行（SQL 出力のみ）"""
    url = current_app.config.get("SQLALCHEMY_DATABASE_URI")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        compare_type=True
    )

    with context.begin_transaction():
        context.run_migrations()

def run_migrations_online():
    """オンラインモードでマイグレーションを実行（実際に DB へ適用）"""
    connectable = current_app.extensions['migrate'].db.engine

    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            compare_type=True
        )

        with context.begin_transaction():
            context.run_migrations()

# 実行モードを判定して実行
if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
