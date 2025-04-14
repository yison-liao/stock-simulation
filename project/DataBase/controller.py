from pathlib import Path

import pandas as pd
from DbInit import DatabaseInit
from models import Base, StockPerformance

# 初始化資料庫
engine = DatabaseInit()
Base.metadata.create_all(engine.pg_engine)  # 建立表格

# 設定檔案路徑
BASE_PATH = Path(__file__).resolve().parent.parent
file_path = f"{BASE_PATH}/merged_financial_stock_data.csv"

# 讀取並清理資料
stock_file = pd.read_csv(file_path)
stock_file["date"] = pd.to_datetime(
    stock_file["date"]
).dt.date  # 轉為日期格式，去除時間
stock_file = stock_file.drop_duplicates(subset=["company_id", "date"])  # 去除重複值
stock_file = stock_file.dropna(subset=["company_id", "date"])  # 去除關鍵欄位空值

# 準備資料寫入
data_to_write = []
existing_ids = engine.check_duplicates(
    "StockPerformance",
    [f"{row['company_id']}@{row['date']}" for _, row in stock_file.iterrows()],
)

for _, row in stock_file.iterrows():
    data_id = f"{row['company_id']}@{row['date']}"
    if data_id in existing_ids:  # 避免重複寫入
        continue
    write_data = {
        "id": data_id,
        "stock_code": str(row["company_id"]),
        "year": str(row["date"].year),
        "ROE": float(row["ROE"]) if pd.notna(row["ROE"]) else 0.0,
        "EPS": float(row["EPS"]) if pd.notna(row["EPS"]) else 0.0,
        "revenue_growth": float(row["revenue_growth"])
        if pd.notna(row["revenue_growth"])
        else 0.0,
        "date": row["date"],
        "open_price": float(row["Open"]) if pd.notna(row["Open"]) else 0.0,
        "close_price": float(row["Close"]) if pd.notna(row["Close"]) else 0.0,
        "volume": int(row["Volume"]) if pd.notna(row["Volume"]) else 0,
    }
    data_to_write.append(StockPerformance(**write_data))

# 批量寫入資料
if data_to_write:
    engine.write_in(data_to_write)
    print(f"Inserted {len(data_to_write)} new records.")


# 數據驗證
def verify_data():
    with engine.pg_engine.connect() as conn:
        # 檢查總筆數
        total_rows = conn.execute("SELECT COUNT(*) FROM StockPerformance").scalar()
        print(f"Total rows in database: {total_rows}")
        print(f"Total rows in CSV: {len(stock_file)}")

        # 隨機抽查特定股票數據
        sample_stock = "0050"  # 示例股票代號
        sample_date = "2020-01-02"
        sample_id = f"{sample_stock}@{sample_date}"
        result = conn.execute(
            "SELECT * FROM StockPerformance WHERE id = %s", (sample_id,)
        ).fetchone()
        if result:
            print(f"Sample data from DB: {dict(result)}")
            csv_row = stock_file[
                (stock_file["company_id"] == sample_stock)
                & (stock_file["date"] == pd.to_datetime(sample_date).date())
            ]
            if not csv_row.empty:
                print(f"Sample data from CSV: {csv_row.iloc[0].to_dict()}")


# 執行驗證
verify_data()


# 更新機制（示例：檢查並更新最新資料）
def update_data(new_file_path: str):
    new_data = pd.read_csv(new_file_path)
    new_data["date"] = pd.to_datetime(new_data["date"]).dt.date
    new_data = new_data.drop_duplicates(subset=["company_id", "date"])

    data_to_update = []
    existing_ids = engine.check_duplicates(
        "StockPerformance",
        [f"{row['company_id']}@{row['date']}" for _, row in new_data.iterrows()],
    )

    for _, row in new_data.iterrows():
        data_id = f"{row['company_id']}@{row['date']}"
        if data_id not in existing_ids:  # 只新增不存在的資料
            write_data = {
                "id": data_id,
                "stock_code": str(row["company_id"]),
                "year": str(row["date"].year),
                "ROE": float(row["ROE"]) if pd.notna(row["ROE"]) else 0.0,
                "EPS": float(row["EPS"]) if pd.notna(row["EPS"]) else 0.0,
                "revenue_growth": float(row["revenue_growth"])
                if pd.notna(row["revenue_growth"])
                else 0.0,
                "date": row["date"],
                "open_price": float(row["Open"]) if pd.notna(row["Open"]) else 0.0,
                "close_price": float(row["Close"]) if pd.notna(row["Close"]) else 0.0,
                "volume": int(row["Volume"]) if pd.notna(row["Volume"]) else 0,
            }
            data_to_update.append(StockPerformance(**write_data))

    if data_to_update:
        engine.write_in(data_to_update)
        print(f"Updated {len(data_to_update)} new records.")


# 示例更新（假設有新檔案）
# update_data(f"{BASE_PATH}/new_financial_stock_data.csv")


# 查詢腳本示例：選股條件
def query_stocks(min_roe: float = 10.0, min_eps: float = 1.0):
    with engine.mysql_engine.connect() as conn:
        query = """
            SELECT stock_code, year, ROE, EPS, revenue_growth, date, close_price
            FROM StockPerformance
            WHERE ROE >= %s AND EPS >= %s
            ORDER BY date DESC
            LIMIT 10
        """
        result = conn.execute(query, (min_roe, min_eps)).fetchall()
        for row in result:
            print(dict(row))


# 執行查詢示例
query_stocks(min_roe=15.0, min_eps=2.0)
