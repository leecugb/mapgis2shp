# -*- coding: utf-8 -*-
# SPDX-License-Identifier: Apache-2.0
"""MapGIS 6.x 符号库（Subgraph.lib）解析器（2026-10-14 逆向定案版 v2）。

格式规格（经用户目视核验定案，符号 7/27/30/43/56 实证；含未索引尾段）：

  文件 = [1840 × u32 偏移表（小端）] + [索引记录区 7360..1330364]
         + [未索引记录链 1330364..——#1840 起链式续号；本库走查定案
            #1840–#1995 共 156 条（155 条"后继记录样+载荷样"双门链证，
            #1961 为单门）]
         + [尾段区域 #1996 起——2026-10-18 破解定案：根因是记录头超出
            旧走查 512B 扫描上限；模型 (t,n)+描述区(10B块×L)+点数表
            (k 项≥2 和==n//2)+n×4 f32，三重验证+前瞻 3 选链；本库
            5364 条 #1996–#7359 100% 字节覆盖到文件末尾，全链坐标
            审计 [-1.375,+1.485]mm 零越界；#7331/#7358 图面锚验证]
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
from bisect import bisect_left
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import numpy as np

_U16 = struct.Struct("<H")
_U32 = struct.Struct("<I")
_F32 = struct.Struct("<f")
# 三点参数弧组"空槽"哨兵位型（#23 实证：0xB3000000，f32 负非规格化 ≈ -1.5e-8）
_ARC_SENTINEL = b"\x00\x00\x00\xb3"


@dataclass
class SubPath:
    points: List[Tuple[float, float]] = field(default_factory=list)
    closed: bool = False
    circle: Optional[Tuple[float, float, float]] = None  # (cx, cy, r) 圆拟合
    arc: Optional[Tuple[float, float, float, float, float]] = None
    # (cx, cy, r, a0, a1) 参数弧段——角度为度、自 +x 轴逆时针；
    # 2026-10-18 子图 23 用户裁定定案（见 _three_point_arc）


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

    # 尾段区域（#1996 起，2026-10-18 破解——根因：记录头超旧走查 512B
    # 扫描上限。模型：(u16 type, u16 n) + 描述区（10B 块×L，内容不透明）
    # + 点数表（k 项 ≥2，总和==n//2）+ n×4 f32 载荷。三重验证+前瞻 3）
    _REGION_T_MAX = 0x8000   # 挂账待裁定：实测 type 397/413（原裁定 255）
    _REGION_N_MAX = 16000    # 挂账待裁定：实测 n=4300+（原 4000）
    _REGION_K_MAX = 4000     # 点数表项数上限（n=16000 全 2 点组时恰 4000）
    _REGION_SEQ_MAX = 512    # 描述区 10B 块数上限（#1996 实测 62 块）
    _REGION_WIN = (_REGION_SEQ_MAX * 10 + _REGION_K_MAX * 2) // 2  # 前缀和窗口 u16 数

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
        # 尾段区域（#1996 起）走查结果，惰性：首次访问深位符号时执行
        # 并缓存；每条 (start, end, payload_offset, k)
        self._region: Optional[List[Tuple[int, int, int, int]]] = None

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
    def n_region(self) -> int:
        """尾段区域符号数（#n_indexed+n_tail 起；首次访问触发结构走查）。"""
        return len(self._walk_region())

    @property
    def symbol_count(self) -> int:
        """全库符号总数 = 索引 + 尾段链 + 尾段区域。

        访问本属性会触发尾段区域结构走查（惰性、结果缓存；大库约数秒）。
        """
        return len(self.offsets) + len(self._tail) + len(self._walk_region())

    # -- 尾段区域（#1996 起）结构走查 ------------------------------------
    # 与 _slib_tail7331_probe.py v8 同门同证；2026-10-18 D:/SLIB 实证
    # 5364 条（#1996–#7359）100% 字节覆盖到文件末尾。

    def _region_sane_tn(self, o: int) -> bool:
        if o + 4 > len(self.data):
            return False
        t, n = struct.unpack_from("<HH", self.data, o)
        return 0 < t < self._REGION_T_MAX and \
            4 <= n <= self._REGION_N_MAX and n % 2 == 0

    def _region_payload_ok(self, o: int, n: int) -> bool:
        vals = np.frombuffer(self.data, dtype="<f4", count=n, offset=o)
        return int((np.abs(vals) > 3.0).sum() + np.isnan(vals).sum()) * 10 <= n

    def _region_candidates(self, o: int) -> List[Tuple[int, int, int, tuple]]:
        """@o 处记录的全部有效解析（end, L, k, counts）。

        描述区长度 L（u16 数，步进 5）枚举 + 点数表前缀和二分定位；
        候选由三重验证（点数表和==n//2 且项≥2、载荷抽查、总数表长）
        挑出。与 v8 探针逐门一致。
        """
        if not self._region_sane_tn(o):
            return []
        t, n = struct.unpack_from("<HH", self.data, o)
        npts = n // 2
        avail = len(self.data) - o - 4
        m = min(avail // 2, self._REGION_WIN)
        if m < npts:
            return []
        stream = np.frombuffer(self.data, dtype="<u2", count=m, offset=o + 4)
        csum = np.cumsum(stream, dtype=np.int64).tolist()
        ps = [0] + csum
        out = []
        for L in range(0, min(self._REGION_SEQ_MAX * 5, m) + 1, 5):
            target = ps[L] + npts
            k = bisect_left(ps, target, lo=L + 1)
            if k > L + self._REGION_K_MAX or k > m:
                continue
            if ps[k] != target:
                continue
            counts = stream[L:k].tolist()
            if not counts or min(counts) < 2:
                continue
            end = o + 4 + 2 * k + n * 4
            if end <= len(self.data) and \
                    self._region_payload_ok(o + 4 + 2 * k, n):
                out.append((end, L, k - L, tuple(counts)))
        return out

    def _walk_region(self) -> List[Tuple[int, int, int, int]]:
        """尾段区域链式走查（惰性 + 缓存；前瞻 3 条选链最长者）。

        每记录缓存 (start, end, payload_offset, k)。验证失败的记录
        不被解码——诚实停止点即 walk 终点（decode 越界返 None）。
        """
        if self._region is not None:
            return self._region
        recs: List[Tuple[int, int, int, int]] = []
        o = self._tail[-1][1] if self._tail else self._indexed_end
        memo: Dict[int, list] = {}

        def cands(x: int) -> list:
            if x not in memo:
                memo[x] = self._region_candidates(x)
            return memo[x]

        while o < len(self.data):
            cs = cands(o)
            if not cs:
                break
            best, best_len = None, -1
            for c in sorted(cs, key=lambda x: (x[1], x[2])):
                chain, no = 0, c[0]
                while chain < 3:
                    nxt = cands(no)
                    if not nxt:
                        break
                    nxt = min(nxt, key=lambda x: (x[1], x[2]))
                    no = nxt[0]
                    chain += 1
                if chain > best_len:
                    best, best_len = c, chain
            end, L, k, counts = best
            poff = o + 4 + 2 * L + 2 * k
            recs.append((o, end, poff, k))
            o = end
        self._region = recs
        return recs

    def record_bounds(self, no: int) -> Tuple[int, int]:
        """符号 no 的记录字节区间（0-based；含尾段与尾段区域）。"""
        n_idx = len(self.offsets)
        if no < 0:
            raise IndexError(no)
        if no < n_idx:
            end = self.offsets[no + 1] if no + 1 < n_idx else self._indexed_end
            return self.offsets[no], end
        j = no - n_idx
        if j < len(self._tail):
            return self._tail[j]
        region = self._walk_region()
        j -= len(self._tail)
        if 0 <= j < len(region):
            return region[j][0], region[j][1]
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
        """解码符号 no（0-based，含未索引尾段与尾段区域）；越界返回 None。

        尾段区域符号（no ≥ n_indexed + n_tail）首次访问时触发结构
        走查（惰性、缓存）；走查终点即当前诚实停止点，其后的号返回
        None——绝不返回臆造几何。
        """
        n_old = len(self.offsets) + len(self._tail)
        if no < 0:
            return None
        if no >= n_old:
            region = self._walk_region()
            j = no - n_old
            if j >= len(region):
                return None
            return self._decode_region_symbol(no, region[j])
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

    def _decode_region_symbol(
        self, no: int, rec: Tuple[int, int, int, int]
    ) -> Optional[Symbol]:
        """尾段区域记录解码（rec = (start, end, payload_offset, k)）。"""
        o, e, poff, k = rec
        t, n = self._u16(o), self._u16(o + 2)
        hl = poff - o
        header_u16 = [self._u16(o + j) for j in range(0, hl, 2)]
        arr = np.frombuffer(self.data, dtype="<f4", count=n, offset=poff)
        pts = list(zip(arr[0::2].tolist(), arr[1::2].tolist()))
        sym = Symbol(no=no, type=t, n=n, header_len=hl, header_u16=header_u16)
        counts = list(header_u16[-k:]) if k else []
        if not counts or sum(counts) != len(pts) or min(counts) < 2:
            return None  # 走查元数据与实际不符 → 诚实拒解
        i = 0
        for cnt in counts:
            sp = SubPath(points=pts[i:i + cnt])
            sym.subpaths.append(sp)
            i += cnt
        self._classify(sym)
        return sym

    def _classify(self, sym: Symbol) -> None:
        """子路径几何分类：三点整圆组→中心参考圆（[圆心, 半径参考点,
        圆心回点]，符号 7 锚定；2026-10-18 用户裁定扩展至全部 type：
        子图 21（type=2）三点组 r≈0.4475 为圆，半径连线不得描边）；
        三点参数弧组→弧段/整圆（子图 23 裁定，_three_point_arc）；
        密集弧列→圆拟合；短点组跳过拟合。"""
        for sp in sym.subpaths:
            c = _center_ref_circle(sp.points)
            if c is not None:
                sp.circle = c
                sp.closed = True
                continue
        for sp in sym.subpaths:
            if sp.circle is not None or len(sp.points) != 3:
                continue
            r = _three_point_arc(sp.points)
            if r is None:
                continue
            if r[0] == "circle":
                sp.circle = r[1]
                sp.closed = True
            else:
                sp.arc = r[1]
        for sp in sym.subpaths:
            if len(sp.points) < 8:
                continue
            c = fit_circle(sp.points)
            if c is not None and 0.005 < c[2] <= 1.0:
                # 残差门（2026-10-18）：库内真圆/弧为精确圆（锚 rms=0），
                # 非圆曲线（#7331 波浪环 rms≈0.09）不得判圆/弧——
                # 拟合对 partial arc 本身有 0.07–0.13mm 弦偏差，
                # 故弧段参数仅供语义导出，忠实渲染须描存储点。
                rms = math.sqrt(sum(
                    (math.hypot(x - c[0], y - c[1]) - c[2]) ** 2
                    for x, y in sp.points) / len(sp.points))
                if rms > 0.01:
                    continue
                cov, a0, a1 = _arc_coverage(sp.points, c)
                d = math.hypot(sp.points[0][0] - sp.points[-1][0],
                               sp.points[0][1] - sp.points[-1][1])
                if cov >= 300.0 and d < 0.01:
                    # 全覆盖且首尾相接 → 闭合整圆
                    sp.circle = c
                    sp.closed = True
                elif cov >= 5.0:
                    # 部分弧 → 弧段（2026-10-18 子图 23 图面裁定：
                    # 密集弧列的角度覆盖必须核验，部分弧不得过绘为整圆；
                    # #56 外圆"8 弧段拼合"断线效果即依赖此判读）
                    sp.arc = (c[0], c[1], c[2], a0, a1)


def _arc_coverage(
    pts: List[Tuple[float, float]], center: Tuple[float, float, float]
) -> Tuple[float, float, float]:
    """密集采样弧列的角度覆盖度：返回 (coverage_deg, a0, a1)。

    coverage = 360° − 相邻采样角最大间隙（环形）。全覆盖圆 ≈360；
    部分弧 = 其实际张角。a0/a1 = 弧的逆时针起止角（覆盖区两端，
    跨 0° 亦正确）。采样间距即最小可辨张角——n 点全覆盖圆的理论
    coverage = 360 − 360/n，故整圆判定须与首尾距联合使用（见
    _classify）。
    """
    cx, cy, _ = center
    angs = sorted(math.degrees(math.atan2(y - cy, x - cx)) % 360.0
                  for x, y in pts)
    n = len(angs)
    gaps = [(angs[(i + 1) % n] - angs[i]) % 360.0 for i in range(n)]
    k = max(range(n), key=lambda i: gaps[i])
    coverage = 360.0 - gaps[k]
    a0 = angs[(k + 1) % n]          # 最大间隙之后 = 覆盖起点
    a1 = angs[k]                    # 最大间隙之前 = 覆盖终点
    return coverage, a0 % 360.0, a1 % 360.0


def _three_point_arc(
    pts: List[Tuple[float, float]],
) -> Optional[tuple]:
    """三点参数弧组判读（2026-10-18 子图 23 用户图面裁定定案）。

    结构 [圆心, (半径, 弧起角), (弧终角, 0)]：
      - ``p0``  = 弧/圆圆心（符号空间 mm）
      - ``p1.x`` = 半径（mm）；``p1.y`` = 弧起角（度，自 +x 逆时针）
      - ``p2.x`` = 弧终角（度）；``p2.y`` = 0（恒零槽）
    裁定语义（v6 右图定案）：起终角均 ≈0（哨兵 0xB3000000，实测
    -1.5e-8）→ 画**整圆**（r=p1.x）；否则画**弧段**（逆时针 p1.y→p2.x，
    同一半径）。子图 23（type=46）44 组实证：22 空槽整圆 r=B.x
    0.012–0.055mm，22 弧段 r=B.x 自 B.y≈180° 扫至 C.x≈253–284°（左下象限）。

    判定门（防止误吞普通三点折线）：
      ① 恰 3 点；② |p2.y| ≤ 0.01（恒零槽）；
      ③ 0.005 ≤ p1.x ≤ 1.0（半径合法域）；
      ④ 弧段要求 |p1.y| ≥ 5°、|p2.x| ≥ 5° 且
         5° ≤ (p2.x − p1.y) mod 360 ≤ 355°（非退化）；
      ⑤ 圆心 |p0| 各分量 ≤ 1.5mm。不满足返回 None（维持点序直连）。
    与 _center_ref_circle 的区分：后者首末点 ≈ 同点（p0≈p2），
    本规则 p0 与 p2 无关——_classify 中中心参考圆优先。
    """
    if len(pts) != 3:
        return None
    (x0, y0), (x1, y1), (x2, y2) = pts
    if abs(y2) > 0.01:
        return None
    if not (0.005 <= x1 <= 1.0):
        return None
    if abs(x0) > 1.5 or abs(y0) > 1.5:
        return None
    # ⑥ 排除中心参考圆同构组：|p0−p2| ≤0.01 的组走 _center_ref_circle
    # 通道（其双侧不等距的退化实例是"断笔"不是圆——#7 sp1 实证：尾值
    # 同样带 0xB3000000 哨兵，但 p0≈p2 且 |p1−p0|≠|p1−p2|，裁定维持直连；
    # #23 空槽 p0 与 p2 相距 0.4mm+，才是真参数弧组）。
    if math.hypot(x0 - x2, y0 - y2) <= 0.01:
        return None
    # 整圆分支：哨兵须为 0xB3000000 精确位型（#23 空槽实证）。
    # 普通退化三点组（p1.y/p2.x=0.0，如符号 7 不对称小子路径）不得误判——
    # 哨兵是特定的负非规格化值而非数学零。
    if struct.pack("<f", y1) == _ARC_SENTINEL and \
            struct.pack("<f", x2) == _ARC_SENTINEL:
        return ("circle", (x0, y0, x1))
    a0, a1 = y1 % 360.0, x2 % 360.0
    if abs(y1) < 5.0 or abs(x2) < 5.0:
        return None
    sweep = (a1 - a0) % 360.0
    if not (5.0 <= sweep <= 355.0):
        return None
    return ("arc", (x0, y0, x1, a0, a1))


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
    竖直径线、#116/#117 原点引线——直连无伪迹）。2026-10-18 用户裁定
    扩展至全部 type：子图 21（type=2）三点组 [(0.0056,-0.0056),
    (0.4503,0), (0,0)] 判圆（r≈0.4475，圆心≈原点），半径连线为编辑
    表示、不得描边；同构挂账（#56 内圆，type=2）随之解除。
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
           "arcs": [[round(v, 6) for v in sp.arc] for sp in sym.subpaths
                    if sp.arc],
           "bbox": None}
    xs, ys = [], []
    for sp in sym.subpaths:
        out["subpaths"].append({
            "points": [[round(x, 6), round(y, 6)] for x, y in sp.points],
            "closed": sp.closed,
            "circle": [round(v, 6) for v in sp.circle] if sp.circle else None,
            "arc": [round(v, 6) for v in sp.arc] if sp.arc else None,
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
