"""Schema 生成命令行入口。"""

from pathlib import Path
import sys


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from schema_generator import generate_schema


def main() -> None:
    """打印当前数据库 Schema 文本。"""
    print(generate_schema())


if __name__ == "__main__":
    main()
