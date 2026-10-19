"""
크롤러가 뽑아낸 레코드를 BigQuery 통합 테이블에 적재하는 모듈.

- 테이블은 전국 지자체를 한 테이블에 모으는 통합 테이블 (province/city 컬럼으로 구분)
- detail_url 기준으로 이미 적재된 레코드는 건너뛰어, 크롤러를 반복 실행해도
  (최근 N일 이내 재수집으로 인한) 중복이 쌓이지 않게 한다.
- config.json (config.example.json 참고)에서 project_id / dataset / table /
  credentials_path 를 읽는다.
"""

import json
from pathlib import Path

from google.cloud import bigquery
from google.cloud.exceptions import NotFound
from google.oauth2 import service_account

SCHEMA = [
    bigquery.SchemaField("province", "STRING", mode="REQUIRED"),
    bigquery.SchemaField("city", "STRING", mode="REQUIRED"),
    bigquery.SchemaField("board_name", "STRING"),
    bigquery.SchemaField("notice_no", "STRING"),
    bigquery.SchemaField("title", "STRING", mode="REQUIRED"),
    bigquery.SchemaField("post_date", "DATE"),
    bigquery.SchemaField("detail_url", "STRING", mode="REQUIRED"),
    bigquery.SchemaField("attachment_urls", "STRING", mode="REPEATED"),
    bigquery.SchemaField("matched_keywords", "STRING", mode="REPEATED"),
    bigquery.SchemaField("crawled_at", "TIMESTAMP", mode="REQUIRED"),
]


def load_config(config_path: str) -> dict:
    path = Path(config_path)
    if not path.exists():
        raise FileNotFoundError(
            f"{config_path} 가 없습니다. config.example.json을 복사해 채워주세요."
        )
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def get_client(config: dict) -> bigquery.Client:
    credentials = service_account.Credentials.from_service_account_file(config["credentials_path"])
    return bigquery.Client(project=config["project_id"], credentials=credentials)


def ensure_table(client: bigquery.Client, dataset: str, table: str) -> str:
    dataset_ref = bigquery.DatasetReference(client.project, dataset)
    try:
        client.get_dataset(dataset_ref)
    except NotFound:
        client.create_dataset(bigquery.Dataset(dataset_ref))
        print(f"데이터셋 생성: {dataset}")

    table_ref = dataset_ref.table(table)
    try:
        client.get_table(table_ref)
    except NotFound:
        client.create_table(bigquery.Table(table_ref, schema=SCHEMA))
        print(f"테이블 생성: {dataset}.{table}")

    return f"{client.project}.{dataset}.{table}"


def fetch_existing_urls(client: bigquery.Client, table_id: str, urls: list) -> set:
    if not urls:
        return set()
    query = f"SELECT DISTINCT detail_url FROM `{table_id}` WHERE detail_url IN UNNEST(@urls)"
    job_config = bigquery.QueryJobConfig(
        query_parameters=[bigquery.ArrayQueryParameter("urls", "STRING", list(urls))]
    )
    rows = client.query(query, job_config=job_config).result()
    return {row.detail_url for row in rows}


def load_records(records: list, config_path: str = "config.json") -> int:
    if not records:
        print("적재할 레코드가 없습니다.")
        return 0

    config = load_config(config_path)
    client = get_client(config)
    table_id = ensure_table(client, config["dataset"], config["table"])

    urls = [r["detail_url"] for r in records]
    existing = fetch_existing_urls(client, table_id, urls)
    new_records = [r for r in records if r["detail_url"] not in existing]

    skipped = len(records) - len(new_records)
    if not new_records:
        print(f"적재할 새 레코드 없음 (중복 {skipped}건 제외)")
        return 0

    errors = client.insert_rows_json(table_id, new_records)
    if errors:
        raise RuntimeError(f"BigQuery 적재 실패: {errors}")

    print(f"BigQuery 적재 완료: {len(new_records)}건 (중복 {skipped}건 제외) -> {table_id}")
    return len(new_records)


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="records.jsonl을 BigQuery에 적재")
    parser.add_argument("jsonl_path", help="wonju_crawler.py가 생성한 records.jsonl 경로")
    parser.add_argument("--config", type=str, default="config.json")
    args = parser.parse_args()

    with open(args.jsonl_path, encoding="utf-8") as f:
        loaded_records = [json.loads(line) for line in f if line.strip()]

    load_records(loaded_records, config_path=args.config)
