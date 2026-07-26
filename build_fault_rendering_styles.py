#!/usr/bin/env python3
"""根据 geological_fault_rendering_scheme.md 与 DZ/T 0179 PDF 表22（其他地质要素用色），
生成结构化的断裂构造渲染样式配置文件 fault_rendering_styles.json，
并输出可读摘要 fault_rendering_styles_summary.md。

说明：
- 符号几何样式参考 `dz_t_0179_fault_symbols.md` 从 PDF 中解析的图例；
- 类型代码（GZEEB / GZEEBM / GZEGD）到符号的对应关系仍为暂定推断，待图例确认；
- 所有长度/距离单位均为米（m），角度单位为度（°）。
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict

ROOT = Path(__file__).parent
OUT_JSON = ROOT / "fault_rendering_styles.json"
OUT_MD = ROOT / "fault_rendering_styles_summary.md"


def build_config() -> Dict[str, Any]:
    return {
        "_meta": {
            "version": "dz_t_0179_table22",
            "note": "符号几何参考 DZ/T 0179 表22；类型代码到符号的映射仍为暂定推断，"
                    "待图例确认后仅替换各 source 的 type_map 即可。",
            "source_scheme": "geological_fault_rendering_scheme.md",
            "source_pdf": "dz_t_0179_fault_symbols.md",
        },
        "global": {
            "short_segment_threshold_m": 5000.0,
            "named_fault_merge": True,
            "dip_angle_min": 0.1,
            "dip_angle_max_display": 90.0,
            "abnormal_dip_highlight": 90.0,
        },
        "sources": {
            "LDZOFBA003": {
                "file": "LDZOFBA003.WL",
                "data_type": "实测断层",
                "type_field": "GZEEB",
                "dip_field": "GZECE",
                "tendency_field": "GZECD",
                "name_field": "GZEAB",
                "description_field": "GZEHG",
                "reliability_field": "GZAG",
                "base_style": {
                    "color": "#e41a1c",
                    "linewidth": 0.7,
                    "linestyle": "-",
                    "alpha": 1.0,
                },
                "symbol_defaults": {
                    "sample_spacing_m": 5000.0,
                    "short_segment_sample": "midpoint",
                    "tick_len_m": 350.0,
                    "tooth_len_m": 420.0,
                    "dip_label_offset_m": 300.0,
                    "font_size": 3.2,
                    "font_color": "#000000",
                },
                "type_map": {
                    "01": {
                        "symbol_type": "solid_unknown",
                        "default_side": None,
                        "label_dip": False,
                        "linestyle": "-",
                        "note": "实测性质不明断层（DZ/T 0179 表22）",
                    },
                    "05": {
                        "symbol_type": "normal",
                        "default_side": "right",
                        "label_dip": True,
                        "linestyle": "-",
                        "note": "实测正断层（暂定）；GZELD=101 与之完全绑定",
                    },
                    "31": {
                        "symbol_type": "reverse",
                        "default_side": "right",
                        "label_dip": True,
                        "linestyle": "-",
                        "note": "实测逆断层/冲断层/推覆断层（暂定）；三角齿",
                    },
                    "04": {
                        "symbol_type": "concealed",
                        "default_side": None,
                        "label_dip": False,
                        "linestyle": "--",
                        "note": "推测性质不明断层 / 隐伏断层（DZ/T 0179 表22）",
                    },
                    "41": {
                        "symbol_type": "shear_zone_double_line",
                        "default_side": None,
                        "label_dip": False,
                        "linestyle": "-",
                        "note": "韧性剪切带/断层破碎带（红色双线，DZ/T 0179 表22）",
                    },
                    "28": {
                        "symbol_type": "shear_zone_double_line",
                        "default_side": None,
                        "label_dip": False,
                        "linestyle": "-",
                        "note": "断层破碎带/脆韧性剪切带",
                    },
                    "07": {
                        "symbol_type": "solid_unknown",
                        "default_side": None,
                        "label_dip": False,
                        "linestyle": "-",
                        "note": "实测性质不明断层（DZ/T 0179 表22）",
                    },
                    "18": {
                        "symbol_type": "active",
                        "default_side": "right",
                        "label_dip": False,
                        "linestyle": "-",
                        "note": "实测活动断层（暂定）；双箭头",
                    },
                    "16": {
                        "symbol_type": "active",
                        "default_side": "right",
                        "label_dip": False,
                        "linestyle": "-",
                        "note": "实测活动断层（暂定）；双箭头",
                    },
                },
            },
            "LYGREBA001": {
                "file": "LYGREBA001.WL",
                "data_type": "遥感/地质解译断层",
                "type_field": ["GZEEBM", "GZEGD"],
                "dip_field": "GZEEI",
                "tendency_field": None,
                "name_field": "GZEAB",
                "description_field": "GZEAD",
                "reliability_field": "GZEDRA",
                "base_style": {
                    "color": "#e41a1c",
                    "linewidth": 0.6,
                    "linestyle": "-.",
                    "alpha": 0.9,
                },
                "symbol_defaults": {
                    "sample_spacing_m": 12000.0,
                    "short_segment_sample": "midpoint",
                    "tick_len_m": 300.0,
                    "tooth_len_m": 360.0,
                    "dip_label_offset_m": 260.0,
                    "font_size": 3.0,
                    "font_color": "#000000",
                },
                "type_map": {
                    "01,04": {
                        "symbol_type": "reverse",
                        "default_side": "right",
                        "label_dip": True,
                        "linestyle": "-.",
                        "note": "航卫片解译断层 / 逆冲（DZ/T 0179 表22 点划线）",
                    },
                    "02,03": {
                        "symbol_type": "normal",
                        "default_side": "right",
                        "label_dip": True,
                        "linestyle": "-.",
                        "note": "航卫片解译断层 / 正断层（暂定）",
                    },
                    "05,05": {
                        "symbol_type": "concealed",
                        "default_side": None,
                        "label_dip": False,
                        "linestyle": "--",
                        "note": "隐伏或物探推测断层（DZ/T 0179 表22 长虚线+点）",
                    },
                },
            },
            "LZLPGDJ002": {
                "file": "LZLPGDJ002.WL",
                "data_type": "深部/物探推断大断裂",
                "type_field": None,
                "dip_field": "GZEEL",
                "tendency_field": None,
                "name_field": "GZEAB",
                "description_field": "GZECC",
                "reliability_field": None,
                "base_style": {
                    "color": "#e41a1c",
                    "linewidth": 1.5,
                    "linestyle": "--",
                    "alpha": 1.0,
                },
                "symbol_defaults": {
                    "sample_spacing_m": None,
                    "short_segment_sample": None,
                    "tick_len_m": 0.0,
                    "tooth_len_m": 0.0,
                    "dip_label_offset_m": 0.0,
                    "font_size": 4.0,
                    "font_color": "#e41a1c",
                },
                "type_map": {
                    "_all": {
                        "symbol_type": "none",
                        "default_side": None,
                        "label_dip": False,
                        "linestyle": "--",
                        "note": "深部大断裂，仅绘制粗虚线与名称注记",
                    }
                },
            },
        },
        "named_faults": {
            "LDZOFBA003": {
                "F48": {
                    "label": "F48",
                    "label_at": "middle",
                    "merge_segments": True,
                    "note": "含 05/28 两种代码，按段分别渲染符号",
                },
                "F50": {
                    "label": "F50",
                    "label_at": "middle",
                    "merge_segments": True,
                    "note": "含 04/41 两种代码，04 用虚线、41 用破碎带双线",
                },
                "F9": {
                    "label": "F9",
                    "label_at": "middle",
                    "merge_segments": True,
                    "note": "全部为 41，用破碎带双线",
                },
            },
            "LYGREBA001": {
                "乌赤别里山口断裂": {
                    "label": "乌赤别里山口断裂",
                    "label_at": "inflection_outer",
                    "merge_segments": True,
                    "note": "西段齿指向北，东段齿指向南；南侧局部倒转",
                },
                "布伦口断裂": {
                    "label": "布伦口断裂",
                    "label_at": "middle",
                    "merge_segments": True,
                    "note": "齿指向北东，倾角 60–70°",
                },
            },
        },
        "symbol_definitions": {
            "solid_unknown": {
                "description": "实测性质不明断层：仅实线，不画侧向符号",
                "geometry": "solid_line_only",
                "fill": False,
            },
            "normal": {
                "description": "正断层：下降盘短齿",
                "geometry": "barb_on_downdip_side",
                "fill": False,
            },
            "reverse": {
                "description": "逆断层/冲断层/推覆断层：上盘三角齿",
                "geometry": "triangle_teeth_on_hangingwall",
                "fill": True,
            },
            "thrust": {
                "description": "推覆断层：上盘三角齿（同 reverse）",
                "geometry": "triangle_teeth_on_hangingwall",
                "fill": True,
            },
            "strike_slip": {
                "description": "平推断层：半箭头",
                "geometry": "half_arrows",
                "fill": False,
            },
            "active": {
                "description": "活动断层：双箭头",
                "geometry": "double_arrows",
                "fill": False,
            },
            "concealed": {
                "description": "隐伏/推测断层：长虚线+点",
                "geometry": "dashed_line_with_dot",
                "fill": False,
            },
            "shear_zone_double_line": {
                "description": "韧性/脆韧性剪切带：红色平行双线",
                "geometry": "double_parallel_line",
                "fill": False,
            },
            "interpreted": {
                "description": "航卫片解译断层：点划线",
                "geometry": "dash_dot_line",
                "fill": False,
            },
            "neutral_tick": {
                "description": "短垂线，不指定盘侧",
                "geometry": "perpendicular_tick",
                "fill": False,
            },
            "arc_unknown": {
                "description": "弧形/性质不明断层：虚线+中点短垂线",
                "geometry": "dashed_line_with_midpoint_tick",
                "fill": False,
            },
            "none": {
                "description": "不绘制符号",
                "geometry": None,
                "fill": False,
            },
        },
    }


def build_markdown(config: Dict[str, Any]) -> str:
    lines = [
        "# 断裂构造渲染样式总表\n",
        "> 状态：**临时方案**。类型代码地质含义待图例最终确认；确认后仅需修改 ",
        "`fault_rendering_styles.json` 中的 `type_map`。\n",
        "## 1. 全局参数\n",
        "| 参数 | 值 | 说明 |",
        "|------|-----|------|",
    ]
    for k, v in config["global"].items():
        lines.append(f"| `{k}` | {v} | |")

    lines.extend(["\n## 2. 数据源与基础线型\n", "| 数据源 | 文件 | 类型字段 | 倾角字段 | 线色 | 线宽 | 线型 | 透明度 |"])
    lines.append("|--------|------|----------|----------|------|------|------|--------|")
    for src_name, src in config["sources"].items():
        type_field = ", ".join(src["type_field"]) if isinstance(src["type_field"], list) else (src["type_field"] or "-")
        dip_field = src["dip_field"] or "-"
        style = src["base_style"]
        lines.append(
            f"| `{src_name}` | `{src['file']}` | {type_field} | {dip_field} | "
            f"{style['color']} | {style['linewidth']} | {style['linestyle']} | {style['alpha']} |"
        )

    lines.extend(["\n## 3. 实测断层 `LDZOFBA003.WL` 类型代码映射\n",
                  "| 代码 | 符号类型 | 默认倾向侧 | 标注倾角 | 线型 | 说明 |",
                  "|------|----------|------------|----------|------|------|"])
    for code, m in config["sources"]["LDZOFBA003"]["type_map"].items():
        side = m["default_side"] if m["default_side"] else "无"
        lines.append(
            f"| `{code}` | `{m['symbol_type']}` | {side} | {'是' if m['label_dip'] else '否'} | "
            f"{m['linestyle']} | {m['note']} |"
        )

    lines.extend(["\n## 4. 解译断层 `LYGREBA001.WL` 类型代码映射\n",
                  "| GZEEBM/GZEGD | 符号类型 | 默认倾向侧 | 标注倾角 | 线型 | 说明 |",
                  "|--------------|----------|------------|----------|------|------|"])
    for code, m in config["sources"]["LYGREBA001"]["type_map"].items():
        side = m["default_side"] if m["default_side"] else "无"
        lines.append(
            f"| `{code}` | `{m['symbol_type']}` | {side} | {'是' if m['label_dip'] else '否'} | "
            f"{m['linestyle']} | {m['note']} |"
        )

    lines.extend(["\n## 5. 深部大断裂 `LZLPGDJ002.WL`\n",
                  "| 处理方式 | 线色 | 线宽 | 线型 | 符号 | 注记 |",
                  "|----------|------|------|------|------|------|"])
    style = config["sources"]["LZLPGDJ002"]["base_style"]
    lines.append(
        f"| 全部记录 | {style['color']} | {style['linewidth']} | {style['linestyle']} | 无 | 沿线标注名称 |"
    )

    lines.extend(["\n## 6. 命名断层特殊处理\n", "| 数据源 | 名称 | 合并线段 | 标注位置 | 备注 |"])
    lines.append("|--------|------|----------|----------|------|")
    for src_name, faults in config["named_faults"].items():
        for name, info in faults.items():
            lines.append(
                f"| `{src_name}` | {info['label']} | {'是' if info['merge_segments'] else '否'} | "
                f"{info['label_at']} | {info['note']} |"
            )

    lines.extend(["\n## 7. 符号几何定义\n", "| 符号类型 | 几何描述 | 填充 |"])
    lines.append("|----------|----------|------|")
    for sym, info in config["symbol_definitions"].items():
        lines.append(f"| `{sym}` | {info['description']} | {'是' if info['fill'] else '否'} |")

    lines.extend([
        "\n## 8. 使用方式\n",
        "1. 运行 `python3 build_fault_rendering_styles.py` 重新生成本表与 JSON 配置；\n",
        "2. 在 `render_strict_standard_map.py` 中加载 `fault_rendering_styles.json`；\n",
        "3. 按数据源遍历断层线，依据 `type_map` 选择符号类型与线型；\n",
        "4. 图例确认后，修改 `type_map` 中的 `symbol_type` / `default_side` / `note` 并重新渲染。\n",
    ])
    return "\n".join(lines)


def main() -> int:
    config = build_config()

    with open(OUT_JSON, "w", encoding="utf-8") as f:
        json.dump(config, f, ensure_ascii=False, indent=2)
    print(f"Saved: {OUT_JSON}")

    md = build_markdown(config)
    OUT_MD.write_text(md, encoding="utf-8")
    print(f"Saved: {OUT_MD}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
