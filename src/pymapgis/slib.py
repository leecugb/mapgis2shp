# -*- coding: utf-8 -*-
# SPDX-License-Identifier: Apache-2.0
"""MapGIS 6.x 符号库（Subgraph.lib）解析器（2026-10-14 逆向定案版 v2）。

格式规格（经用户目视核验定案，符号 7/27/30/43/56 实证；含未索引尾段）：

  文件 = [1840 × u32 偏移表（小端）] + [索引记录区 7360..1330364]
         + [未索引记录链 1330364..——#1840 起链式续号；本库走查定案
            #1840–#1995 共 156 条（155 条"后继记录样+载荷样"双门链证，
            #1961 为单门）；#1996@1373810 起结构变化（t=62/n=372 但头长
            ≤4100B 内无链，疑嵌套段或非记录区），其后 7.76MB 专项逆向
            挂账]；#1960=蚀变符号实证
  记录号 = 符号号（位置映射，0-based；高位号在未索引链中按序续号）
  记录 = [u16 type][u16 n][记录头（长 = 记录总长 − n×4）] + [n × f32 载荷]
  载荷 = mm 坐标点对（符号空间 ±0.5mm，**点距 8B**——f32×2，曾误写 4B
        致天文坐标，教训在案），按**头尾 u16 序列 = 子路径点数**
        分段连线（总和 = 点数；抬笔规则）
  类型语义：1=折线  2=线+填  3=多子路径复合  6=曲线（圆）
  圆表示：中心三点组 [圆心, 半径参考点, 圆心回点]（type=6 三点子路径，
        2026-10-15 定案；符号 7 锚 r=0.318≈裁定 0.315）或密集弧列
        （189 点/圈）；断线圆 = 弧段分组天然缝隙（无专用线型参数）

挂账（未定案，如实标注）：各符号的颜色（笔/填充）由**图元数据层**指定，
色号引用 Colorlib.lib（YMCK 4B/条色库）；库内头不含颜色参数。图元层定位：
.WL 线颜色@26 已定位（211 号全图元恒 194 锚定），辅助色@43/图层@47/
透明输出@48 亦已定位（2026-10-15 官方明码 9 参数补齐）；.WT 点图元
颜色@75/图层@83/笔宽@49/字体@49-53 已定位（2026-10-15 wat 明码补齐，
见 reader._read_point_params 文档串）。

官方语义锚（MapGIS 官方点参数文档审计 2026-10-14，smaryun）：
  - 子图按 **1×1 正方形格网**构建（与本库 ±0.5mm 符号空间互证 ✓）
  - 点图元参数：子图号、高度/宽度（mm）、角度（**逆时针旋转**——与
    reader.py 点记录 angle CCW-from-east 约定一致 ✓）、子图颜色/
    可变颜色、笔宽/可变笔宽、透明输出
  - **可变颜色/可变笔宽 = 图元层覆盖符号默认**——官方支持"颜色在图元层"
    的定案架构
  - 透明输出：含白色（Colorlib 9 号）填充区时，"是"→白色区透明显示
"""
from __future__ import annotations

import math
import struct
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional, Tuple

import numpy as np

_U16 = struct.Struct("<H")
_U32 = struct.Struct("<I")
_F32 = struct.Struct("<f")


@dataclass
class SubPath:
    points: List[Tuple[float, float]] = field(default_factory=list)
    closed: bool = False
    circle: Optional[Tuple[float, float, float]] = None  # (cx, cy, r) 圆拟合


@dataclass
class Symbol:
    no: int
    type: int
    n: int
    header_len: int
    header_u16: List[int]
    subpaths: List[SubPath] = field(default_factory=list)

    @property
    def n_points(self) -> int:
        return sum(len(sp.points) for sp in self.subpaths)


class SubgraphLib:
    """Subgraph.lib 解析器。

    索引表项数 = 首记录偏移 / 4（首个 u32 = 索引区末尾 = 记录区起点；
    原探测法会把记录区内小值误吞为索引，已废弃）。
    未索引尾段（符号号 ≥ 索引数）由链式走查定界——#1840 起地质专用
    符号在未索引链中按序续号（#1960=蚀变实证）；本库走查定案至
    #1995（155 条双门链证 + #1961 单门），#1996 起结构变化、其后
    7.76MB 挂账专项逆向。旧版"0xBE×3 预留区"扫描是载荷内 0xBE 假阳性
    （record_end=945916 误判），已移除。
    """

    # 尾段走查参数（探针 subgraph_tail_walk2.py 初版 + 2026-10-14 官方审计
    # 修订：类型上限放宽至 255——尾段实证 t=15/21/62，索引区亦有 11..66；
    # 链证升级为先双门（后继记录样 + 后继载荷样）后单门，诚实停止）
    _TAIL_T_MAX = 255    # 类型上限（0x00 为非法；索引区实证类型 ≤66，留裕量）
    _TAIL_HL_MAX = 512   # 头长扫描上限（#1839 实测 88B，#1982 实测 256B）

    def __init__(self, path: str):
        self.data = Path(path).read_bytes()
        # 2026-10-15 优化：np.frombuffer 向量化（原逐 u32 struct 解包）
        n_idx = self._u32(0) // 4
        self.offsets = np.frombuffer(self.data, dtype="<u4",
                                     count=n_idx).tolist()
        # 末条索引记录的真实终点 = 未索引尾段链起点：头长走查定界
        last = self._scan_record(self.offsets[-1]) if self.offsets else None
        self._indexed_end = last[3] if last else len(self.data)
        # 未索引记录链：每条 (start, end)；符号号 = len(offsets) + j
        self._tail: List[Tuple[int, int]] = self._walk_tail(self._indexed_end)

    def _u16(self, o: int) -> int:
        return _U16.unpack_from(self.data, o)[0]

    def _u32(self, o: int) -> int:
        return _U32.unpack_from(self.data, o)[0]

    def _f32(self, o: int) -> float:
        return _F32.unpack_from(self.data, o)[0]

    # -- 尾段链式走查 ------------------------------------------------------

    def _rec_like(self, t: int, n: int) -> bool:
        """记录首 (type, n) 合法性门：类型上限取 255 的依据是索引区类型
        实证 1..66（#0 的 19644 属已知的头部指针表异类）、尾段实证
        15/21/62——旧走查的 t≤10 会在 #1966（t=15）处提前断链。"""
        return 0 < t <= self._TAIL_T_MAX and 4 <= n <= 4000 and n % 2 == 0

    def _payload_sane(self, o: int, hl: int, n: int) -> Optional[int]:
        """@o 处按头长 hl 试读载荷：返回记录终点 end；载荷抽查不合格
        （mm 坐标，符号空间 ±0.5，大多应 |v| ≤ 3.0）返回 None。"""
        end = o + hl + n * 4
        if end > len(self.data):
            return None
        step = max(2, n // 40)
        ok = bad = 0
        for j in range(0, n, step):
            if abs(self._f32(o + hl + 4 * j)) <= 3.0:
                ok += 1
            else:
                bad += 1
        if bad > ok * 0.3:
            return None
        return end

    def _scan_record(self, o: int) -> Optional[Tuple[int, int, int, int]]:
        """在 @o 处识别一条记录：扫头长 4..512B（偶），返回
        (header_len, type, n, end)。链证两级：优先"后继记录样合法且
        后继载荷抽查亦过"（双门，取最短头）；否则退"后继仅记录样合法"
        （单门）；无链候选即诚实停止（不臆猜头长）。"""
        c1 = c2 = None
        for hl in range(4, self._TAIL_HL_MAX + 2, 2):
            t, n = self._u16(o), self._u16(o + 2)
            if not self._rec_like(t, n):
                break  # hl 不改变首 (t,n)，首步即定
            end = self._payload_sane(o, hl, n)
            if end is None or end + 4 > len(self.data):
                continue
            nt, nn = self._u16(end), self._u16(end + 2)
            if not self._rec_like(nt, nn):
                continue
            if c1 is None:
                c1 = (hl, t, n, end)
            ok = bad = 0
            step = max(2, nn // 20)
            for j in range(0, nn, step):
                if abs(self._f32(end + 4 + 4 * j)) <= 3.0:
                    ok += 1
                else:
                    bad += 1
            if bad <= ok * 0.3:
                c2 = (hl, t, n, end)
                break
        rec = c2 or c1
        return rec

    def _walk_tail(self, start: int) -> List[Tuple[int, int]]:
        """自 start 链式走查未索引记录，至识别失败或 EOF 止。"""
        bounds = []
        o = start
        while o + 8 <= len(self.data):
            rec = self._scan_record(o)
            if rec is None:
                break
            end = rec[3]
            bounds.append((o, end))
            o = end
        return bounds

    # -- 公共接口 ----------------------------------------------------------

    @property
    def n_indexed(self) -> int:
        """索引区内符号数（0..n_indexed-1 直接走偏移表）。"""
        return len(self.offsets)

    @property
    def n_tail(self) -> int:
        """未索引尾段符号数（#n_indexed 起链式续号）。"""
        return len(self._tail)

    @property
    def symbol_count(self) -> int:
        """全库符号总数 = 索引数 + 未索引尾段数。"""
        return len(self.offsets) + len(self._tail)

    def record_bounds(self, no: int) -> Tuple[int, int]:
        """符号 no 的记录字节区间（0-based；含尾段）。"""
        n_idx = len(self.offsets)
        if no < 0:
            raise IndexError(no)
        if no < n_idx:
            end = self.offsets[no + 1] if no + 1 < n_idx else self._indexed_end
            return self.offsets[no], end
        j = no - n_idx
        if j < len(self._tail):
            return self._tail[j]
        raise IndexError(no)

    def _subpath_counts(self, header_u16: List[int], n_points: int) -> List[int]:
        """头尾 u16 序列 = 子路径点数：从尾部向前贪心，取和恰为 n_points 的最长尾缀。"""
        acc = 0
        for i in range(len(header_u16) - 1, 1, -1):
            acc += header_u16[i]
            if acc > n_points:
                return []
            if acc == n_points:
                return header_u16[i:]
        return []

    def decode(self, no: int) -> Optional[Symbol]:
        """解码符号 no（0-based，含未索引尾段）；越界返回 None。"""
        if not (0 <= no < len(self.offsets) + len(self._tail)):
            return None
        o, e = self.record_bounds(no)
        total = e - o
        if total <= 8:
            return Symbol(no=no, type=0, n=0, header_len=total, header_u16=[])
        t = self._u16(o)
        n = self._u16(o + 2)
        hl = total - n * 4
        if hl < 4:
            return None
        header_u16 = [self._u16(o + j) for j in range(0, hl, 2)]
        # 载荷 = n×f32 的 (x,y) 点对（2026-10-15 优化：向量化，原逐点
        # struct 解包）；n 为奇数时末值丢弃，与原 range(n//2) 一致。
        arr = np.frombuffer(self.data, dtype="<f4", count=n, offset=o + hl)
        pts = list(zip(arr[0::2].tolist(), arr[1::2].tolist()))
        sym = Symbol(no=no, type=t, n=n, header_len=hl, header_u16=header_u16)
        counts = self._subpath_counts(header_u16, len(pts))
        if not counts:
            counts = [len(pts)]  # 头尾无点数表 → 单子路径
        i = 0
        for cnt in counts:
            sp = SubPath(points=pts[i:i + cnt])
            sym.subpaths.append(sp)
            i += cnt
        self._classify(sym)
        return sym

    def _classify(self, sym: Symbol) -> None:
        """子路径几何分类：密集弧列→圆拟合；type=6 三点子路径→中心三点
        组整圆（[圆心, 半径参考点, 圆心回点]，符号 7 锚定）；短点组跳过拟合。"""
        if sym.type == 6:
            for sp in sym.subpaths:
                c = _center_ref_circle(sp.points)
                if c is not None:
                    sp.circle = c
                    sp.closed = True
                    continue
        for sp in sym.subpaths:
            if len(sp.points) < 8:
                continue
            c = fit_circle(sp.points)
            if c is not None and 0.005 < c[2] <= 1.0:
                sp.circle = c
                # 密集弧列且首尾相接 → 闭合圆
                d = math.hypot(sp.points[0][0] - sp.points[-1][0],
                               sp.points[0][1] - sp.points[-1][1])
                if len(sp.points) >= 16 and d < 0.01:
                    sp.closed = True


def _center_ref_circle(pts: List[Tuple[float, float]]) -> Optional[Tuple[float, float, float]]:
    """type=6 三点整圆组判读：[圆心, 半径参考点, 圆心回点]。

    实证链：符号 7（type=6，用户裁定空心圆 r≈0.315mm）的两条三点子路径
    实为该结构——首尾点相距 ≤0.01mm（≈同一圆心），参考点与之等距；
    与符号 56 内圆"中心 3 点 (0,0)→(0.32,0)→(0,0) 半径参考"裁定同构。
    四门全过才判圆，否则返回 None（维持点序直连，不产生新 artifact）：
      ① 恰好 3 点；② 首尾距 ≤0.01mm；③ r=|参考点−圆心| 双侧等距
      （±2%）；④ 0.005 ≤ r ≤ 1.0mm（符号空间 ±0.5 的合理上限）。
    全库扫描（1996 符号）：68 条 type=6 记录 70 条三点子路径，判圆 33
    （半径聚类 0.32/0.36/0.5/0.51，全为可信符号圆），拒绝 37（如 #112
    竖直径线、#116/#117 原点引线——直连无伪迹）。残留挂账：type≠6
    记录中的同构三点组（如 #56 内圆，type=2）尚未扩展判读。
    """
    if len(pts) != 3:
        return None
    (x0, y0), (x1, y1), (x2, y2) = pts
    if math.hypot(x0 - x2, y0 - y2) > 0.01:
        return None
    r1 = math.hypot(x1 - x0, y1 - y0)
    r2 = math.hypot(x1 - x2, y1 - y2)
    if r1 < 0.005 or max(r1, r2) > 1.0:
        return None
    if abs(r1 - r2) > 0.02 * max(r1, r2):
        return None
    return ((x0 + x2) / 2.0, (y0 + y2) / 2.0, (r1 + r2) / 2.0)


def fit_circle(pts: List[Tuple[float, float]]) -> Optional[Tuple[float, float, float]]:
    """Kåsa 圆拟合（最小二乘）：返回 (cx, cy, r)；退化（近共线）→ None。"""
    if len(pts) < 3:
        return None
    n = len(pts)
    sx = sum(p[0] for p in pts)
    sy = sum(p[1] for p in pts)
    mx, my = sx / n, sy / n
    suu = suv = svv = suuu = suvv = svuu = svvv = 0.0
    for x, y in pts:
        u, v = x - mx, y - my
        suu += u * u
        suv += u * v
        svv += v * v
        suuu += u * u * u
        svvv += v * v * v
        suvv += u * v * v
        svuu += v * u * u
    den = 2.0 * (suu * svv - suv * suv)
    if abs(den) < 1e-7:
        return None
    uc = (svv * (suuu + suvv) - suv * (svuu + svvv)) / den
    vc = (suu * (svuu + svvv) - suv * (suuu + suvv)) / den
    r = math.sqrt(uc * uc + vc * vc + (suu + svv) / n)
    return (mx + uc, my + vc, r)


def symbol_geometries(lib: SubgraphLib, no: int) -> dict:
    """符号几何的结构化导出（渲染/重建消费）：{subpaths, circles, bbox}。"""
    sym = lib.decode(no)
    if sym is None:
        return {"no": no, "error": "decode failed"}
    out = {"no": no, "type": sym.type, "subpaths": [],
           "circles": [[round(v, 6) for v in sp.circle] for sp in sym.subpaths
                       if sp.circle],
           "bbox": None}
    xs, ys = [], []
    for sp in sym.subpaths:
        out["subpaths"].append({
            "points": [[round(x, 6), round(y, 6)] for x, y in sp.points],
            "closed": sp.closed,
            "circle": [round(v, 6) for v in sp.circle] if sp.circle else None,
        })
        for x, y in sp.points:
            xs.append(x)
            ys.append(y)
    if xs:
        out["bbox"] = [round(min(xs), 4), round(min(ys), 4),
                       round(max(xs), 4), round(max(ys), 4)]
    return out


if __name__ == "__main__":
    import sys
    lib = SubgraphLib(sys.argv[1] if len(sys.argv) > 1 else
                      r"//NAS1/Public/1：25万 建造构造图 空间数据库/SLIB/Subgraph.lib")
    print(f"Subgraph.lib：索引 {lib.n_indexed} 符号 + 未索引尾段 {lib.n_tail} 符号"
          f" = 共 {lib.symbol_count}（索引区 {lib.n_indexed * 4}B，"
          f"索引记录区终点 {lib._indexed_end}）")
    for no in (7, 27, 30, 43, 56):
        s = lib.decode(no)
        if s is None:
            continue
        circles = [sp.circle for sp in s.subpaths if sp.circle]
        print(f"  #{no}: type={s.type} 子路径={[len(sp.points) for sp in s.subpaths]}"
              f" 圆={[(round(c[2], 4)) for c in circles]}")
    # 尾段可达性演示：#1839（末条索引记录，旧 0xBE 误判的受害者）+ 尾段符号
    s = lib.decode(lib.n_indexed - 1)
    if s is not None:
        print(f"  #{lib.n_indexed - 1}（末条索引）: header_len={s.header_len}"
              f" 子路径数={len(s.subpaths)}")
    for no in (lib.n_indexed, lib.symbol_count - 1):
        s = lib.decode(no)
        if s is not None:
            print(f"  #{no}（尾段）: type={s.type} 点数={s.n_points}")
