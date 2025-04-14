from pathlib import Path

from dotenv import dotenv_values
from sqlalchemy import create_engine
from sqlalchemy.orm import Session


class DatabaseInit:
    def __init__(self) -> None:
        BASE_PATH = Path(__file__).resolve().parent.parent
        db_config = dict(**dotenv_values(f"{BASE_PATH}/.env"))
        pg_url = f"postgresql://{db_config['POSTGRES_USER']}:{db_config['POSTGRES_PASSWORD']}@{db_config['POSTGRES_HOST']}:{db_config['POSTGRES_PORT']}/{db_config['POSTGRES_DBNAME']}"
        self.pg_engine = create_engine(pg_url, echo=True)

    def write_in(self, data_in: list):
        try:
            with Session(self.pg_engine) as sess:
                sess.add_all(data_in)
                sess.commit()
                print("Data write in success")
        except Exception as e:
            sess.rollback()
            raise e

    def check_duplicates(self, table_name: str, id_list: list) -> list:
        """檢查資料庫中是否已有這些 ID，避免重複寫入"""
        with Session(self.pg_engine) as sess:
            query = f"SELECT id FROM {table_name} WHERE id IN :ids"
            result = sess.execute(query, {"ids": tuple(id_list)}).fetchall()
            existing_ids = {row[0] for row in result}
            return [id for id in id_list if id not in existing_ids]
