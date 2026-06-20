#!/usr/bin/env python3
"""
金字塔原理重构工具：将杂乱无章的内容按金字塔原理重组。

Usage:
    python restructure.py <input-file> [--output <output-file>]
    python restructure.py --interactive   # 交互模式，逐步引导构建金字塔

输出格式：Markdown 格式的金字塔结构文档
"""

import sys
import re
import json
import argparse
from pathlib import Path


def read_text(source: str) -> str:
    path = Path(source)
    if path.exists():
        return path.read_text(encoding="utf-8")
    return source


def extract_bullet_points(text: str) -> list[str]:
    """从文本中提取要点"""
    lines = text.strip().split("\n")
    points = []

    for line in lines:
        stripped = line.strip()
        if not stripped:
            continue
        # Skip markdown headers
        if stripped.startswith("#"):
            continue
        # Remove leading bullet markers
        cleaned = re.sub(r"^[-*•·]\s*", "", stripped)
        cleaned = re.sub(r"^\d+[\.\)]\s*", "", cleaned)
        if len(cleaned) > 5:
            points.append(cleaned)

    return points


def guess_top_level_conclusion(points: list[str]) -> str:
    """尝试从要点中推断顶层结论"""
    # 找包含结论性句子的点
    conclusion_markers = [
        "总之", "结论", "因此", "所以", "建议", "关键",
        "核心", "综上", "目标", "目的", "愿景"
    ]

    for p in points[:3]:
        if any(m in p for m in conclusion_markers):
            return p

    # Fallback: 使用第一个要点作为候选结论
    if points:
        first = points[0]
        if len(first) > 80:
            first = first[:77] + "..."
        return f"结论：{first}"
    return "待补充核心结论（请用一句话概括你的主张）"


def classify_points(points: list[str]) -> list[dict]:
    """
    将要点分类成金字塔结构。
    返回嵌套结构：[{group: "组名", items: [...], level: 0}]
    """
    if not points:
        return []

    # 启发式分组：使用关键词聚类
    categories = {
        "问题/现状": ["问题", "现状", "挑战", "困难", "痛点", "不足", "短板",
                     "瓶颈", "风险", "危机", "下降", "增加", "减少"],
        "原因/分析": ["原因", "根源", "因为", "由于", "导致", "因素",
                     "分析", "本质", "溯源", "背后"],
        "方案/建议": ["建议", "方案", "措施", "对策", "方法", "策略",
                     "路径", "手段", "步骤", "行动计划", "优化", "改进",
                     "加强", "提升", "推动", "推进"],
        "预期效果": ["效果", "收益", "价值", "ROI", "回报", "成果",
                     "产出", "影响", "目标", "指标", "KPI"]
    }

    grouped = {k: [] for k in categories}
    grouped["其他"] = []
    used = set()

    for i, p in enumerate(points):
        assigned = False
        for cat, keywords in categories.items():
            if any(k in p for k in keywords):
                grouped[cat].append({"index": i, "text": p})
                used.add(i)
                assigned = True
                break
        if not assigned:
            grouped["其他"].append({"index": i, "text": p})
            used.add(i)

    # 过滤空分组
    result = [{"group": k, "items": v} for k, v in grouped.items() if v]

    return result


def build_pyramid_markdown(conclusion: str, groups: list[dict], points_raw: list[str]) -> str:
    """构建金字塔结构Markdown"""

    lines = []
    lines.append(f"# {conclusion}")
    lines.append("")

    for g in groups:
        group_name = g["group"]
        lines.append(f"## {group_name}")
        lines.append("")

        for item in g["items"]:
            lines.append(f"- **{item['text'][:60]}**")
            lines.append(f"  - 展开说明：{item['text']}")
            lines.append("")

        lines.append("")

    return "\n".join(lines)


def interactive_build():
    """交互式引导用户构建金字塔"""
    print("\n🧠 金字塔原理 · 交互式构建")
    print("=" * 50)

    conclusion = input("\n📌 请输入核心结论（一句话概括你的主张）：\n> ").strip()
    if not conclusion:
        print("⚠️ 核心结论不能为空，请重新开始。")
        return

    groups = []
    print("\n📂 现在来分解支撑结论的论点（每组3-7个要点）")
    print("   按回车结束输入")

    while True:
        print(f"\n--- 第 {len(groups) + 1} 组论点 ---")
        group_name = input("组名（如'市场分析''产品策略'等，直接回车结束构建）：\n> ").strip()
        if not group_name:
            if groups:
                break
            else:
                print("至少需要一组论点才能构建金字塔。")
                continue

        items = []
        print(f"输入支撑「{group_name}」的要点（每行一个，空行结束）：")
        while True:
            item = input("  → ").strip()
            if not item:
                break
            items.append(item)

        if items:
            groups.append({"group": group_name, "items": items})
        else:
            print("该组没有输入要点，跳过。")

        more = input("\n继续添加下一组？(y/n): ").strip().lower()
        if more != "y":
            break

    # 输出结果
    print("\n" + "=" * 50)
    print("✅ 金字塔结构已构建！\n")
    print(f"# {conclusion}\n")

    for g in groups:
        print(f"## {g['group']}")
        for item in g["items"]:
            print(f"- {item}")
        print()

    save = input("\n保存到文件？(y/n): ").strip().lower()
    if save == "y":
        output_path = input("文件路径（默认：pyramid_output.md）：\n> ").strip() or "pyramid_output.md"
        content = f"# {conclusion}\n\n"
        for g in groups:
            content += f"## {g['group']}\n\n"
            for item in g["items"]:
                content += f"- {item}\n"
            content += "\n"
        save_with_safety(output_path, content)


def save_with_safety(path: str, content: str):
    """安全写入：有覆盖保护"""
    p = Path(path)
    if p.exists():
        import sys as _sys
        # 非交互模式下自动生成唯一文件名
        stem = p.stem
        suffix = p.suffix
        counter = 1
        while p.exists():
            p = p.with_name(f"{stem}_{counter}{suffix}")
            counter += 1
        print(f"⚠️ 文件已存在，保存为: {p.name}")
    p.write_text(content, encoding="utf-8")
    print(f"✅ 已保存至: {p}")


def main():
    parser = argparse.ArgumentParser(description="金字塔原理 - 内容重构工具")
    parser.add_argument("input", nargs="?", help="输入文件路径")
    parser.add_argument("--output", "-o", help="输出文件路径")
    parser.add_argument("--interactive", "-i", action="store_true", help="交互模式")
    parser.add_argument("--json", "-j", action="store_true", help="以JSON格式输出")

    args = parser.parse_args()

    if args.interactive or not args.input:
        interactive_build()
        return

    text = read_text(args.input)
    points = extract_bullet_points(text)
    conclusion = guess_top_level_conclusion(points)
    groups = classify_points(points)

    if args.json:
        result = {
            "conclusion": conclusion,
            "groups": [(g["group"], [item["text"] for item in g["items"]]) for g in groups]
        }
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return

    output = build_pyramid_markdown(conclusion, groups, points)

    if args.output:
        save_with_safety(args.output, output)
    else:
        print(output)


if __name__ == "__main__":
    main()
