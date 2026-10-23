# -*- coding: utf-8 -*-
"""jws 12 文件图形库解析渲染（2026-10-21）。

geosciml4china 分析的 12 文件（D:/jws 域内 11 矢量 + README）：
  WL → 线形引擎（feature_rhythm 单源 / payload_geometry）+ Colorlib 线色
  WP → 面填充色（Colorlib YMCK→RGB）+ 边界细线
  WT → 子图符号实例化（SubgraphLib）/ 文本注记（GBK 属性）
输出：每文件单渲 + 合成全图。
"""
import sys
sys.path.insert(0, r'D:\JWD\src')
import warnings
warnings.filterwarnings('ignore')
import math
import os
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.figure import Figure
from matplotlib.backends.backend_agg import FigureCanvasAgg
from matplotlib.patches import Polygon
from matplotlib.patches import Circle as MplCircle
from pymapgis.colorlib import ColorLib
from pymapgis.fillgrph import FillgrphLib, pattern_geometry
from pymapgis.reader import Reader
from pymapgis.linesty import LinestyLib, feature_rhythm
from pymapgis.slib import SubgraphLib, symbol_geometries

ROOT = r'D:\jws'
LST = LinestyLib(r'D:\SLIB\LINESTY.lib')
SLIB = SubgraphLib(r'D:\SLIB\Subgraph.lib')
COLORS = ColorLib(r'D:\SLIB\Colorlib.lib')
FG = FillgrphLib(r'D:\SLIB\Fillgrph.lib')

MM2DEG = 250.0 / 111320.0         # 1:250000：1mm=250m→度（纬度向）
TILE_PX = 26                      # 瓦片栅格分辨率（约 2× 超采样）


def color(idx):
    """色号 → (r,g,b) 0–1——单源 = pymapgis.colorlib.ColorLib
    （2026-10-21 四锚定案；越界灰降级）。"""
    rgb = COLORS.rgb01(idx)
    return rgb if rgb is not None else (0.85, 0.85, 0.85)


def _tile_mask(no):
    """图案号 → TILE_PX² alpha 掩膜（float 0..1）；解析失败 None（诚实）。

    圆一律实心渲染（暂定，kind 4/5/6 角色挂账中）；弧按 12 段折线逼近。
    """
    geo = pattern_geometry(FG, no)
    if geo is None:
        return None
    fig = Figure(figsize=(TILE_PX / 100.0, TILE_PX / 100.0), dpi=100,
                 facecolor='none')
    FigureCanvasAgg(fig)
    ax = fig.add_axes([0, 0, 1, 1])
    ax.set_xlim(0, 1); ax.set_ylim(0, 1); ax.axis('off')
    ax.patch.set_alpha(0)
    for ring in geo['fill_polygons']:
        ax.add_patch(Polygon(ring, closed=True, fc='k', ec='none'))
    for pts in geo['polylines']:
        ax.plot([p[0] for p in pts], [p[1] for p in pts], 'k-',
                lw=0.8, solid_capstyle='round')
    for cx, cy, rad in geo['circles']:
        ax.add_patch(MplCircle((cx, cy), rad, fc='k', ec='none'))
    for cx, cy, rad, a0, a1 in geo['arcs']:
        ts = [math.radians(a0 + (a1 - a0) * i / 12.0) for i in range(13)]
        ax.plot([cx + rad * math.cos(t) for t in ts],
                [cy + rad * math.sin(t) for t in ts], 'k-', lw=0.8)
    fig.canvas.draw()
    buf = np.asarray(fig.canvas.buffer_rgba())
    plt.close('all')
    return buf[..., 3].astype(np.float32) / 255.0


_TILE_CACHE = {}
def tile_mask(no):
    if no not in _TILE_CACHE:
        _TILE_CACHE[no] = _tile_mask(no)
    return _TILE_CACHE[no]


# Pcolor 锚定表（用户 MapGIS 读数裁定；>870 扩展色域）。
# 2026-10-22 审计定案：该色域在 D:\SLIB 内无存储表可逆推——
#   Colorlib 全副本 3500B/871 条（≤870 已闭环四锚公式）；
#   Pcolor.lib 算术表扫描（基 0-128×步长 4-64×8 字节序）0 命中，
#   相邻色号锚无相邻条目——其 u32 斜坡值（13/26/40/51/77/102/128/
#   153/179/204/230）为颜色树分裂坐标非色表；
#   xqw 三 LUT 为排序色匹配树（881 的 RGB 不在 Rgblut、882 的 KCMY
#   不在 Cmyklut）——该色域为 MapGIS 程序内置生成，不落盘于 D:\SLIB。
# 结构性发现：锚呈局部平滑族（881/882、903/904、1045=1046 相邻同族，
# 882→903 族间跳变）。剩余 13 号按族内插（2026-10-22 用户认可为
# **暂定策略**——推断值入 PCOLOR_INFERRED 与裁定锚分离计数；1167/1168
# 未定族保持诚实灰）。
PCOLOR_ANCHORS = {
    881:  (242 / 255, 1.0, 102 / 255),   # RGB(242,255,102)
    882:  (229 / 255, 1.0, 76 / 255),    # RGB(229,255,76)
    903:  (242 / 255, 178 / 255, 76 / 255),  # RGB(242,178,76)
    904:  (242 / 255, 153 / 255, 51 / 255),   # RGB(242,153,51)
    914:  (217 / 255, 1.0, 25 / 255),    # RGB(217,255,25)
    923:  (178 / 255, 1.0, 0.0),         # RGB(178,255,0)
    1045: (1.0, 1.0, 215 / 255),         # 与 1046 同色
    1046: (1.0, 1.0, 215 / 255),         # RGB(255,255,215)
    1051: (1.0, 1.0, 1.0),               # 纯白
    1096: (229 / 255,) * 3,              # RGB(229,229,229)
    1224: (1.0, 76 / 255, 215 / 255),    # RGB(255,76,215)
    1226: (1.0, 127 / 255, 229 / 255),   # RGB(255,127,229)（000019 对话框）
    1239: (242 / 255,) * 3,              # RGB(242,242,242)（000016 对话框）
    1465: (167 / 255, 222 / 255, 98 / 255),  # RGB(167,222,98)
}

# 族内插暂定值（2026-10-22 用户认可暂定策略；**非裁定锚**，图面核验
# 后可升级为锚或修订）
PCOLOR_INFERRED = {
    1043: (1.0, 1.0, 215 / 255),         # 淡黄白族（同 1045/1046）
    1044: (1.0, 1.0, 215 / 255),
    1092: (229 / 255,) * 3,              # 灰族（同 1096）
    1097: (229 / 255,) * 3,
    1205: (1.0, 76 / 255, 215 / 255),    # 品红族（同 1224）
    1215: (1.0, 76 / 255, 215 / 255),
    1243: (242 / 255,) * 3,              # 浅灰族（同 1239）
    1248: (242 / 255,) * 3,
    1425: (167 / 255, 222 / 255, 98 / 255),  # 橄榄族（同 1465）
    1426: (167 / 255, 222 / 255, 98 / 255),
    1427: (167 / 255, 222 / 255, 98 / 255),
}


def draw_pattern(ax, geom, pat_no, pat_rgb, w_mm, h_mm):
    """在面内平铺图案瓦片（页面锚定全局网格，跨面连续）；
    瓦片物理尺寸 = (w_mm, h_mm)（记录真值，对话框锚定）。"""
    mask = tile_mask(pat_no)
    if mask is None:
        return False
    td_x, td_y = w_mm * MM2DEG, h_mm * MM2DEG
    polys = [geom] if geom.geom_type == 'Polygon' else list(geom.geoms)
    tile = np.zeros((TILE_PX, TILE_PX, 4), np.float32)
    tile[..., 0], tile[..., 1], tile[..., 2] = pat_rgb
    tile[..., 3] = mask
    for p in polys:
        minx, miny, maxx, maxy = p.bounds
        x0 = math.floor(minx / td_x) * td_x
        y0 = math.floor(miny / td_y) * td_y
        nx = max(1, int(math.ceil((maxx - x0) / td_x)))
        ny = max(1, int(math.ceil((maxy - y0) / td_y)))
        if nx * ny > 40000:      # 超大面防御（内存闸门，如实上报）
            print('  !! 面过大跳过花纹 bbox=%.3f,%.3f,%.3f,%.3f' %
                  (minx, miny, maxx, maxy))
            continue
        big = np.tile(tile, (ny, nx, 1))
        im = ax.imshow(big, extent=(x0, x0 + nx * td_x,
                                    y0, y0 + ny * td_y),
                       origin='upper', interpolation='bilinear', zorder=3)
        clip = Polygon(np.asarray(p.exterior.coords), closed=True,
                       fc='none', ec='none')
        ax.add_patch(clip)
        im.set_clip_path(clip)
    return True


def fill_rgb(no):
    """填充色解析单源：裁定锚 > 族内插（暂定策略）> Colorlib(≤870) > 灰。
    返回 (rgb, status)；status ∈ anchored/inferred/colorlib/gray。"""
    if no in PCOLOR_ANCHORS:
        return PCOLOR_ANCHORS[no], "anchored"
    if no in PCOLOR_INFERRED:
        return PCOLOR_INFERRED[no], "inferred"
    rgb = COLORS.rgb01(no)
    if rgb is not None:
        return rgb, "colorlib"
    return (0.85, 0.85, 0.85), "gray"


def _rhythm_stamps(rhy):
    """feature_rhythm 结构 → 图案空间(mm) 印记集（单源：面板平铺与
    沿线戳印共用）。dots: ('circle', (x, y, r)) 或 ('vline', (x, ya, yb))。"""
    out = dict(polylines=[], dots=[], fills=[])
    for tup in rhy.get('lines', []):
        a, b = tup[0], tup[1]
        y = 0.0 if len(tup) == 2 else tup[2]
        out['polylines'].append([(a, y), (b, y)])
    for x, ya, yb in rhy.get('verticals', []):
        out['polylines'].append([(x, ya), (x, yb)])
    for tup in rhy.get('dots', []):
        x = tup[0]
        if len(tup) == 2:
            out['dots'].append(('circle', (x, 0.0, tup[1])))
        elif rhy['kind'] in ('dash_dot_raised', 'dotline_lib_r',
                             'line_slash_dot', 'filled_rect_dot_bars'):
            out['dots'].append(('circle', (x, tup[1], tup[2])))
        else:
            h, top = tup[1], tup[2]
            ya, yb = (-h, top) if (abs(abs(h) - abs(top)) < 1e-9 and h > 0) \
                else (h, top)
            out['polylines'].append([(x, ya), (x, yb)])
    for key in ('fills', 'teeth', 'rects'):
        for ring in rhy.get(key, []):
            out['fills'].append([(x, y) for x, y in ring])
    for cx, cy, rad in rhy.get('circles', []):
        out['dots'].append(('circle', (cx, cy, rad)))
    for a, b in rhy.get('strokes', []):
        out['polylines'].append([(a[0], a[1]), (b[0], b[1])])
    for x, ya, yb in rhy.get('bars', []):
        out['polylines'].append([(x, ya), (x, yb)])
    for x0, y0_, x1, y1_ in rhy.get('slashes', []):
        out['polylines'].append([(x0, y0_), (x1, y1_)])
    return out


def draw_linestyle(ax, lt, aux, lw_scale=1.0):
    """线形 → 路径绘制（rhythm 单源 / payload_geometry 引擎）。"""
    st = LST.decode(lt)
    r = feature_rhythm(st, aux) if st else None
    if r is not None:
        period = r['period_mm']
        stm = _rhythm_stamps(r)
        for k in range(int(8 / max(period, 0.1)) + 1):
            for poly in stm['polylines']:
                ax.plot([p[0] + k*period for p in poly],
                        [p[1] for p in poly], 'k-', lw=1.0,
                        solid_capstyle='round', zorder=3)
            for shape, tup in stm['dots']:
                if shape == 'circle':
                    x, y, rad = tup
                    ax.add_patch(MplCircle((x + k*period, y), rad,
                                           fc='k', ec='none', zorder=4))
                else:
                    x, ya, yb = tup
                    ax.plot([x + k*period]*2, [ya, yb], 'k-', lw=1.0,
                            zorder=3)
            for ring in stm['fills']:
                ax.add_patch(Polygon([(x + k*period, y) for x, y in ring],
                                     closed=True, fc='k', ec='none', zorder=2))
        return True
    if st is not None and st.sublines and aux < len(st.sublines):
        sl = st.sublines[aux]
        for kind, data in sl.payload_geometry():
            for k in range(9):
                if kind == 'dot':
                    x, y, rad, filled = data
                    if filled:
                        ax.add_patch(MplCircle((x + k, y), rad, fc='k', ec='none', zorder=4))
                    else:
                        ax.add_patch(MplCircle((x + k, y), rad, fc='none', ec='k', lw=1.1, zorder=4))
                elif kind == 'fill':
                    ax.add_patch(Polygon([(x + k, y) for x, y in data],
                                         closed=True, fc='k', ec='none', zorder=2))
                elif kind == 'segment':
                    x0, sy0, x1, sy1 = data
                    ax.plot([x0 + k, x1 + k], [sy0, sy1], 'k-', lw=1.2,
                            solid_capstyle='round', zorder=3)
                elif kind == 'polyline':
                    ax.plot([p[0] + k for p in data], [p[1] for p in data],
                            'k-', lw=1.0, solid_capstyle='round', zorder=3)
        return True
    return False


# ---------- 1. WL 线层：线型沿几何戳印（rhythm 单源） ----------
def _stamp_along(pts, rhy, xc, yc, buf):
    """把 rhythm 印记沿折线戳印（矢量数组，追加到 buf）。

    X 系数沿线伸缩（周期×xc）、Y 系数垂向伸缩；元素坐标 mm→度。
    buf: dict(segs=[], seg_col=[], seg_lw=[], dots=[], dot_sz=[],
    dot_col=[], fills=[], fill_col=[])。"""
    P = rhy['period_mm'] * xc * MM2DEG          # 周期（度）
    stm = _rhythm_stamps(rhy)
    d = np.diff(pts, axis=0)
    if len(d) == 0:
        return
    segl = np.hypot(d[:, 0], d[:, 1])
    cum = np.concatenate(([0.0], np.cumsum(segl)))
    total = cum[-1]
    if total <= 1e-12:
        return
    n = int(total / P) + 2
    kk = np.arange(n)

    def anchor(S):
        """弧长 S（度，任意形状）→ 沿线 (x, y) 与单位切向 (tx, ty)。"""
        idx = np.searchsorted(cum, S, side='right') - 1
        np.clip(idx, 0, len(segl) - 1, out=idx)
        sl = np.where(segl[idx] > 0, segl[idx], 1.0)
        t = (S - cum[idx]) / sl
        bx = pts[idx, 0] + t * d[idx, 0]
        by = pts[idx, 1] + t * d[idx, 1]
        tx = d[idx, 0] / sl
        ty = d[idx, 1] / sl
        return bx, by, tx, ty

    col = buf['_col']
    lw = buf['_lw']
    rmin = buf['_rmin']
    for poly in stm['polylines']:
        px = np.array([p[0] for p in poly]) * xc * MM2DEG
        py = np.array([p[1] for p in poly]) * yc * MM2DEG
        S = (kk[:, None] * P + px[None, :]).ravel()
        bx, by, tx, ty = anchor(S)
        py2 = np.tile(py, n)
        X = bx - ty * py2
        Y = by + tx * py2
        X = X.reshape(n, len(px)); Y = Y.reshape(n, len(px))
        for i in range(len(px) - 1):
            buf['segs'].append(np.stack(
                [np.column_stack([X[:, i], Y[:, i]]),
                 np.column_stack([X[:, i + 1], Y[:, i + 1]])], axis=1))
            buf['seg_col'].extend([col] * n)
            buf['seg_lw'].extend([lw] * n)
    for shape, tup in stm['dots']:
        if shape == 'circle':
            x, y, r = tup
            S = kk * P + x * xc * MM2DEG
            bx, by, tx, ty = anchor(S)
            off = y * yc * MM2DEG
            buf['dots'].append(np.column_stack(
                [bx - ty * off, by + tx * off]))
            buf['dot_sz'].extend([max(r * MM2DEG, rmin)] * n)
            buf['dot_col'].extend([col] * n)
        else:
            x, ya, yb = tup
            S = kk * P + x * xc * MM2DEG
            bx, by, tx, ty = anchor(S)
            for yy in (ya, yb):
                off = yy * yc * MM2DEG
                buf['segs'].append(np.stack(
                    [np.column_stack([bx - ty * off, by + tx * off])] * 2, axis=1))
                buf['seg_col'].extend([col] * n)
                buf['seg_lw'].extend([lw] * n)
    for ring in stm['fills']:
        px = np.array([p[0] for p in ring]) * xc * MM2DEG
        py = np.array([p[1] for p in ring]) * yc * MM2DEG
        S = (kk[:, None] * P + px[None, :]).ravel()
        bx, by, tx, ty = anchor(S)
        py2 = np.tile(py, n)
        X = (bx - ty * py2).reshape(n, len(px))
        Y = (by + tx * py2).reshape(n, len(px))
        for i in range(n):
            buf['fills'].append(np.column_stack([X[i], Y[i]]))
            buf['fill_col'].append(col)


def draw_wl_layer(ax, g, report=None):
    """WL 线层：线型沿几何戳印（feature_rhythm 单源）。

    调用方须先定轴限（transData 换算显示尺度）。solid 族与无 rhythm
    线直绘；图案线经 _stamp_along 矢量化（LineCollection/散点/
    PolyCollection）。report 计数 dict(solid/pattern/fallback)。"""
    rep = report if report is not None else dict(solid=0, pattern=0, fb=0)
    tr = ax.transData
    pts_per_deg = tr.transform((1.0, 0.0))[0] - tr.transform((0.0, 0.0))[0]
    pts_per_deg = max(abs(pts_per_deg), 1e-9)
    buf = dict(segs=[], seg_col=[], seg_lw=[], dots=[], dot_sz=[],
               dot_col=[], fills=[], fill_col=[])
    buf['_rmin'] = 0.8 / pts_per_deg      # 点径显示下限（度）
    for _, row in g.iterrows():
        geom = row.geometry
        if geom.geom_type != 'LineString':
            continue
        pts = np.asarray(geom.coords)
        col = color(int(row.get('color', 0) or 0))
        w = float(row.get('width', 0.1) or 0.1)
        buf['_lw'] = max(w * MM2DEG * pts_per_deg, 0.5)
        lt = int(row['linetype'])
        aux = int(row.get('aux_linetype', 0) or 0)
        xc = float(row.get('x_coef', 1.0) or 1.0)
        yc = float(row.get('y_coef', 1.0) or 1.0)
        st = LST.decode(lt)
        rhy = feature_rhythm(st, aux) if st else None
        if rhy is None or rhy['kind'] == 'solid_pen':
            ax.plot(pts[:, 0], pts[:, 1], color=col, lw=buf['_lw'],
                    solid_capstyle='round', zorder=4)
            rep['solid' if rhy is not None else 'fb'] += 1
            continue
        buf['_col'] = col
        _stamp_along(pts, rhy, xc, yc, buf)
        rep['pattern'] += 1
    if buf['segs']:
        from matplotlib.collections import LineCollection, PolyCollection
        segs = np.concatenate(buf['segs'], axis=0)
        ax.add_collection(LineCollection(
            segs, colors=buf['seg_col'], linewidths=buf['seg_lw'],
            capstyle='round', zorder=4))
    if buf['dots']:
        pts_d = np.concatenate(buf['dots'], axis=0)
        ax.scatter(pts_d[:, 0], pts_d[:, 1],
                   s=(2 * np.asarray(buf['dot_sz']) * pts_per_deg) ** 2,
                   c=buf['dot_col'], linewidths=0, zorder=5)
    if buf['fills']:
        from matplotlib.collections import PolyCollection
        ax.add_collection(PolyCollection(
            buf['fills'], facecolors=buf['fill_col'], edgecolors='none',
            zorder=3))
    return rep


# ---------- 1b. WL 单图输出 ----------
def render_wl():
    """WL 线层单图输出（轴限先行，供 transData 尺度换算）。"""
    for name in ('LDLYAAE001', 'LDZOFBA002', 'LDZOFBA003', 'LDZOFBA005'):
        fp = ROOT + '\\' + name + '.WL'
        g = Reader(fp, read_graphic_params=True).geodataframe
        fig, ax = plt.subplots(figsize=(10, 8))
        b = g.total_bounds
        ax.set_xlim(b[0] - 0.02, b[2] + 0.02)
        ax.set_ylim(b[1] - 0.02, b[3] + 0.02)
        rep = draw_wl_layer(ax, g)
        ax.set_title('%s.WL  (%d lines; 图案线 %d, 实线 %d, 回退 %d)'
                     % (name, len(g), rep['pattern'], rep['solid'],
                        rep['fb']), fontsize=9)
        ax.set_aspect('equal'); ax.axis('off')
        fig.savefig(ROOT + '\\_render_%s.png' % name, dpi=110,
                    bbox_inches='tight', pad_inches=0.02)
        plt.close(fig)
        print('WL', name, len(g), 'pattern %d solid %d fb %d'
              % (rep['pattern'], rep['solid'], rep['fb']))

# ---------- 2. WP 面层：布局 v2 单源（reader 列：填充=u16@9、图案=u16@13、
# 高宽=u16@17/@21、图案色=u8@23；花纹仅尺寸非零时按真值平铺） ----------
# 2026-03-12 重写丢失图案层（writer 旧布局清零 @12-39）——此两幅改用
# 2019-10-31 原版 .WP~ 渲染
WP_SOURCE = {
    'LDLYAAE002': 'LDLYAAE002.WP~',
    'LDZOFBB003': 'LDZOFBB003.WP~',
}


def draw_wp_layer(ax, g):
    """把 WP 面层画到 ax（单源：reader 布局 v2 列）；返回计数 dict。"""
    cnt = dict(pat=0, pat_none=0, infer=0, fb=0)
    for _, row in g.iterrows():
        geom = row.geometry
        frgb, st = fill_rgb(int(row['fill_color']))
        if st == "inferred":
            cnt['infer'] += 1
        elif st == "gray":
            cnt['fb'] += 1
        polys = [geom] if geom.geom_type == 'Polygon' else list(geom.geoms)
        for p in polys:
            ax.add_patch(Polygon(np.asarray(p.exterior.coords), closed=True,
                                 fc=frgb, ec='#666666', lw=0.3, zorder=2))
        # 花纹层：尺寸非零才显示（对话框锚定的显示闸门）
        pat = int(row['pattern'])
        h = float(row['pattern_height'])
        w = float(row['pattern_width'])
        if pat > 0 and h > 0 and w > 0:
            prgb = color(int(row['pattern_color']))
            if draw_pattern(ax, geom, pat, prgb, w, h):
                cnt['pat'] += 1
            else:
                cnt['pat_none'] += 1
    return cnt


def render_wp():
    """WP 面层单图输出。"""
    for name in ('LDLYAAE002', 'LDZOFBB001', 'LDZOFBB002', 'LDZOFBB003',
                 'LDZOFBB004'):
        fp = ROOT + '\\' + WP_SOURCE.get(name, name + '.WP')
        g = Reader(fp, read_graphic_params=True).geodataframe
        fig, ax = plt.subplots(figsize=(10, 8))
        cnt = draw_wp_layer(ax, g)
        src = os.path.basename(fp)
        ax.set_title('%s  (%d polygons; 花纹 %d, 花纹未解 %d, 族推断 %d, 未锚 %d)'
                     % (src, len(g), cnt['pat'], cnt['pat_none'],
                        cnt['infer'], cnt['fb']), fontsize=9)
        ax.set_aspect('equal'); ax.axis('off')
        ax.autoscale_view()
        fig.savefig(ROOT + '\\_render_%s.png' % name, dpi=110,
                    bbox_inches='tight', pad_inches=0.02)
        plt.close(fig)
        print('WP', name, 'src=' + src, len(g),
              'pattern %d none %d infer %d fb %d'
              % (cnt['pat'], cnt['pat_none'], cnt['infer'], cnt['fb']))


# ---------- 3. WT 点层：子图实例化（Subgraph.lib 单源） ----------
_SYM_CACHE = {}
def symbol_geo(no):
    if no not in _SYM_CACHE:
        _SYM_CACHE[no] = symbol_geometries(SLIB, no)
    return _SYM_CACHE[no]


def draw_symbol_point(ax, x, y, no, h_mm, w_mm, angle_deg, rgb, lw=0.7):
    """子图实例化：库几何（1mm 设计单位）× (w,h) 毫米 × 角度旋转（CCW）。
    圆/弧采样折线过同一变换（w≠h 时自然成椭圆）。解析失败诚实返回 False。"""
    geo = symbol_geo(no)
    if geo is None or 'error' in geo:
        return False
    ca = math.cos(math.radians(angle_deg))
    sa = math.sin(math.radians(angle_deg))
    sx, sy = w_mm * MM2DEG, h_mm * MM2DEG

    def T(px, py):
        return (x + (px * ca - py * sa) * sx, y + (px * sa + py * ca) * sy)

    for sp in geo['subpaths']:
        pts = sp['points']
        if not pts:
            continue
        tp = [T(px, py) for px, py in pts]
        if len(tp) == 1:
            ax.plot([tp[0][0]], [tp[0][1]], '.', color=rgb, ms=2.0, zorder=5)
        else:
            if sp['closed']:
                tp = tp + [tp[0]]
            ax.plot([p[0] for p in tp], [p[1] for p in tp], color=rgb,
                    lw=lw, solid_capstyle='round', zorder=5)
    for cx, cy, r in geo['circles']:
        ts = [math.radians(360.0 * i / 48) for i in range(48)]
        pts = [T(cx + r * math.cos(t), cy + r * math.sin(t)) for t in ts]
        pts.append(pts[0])
        ax.plot([p[0] for p in pts], [p[1] for p in pts], color=rgb,
                lw=lw, zorder=5)
    for cx, cy, r, a0, a1 in geo['arcs']:
        ts = [math.radians(a0 + (a1 - a0) * i / 24.0) for i in range(25)]
        pts = [T(cx + r * math.cos(t), cy + r * math.sin(t)) for t in ts]
        ax.plot([p[0] for p in pts], [p[1] for p in pts], color=rgb,
                lw=lw, solid_capstyle='round', zorder=5)
    return True


def draw_wt_layer(ax, g, report=None):
    """WT 点层：子图点按 Subgraph.lib 实例化；文本点暂以淡点标注
    （注记实例化挂账）。report 计数 dict（sym_ok/sym_none/text）。"""
    rep = report if report is not None else dict(sym_ok=0, sym_none=0, text=0)
    for _, row in g.iterrows():
        x, y = row.geometry.x, row.geometry.y
        if int(row['point_type']) == 1:
            ok = draw_symbol_point(
                ax, x, y, int(row['symbol_no']),
                float(row['height']), float(row['width']),
                float(row['angle']), color(int(row.get('color', 0) or 0)))
            if ok:
                rep['sym_ok'] += 1
            else:
                rep['sym_none'] += 1
        else:
            ax.plot([x], [y], '.', color='#c0392b', ms=1.5, zorder=5)
            rep['text'] += 1
    return rep


def render_wt():
    for name in ('LDZOFBA016', 'LDZOFBB099'):
        fp = ROOT + '\\' + name + '.WT'
        g = Reader(fp, read_graphic_params=True,
                   read_point_params=True).geodataframe
        fig, ax = plt.subplots(figsize=(10, 8))
        rep = draw_wt_layer(ax, g)
        ax.set_title('%s.WT  (%d points; 子图 %d, 子图未解 %d, 文本点 %d)'
                     % (name, len(g), rep['sym_ok'], rep['sym_none'],
                        rep['text']), fontsize=9)
        ax.set_aspect('equal'); ax.axis('off')
        fig.savefig(ROOT + '\\_render_%s.png' % name, dpi=110,
                    bbox_inches='tight', pad_inches=0.02)
        plt.close(fig)
        print('WT', name, len(g), 'sym %d none %d text %d'
              % (rep['sym_ok'], rep['sym_none'], rep['text']))


# ---------- 4. 线形图版（图形库解析展示，每文件一行） ----------
SPECS = [
    ('LDZOFBA002.WL', 'LDZOFBA002', (1, 0)), ('LDZOFBA002.WL', None, (2, 0)),
    ('LDZOFBA002.WL', None, (16, 0)), ('LDZOFBA002.WL', None, (17, 0)),
    ('LDZOFBA002.WL', None, (3, 0)), ('LDZOFBA002.WL', None, (48, 0)),
    ('LDZOFBA003.WL', 'LDZOFBA003', (1, 0)), ('LDZOFBA005.WL', 'LDZOFBA005', (1, 0)),
    ('LDLYAAE001.WL', 'LDLYAAE001', (1, 0)),
]


def render_panel():
    fig, axes = plt.subplots(len(SPECS), 1,
                             figsize=(10, len(SPECS) * 0.6 + 0.3))
    for ax, (fname, sheet_lt, (lt, aux)) in zip(axes, SPECS):
        draw_linestyle(ax, lt, aux)
        ax.set_xlim(-0.1, 4.1)
        ax.set_ylim(-0.35, 0.35)
        ax.set_aspect('equal', adjustable='box')
        for sp in ax.spines.values():
            sp.set_visible(False)
        ax.set_xticks([]); ax.set_yticks([])
        label = '%s  %d|%d' % (fname, lt, aux)
        ax.text(-0.02, 0.5, label, transform=ax.transAxes, fontsize=8,
                va='center', ha='right', fontweight='bold',
                fontfamily='monospace')
    fig.subplots_adjust(left=0.24, right=0.98, top=0.99, bottom=0.004,
                        hspace=0.3)
    fig.savefig(ROOT + '\\_render_linestyle_panel.png', dpi=110,
                bbox_inches='tight', pad_inches=0.02)
    print('linestyle panel ok')


if __name__ == '__main__':
    render_wl()
    render_wp()
    render_wt()
    render_panel()
    print('ALL DONE')
