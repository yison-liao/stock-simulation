import os
import time
from datetime import datetime, timedelta
from pathlib import Path

import pandas as pd
import requests
import twstock
import yfinance
from bs4 import BeautifulSoup
from DbInit import DatabaseInit
from models import Base

# 初始化資料庫（假設已調整為 MySQL）
engine = DatabaseInit()
Base.metadata.create_all(engine.pg_engine)

# 設定路徑
BASE_PATH = Path(__file__).resolve().parent.parent
set_twstock = set(
    stock for stock in twstock.twse if len(stock) < 5 and stock[:2] != "00"
)


# 工具函數：從台灣證交所獲取財報資料
def finance_data(year, season, type="綜合損益表"):
    if season > 4 or season < 1:
        raise Exception("incorrect season")
    season = f"0{season}"
    payload = {
        "encodeURIComponent": "1",
        "run": "",
        "step": "1",
        "TYPEK": "sii",
        "firstin": "true",
        "year": str(year),
        "season": season,
    }
    url = (
        "https://mops.twse.com.tw/mops/web/ajax_t51sb08"
        if type == "綜合損益表"
        else "https://mops.twse.com.tw/mops/web/ajax_t51sb07"
    )
    if year > 101:
        url = (
            "https://mops.twse.com.tw/mops/web/ajax_t163sb04"
            if type == "綜合損益表"
            else "https://mops.twse.com.tw/mops/web/ajax_t163sb05"
        )

    headers = {"Cookie": "jcsession=jHttpSession@9bf9964", "user-agent": "Mozilla/5.0"}
    s = requests.Session()
    r = s.post(url=url, data=payload, headers=headers)
    r.encoding = "utf8"
    dfs = pd.read_html(r.text)[1:]
    dfs = pd.concat(dfs, axis=0, ignore_index=True).drop(
        columns=["合計：共 450 家"], errors="ignore"
    )
    dfs = (
        dfs.loc[:, ~dfs.columns.duplicated()]
        .rename(columns={"公司 代號": "公司代號"})
        .set_index("公司代號")
    )
    return dfs


# 工具函數：儲存股價數據
def save_ticker(ticker):
    now = datetime.now().strftime("%Y-%m-%d")
    start_date = (datetime.now() - timedelta(days=90)).strftime(
        "%Y-%m-%d"
    )  # 更新最近 90 天
    data = yfinance.Ticker(ticker)
    df = data.history(start=start_date, end=now)
    if df.empty:
        return
    file_name = f"{BASE_PATH}/上市股票歷史成交價/{ticker}.csv"
    df.to_csv(file_name)
    print(f"{ticker} save success")
    return df


# 工具函數：獲取財報發布日期
def get_publish_date(ticker, year):
    sess = requests.Session()
    url = "https://mops.twse.com.tw/mops/web/ajax_t57sb01_q1"
    payload = {
        "encodeURIComponent": "1",
        "step": "1",
        "firstin": "1",
        "off": "1",
        "TYPEK": "all",
        "keyword4": "",
        "code1": "",
        "TYPEK2": "",
        "checkbtn": "",
        "queryName": "co_id",
        "inpuType": "co_id",
        "co_id": ticker,
        "year": str(year - 1911),
    }
    headers = {"user-agent": "Mozilla/5.0"}
    response = sess.post(url=url, data=payload, headers=headers)
    html_parser = BeautifulSoup(response.text, "html.parser")
    second_url = html_parser.find("input")["value"].split("'")[1].strip("&")
    response = sess.get(url=second_url, headers=headers)
    df_list = pd.read_html(response.text)
    for df in df_list:
        if "資料年度" in df.columns:
            return df
    return None


# 更新財報資料
def update_financial_data(year, season):
    revenue_df = finance_data(year, season, "綜合損益表")
    capital_df = finance_data(year, season, "資產負債表")
    revenue_df.to_csv(f"{BASE_PATH}/綜合損益表/{year + 1911}Q{season}.csv")
    capital_df.to_csv(f"{BASE_PATH}/資產負債表/{year + 1911}Q{season}.csv")
    print(f"Financial data for {year + 1911}Q{season} updated")


# 更新股價資料
def update_stock_data():
    stock_data = {}
    for ticker in set_twstock:
        df = save_ticker(f"{ticker}.TW")
        if df is not None:
            stock_data[ticker] = df
        time.sleep(1)  # 避免過快請求
    return stock_data


# 合併最新資料
def merge_latest_data(year, season):
    # 讀取現有合併資料
    existing_file = f"{BASE_PATH}/merged_financial_stock_data.csv"
    if os.path.exists(existing_file):
        existing_df = pd.read_csv(existing_file)
    else:
        existing_df = pd.DataFrame()

    # 更新財報
    update_financial_data(year, season)
    revenue_df = pd.read_csv(f"{BASE_PATH}/綜合損益表/{year + 1911}Q{season}.csv")
    capital_df = pd.read_csv(f"{BASE_PATH}/資產負債表/{year + 1911}Q{season}.csv")

    # 更新股價
    stock_data = update_stock_data()

    # 處理財報發布日期並合併
    financials = {
        "date": [],
        "company_id": [],
        "revenue": [],
        "net_profit": [],
        "EPS": [],
        "Shareholders_equity": [],
    }
    for ticker in set_twstock:
        pub_df = get_publish_date(ticker, year + 1911)
        if pub_df is None:
            continue
        for _, row in pub_df.iterrows():
            season_str = f"Q{season}"
            if season_str in row["資料年度"]:
                date = pd.to_datetime(
                    row["上傳日期"].split(" ")[0].replace("/", "-")
                ) + timedelta(days=1911 * 365)  # 轉西元年
                rev_row = revenue_df[revenue_df.index == int(ticker)]
                cap_row = capital_df[capital_df.index == int(ticker)]
                if not rev_row.empty and not cap_row.empty:
                    financials["date"].append(date)
                    financials["company_id"].append(ticker)
                    financials["revenue"].append(
                        rev_row["營業收入"].iloc[0]
                        if "營業收入" in rev_row.columns
                        else 0
                    )
                    financials["net_profit"].append(
                        rev_row["本期淨利（淨損）"].iloc[0]
                        if "本期淨利（淨損）" in rev_row.columns
                        else 0
                    )
                    financials["EPS"].append(
                        rev_row["基本每股盈餘"].iloc[0]
                        if "基本每股盈餘" in rev_row.columns
                        else 0
                    )
                    financials["Shareholders_equity"].append(
                        cap_row["股東權益總計"].iloc[0]
                        if "股東權益總計" in cap_row.columns
                        else 0
                    )

    financials_df = pd.DataFrame(financials)
    financials_df["date"] = pd.to_datetime(financials_df["date"]).dt.tz_localize(None)

    # 合併股價
    stocks_df = pd.concat(
        [
            df.reset_index().rename(
                columns={
                    "Date": "date",
                    "Open": "Open",
                    "High": "High",
                    "Low": "Low",
                    "Close": "Close",
                    "Volume": "Volume",
                }
            )
            for ticker, df in stock_data.items()
        ],
        keys=set_twstock,
        names=["company_id"],
    ).reset_index()
    stocks_df["date"] = pd.to_datetime(stocks_df["date"]).dt.tz_localize(None)

    # 使用 merge_asof 合併
    merged = pd.merge_asof(
        stocks_df.sort_values("date"),
        financials_df.sort_values("date"),
        by="company_id",
        on="date",
        direction="forward",
    )

    # 計算 growth_rate 和 ROE
    merged["revenue"] = pd.to_numeric(merged["revenue"], errors="coerce").fillna(0)
    merged["growth_rate"] = round(
        merged.groupby("company_id")["revenue"].pct_change().fillna(0), 4
    )
    merged["Shareholders_equity"] = pd.to_numeric(
        merged["Shareholders_equity"], errors="coerce"
    ).fillna(0)
    merged["net_profit"] = pd.to_numeric(merged["net_profit"], errors="coerce").fillna(
        0
    )
    merged["ROE"] = round(merged["net_profit"] / merged["Shareholders_equity"] * 100, 4)

    # 與現有資料合併並去重
    if not existing_df.empty:
        merged = pd.concat([existing_df, merged]).drop_duplicates(
            subset=["company_id", "date"]
        )

    # 儲存結果
    merged.to_csv(f"{BASE_PATH}/merged_financial_stock_data.csv", index=False)
    print("Latest data merged and saved successfully")


# 主程式：更新 2025 年 Q1 資料
if __name__ == "__main__":
    merge_latest_data(114, 1)  # 民國 114 年 = 2025 年
