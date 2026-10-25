"""从 ECDICT 原始 CSV 为本地 SQLite 数据库补齐 tag 字段。

这个脚本只在上游 ECDICT 数据缺失 tag 时使用一次。
它会先备份数据库，再通过一个事务导入标签；失败时回滚标签更新。

用法：
    python migrate_cet_tags.py
    python migrate_cet_tags.py --csv .ecdict-source/ecdict.csv
"""

import argparse
import csv
import shutil
import sqlite3
import urllib.request
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parent
DATABASE_FILE = BASE_DIR / "data" / "ecdict.sqlite3"
SOURCE_URL = "https://raw.githubusercontent.com/skywind3000/ECDICT/master/ecdict.csv"
SOURCE_FILE = BASE_DIR / ".ecdict-source" / "ecdict.csv"


def download_source(target: Path) -> None:
    """下载 ECDICT CSV；已经存在时直接复用。"""

    if target.is_file() and target.stat().st_size > 0:
        print(f"复用已有源文件：{target}")
        return

    target.parent.mkdir(parents=True, exist_ok=True)
    temporary_file = target.with_name(f"{target.name}.part")
    print("正在下载 ECDICT 原始数据，首次运行需要一些时间……")
    try:
        with urllib.request.urlopen(SOURCE_URL, timeout=60) as response:
            with temporary_file.open("wb") as output_file:
                shutil.copyfileobj(response, output_file)
        temporary_file.replace(target)
    except Exception:
        # 保留 .part 文件方便检查下载中断的原因，但不会把它当成完整数据。
        raise

    print(f"下载完成：{target}")


def ensure_tag_column(connection: sqlite3.Connection) -> None:
    """如果旧数据库没有 tag 列，就增加一列空标签。"""

    columns = {
        row[1] for row in connection.execute("PRAGMA table_info(entries)")
    }
    if "tag" not in columns:
        connection.execute(
            "ALTER TABLE entries ADD COLUMN tag TEXT NOT NULL DEFAULT ''"
        )
        print("已为 entries 表增加 tag 字段。")


def import_tags(connection: sqlite3.Connection, source_file: Path) -> int:
    """把 CSV 中非空的标签更新到数据库，返回更新行数。"""

    with source_file.open("r", encoding="utf-8-sig", newline="") as csv_file:
        reader = csv.DictReader(csv_file)
        missing_columns = {"word", "tag"} - set(reader.fieldnames or [])
        if missing_columns:
            raise ValueError(
                f"源 CSV 缺少必要字段：{', '.join(sorted(missing_columns))}"
            )

        updated = 0
        connection.execute("BEGIN IMMEDIATE")
        try:
            # 先清空旧标签，保证重复执行时不会保留过期数据。
            connection.execute("UPDATE entries SET tag = ''")
            batch = []
            for row in reader:
                word = (row.get("word") or "").strip()
                tag = " ".join((row.get("tag") or "").casefold().split())
                if not word or not tag:
                    continue

                batch.append((tag, word.casefold()))
                if len(batch) >= 10_000:
                    connection.executemany(
                        "UPDATE entries SET tag = ? WHERE normalized = ?",
                        batch,
                    )
                    updated += len(batch)
                    batch.clear()
                    print(f"已处理 {updated:,} 条标签……")

            if batch:
                connection.executemany(
                    "UPDATE entries SET tag = ? WHERE normalized = ?",
                    batch,
                )
                updated += len(batch)

            connection.execute(
                """
                INSERT INTO metadata (key, value)
                VALUES ('cet_tag_source', ?)
                ON CONFLICT(key) DO UPDATE SET value = excluded.value
                """,
                (SOURCE_URL,),
            )
            connection.commit()
        except Exception:
            connection.rollback()
            raise

    return updated


def main() -> None:
    parser = argparse.ArgumentParser(
        description="为本地 ECDICT SQLite 数据库补充分词标签"
    )
    parser.add_argument(
        "--csv",
        type=Path,
        default=SOURCE_FILE,
        help="已经下载的 ECDICT CSV；默认自动下载到 .ecdict-source/",
    )
    args = parser.parse_args()

    if not DATABASE_FILE.is_file():
        raise FileNotFoundError(f"找不到数据库：{DATABASE_FILE}")
    if not args.csv.is_file():
        download_source(args.csv)

    backup_file = DATABASE_FILE.with_suffix(".sqlite3.bak")
    if not backup_file.exists():
        shutil.copy2(DATABASE_FILE, backup_file)
        print(f"已备份原数据库：{backup_file}")

    with sqlite3.connect(DATABASE_FILE) as connection:
        ensure_tag_column(connection)
        connection.commit()
        updated = import_tags(connection, args.csv)
        total = connection.execute("SELECT COUNT(*) FROM entries").fetchone()[0]
        cet_total = connection.execute(
            """
            SELECT COUNT(*)
            FROM entries
            WHERE instr(' ' || lower(trim(tag)) || ' ', ' cet4 ') > 0
               OR instr(' ' || lower(trim(tag)) || ' ', ' cet6 ') > 0
            """
        ).fetchone()[0]

    print(f"导入完成：{updated:,} 条非空标签，词库共 {total:,} 条。")
    print(f"其中属于 CET4/CET6 的词条：{cet_total:,} 条。")


if __name__ == "__main__":
    main()
