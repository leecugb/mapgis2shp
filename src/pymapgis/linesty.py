# -*- coding: utf-8 -*-
# SPDX-License-Identifier: Apache-2.0
"""MapGIS 6.x 线型库（LINESTY.lib）解析器（2026-10-14 逆向定案版 v3）。

格式规格（索引链式结构 8/8 验证；元素模板长度律全库命中）：

  文件 = [u32 记录数][u16 保留=0][N × 6B 索引项（u32 记录偏移 + u16 子线数）] + 记录区
  记录 = [N × (u32 子线偏移, u16 子线长)] + N 条子线（子线链式相接）
  记录号 = .WL linetype 字段 − 1（1-based；linetype 1 = 32132 处使用锚定）

  子线 = [u16 n][n × 6B 元素模板（u16 单元, u16 点数, u16 偏移）] + [f32 载荷区]
  长度律：24 + (n−1)×22 字节（n=1~26 主导长度全命中；±8B 倍数变体在案）

元素模板（三元组语义 2026-10-14 补齐，线型 211 自洽锚定）：
  unit   语义
    0    空移（线型 4 裁定回溯）；坐标列族中=不填充多段线（211 基线）
    1    填充多边形（线型 211 矩形节裁定：5 点闭合轮廓+填充）
    2    随动/间隔（16/17 与点共存，不定形态）
    3    画点（线型 4 裁定回溯）
    ≥5   子图号（258/259=圆点单元，形状实证；32/35 短线段嫌疑待裁定）
  marker = 该元素消费的载荷点数（211：5+2=7 恰合全部载荷点 ✓）
  offset = 元素在周期内的位置，0.1mm 单位（211：元素 1 @10 → 周期 1.0mm；
           16/17 的 3/6/9 = 0.3mm 点距同律佐证）

f32 载荷区三型：
  - 坐标列型：含 unit=1 且 Σmarker×2 == 载荷数 → 载荷 = (x,y) 点列
    按 marker 分配（211：矩形 5 点 + 基线 2 点；unit=1 为必要条件）
  - 沿线节奏型：全元素 unit=0 且 Σmarker×2 == 载荷数 且 每元素内
    x 严格递增 → 载荷 = 沿线点列，每元素一段 (x0,x1,y)，段间跳变 = 空段
    （线型 2 锚定：实 0.35/空 0.30/实 0.35 周期 1.0mm；线型 4 节奏表
    x 非单调 → 拒绝，防参数表撞车）
  - 参数型：其余 → 元素参数（节奏表/点位置等）

  n=1 且 24B = 实线型：色@2（Colorlib 1-based，0=默认/随图元，全库笔色
                       普查 0×31 主用）、宽@16 f32（mm）、纵向偏移@20 f32

形态自持判定规则（用户裁定 16/17 回溯双中）：
  展开元素模板 → 全点状单元且线分量宽 <0.1mm → 纯点线；
  含 ≥0.1mm 实线分量 + 点状单元 → 线+点复合；
  含 unit=1 坐标列元素 → 坐标列花样（填充多边形族）；
  实线笔 + 沿线节奏子线 → 虚线族（沿线节奏+笔）。

已裁定线型（用户目视裁定 2026-10-13/14；颜色以 .WL @26 数据锚为准）：
  1/2/4/16/17/211 的形态与 (线型, aux) 双键语义（含地质语义与图幅统计）
  的裁定表本体在仓内 `pymapgis.linesty_adjudicated`（**不进发布件**），
  经 `_adjudicated_tables()` 惰性加载；发布环境缺表时 `pair_semantics()`
  返回 None、`classify_form()` 仅给格式级形态判定。

挂账（如实）：
  - 颜色归属半闭环：.WL @26=线颜色已定位并入 reader.py（2026-10-14，
    211 号 202 图元恒值 194 锚定；全 18 层值域 [1,546] 无越界）；
    **@43=辅助色/@47=图层/@48=透明输出已消挂**（2026-10-15 官方明码
    9 参数 1538 样本逐字段等值定位 + 多幅 7675 记录值域复核，并入
    reader.py 图形参数列）
  - 点在线侧的侧别规则未定
  - 大载荷子线（n≥15，含点列三联组）语义未定
  - 记录内子线渲染选择规则——线型 3 已定案（2026-10-19：aux 选择
    主记录子线索引，见 feature_rhythm）；线型 2 的 4 条 24B 子线段
    角色仍挂账

官方语义锚（MapGIS 文档审计 2026-10-14，smaryun 官方帮助+map2shp）：
  - **线型号标准格式 = "线型号-辅助线型号"（均为 ≥0 整数）**——
    本库 decode(linetype) + compose_feature_style(lt, aux) 即此双参数
  - X 系数 = 符号沿线方向伸缩（改间隔/符号长度）；Y 系数 = 垂线方向
    伸缩（线宽方向；M67 虚线 Y 系数越大线越宽）；M10 注：线宽不受
    比例系数影响
  - 透明输出：值为"是"时，符号中 **9 号色（白色）** 填充部分透明
    （与本库 Colorlib 9=白 解码互证 ✓）
  - 线颜色/线宽（可变颜色/可变线宽）在图元层（.WL 记录）
  - 线型生成方法：规律性（等大单元周期平铺）/ 按控制点（相邻点间填一单元）；
    线型调整方法："调整"=端部符号完整化——图元级渲染开关（.WL 字段待定位）

M67 线型保存语义（Mpedit60.hlp"保存线型"节，2026-10-14 提取——
点线解析的决定性规格）：
  - 线型=符号编辑框内几何：基线（首尾相接线段）+上下复制一个单位+普染
  - **主色/辅助色**：存库时指定主色，其余为辅助色；使用时图元参数
    可重指定（=可变颜色）
  - **可变线宽/固定线宽（点线点径的来源）**：存库时指定线宽号→转成
    线的可变线宽，其它为固定线宽；**使用时图元线宽参数替换可变线宽**。
    → 点线族（16 等）的**点径 = 图元线宽**（库内数值只是可变标记），
    点距 = 库内固定间距 × X系数；线宽类尺寸不受 Y 系数影响。
    （(16,0) w=0.15 x=0.8 y=0.3 → 点径 0.15mm、点距 0.24mm，
    用户核验定案 2026-10-14）
"""
from __future__ import annotations

import struct
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import numpy as np

_U16 = struct.Struct("<H")
_U32 = struct.Struct("<I")
_F32 = struct.Struct("<f")

# 元素模板 unit 语义（裁定回溯）
UNIT_GAP = 0         # 空移（线型 4）
UNIT_FILLED_POLY = 1  # 填充多边形（线型 211）
UNIT_FOLLOW = 2      # 随动/间隔（16/17）
UNIT_DOT = 3         # 画点（线型 4）
UNIT_SYMBOL_MIN = 5  # ≥此值为子图号（258/259 实证）

# 元素 offset 单位（0.1mm）
OFFSET_UNIT_MM = 0.1

# 亚视觉线宽阈值（16/17 回溯：0.078mm 线分量判隐匿）
SUBLINE_VISIBLE_MIN_MM = 0.1

# 用户裁定表（ADJUDICATED / PAIR_SEMANTICS）已迁至仓内
# pymapgis.linesty_adjudicated（含地质语义与图幅统计，不进发布件——
# 2026-10-14 包定位裁定：地质语义解析不属于 mapgis2shp）。经
# _adjudicated_tables() 惰性加载；发布环境缺表时 pair_semantics() 恒
# None、classify_form() 仅给格式级判定，功能完整降级。


def _adjudicated_tables():
    """载入裁定表 (ADJUDICATED, PAIR_SEMANTICS)；缺席时返回两张空表。"""
    try:
        from pymapgis.linesty_adjudicated import ADJUDICATED, PAIR_SEMANTICS
    except ImportError:
        return {}, {}
    return ADJUDICATED, PAIR_SEMANTICS


def pair_semantics(linetype: int, aux: int = 0) -> Optional[str]:
    """(线型, aux) 双键语义；无实证（或裁定表不在环境中）返回 None。"""
    _, pairs = _adjudicated_tables()
    return pairs.get((str(linetype), str(aux)))


def compose_feature_style(lib: "LinestyLib", linetype: int, aux: int = 0):
    """图元显示样式 = 线型号记录 + 辅助线型号记录叠加（aux=0 不叠加）。

    官方语义（2026-10-14 三重证实：用户裁定 (2,0)=纯虚线 + MapGIS67
    编辑器 DLL 字段名『线型号/辅助线型号/辅助色/覆盖方式』+ MapGIS 官方
    文档『线型由线型号+辅助线型号唯一确定』）。
    返回 (主样式 LineStyle|None, 辅助样式 LineStyle|None)。
    X/Y 系数语义（官方）：X=沿线方向伸缩（改间隔与符号长度），
    Y=垂线方向伸缩（改线宽方向）。
    """
    main = lib.decode(linetype)
    aux_style = lib.decode(aux) if aux else None
    return main, aux_style


def _consume_groups(sl: "SubLine") -> List[Tuple[int, list]]:
    """通用元素消费器：按元素 (unit, marker) 逐组消费 f32 载荷。

    默认消费律 = marker×2 个 f32（每点 2 值）。**变体线型**（58 的
    三元组档、127/153 的三点括号）消费律与默认不同——调用方按
    实测覆盖，逐元素对账是纪律（127|0 漏画尾段教训）。
    返回 [(unit, 值列表), ...]；越界诚实截断。
    """
    f = sl.f32_zone
    groups: List[Tuple[int, list]] = []
    fi = 0
    for e in sl.elements:
        n = 2 * e.marker
        if fi + n > len(f):
            break
        groups.append((e.unit, f[fi:fi + n]))
        fi += n
    return groups


def _pairs_to_lines_verticals(
    pairs: List[Tuple[float, float]],
) -> Tuple[list, list]:
    """连续坐标对 → (lines, verticals)：端点 y 相等判水平线
    (x0,x1,y)，否则判竖线 (x, ymin, ymax)。共享于 48/58/153。"""
    lines, verticals = [], []
    for k in range(len(pairs) // 2):
        x0, y0 = pairs[2 * k]
        x1, y1 = pairs[2 * k + 1]
        if abs(y0 - y1) < 1e-9:
            lines.append((x0, x1, y0))
        else:
            verticals.append((x0, min(y0, y1), max(y0, y1)))
    return lines, verticals


def _period_from_lines(lines: List[Tuple[float, ...]]) -> float:
    """周期规则（38|1/48|1 教训定案）：基本单元等间距族 = 相邻线
    起点差的最小正值；单线族 = 最大线终点。记录末 x ≠ 周期。
    兼容 (x0,x1) 与 (x0,x1,y) 两种线元组；**多 y 层级时取最大线
    终点**（48 抬升线教训：不同层的线起点不得参与等间距计算）。"""
    if len(lines) > 0 and len(lines[0]) > 2:
        levels = {round(t[2], 6) for t in lines}
        if len(levels) > 1:
            return max(t[1] for t in lines)
    starts = sorted({t[0] for t in lines})
    if len(starts) >= 2:
        return min(b - a for a, b in zip(starts, starts[1:]) if b > a)
    return max(t[1] for t in lines)


def _tick_line_rhythm(
    f: list, period: float, n_ticks: int, repeats: int
) -> Tuple[list, list]:
    """竖短线-水平线相间节奏解码（3|5 与 4|3 用户裁定同构，2026-10-19）。

    档区 = n_ticks 档 × repeats 遍三元组 (x, y0, y1)：x=档值（非渲染
    位置）、y0=纵向起点（−h）、y1=顶端（略高于基线）；尾段 6 对 =
    三水平线（连续两对 = 起终点，y 为噪声忽略）。渲染规则（用户裁定，
    2026-10-19）：**档文件序 = 间隙序**（档1=第1条竖线→第1间隙；
    4|3 实证，3|5 纠正——档 x 值不作位置用）；**tick 组与两侧线
    等间距**——组中心平移至间隙中心、组内间距保持；第 3 间隙跨周期。
    返回 (lines, dots)；dots 元素 (x, h, top)。
    """
    ticks = []
    for k in range(n_ticks):
        base = 3 * repeats * k
        ticks.append((f[base], abs(f[base + 1]), f[base + 2]))
    o = 3 * repeats * n_ticks
    lines = sorted([(f[o], f[o + 2]), (f[o + 4], f[o + 6]),
                    (f[o + 8], f[o + 10])])
    per_gap = n_ticks // 3
    dots = []
    for k in range(3):
        g0 = lines[k][1]
        g1 = lines[(k + 1) % 3][0] + (period if k == 2 else 0.0)
        gc = (g0 + g1) / 2
        grp = ticks[k * per_gap:(k + 1) * per_gap]   # 档文件序 = 间隙序
        if k == 2:
            grp = [(x + period, h, top) for (x, h, top) in grp]
        grp = sorted(grp)                            # 组内按位置排序
        center = sum(t[0] for t in grp) / len(grp)
        shift = gc - center
        for (x, h, top) in grp:
            dots.append((x + shift, h, top))
    return lines, dots


def feature_rhythm(style: Optional[LineStyle], aux: int = 0) -> Optional[dict]:
    """线型 3/4 节奏裁定读法（2026-10-19 用户逐行目视定案，3|x 六行 +
    4|x 四行全裁定）。

    定案规则（"aux 选择主记录子线索引"——旧挂账"记录内子线渲染选择
    规则"的定案实例）：
      - (lt, aux) 渲染**主记录 sub[aux]**；aux 记录的笔不渲染
        （3|1 的红色 24B 实线笔已裁定弃画）。
      - 节奏 f32 = (x, y) 坐标对序列；点/竖线与线相间、与两侧线等距。
      - 线型 3：sub0–4 同构 dash_dot（线 0→f[2]、点@f[4] r=f[6]、
        两侧空白对称、周期 = 线 + 2×空 + 2×r；sub4 记录内第二组为
        下周期冗余复写）；sub5 = tick_dash_interleave（3 档 ×4 遍 +
        尾段三线，_tick_line_rhythm）。
      - 线型 4：sub0–2 = dash_double_dot（短线 + 双点；4|1 双点与
        两侧线等距裁定）；sub3 = tick_dash_interleave（6 档 ×5 遍 +
        尾段三线，_tick_line_rhythm）。

    返回 {"kind", "lines": [(x0,x1)...], "dots": [...], "period_mm"}；
    dots 元素：dash 族 (x, r)，tick 族 (x, h, top)。
    非线型 3/4 或越界返回 None（未裁定线型不做臆断）。

    新线型落码三查纪律（2026-10-19 教训制度化，58|0 一次通过实证）：
      ① elements 结构先行——按 unit/marker 定消费与角色（unit=0/5
        线对、unit=3 点三元组、unit=1 坐标列多边形）；
      ② (x,y) 对的 y 是真实坐标、对与对之间可能是线起终点——不得
        先入为主套已裁定线型的模板（51/48/18 教训）；
      ③ 周期 = 基本单元间距（相邻线起点差；单线族 = 最大线终点），
        记录末 x 不是周期（38|1/48|1 教训）。
      渲染对账纪律：**全部元素都必须消费**，尾段元素同样是图形
      （127|0 漏画尾段下线教训）。每行至少一条逐值锚定测试。
    """
    if style is None or style.no not in (3, 4, 5, 7, 16, 18, 38, 48, 50, 51, 58, 153):
        return None
    if not (0 <= aux < len(style.sublines)):
        return None
    sl = style.sublines[aux]
    f = sl.f32_zone
    if style.no == 3:
        if aux <= 4:
            # 单线+点（sub0–4 同构，参数各异）
            if len(f) < 8:
                return None
            solid, dot_pos, dot_r = f[2], f[4], f[6]
            gap = dot_pos - dot_r - solid      # 线末端→点边缘（两侧对称）
            period = solid + 2 * gap + 2 * dot_r
            return {"kind": "dash_dot",
                    "lines": [(0.0, solid)],
                    "dots": [(dot_pos, dot_r)],
                    "period_mm": period}
        if len(f) < 48:
            return None
        lines, dots = _tick_line_rhythm(f, 1.0, 3, 4)
        return {"kind": "tick_dash_interleave",
                "lines": lines, "dots": dots, "period_mm": 1.0}
    if style.no == 4:
        if aux == 0:
            if len(f) < 20:
                return None
            # 裁定渲染：线 0→f[2]，点1 (f[4], f[6])，点2 (f[16], f[12])；
            # f[10]（0.551）在接受版渲染中未消费，如实注释
            return {"kind": "dash_double_dot",
                    "lines": [(0.0, f[2])],
                    "dots": [(f[4], f[6]), (f[16], f[12])],
                    "period_mm": 1.0}
        if aux == 1:
            if len(f) < 14:
                return None
            # 双点与两侧线等距（用户裁定）：0.65−0.5 = 1.0−0.85 = 0.15
            return {"kind": "dash_double_dot",
                    "lines": [(0.0, f[2])],
                    "dots": [(f[4], f[6]), (f[10], f[12])],
                    "period_mm": 1.0}
        if aux == 2:
            if len(f) < 18:
                return None
            # 前四对 = 两线（(0,0)→(f[2],0)、(f[4],0)→(f[6],0)）、
            # 5/6 对 = 点1、8/9 对 = 点2（用户 2026-10-19 逐对裁定）
            return {"kind": "dash_double_dot",
                    "lines": [(0.0, f[2]), (f[4], f[6])],
                    "dots": [(f[8], f[10]), (f[14], f[16])],
                    "period_mm": 1.0}
        # aux == 3：6 档 ×5 遍 + 尾段三线
        if len(f) < 102:
            return None
        lines, dots = _tick_line_rhythm(f, 1.0, 6, 5)
        return {"kind": "tick_dash_interleave",
                "lines": lines, "dots": dots, "period_mm": 1.0}
    # 线型 5（2026-10-19 用户目视定案）：5|0 = 两水平线 + 一竖线，
    # 档三元组 ×3（x, |y0|=高, y1=顶）+ 尾段 4 对 = 两线（连续对成线）
    if style.no == 5:
        if aux != 0 or len(f) < 17:
            return None
        tick = (f[0], abs(f[1]), f[2])
        o = 9
        lines = sorted([(f[o], f[o + 2]), (f[o + 4], f[o + 6])])
        return {"kind": "tick_dash_interleave",
                "lines": lines,
                "dots": [tick],
                "period_mm": 1.0}
    # 线型 7（2026-10-19 用户目视定案）：aux 选主记录子线索引，sub0-2
    # 全裁定（7|0 只渲染 sub0——sub1 的子图 1280 引用不影响节奏）；
    # 基线 (f[0],0)→(f[2],0) + 上下对称竖线对（(x,+y),(x,-y) 成对
    # 编码，半高 = |y|，顶端 = 半高；sub2 两组对 @f[4]/f[8]）
    if style.no == 7:
        if aux not in (0, 1, 2) or len(f) < 8:
            return None
        if aux == 2:
            if len(f) < 12:
                return None
            dots = [(f[4], abs(f[5]), abs(f[5])),
                    (f[8], abs(f[9]), abs(f[9]))]
        else:
            dots = [(f[4], abs(f[5]), abs(f[5]))]
        return {"kind": "tick_dash_interleave",
                "lines": [(f[0], f[2])],
                "dots": dots,
                "period_mm": f[2]}
    # 线型 38（2026-10-19 用户目视定案，推覆体齿线族）：aux 选主记录
    # 子线索引；sub0/sub1 裁定。unit=1 元素 = 坐标列填充多边形（齿），
    # unit∈{0,5} 元素 = 线起终点对；**基本单元等间距**——周期 = 相邻
    # 线起点差的最小正值（38|1 实证：线起点 0/0.5 → 周期 0.5，此前误
    # 把记录末 x=0.875 当周期的教训）；单线记录（38|0）周期 = 线终点。
    if style.no == 38:
        if aux not in (0, 1):
            return None
        lines, teeth = [], []
        for unit, vals in _consume_groups(sl):
            if unit == 1 and len(vals) >= 6:
                teeth.append(list(zip(vals[0::2], vals[1::2])))
            elif unit in (0, 5) and len(vals) >= 4:
                lines.append((vals[0], vals[2]))
        if not lines:
            return None
        return {"kind": "tooth_dash",
                "lines": lines,
                "teeth": teeth,
                "period_mm": _period_from_lines(lines)}
    # 线型 16（16|0/16|1 走 dotline_params/PAIR_SEMANTICS；16|2 于
    # 2026-10-19 用户目视定案）：16|2 = 两段基线 + 两个抬升圆点
    # （(x,y,r) 三元组各 ×2 冗余：@(0.2541,0.1504)/@(0.7541,0.1504)
    # r=0.02）+ 尾段两线（连续对成线），周期 1.0
    if style.no == 16:
        if aux != 2 or len(f) < 20:
            return None
        dots = [(f[0], f[1], f[2]), (f[6], f[7], f[8])]
        lines = [(f[12], f[14]), (f[16], f[18])]
        return {"kind": "dash_dot_raised",
                "lines": lines,
                "dots": dots,
                "period_mm": 1.0}
    # 线型 18（2026-10-19 用户目视定案）：18|0 = 基线 0→1.0 + 周期
    # 起点竖线（(0, 0.125)→(0, 0) 为一竖线——(x,y) 对是线端点不是
    # 点；竖线从基线向上：dots 编码 (x, 0, top)）
    if style.no == 18:
        if aux != 0 or len(f) < 8:
            return None
        return {"kind": "tick_dash_interleave",
                "lines": [(f[4], f[6])],
                "dots": [(f[0], 0.0, f[1])],
                "period_mm": f[6]}
    # 线型 58（2026-10-19 用户目视定案）：58|0 = 基线 + 三竖线（向上
    # 0.1875）+ 三圆点（基线下方 y=-0.0625）。按 marker×2 逐元素消费：
    # unit=0 对 = 线起终点（水平 → lines(x0,x1,y)；竖线 → verticals
    # (x,0,top)）；unit=3 三元组 = 圆点 (x, y, r)
    if style.no == 58:
        if aux != 0:
            return None
        lines, verticals, dots = [], [], []
        for unit, vals in _consume_groups(sl):
            if unit == 0 and len(vals) >= 4:
                hl, vt = _pairs_to_lines_verticals(
                    [(vals[0], vals[1]), (vals[2], vals[3])])
                lines.extend(hl)
                verticals.extend(vt)
            elif unit == 3 and len(vals) >= 6:
                dots.append((vals[0], vals[1], vals[2]))
        if not lines:
            return None
        return {"kind": "mixed_dash",
                "lines": lines,
                "verticals": verticals,
                "dots": dots,
                "period_mm": _period_from_lines(lines)}
    # 线型 153（2026-10-19 用户目视定案）：153|0 = 两条均匀平行线
    # （y=0 与 y=0.0994，各 0→1.0；重复坐标为冗余不叠画——用户裁定
    # "中段不重笔加粗"）+ 两个下垂方括号（竖下-横-竖上，底 y=-0.067）
    if style.no == 153:
        if aux != 0 or len(f) < 64:
            return None
        # 两条平行线带（各 20 值：y=0 与 y=0.0994，0→1.0；重复坐标冗余）
        lines = [(0.0, 1.0, f[1]), (0.0, 1.0, f[21])]
        # 尾 24 值 = 两个下垂方括号（3 点各、含重复；去重后 4 点/括号）
        pts = []
        for k in range(12):
            p = (f[40 + 2 * k], f[41 + 2 * k])
            if p not in pts:
                pts.append(p)
        verticals = [(pts[2 * k][0], min(pts[2 * k][1], pts[2 * k + 1][1]),
                      max(pts[2 * k][1], pts[2 * k + 1][1]))
                     for k in range(4)]
        lines.append((pts[1][0], pts[2][0], pts[1][1]))
        lines.append((pts[5][0], pts[6][0], pts[5][1]))
        return {"kind": "mixed_dash",
                "lines": lines,
                "verticals": verticals,
                "dots": [],
                "period_mm": 1.0}
    # 线型 48（2026-10-19 用户目视定案）：48|0/48|1 全裁定。连续
    # (x,y) 对 = 线起终点（每对 k：线 = (f[4k], f[4k+2])，y = f[4k+1]）
    # ——(x,y) 点对是线端点不是圆点；lines 为 (x0, x1, y) 三元组
    if style.no == 48:
        if aux not in (0, 1) or len(f) < 12:
            return None
        lines, _ = _pairs_to_lines_verticals(
            list(zip(f[0::2], f[1::2])))
        return {"kind": "raised_lines",
                "lines": lines,
                "dots": [],
                "period_mm": _period_from_lines(lines)}
    # 线型 50（2026-10-19 用户目视定案）：50|0 = 线 0→1.0 + 两个抬升
    # 圆点（(x, y, r) 三元组 ×2：@(0.5,0.0684)/@(0.6992,0.0684) r=0.0312）
    if style.no == 50:
        if aux != 0 or len(f) < 16:
            return None
        return {"kind": "dash_dot_raised",
                "lines": [(f[0], f[2])],
                "dots": [(f[4], f[5], f[6]), (f[10], f[11], f[12])],
                "period_mm": f[2]}
    # 线型 51（2026-10-19 用户目视定案）：51|0 = 线 0→1.0 + 抬升圆点
    # @(f[4], f[5]) r=f[6]——点 y 是真实坐标（0.084 在基线上方），
    # 不是噪声（首版误画 y=0 被用户纠正）
    if style.no == 51:
        if aux != 0 or len(f) < 10:
            return None
        return {"kind": "dash_dot_raised",
                "lines": [(f[0], f[2])],
                "dots": [(f[4], f[5], f[6])],
                "period_mm": f[2]}


def dotline_params(style: Optional[LineStyle], feature_width: float,
                   x_coef: float = 1.0) -> Optional[dict]:
    """点线族绘制参数（(16,0) 核验锚 2026-10-14）。

    点径 = 可变线宽 = 图元线宽 feature_width（M67 保存线型节：库内
    尺寸为可变标记，绘制时被图元线宽替换；线宽类尺寸不受系数影响）；
    点距 = 库内固定间距（元素 offset 差 × 0.1mm）× X系数。
    返回 {"radius_mm", "spacing_mm", "period_mm"}；非点线族返回 None。
    """
    if style is None:
        return None
    dots = []
    for sub in style.sublines:
        for e in sub.elements:
            if e.is_symbol or e.is_dot:
                dots.append(e.offset)
    if not dots:
        return None
    offs = sorted(set(dots))
    # 众数间距（点行间距稳健取法：17 号混入的 35 号元素 offset 2
    # 会制造 0.2 假间距，众数 3→0.3mm 才是点行间距）
    if len(offs) > 1:
        gaps = [b - a for a, b in zip(offs, offs[1:])]
        step = max(set(gaps), key=gaps.count)
    else:
        step = 3
    spacing_lib = step * OFFSET_UNIT_MM
    spacing = spacing_lib * x_coef
    period = spacing * 4
    return {"radius_mm": feature_width / 2.0,
            "spacing_mm": spacing, "period_mm": period}


def linedot_params(style: Optional[LineStyle], feature_width: float,
                   x_coef: float = 1.0, y_coef: float = 1.0) -> Optional[dict]:
    """线+点串族绘制参数（(17,0) 核验锚 2026-10-14，B/2 定稿）。

    线宽 = 点径 = 可变线宽 = 图元线宽 feature_width（不受系数影响）；
    点距 = 库内间距（元素 offset 差×0.1mm）× X系数；
    点侧偏移 = (线宽/2) × Y系数（x=1,y=2.5,w=0.15 → 0.1875mm 核验）。
    返回 {"line_width_mm", "radius_mm", "spacing_mm", "side_offset_mm"}。
    """
    if style is None:
        return None
    dots = []
    for sub in style.sublines:
        for e in sub.elements:
            if e.is_symbol or e.is_dot:
                dots.append(e.offset)
    if not dots:
        return None
    offs = sorted(set(dots))
    # 众数间距（同 dotline_params 规则）
    if len(offs) > 1:
        gaps = [b - a for a, b in zip(offs, offs[1:])]
        step = max(set(gaps), key=gaps.count)
    else:
        step = 3
    return {"line_width_mm": feature_width,
            "radius_mm": feature_width / 2.0,
            "spacing_mm": step * OFFSET_UNIT_MM * x_coef,
            "side_offset_mm": (feature_width / 2.0) * y_coef}


@dataclass
class Element:
    """子线元素模板项（6B）：单元/点数/偏移。"""
    unit: int
    marker: int          # 消费的载荷点数（坐标列型）
    offset: int          # 周期内位置（0.1mm 单位）

    @property
    def pos_mm(self) -> float:
        return self.offset * OFFSET_UNIT_MM

    @property
    def is_filled_poly(self) -> bool:
        return self.unit == UNIT_FILLED_POLY

    @property
    def is_dot(self) -> bool:
        return self.unit == UNIT_DOT

    @property
    def is_gap(self) -> bool:
        return self.unit == UNIT_GAP

    @property
    def is_symbol(self) -> bool:
        return self.unit >= UNIT_SYMBOL_MIN


@dataclass
class SubLine:
    """一条子线：n 个元素模板 + f32 载荷区。"""
    n: int
    length: int
    elements: List[Element] = field(default_factory=list)
    f32_zone: List[float] = field(default_factory=list)  # 载荷区 f32 序列
    f32_start: int = 0                                    # 载荷区在子线内的偏移
    # 实线型（n=1 且 24B）字段
    color: Optional[int] = None
    width: Optional[float] = None
    yoff: Optional[float] = None

    @property
    def is_solid(self) -> bool:
        return self.n == 1 and self.length == 24

    @property
    def is_coord_list(self) -> bool:
        """坐标列型：含 unit=1（填充多边形）元素 且 Σmarker×2 == 载荷 f32 数
        （211 锚定；unit=1 为坐标列族的裁定标志——节奏表型载荷长度
        巧合相等时不得误判，故以 unit=1 为必要条件）。"""
        if self.is_solid or not self.f32_zone:
            return False
        return (any(e.is_filled_poly for e in self.elements)
                and sum(e.marker for e in self.elements) * 2 == len(self.f32_zone))

    @property
    def unit_kinds(self) -> Dict[str, int]:
        """元素单元分类计数：gap/filled/dot/symbol/aux/other。
        实线子线（n=1 且 24B）的模板项是 (色, 2, 0)，不参与分类。"""
        kinds: Dict[str, int] = {"gap": 0, "filled": 0, "dot": 0,
                                 "symbol": 0, "aux": 0, "other": 0}
        if self.is_solid:
            return kinds
        for e in self.elements:
            if e.is_gap:
                kinds["gap"] += 1
            elif e.is_filled_poly:
                kinds["filled"] += 1
            elif e.is_dot:
                kinds["dot"] += 1
            elif e.unit == UNIT_FOLLOW:
                kinds["aux"] += 1
            elif e.is_symbol:
                kinds["symbol"] += 1
            else:
                kinds["other"] += 1
        return kinds

    @property
    def period_mm(self) -> Optional[float]:
        """周期长：max(offset) × 0.1mm（211：元素1@10 → 1.0mm 锚定）。
        沿线节奏型的真实周期以点列末 x 为准（见 inline_pattern）。"""
        if not self.elements:
            return None
        return max(e.offset for e in self.elements) * OFFSET_UNIT_MM

    @property
    def inline_pattern(self) -> Optional[List[Tuple[float, float, float]]]:
        """沿线节奏型读法（线型 2 锚定）：全元素 unit=0 且
        Σmarker×2 == 载荷数 且 每元素内 x 严格递增 →
        载荷 = 沿线点列，返回每元素一段 (x0, x1, y)；段间 x 跳变 = 空段。
        非此型返回 None（线型 4 节奏表 x 非单调 → 拒绝，防撞车）。"""
        if self.is_solid or not self.f32_zone:
            return None
        if any(e.unit != UNIT_GAP for e in self.elements):
            return None
        if sum(e.marker for e in self.elements) * 2 != len(self.f32_zone):
            return None
        pts = [(self.f32_zone[2 * j], self.f32_zone[2 * j + 1])
               for j in range(len(self.f32_zone) // 2)]
        segs = []
        i = 0
        for e in self.elements:
            sub = pts[i:i + e.marker]
            if len(sub) < 2:
                return None
            xs = [p[0] for p in sub]
            if any(xs[j] >= xs[j + 1] for j in range(len(xs) - 1)):
                return None  # 元素内非单调 → 参数表，不是沿线节奏
            segs.append((sub[0][0], sub[-1][0], sub[0][1]))
            i += e.marker
        return segs

    def cell(self) -> List[Dict]:
        """坐标列型单元拆解：按元素 marker 分配 (x,y) 点。
        返回 [{"unit":.., "pos_mm":.., "filled":bool,
               "points":[(x,y),...]}]；非坐标列型返回 []。"""
        if not self.is_coord_list:
            return []
        pts = [(self.f32_zone[2 * j], self.f32_zone[2 * j + 1])
               for j in range(len(self.f32_zone) // 2)]
        out = []
        i = 0
        for e in self.elements:
            sub = pts[i:i + e.marker]
            out.append({"unit": e.unit, "pos_mm": e.pos_mm,
                        "filled": e.is_filled_poly, "points": sub})
            i += e.marker
        return out


@dataclass
class LineStyle:
    """一条线型 = 若干子线。no 为 1-based 线型号（= .WL linetype）。"""
    no: int
    n_subs: int
    sublines: List[SubLine] = field(default_factory=list)
    truncated: bool = False   # 子线指针表存在非法项而被截断（F2 审计）

    @property
    def adjudicated(self) -> Optional[str]:
        adj, _ = _adjudicated_tables()
        return adj.get(self.no)

    @property
    def pens(self) -> List[SubLine]:
        """实线笔子线（24B 实线型）。"""
        return [s for s in self.sublines if s.is_solid]

    def rhythm(self) -> Optional[dict]:
        """虚线/节奏线组合读法（线型 2 锚定）：≥1 实线笔 + ≥1 沿线节奏子线。
        返回 {"pens": [(色,宽)], "segments": [(x0,x1,y)], "gaps": [(x0,x1)],
              "period_mm": float}；非此结构返回 None。"""
        if not self.pens:
            return None
        segs: List[Tuple[float, float, float]] = []
        for s in self.sublines:
            if s.inline_pattern:
                segs.extend(s.inline_pattern)
        if not segs:
            return None
        gaps = [(segs[k][1], segs[k + 1][0])
                for k in range(len(segs) - 1)]
        period = max(p[1] for p in segs) - min(p[0] for p in segs)
        return {"pens": [(s.color, s.width) for s in self.pens],
                "segments": segs, "gaps": gaps, "period_mm": period}


class LinestyLib:
    """LINESTY.lib 解析器。"""

    def __init__(self, path: str):
        self.data = Path(path).read_bytes()
        self.count = _U32.unpack_from(self.data, 0)[0]
        # 索引项：(u32 记录偏移, u16 子线数)；偏移 0 = 空槽
        self.entries: List[Tuple[int, int]] = [
            struct.unpack_from("<IH", self.data, 6 + i * 6)
            for i in range(self.count)
        ]
        self._nonempty = [(i, off) for i, (off, fl) in enumerate(self.entries)
                          if off > 0]
        # 记录号 → _nonempty 位置映射（2026-10-15 优化：record_bounds 每次
        # decode 都 O(N) 线性扫 _nonempty，渲染管线逐图元 decode 时退化为
        # O(N²)；映射后 O(1)）
        self._pos: Dict[int, int] = {ri: k for k, (ri, _) in enumerate(self._nonempty)}

    def record_bounds(self, no: int) -> Tuple[int, int]:
        """no = 1-based 线型号。返回记录字节区间。"""
        i = no - 1
        off = self.entries[i][0]
        k = self._pos.get(i)
        if k is None:
            raise IndexError(f"line style {no} is an empty slot")
        end = (self._nonempty[k + 1][1] if k + 1 < len(self._nonempty)
               else len(self.data))
        return off, end

    def decode(self, no: int) -> Optional[LineStyle]:
        """解码线型号 no（1-based）；空槽返回 None。"""
        i = no - 1
        if not (0 <= i < self.count):
            return None
        off, n_subs = self.entries[i]
        if off == 0:
            return None
        _, end = self.record_bounds(no)
        style = LineStyle(no=no, n_subs=n_subs)
        # 子线指针表 = n_subs × 6B（索引 flag=子线数，8/8 验证）；
        # 非法指针置 truncated（2026-10-19 F2 审计：旧版静默 break，
        # 调用方无法区分"真空"与"损坏"——真库 859 条无触发，防御加固）
        for s in range(n_subs):
            ptr, ln = struct.unpack_from("<IH", self.data, off + s * 6)
            if ptr <= 0 or ln <= 0 or ptr + ln > end:
                style.truncated = True
                break
            style.sublines.append(self._decode_subline(ptr, ln))
        return style

    def _decode_subline(self, ptr: int, ln: int) -> SubLine:
        n = _U16.unpack_from(self.data, ptr)[0]
        sub = SubLine(n=n, length=ln)
        # 元素模板：n × 6B 自 byte 2 起
        for e in range(n):
            base = ptr + 2 + e * 6
            if base + 6 > ptr + ln:
                break
            u, m, o = struct.unpack_from("<3H", self.data, base)
            sub.elements.append(Element(unit=u, marker=m, offset=o))
        # f32 载荷区（起点 = 2 + 6n；长度律允许 ±8B 变体，故按区扫）
        # 2026-10-15 优化：np.frombuffer 向量化（原逐 f32 struct 解包循环，
        # 大载荷子线 n≥15 时逐点开销显著）；|v|>1e8 → NaN 语义不变——
        # 先转 float64 再比较，严格复刻原 Python 浮点比较（f32 直接比
        # 1e8 会在边界因 f32(1e8) 舍入产生语义差）。
        sub.f32_start = 2 + n * 6
        n_f32 = (ln - sub.f32_start) // 4
        if n_f32 > 0:
            arr = np.frombuffer(self.data, dtype="<f4", count=n_f32,
                                offset=ptr + sub.f32_start).astype(np.float64)
            sub.f32_zone = np.where(np.abs(arr) <= 1e8, arr, np.nan).tolist()
        # 实线型字段（n=1 且 24B）
        if sub.is_solid:
            sub.color = _U16.unpack_from(self.data, ptr + 2)[0]
            sub.width = _F32.unpack_from(self.data, ptr + 16)[0]
            sub.yoff = _F32.unpack_from(self.data, ptr + 20)[0]
        return sub

    def __len__(self) -> int:
        return self.count


def classify_form(style: LineStyle) -> Tuple[str, str]:
    """形态判定：返回 (形态标签, 证据串)。

    确定性规则（裁定回溯支撑处不越界）：
      全部子线为 24B 实线型 → 实线（单/多）
      含 unit=1 坐标列元素 → 坐标列花样（填充多边形族，211 锚定）
      实线笔 + 沿线节奏子线 → 虚线族（沿线节奏+笔，线型 2 锚定）
      含点状单元（dot/子图引用）→ 报告构成；是否"纯点线"取决于
        线分量可见性——24B 实线分量宽 ≥0.1mm 判可见（16/17 回溯锚）；
        花样子线的段宽字段位次未定案，不据此断言形态（准确性优先）。
    """
    dots = syms = aux = gaps = filled = 0
    strokes = 0
    stroke_w = 0.0
    coord = inline = False
    for sub in style.sublines:
        kinds = sub.unit_kinds
        dots += kinds["dot"]
        syms += kinds["symbol"]
        aux += kinds["aux"]
        gaps += kinds["gap"]
        filled += kinds["filled"]
        coord = coord or sub.is_coord_list
        inline = inline or sub.inline_pattern is not None
        if sub.is_solid and (sub.width or 0) >= SUBLINE_VISIBLE_MIN_MM:
            strokes += 1
            stroke_w = max(stroke_w, sub.width or 0)
    ev = (f"{len(style.sublines)} 子线[点{dots} 子图{syms} 填充多边形{filled} "
          f"随动{aux} 空{gaps}], 实线分量 {strokes}（w≤{stroke_w:.3g}mm）")
    if style.adjudicated:
        return (style.adjudicated, ev + "；已裁定")
    if filled or coord:
        return ("坐标列花样（填充多边形族）", ev)
    if inline and strokes > 0:
        return ("虚线族（沿线节奏+笔）", ev)
    if dots == 0 and syms == 0 and strokes > 0:
        return ("实线", ev)
    if (dots or syms) and strokes == 0:
        return ("点线族（无可见 24B 实线分量）", ev)
    if (dots or syms) and strokes > 0:
        return ("线+点复合", ev)
    return ("复合花样（形态待裁定）", ev)


def census(lib: LinestyLib) -> dict:
    """全库解析普查：长度律符合率、形态分布、失败清单。"""
    ok = law_ok = coord_n = inline_n = rhythm_n = 0
    forms: Dict[str, int] = {}
    bad: List[int] = []
    for k, (i, off) in enumerate(lib._nonempty):
        no = i + 1
        st = lib.decode(no)
        if st is None or not st.sublines:
            bad.append(no)
            continue
        ok += 1
        for sub in st.sublines:
            if sub.length == 24 + (sub.n - 1) * 22:
                law_ok += 1
            if sub.is_coord_list:
                coord_n += 1
            if sub.inline_pattern:
                inline_n += 1
        if st.rhythm():
            rhythm_n += 1
        form, _ = classify_form(st)
        forms[form] = forms.get(form, 0) + 1
    return {"total": len(lib._nonempty), "decoded": ok,
            "subline_law_ok": law_ok, "coord_list_sublines": coord_n,
            "inline_pattern_sublines": inline_n, "rhythm_styles": rhythm_n,
            "forms": forms, "bad": bad}


# ---------------------------------------------------------------------------
# 裁定渲染操作码（2026-10-15）：按用户裁定的形状生成结构化渲染指令，
# 目标是"与用户裁定形状相似"。已裁定线型走锚定规格；未裁定线型
# 尽力从库内结构推导，不足则如实标注"待裁定"——不冒充。
# ---------------------------------------------------------------------------

# 已裁定线型的结构规格（用户 2026-10-15/16 裁定形状固化）
ADJUDICATED_STRUCTS = {
    "1|0": "单实线（通用载体）",
    "1|1": "单实线（用户 10-16 裁定，断裂层）",
    "1|2": "单实线（一般断层；用户 10-16 裁定）",
    "1|5": "单实线（等价 1|0；用户 10-16 裁定）",
    "1|7": "单实线（等价 1|0；用户 10-16 裁定）",
    "1|16": "单实线（等价 1|0；用户 10-16 裁定）",
    "2|0": "纯虚线（实0.35/空0.30/实0.35，周期1.0mm）",
    "2|1": "虚线（实>空，环状，火山洼地构造；用户 10-16 裁定）",
    "2|4": "纯虚线（等价 2|0；用户 10-16 裁定）",
    "2|18": "纯虚线（等价 2|0；用户 10-16 裁定）",
    "10|0": "平行双实线（区域性复合断层；用户 10-16 裁定）",
    "12|0": "平行双虚线（主要复合断层；用户 10-16 裁定）",
    "15|0": "平行双实线·一粗一细（岩石圈断层；用户 10-16 裁定）",
    "44|0": "推覆体齿线（推覆体界线；同38|2 规格族；用户 10-16 裁定）",
    "174|0": "断线+双点相间（类(4,0)；遥感解译断层；用户 10-16 裁定）",
    "204|0": "推覆体齿线（推覆体界线；同38|2 规格族；用户 10-16 裁定）",
    "595|0": "推覆体齿线（推覆体界线；同38|2 规格族；用户 10-16 裁定）",
    "16|0": "纯圆点串（点径=图元线宽，点距0.3×x，无基线）",
    "16|1": "纯圆点串（同16|0）",
    "17|0": "直线+正圆点串在线侧，点线保持间距（侧偏移=(线宽/2)×y）",
    "3|0": "短线与点相间（划-点交替，周期1.2mm）",
    "4|0": "短线+双点相互间隔（线占比长，周期8mm：线4.5/点组2.5）",
    "4|1": "同 (4,0)",
    "48|0": "平行断线+实线双线（平行不整合界线）",
    "18|0": "实线+单侧短刺（超动界线，参照复活断层样式）",
    "38|2": "实线+右侧等腰三角齿底边贴实线（参照推覆体界线样式）",
    "110|0": "实线+右侧等边三角齿底边贴实线（同38|2 等边变体）",
    "148|0": "平行双实线·一粗一细（岩石圈断层；用户 10-16 裁定修订原'平行双实线'）",
    "50|0": "实线+平行双点线（双点基本单元，单元间距>点间距）",
    "211|0": "青绿矩形节骑线+矩形填充+单元间空白（周期1.0mm）",
}


def render_ops(style: Optional[LineStyle], linetype: int = 0, aux: int = 0,
               feature_width: float = 0.15, x_coef: float = 1.0,
               y_coef: float = 1.0) -> dict:
    """生成结构化渲染操作码列表，与用户裁定形状相似。

    返回 {"ops": [...], "verdict_match": 是否命中裁定规格, "spec": 说明}。
    ops 元素为 (操作, 参数) 元组，操作 ∈
      solid / dashed / dotline / dash_dot / solid_side_ticks /
      solid_teeth / parallel_solid / parallel_solid_dashed /
      solid_parallel_pairdots / rect_chain / cell_pattern
    """
    key = f"{linetype}|{aux}"
    spec = ADJUDICATED_STRUCTS.get(key)
    if spec is None and aux == 0:
        spec = ADJUDICATED_STRUCTS.get(str(linetype))
    r = feature_width / 2.0  # 可变线宽 → 点径/半宽
    W = feature_width

    def T(op, **kw):
        return (op, kw)

    ops: List[tuple] = []
    # —— 已裁定线型：锚定规格（注意 dict 身份比较，勿用 == 字符串）——
    if key == "1|0" or (linetype == 1 and aux == 0 and style is None):
        ops = [T("solid", width_mm=W)]
        spec = ADJUDICATED_STRUCTS.get("1|0", "单实线")
    elif key == "2|0":
        ops = [T("dashed", on_mm=0.35 * x_coef, off_mm=0.30 * x_coef)]
    elif key == "1|1" or (linetype == 1 and aux == 1):
        ops = [T("solid", width_mm=W)]
    elif key == "1|2" or (linetype == 1 and aux == 2):
        ops = [T("solid", width_mm=W)]
    elif key in ("1|5", "1|7", "1|16") or (linetype == 1 and aux in (5, 7, 16)):
        # 用户 10-16 裁定：aux=5/7/16 等价 (1,0) 单实线
        ops = [T("solid", width_mm=W)]
    elif key == "2|1" or (linetype == 2 and aux == 1):
        # 用户 10-16 裁定：实>空 虚线（环状用法=火山洼地构造）；
        # 同 (2,0) 节奏规格，aux=1 不改形状（比照 (4,0)/(4,1) 先例）
        ops = [T("dashed", on_mm=0.35 * x_coef, off_mm=0.30 * x_coef)]
    elif key in ("2|4", "2|18") or (linetype == 2 and aux in (4, 18)):
        # 用户 10-16 裁定：等价 (2,0) 纯虚线
        ops = [T("dashed", on_mm=0.35 * x_coef, off_mm=0.30 * x_coef)]
    elif key == "10|0" or (linetype == 10 and aux == 0):
        # 用户 10-16 裁定：平行双实线（区域性复合断层）
        ops = [T("parallel_solid", gap_mm=0.18, width_mm=W)]
    elif key == "12|0" or (linetype == 12 and aux == 0):
        # 用户 10-16 裁定：平行双虚线（主要复合断层）
        ops = [T("dashed", on_mm=0.35 * x_coef, off_mm=0.30 * x_coef, y_mm=0.09),
               T("dashed", on_mm=0.35 * x_coef, off_mm=0.30 * x_coef, y_mm=-0.09)]
    elif key == "174|0" or (linetype == 174 and aux == 0):
        # 用户 10-16 裁定：断线+双点相间，类 (4,0) 形态（用户参照
        # boundary_linetypes_all.png 的 (4,0) 面板比对定案）
        ops = [T("dash_dotdot", dash_mm=4.5, dot_gap_mm=1.4, period_mm=8.0)]
    elif key in ("204|0", "595|0", "44|0") or (linetype in (204, 595, 44) and aux == 0):
        # 用户 10-16 裁定：推覆体齿线（推覆体界线）——与已裁 38|2
        # 同规格族：实线+右侧等腰三角齿底边贴实线
        ops = [T("solid", width_mm=W),
               T("solid_teeth", spacing_mm=0.55 * x_coef,
                 tooth_mm=0.16 * y_coef, side="right", shape="isosceles")]
    elif key in ("15|0", "148|0") or (linetype in (15, 148) and aux == 0):
        # 用户 10-16 裁定：平行双实线一粗一细（岩石圈断层；148|0 修订）。
        # 粗细比 2:1 为用户规格未给数值的暂定（细=W/2），待目视核。
        ops = [T("solid", width_mm=W, y_mm=0.09),
               T("solid", width_mm=W / 2.0, y_mm=-0.09)]
    elif key in ("16|0", "16|1") or (linetype == 16 and aux in (0, 1)):
        ops = [T("dotline", radius_mm=r, spacing_mm=0.3 * x_coef, baseline=False)]
    elif key == "17|0" or (linetype == 17 and aux == 0):
        ops = [T("solid", width_mm=W),
               T("dotline", radius_mm=r, spacing_mm=0.3 * x_coef,
                 side_offset_mm=(W / 2.0) * y_coef)]
    elif key == "3|0" or (linetype == 3 and aux == 0):
        ops = [T("dash_dot", dash_mm=0.9 * x_coef, gap_mm=0.9 * x_coef)]
    elif key in ("4|0", "4|1") or (linetype == 4 and aux in (0, 1)):
        ops = [T("dash_dotdot", dash_mm=4.5, dot_gap_mm=1.4, period_mm=8.0)]
    elif key == "48|0" or (linetype == 48 and aux == 0):
        ops = [T("solid", width_mm=W, y_mm=0.11),
               T("dashed", on_mm=0.55 * x_coef, off_mm=0.35 * x_coef, y_mm=-0.11)]
    elif key == "18|0" or (linetype == 18 and aux == 0):
        ops = [T("solid", width_mm=W),
               T("solid_side_ticks", spacing_mm=0.55 * x_coef,
                 tick_mm=0.16 * y_coef, side="left")]
    elif key == "38|2" or (linetype == 38 and aux == 2):
        ops = [T("solid", width_mm=W),
               T("solid_teeth", spacing_mm=0.55 * x_coef,
                 tooth_mm=0.16 * y_coef, side="right", shape="isosceles")]
    elif key == "110|0" or (linetype == 110 and aux == 0):
        ops = [T("solid", width_mm=W),
               T("solid_teeth", spacing_mm=0.55 * x_coef,
                 tooth_mm=0.16 * y_coef, side="right", shape="equilateral")]
    elif key == "50|0" or (linetype == 50 and aux == 0):
        ops = [T("solid", width_mm=W, y_mm=0.10),
               T("dotline", radius_mm=r, y_mm=-0.10, pair=True,
                 pair_gap_mm=0.30 * x_coef, unit_gap_mm=1.0 * x_coef)]
    elif key == "211|0" or (linetype == 211 and aux == 0):
        ops = [T("rect_chain", color_no=194, period_mm=1.0 * x_coef)]
    elif style is not None:
        # —— 未裁定线型：按结构优先级推导（优先级=结构特异性，借鉴裁定图分类）——
        # ① 节奏型（linesty 节奏+笔结构，最特异）→ 虚线
        rhy = style.rhythm()
        # ② 坐标列型（unit=1 填充多边形 → 矩形节骑线/齿链等）
        cells = []
        for sub in style.sublines:
            c = sub.cell()
            if c:
                cells.extend(c)
        # ③ 复合结构判别（修正 10-15）：
        #    unit=2 仅在同一子线内与 unit=3 点配对出现时才为"真短线"，
        #    否则为随动/占位标记（点线族的 16/17 因此误判）；
        #    sym 分点类(258/259)与齿/刺类(其它)——18/38 的嵌入子图属齿/刺。
        has_dot = any(e.is_dot for s in style.sublines for e in s.elements)
        has_seg = any(
            e.unit == 2 and any(e2.is_dot for e2 in s.elements)
            for s in style.sublines for e in s.elements)
        has_sym_dot = any(e.is_symbol and e.unit in (258, 259)
                          for s in style.sublines for e in s.elements)
        # unit=5=竖短线嵌入子图（子图5=3点折线 0~0.71mm，10-15 裁定补）
        has_sym_tick = any(e.is_symbol and e.unit == 5
                           for s in style.sublines for e in s.elements)

        if rhy and not cells:
            ons = [(b - a) for a, b, _y in rhy["segments"]]
            offs = [rhy["segments"][k + 1][0] - rhy["segments"][k][1]
                    for k in range(len(rhy["segments"]) - 1)]
            on = min(ons) * x_coef if ons else 0.5
            off = min(offs) * x_coef if offs else 0.3
            ops = [T("dashed", on_mm=on, off_mm=off)]
            spec = spec or "虚线（节奏推导）"
        elif cells:
            ops = [T("cell_pattern", cells=cells)]
            spec = spec or "坐标列花样（推导）"
        elif has_dot and has_seg:
            # 短线+点复合（3|0 短线与点相间 / 4|0 短线+双点）
            offs = sorted({e.offset for s in style.sublines for e in s.elements})
            gaps = [b - a for a, b in zip(offs, offs[1:])] if len(offs) > 1 else [3]
            step = max(set(gaps), key=gaps.count) if gaps else 3
            spacing = step * OFFSET_UNIT_MM * x_coef
            nseg = sum(1 for s in style.sublines for e in s.elements if e.unit == 2)
            ops = [T("dash_dot", dash_mm=spacing * 0.5, gap_mm=spacing,
                     pair=(nseg >= 2))]
            spec = spec or "短线与点相间（推导）"
        elif has_sym_tick:
            # 实线+竖短线（7|0 型：基线+unit5 竖短刺串）
            offs = sorted({e.offset for s in style.sublines for e in s.elements
                           if e.is_symbol and e.unit == 5})
            gaps = [b - a for a, b in zip(offs, offs[1:])] if len(offs) > 1 else [6]
            step = max(set(gaps), key=gaps.count) if gaps else 6
            ops = [T("solid", width_mm=W),
                   T("solid_side_ticks", spacing_mm=step * OFFSET_UNIT_MM * x_coef,
                     tick_mm=0.4, side="cross")]
            spec = spec or "实线+竖短线（unit=5 子图推导）"
        elif has_dot and has_sym_dot:
            # 线+点串复合（17|0 型：基线+点串线侧）
            offs = sorted({e.offset for s in style.sublines for e in s.elements
                           if e.is_symbol})
            gaps = [b - a for a, b in zip(offs, offs[1:])] if len(offs) > 1 else [3]
            step = max(set(gaps), key=gaps.count) if gaps else 3
            ops = [T("solid", width_mm=W),
                   T("dotline", radius_mm=r,
                     spacing_mm=step * OFFSET_UNIT_MM * x_coef,
                     side_offset_mm=(W / 2.0) * y_coef)]
            spec = spec or "线+点串复合（推导）"
        elif has_dot:
            dp = dotline_params(style, feature_width, x_coef)
            if dp:
                ops = [T("dotline", **dp, baseline=False)]
                spec = spec or "点线（推导）"
            else:
                offs = sorted({e.offset for s in style.sublines for e in s.elements})
                gaps = [b - a for a, b in zip(offs, offs[1:])] if len(offs) > 1 else [3]
                step = max(set(gaps), key=gaps.count) if gaps else 3
                ops = [T("dotline", radius_mm=r,
                         spacing_mm=step * OFFSET_UNIT_MM * x_coef, baseline=False)]
                spec = spec or "点线（推导）"
        else:
            pens = [s for s in style.sublines if s.is_solid]
            if pens:
                ops = [T("solid", width_mm=pens[0].width or W)]
                spec = spec or "实线（笔推导）"
            else:
                ops = [T("solid", width_mm=W)]
                spec = spec or "实线（缺省——结构待裁定）"
    else:
        ops = [T("solid", width_mm=W)]
        spec = spec or "实线（缺省）"

    verdict_match = (f"{linetype}|{aux}" in ADJUDICATED_STRUCTS
                     or (aux == 0 and str(linetype) in ADJUDICATED_STRUCTS))
    return {"ops": ops, "verdict_match": verdict_match, "spec": spec}


if __name__ == "__main__":
    import sys
    lib = LinestyLib(sys.argv[1] if len(sys.argv) > 1 else r"D:\SLIB\LINESTY.lib")
    print(f"LINESTY.lib：{lib.count} 槽位，非空 {len(lib._nonempty)}")
    for no in (1, 2, 4, 16, 17, 211):
        st = lib.decode(no)
        if st is None:
            continue
        form, ev = classify_form(st)
        comps = [f"n={s.n}/{'实线' if s.is_solid else '模板'}"
                 for s in st.sublines]
        print(f"  线型{no}: {len(st.sublines)} 子线 {comps} → {form}（{ev}）")
        rhy = st.rhythm()
        if rhy:
            print(f"    节奏: 笔={[(c, round(w, 3)) for c, w in rhy['pens']]} "
                  f"实段={[(round(a, 3), round(b, 3)) for a, b, _ in rhy['segments']]} "
                  f"空段={[(round(a, 3), round(b, 3)) for a, b in rhy['gaps']]} "
                  f"周期={round(rhy['period_mm'], 3)}mm")
    stats = census(lib)
    print(f"普查：{stats['decoded']}/{stats['total']} 解码成功，"
          f"长度律符合子线 {stats['subline_law_ok']}，"
          f"坐标列子线 {stats['coord_list_sublines']}，"
          f"沿线节奏子线 {stats['inline_pattern_sublines']}，"
          f"节奏线型 {stats['rhythm_styles']}，"
          f"形态分布 {stats['forms']}，失败 {stats['bad'][:10]}")
