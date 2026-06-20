#!/usr/bin/env python3
"""
金字塔原理分析工具：诊断文本是否符合金字塔原理，给出结构化改进建议。

Usage:
    python analyze.py <text-file-path>
    # 或通过管道输入
    cat input.txt | python analyze.py

输出结构化的诊断报告，包括：
- 是否有明确的结论先行
- 层级结构是否清晰
- 分类是否符合 MECE
- 逻辑递进是否合理
- 改进建议
"""

import sys
import re
import json
from pathlib import Path


def read_text(source: str) -> str:
    """从文件或 stdin 读取文本"""
    path = Path(source)
    if path.exists():
        return path.read_text(encoding="utf-8")
    return source


def extract_paragraphs(text: str) -> list[dict]:
    """将文本分割成段落，保留层级信息"""
    lines = text.strip().split("\n")
    paragraphs = []
    current = []

    for line in lines:
        stripped = line.strip()
        if not stripped:
            if current:
                paragraphs.append({
                    "text": " ".join(current),
                    "raw": "\n".join(current),
                    "indent": len(line) - len(line.lstrip())
                })
                current = []
        else:
            current.append(stripped)

    if current:
        paragraphs.append({
            "text": " ".join(current),
            "raw": "\n".join(current),
            "indent": len(current[0]) - len(current[0].lstrip()) if current else 0
        })

    return paragraphs


def has_obvious_conclusion(paragraphs: list[dict]) -> dict:
    """检查是否有明确的结论先行"""
    if not paragraphs:
        return {"score": 0, "detail": "文本为空", "passed": False}

    first = paragraphs[0]["text"]
    conclusion_markers = [
        "总之", "结论", "因此", "所以", "核心", "关键", "建议",
        "我认为", "我们应", "我认为", "综上所述", "核心观点",
        "中心思想", "我们的判断是", "答案是"
    ]

    found_markers = [m for m in conclusion_markers if m in first]
    first_30 = first[:80]

    if found_markers:
        return {
            "score": 10,
            "detail": f"✅ 开头包含结论标记词：{found_markers}",
            "passed": True,
            "markers": found_markers
        }

    # 检查第一段是否像结论（短句、判断句、祈使句）
    # 判断句标记：包含判断动词、祈使标记
    judgement_markers = ["是", "应", "必须", "需要", "建议", "要", "得"]
    if len(first_30) < 60 and any(m in first_30 for m in judgement_markers):
        return {
            "score": 7,
            "detail": "⚠️ 第一段较短且含判断句特征，可能隐含结论，但无明显结论标记词",
            "passed": True
        }

    return {
        "score": 3,
        "detail": "❌ 未发现明确结论标记。金字塔原理要求'结论先行'——开门见山给出核心观点",
        "passed": False,
        "suggestion": "在第一段用一句话概括你的核心结论，如'建议…'、'核心结论是…'"
    }


def detect_hierarchy(paragraphs: list[dict]) -> dict:
    """检测段落层级结构"""
    if len(paragraphs) < 3:
        return {"score": 3, "detail": "段落太少（<3），无法评估层级结构", "passed": False}

    indents = [p["indent"] for p in paragraphs]
    unique_indents = sorted(set(indents))
    depth = len(unique_indents)

    issues = []
    score = 5

    if depth == 1:
        issues.append("所有段落缩进相同，没有视觉层级区分")
        score = 3
    elif depth <= 2:
        issues.append("层级较少（{depth}层），建议增加细分层级")
        score = 4

    # 检查是否浅层段落过多（没有展开）
    top_level = [p for p in paragraphs if p["indent"] == 0]
    if len(top_level) > 7:
        issues.append(f"顶级段落过多（{len(top_level)}个），建议归类分组，每层控制在3-7个要点")

    # 检查是否有孤立的深层段落
    hierarchy_gaps = 0
    for i in range(1, len(paragraphs)):
        if paragraphs[i]["indent"] > paragraphs[i-1]["indent"] + 4:
            hierarchy_gaps += 1
    if hierarchy_gaps > 0:
        issues.append(f"存在{hierarchy_gaps}处层级跳跃（缩进变化过大）")

    if not issues:
        issues.append(f"层级结构基本清晰（{depth}层），共{len(paragraphs)}个段落")
        score = 8

    return {
        "score": score,
        "depth": depth,
        "detail": "；".join(issues),
        "passed": score >= 5
    }


def check_mece(paragraphs: list[dict]) -> dict:
    """根据段落结构初步检查 MECE"""
    if not paragraphs:
        return {"score": 0, "detail": "无内容可分析", "passed": False}

    grouped = {}
    for p in paragraphs:
        indent = p["indent"]
        if indent not in grouped:
            grouped[indent] = []
        grouped[indent].append(p["text"])

    issues = []
    score = 5

    # 检查同一层级段落数量
    for level, items in grouped.items():
        if level == 0:
            continue  # 顶层结论不适用MECE检查
        count = len(items)
        if count > 10:
            issues.append(f"缩进{level}有{count}项，远超建议的3-7个，可能存在分类不充分或细粒度不一致")
            score = max(1, score - 2)
        elif count == 1:
            issues.append(f"缩进{level}只有1项，无法形成有效的MECE分组")
            score = max(1, score - 1)

    # 检查首段是否用了"三个方面"、"两点原因"等结构性语言
    all_text = " ".join([p["text"] for p in paragraphs])
    structural_markers = re.findall(r"[两三四五六七八九十][个点方面类层维项]", all_text)
    if structural_markers:
        issues.append(f"使用了结构标记词：{structural_markers}")
        score = min(10, score + 1)

    # 检查常见MECE违规模式
    overlap_markers = [
        (r"以及.*和", "可能混用'以及'和'和'导致分类维度不清"),
        (r"包括.*等.*还", "'包括…等…还'结构暗示分类不完全"),
        (r"其他|其它", "'其他'出现表示分类可能不MECE——应尽量将'其他'拆解"),
    ]
    for pattern, hint in overlap_markers:
        if re.search(pattern, all_text):
            issues.append(hint)
            score = max(1, score - 1)

    return {
        "score": score,
        "detail": "；".join(issues) if issues else "未发现明显MECE问题",
        "passed": score >= 5,
        "group_sizes": {str(k): len(v) for k, v in grouped.items()}
    }


def check_logic_flow(paragraphs: list[dict]) -> dict:
    """检查逻辑递进"""
    all_text = " ".join([p["text"] for p in paragraphs])
    score = 5
    issues = []

    # 时间顺序标记
    time_markers = ["首先", "其次", "再次", "最后", "第一步", "第二步", "第一阶段", "第二阶段",
                    "过去", "现在", "未来", "短期", "中期", "长期"]
    found_time = [m for m in time_markers if m in all_text]

    # 结构顺序标记
    struct_markers = ["从…到…", "内部", "外部", "宏观", "微观", "产品", "市场", "运营",
                      "硬件", "软件", "服务"]
    # 程度顺序标记
    degree_markers = ["最重要", "次重要", "最关键", "更", "最", "核心", "辅助"]

    found_logical = []
    if found_time:
        found_logical.append(f"时间顺序：{found_time}")
        score += 1
    if any(m in all_text for m in struct_markers):
        found_logical.append("结构顺序")
        score += 1
    if any(m in all_text for m in degree_markers):
        found_logical.append("程度顺序")
        score += 1

    if found_logical:
        issues.append(f"使用了逻辑递进：{'、'.join(found_logical)}")
    else:
        issues.append("未检测到明确的逻辑顺序标记（时间/结构/程度），论点可能随意排列")
        score = max(1, score - 1)

    return {
        "score": score,
        "detail": "；".join(issues),
        "passed": score >= 5
    }


def check_scqa(text: str) -> dict:
    """检查是否使用了SCQA框架"""
    s_markers = re.findall(r"(背景|Situation|现状|当前情况)", text)

    scqa_paragraphs = re.split(r"\n\s*\n", text)
    detected = {}
    for p in scqa_paragraphs[:6]:
        lower = p.lower()
        if any(m in lower for m in ["背景：", "situation", "现状：", "当前情况"]):
            detected["S"] = True
        if any(m in lower for m in ["冲突：", "问题：", "变化", "但是", "然而", "complication"]):
            detected["C"] = True
        if any(m in lower for m in ["问题：", "question", "我们面临"]):
            detected["Q"] = True
        if any(m in lower for m in ["答案：", "answer", "因此", "建议"]) and "Q" in detected:
            detected["A"] = True

    detected_count = len(detected)
    result = {
        "score": detected_count * 2.5,
        "elements_found": list(detected.keys()),
        "passed": detected_count >= 3
    }

    if detected_count == 4:
        result["detail"] = "✅ 完整使用了SCQA框架（Situation, Complication, Question, Answer）"
    elif detected_count >= 2:
        result["detail"] = f"⚠️ 部分使用了SCQA框架（缺失：{set('SCQA') - set(detected.keys())}）"
    else:
        result["detail"] = "未检测到SCQA框架结构"

    return result


def generate_report(text: str) -> dict:
    """生成完整的诊断报告"""
    paragraphs = extract_paragraphs(text)

    checks = {
        "conclusion_first": has_obvious_conclusion(paragraphs),
        "hierarchy": detect_hierarchy(paragraphs),
        "mece": check_mece(paragraphs),
        "logic_flow": check_logic_flow(paragraphs),
        "scqa": check_scqa(text),
    }

    total_score = sum(c["score"] for c in checks.values())
    max_score = 10 * len(checks)
    percentage = round(total_score / max_score * 100)

    # Generate priorities
    failed = [k for k, v in checks.items() if not v["passed"]]
    suggestions = []
    if "conclusion_first" in failed:
        suggestions.append("【高优先】添加结论先行——在第一句亮出核心观点")
    if "mece" in failed:
        suggestions.append("【高优先】检查MECE——确保同一层论点相互独立且完全穷尽")
    if "hierarchy" in failed:
        suggestions.append("【中优先】建立层级结构——使用缩进/编号表示论点层级")
    if "logic_flow" in failed:
        suggestions.append("【中优先】增加逻辑递进——按时间/结构/程度顺序组织论点")
    if "scqa" in failed and checks["scqa"]["score"] < 5:
        suggestions.append("【低优先】可考虑引入SCQA框架增强开场白结构")

    return {
        "overall_score": percentage,
        "summary": f"金字塔结构评分：{percentage}/100",
        "conclusion": f"表现优异！" if percentage >= 80 else f"需要改进（建议优先解决以下问题）" if percentage < 60 else "基本合格",
        "details": checks,
        "priorities": suggestions
    }


def print_report(report: dict, format: str = "text"):
    """打印报告"""
    if format == "json":
        print(json.dumps(report, ensure_ascii=False, indent=2))
        return

    print("=" * 60)
    print(f"  📊 {report['summary']}  —  {report['conclusion']}")
    print("=" * 60)

    checks = report["details"]
    for key, check in checks.items():
        labels = {
            "conclusion_first": "结论先行",
            "hierarchy": "层级结构",
            "mece": "MECE分类",
            "logic_flow": "逻辑递进",
            "scqa": "SCQA框架"
        }
        score_bar = "█" * max(0, int(check["score"])) + "░" * max(0, 10 - int(check["score"]))
        status = "✅" if check["passed"] else "❌"
        print(f"\n  {labels.get(key, key)} [{score_bar}] {status}")
        print(f"    {check['detail']}")

    if report["priorities"]:
        print("\n" + "-" * 60)
        print("  改进建议（按优先级排序）：")
        for s in report["priorities"]:
            print(f"    • {s}")

    print("=" * 60)


def main():
    if len(sys.argv) > 1:
        text = read_text(sys.argv[1])
    elif not sys.stdin.isatty():
        text = sys.stdin.read()
    else:
        print("用法：python analyze.py <文件路径>  或  cat 输入.txt | python analyze.py")
        sys.exit(1)

    report = generate_report(text)
    fmt = "json" if "--json" in sys.argv else "text"
    print_report(report, fmt)


if __name__ == "__main__":
    main()
