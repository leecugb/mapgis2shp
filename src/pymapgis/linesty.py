# -*- coding: utf-8 -*-
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
    @43/@47（辅助色/覆盖方式候选，官方 DLL 字段序）待扫
  - 点在线侧的侧别规则未定
  - 大载荷子线（n≥15，含点列三联组）语义未定
  - 记录内子线渲染选择规则（线型 2 的 4 条 24B 子线段角色）未破

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

    def record_bounds(self, no: int) -> Tuple[int, int]:
        """no = 1-based 线型号。返回记录字节区间。"""
        i = no - 1
        off = self.entries[i][0]
        k = next(k for k, (ri, _) in enumerate(self._nonempty) if ri == i)
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
        # 子线指针表 = n_subs × 6B（索引 flag=子线数，8/8 验证）
        for s in range(n_subs):
            ptr, ln = struct.unpack_from("<IH", self.data, off + s * 6)
            if ptr <= 0 or ln <= 0 or ptr + ln > end:
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
        sub.f32_start = 2 + n * 6
        for j in range(sub.f32_start, ln - 3, 4):
            v = _F32.unpack_from(self.data, ptr + j)[0]
            if abs(v) <= 1e8:
                sub.f32_zone.append(v)
            else:
                sub.f32_zone.append(float("nan"))
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
