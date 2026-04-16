#!/usr/bin/env python3
"""
Interactive configuration wizard for free-scp-skill.
Run this once before init_db.py to customise paths and the embedding model.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from config_utils import get_config, save_config, get_data_dir, get_default_vector_db_path


def prompt_choice(question, options, default_index=0):
    """Present a numbered list and return the selected index."""
    print(f"\n{question}")
    for idx, (label, desc) in enumerate(options):
        marker = " (默认)" if idx == default_index else ""
        print(f"  [{idx + 1}] {label}{marker}")
        print(f"      {desc}")
    while True:
        choice = input(f"请输入选项编号 (1-{len(options)}), 直接回车选默认 [{default_index + 1}]: ").strip()
        if not choice:
            return default_index
        if choice.isdigit():
            num = int(choice)
            if 1 <= num <= len(options):
                return num - 1
        print("无效输入，请重新选择。")


def prompt_custom_path(default_path):
    """Ask user for a custom directory path."""
    print(f"\n请输入自定义向量库目录路径（直接回车使用默认路径 {default_path}）：")
    while True:
        path = input("> ").strip()
        if not path:
            return default_path
        p = Path(path)
        try:
            p.mkdir(parents=True, exist_ok=True)
            return str(p.resolve())
        except OSError as exc:
            print(f"无法创建目录: {exc}")
            print("请重新输入：")


def main():
    print("=" * 55)
    print("free-scp-skill 配置向导")
    print("=" * 55)
    print("\n本向导将帮助您配置向量库存储位置和 Embedding 模型。")
    print("配置只需设置一次，后续 init_db.py 会自动读取。\n")

    existing = get_config()
    if Path(get_config()["config_version"]).name != "1.0":
        pass  # placeholder for future migration logic

    # --- Vector DB path ---
    default_path = get_default_vector_db_path()
    path_options = [
        ("用户数据目录", f"{default_path}  （推荐，安全隔离）"),
        ("当前项目目录", f"{Path.cwd() / 'vector_db'}  （方便调试和迁移）"),
        ("自定义路径", "手动指定其他磁盘或目录"),
    ]
    path_idx = prompt_choice("请选择向量库的存储位置：", path_options, default_index=0)
    if path_idx == 0:
        vector_db_path = default_path
    elif path_idx == 1:
        vector_db_path = str((Path.cwd() / "vector_db").resolve())
    else:
        vector_db_path = prompt_custom_path(default_path)

    # --- Embedding model ---
    model_options = [
        (
            "all-MiniLM-L6-v2",
            "体积小（约 80MB），速度快，适合大多数用户。",
        ),
        (
            "all-mpnet-base-v2",
            "体积较大（约 420MB），语义精准度更高，追求命中质量首选。",
        ),
        (
            "paraphrase-multilingual-MiniLM-L12-v2",
            "体积约 470MB，对中英文混合查询更友好。",
        ),
    ]
    model_idx = prompt_choice("请选择 Embedding 模型：", model_options, default_index=0)
    embedding_model = model_options[model_idx][0]

    # --- Summary ---
    new_cfg = {
        "vector_db_path": vector_db_path,
        "embedding_model": embedding_model,
        "data_source": existing.get("data_source", "https://scp-data.tedivm.com"),
        "config_version": "1.0",
    }

    print("\n" + "-" * 55)
    print("配置摘要：")
    print(f"  向量库路径: {new_cfg['vector_db_path']}")
    print(f"  Embedding 模型: {new_cfg['embedding_model']}")
    print(f"  数据源: {new_cfg['data_source']}")
    print("-" * 55)

    confirm = input("\n确认保存以上配置？(Y/n): ").strip().lower()
    if confirm in ("n", "no"):
        print("已取消，配置未保存。")
        sys.exit(0)

    save_config(new_cfg)
    print(f"\n配置已保存到: {Path(__file__).parent.parent / 'config_utils.py'} 指向的 config.json")
    print("现在您可以运行:  python tools/init_db.py")


if __name__ == "__main__":
    main()
