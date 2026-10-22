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
from pymapgis.slib import SubgraphLib

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


# Pcolor 锚定表（用户 MapGIS 读数裁定；>870 扩展色域——Pcolor.lib 经审计
# 为颜色匹配树（色号不在其中），锚表暂行。2026-10-22 定案：该色域实为
# **填充色**（u16@9），非图案色）
PCOLOR_ANCHORS = {
    881:  (242 / 255, 1.0, 102 / 255),   # RGB(242,255,102)
    904:  (242 / 255, 153 / 255, 51 / 255),   # RGB(242,153,51)
    914:  (217 / 255, 1.0, 25 / 255),    # RGB(217,255,25)
    1045: (1.0, 1.0, 215 / 255),         # 与 1046 同色
    1046: (1.0, 1.0, 215 / 255),         # RGB(255,255,215)
    1051: (1.0, 1.0, 1.0),               # 纯白
    1096: (229 / 255,) * 3,              # RGB(229,229,229)
    1224: (1.0, 76 / 255, 215 / 255),    # RGB(255,76,215)
    1226: (1.0, 127 / 255, 229 / 255),   # RGB(255,127,229)（000019 对话框）
    1239: (242 / 255,) * 3,              # RGB(242,242,242)（000016 对话框）
    1465: (167 / 255, 222 / 255, 98 / 255),  # RGB(167,222,98)
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
    """填充色：锚表 > Colorlib(≤870) > 灰（未锚诚实降级，计数上报）。"""
    if no in PCOLOR_ANCHORS:
        return PCOLOR_ANCHORS[no], False
    rgb = COLORS.rgb01(no)
    if rgb is not None:
        return rgb, False
    return (0.85, 0.85, 0.85), True


def draw_linestyle(ax, lt, aux, lw_scale=1.0):
    """线形 → 路径绘制（rhythm 单源 / payload_geometry 引擎）。"""
    st = LST.decode(lt)
    r = feature_rhythm(st, aux) if st else None
    if r is not None:
        period = r['period_mm']
        for k in range(int(8 / max(period, 0.1)) + 1):
            for tup in r.get('lines', []):
                a, b = tup[0], tup[1]
                y = 0.0 if len(tup) == 2 else tup[2]
                ax.plot([a + k*period, b + k*period], [y, y], 'k-',
                        lw=1.3*lw_scale, solid_capstyle='butt', zorder=3)
            for x, ya, yb in r.get('verticals', []):
                ax.plot([x + k*period]*2, [ya, yb], 'k-', lw=1.0, zorder=3)
            for tup in r.get('dots', []):
                x = tup[0]
                if len(tup) == 2:
                    ax.add_patch(MplCircle((x + k*period, 0), tup[1],
                                           fc='k', ec='none', zorder=4))
                elif r['kind'] in ('dash_dot_raised', 'dotline_lib_r',
                                   'line_slash_dot', 'filled_rect_dot_bars'):
                    ax.add_patch(MplCircle((x + k*period, tup[1]), tup[2],
                                           fc='k', ec='none', zorder=4))
                else:
                    h, top = tup[1], tup[2]
                    ya, yb = (-h, top) if (abs(abs(h)-abs(top)) < 1e-9 and h > 0) \
                        else (h, top)
                    ax.plot([x + k*period]*2, [ya, yb], 'k-', lw=1.0, zorder=3)
            for ring in r.get('fills', []):
                ax.add_patch(Polygon([(x + k*period, y) for x, y in ring],
                                     closed=True, fc='k', ec='none', zorder=2))
            for tooth in r.get('teeth', []):
                ax.add_patch(Polygon([(x + k*period, y) for x, y in tooth],
                                     closed=True, fc='k', ec='none', zorder=2))
            for ring in r.get('rects', []):
                ax.add_patch(Polygon([(x + k*period, y) for x, y in ring],
                                     closed=True, fc='k', ec='none', zorder=2))
            for cx, cy, rad in r.get('circles', []):
                ax.add_patch(MplCircle((cx + k*period, cy), rad,
                                       fc='k', ec='none', zorder=2))
            for a, b in r.get('strokes', []):
                ax.plot([a[0] + k*period, b[0] + k*period], [a[1], b[1]],
                        'k-', lw=0.9, solid_capstyle='round', zorder=3)
            for x, ya, yb in r.get('bars', []):
                ax.plot([x + k*period]*2, [ya, yb], 'k-', lw=1.0, zorder=3)
            for x0, y0_, x1, y1_ in r.get('slashes', []):
                ax.plot([x0 + k*period, x1 + k*period], [y0_, y1_],
                        'k-', lw=1.0, zorder=3)
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


# ---------- 1. WL 线层：按真实几何渲染 ----------
for name in ('LDLYAAE001', 'LDZOFBA002', 'LDZOFBA003', 'LDZOFBA005'):
    fp = ROOT + '\\' + name + '.WL'
    g = Reader(fp, read_graphic_params=True).geodataframe
    fig, ax = plt.subplots(figsize=(10, 8))
    for _, row in g.iterrows():
        geom = row.geometry
        col = color(int(row.get('color', 0) or 0))
        if geom.geom_type == 'LineString':
            pts = np.asarray(geom.coords)
            ax.plot(pts[:, 0], pts[:, 1], '-', color=col, lw=0.7, zorder=3)
    ax.set_title('%s.WL  (%d lines, Colorlib 线色)' % (name, len(g)), fontsize=9)
    ax.set_aspect('equal'); ax.axis('off')
    fig.savefig(ROOT + '\\_render_%s.png' % name, dpi=110,
                bbox_inches='tight', pad_inches=0.02)
    plt.close(fig)
    print('WL', name, len(g), 'ok')

# ---------- 2. WP 面层：布局 v2 单源（reader 列：填充=u16@9、图案=u16@12、
# 高宽=u16@17/@21、图案色=u8@23；花纹仅尺寸非零时按真值平铺） ----------
# 2026-03-12 重写丢失图案层（writer 旧布局清零 @12-39）——此两幅改用
# 2019-10-31 原版 .WP~ 渲染
WP_SOURCE = {
    'LDLYAAE002': 'LDLYAAE002.WP~',
    'LDZOFBB003': 'LDZOFBB003.WP~',
}
for name in ('LDLYAAE002', 'LDZOFBB001', 'LDZOFBB002', 'LDZOFBB003',
             'LDZOFBB004'):
    fp = ROOT + '\\' + WP_SOURCE.get(name, name + '.WP')
    g = Reader(fp, read_graphic_params=True).geodataframe
    fig, ax = plt.subplots(figsize=(10, 8))
    n_pat = n_pat_none = n_fill_fb = 0
    for _, row in g.iterrows():
        geom = row.geometry
        frgb, fb = fill_rgb(int(row['fill_color']))
        n_fill_fb += fb
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
                n_pat += 1
            else:
                n_pat_none += 1
    src = os.path.basename(fp)
    ax.set_title('%s  (%d polygons; 花纹 %d, 花纹未解 %d, 填充未锚 %d)'
                 % (src, len(g), n_pat, n_pat_none, n_fill_fb), fontsize=9)
    ax.set_aspect('equal'); ax.axis('off')
    ax.autoscale_view()
    fig.savefig(ROOT + '\\_render_%s.png' % name, dpi=110,
                bbox_inches='tight', pad_inches=0.02)
    plt.close(fig)
    print('WP', name, 'src=' + src, len(g), 'pattern %d none %d fill_fb %d'
          % (n_pat, n_pat_none, n_fill_fb))

# ---------- 3. WT 点层：符号/注记 ----------
for name in ('LDZOFBA016', 'LDZOFBB099'):
    fp = ROOT + '\\' + name + '.WT'
    g = Reader(fp, read_graphic_params=True, read_point_params=True).geodataframe
    fig, ax = plt.subplots(figsize=(10, 8))
    xs = [p.x for p in g.geometry]
    ys = [p.y for p in g.geometry]
    ax.plot(xs, ys, 'o', color='#c0392b', ms=2.5, zorder=3)
    ax.set_title('%s.WT  (%d points)' % (name, len(g)), fontsize=9)
    ax.set_aspect('equal'); ax.axis('off')
    fig.savefig(ROOT + '\\_render_%s.png' % name, dpi=110,
                bbox_inches='tight', pad_inches=0.02)
    plt.close(fig)
    print('WT', name, len(g), 'ok')

# ---------- 4. 线形图版（图形库解析展示，每文件一行） ----------
SPECS = [
    ('LDZOFBA002.WL', 'LDZOFBA002', (1, 0)), ('LDZOFBA002.WL', None, (2, 0)),
    ('LDZOFBA002.WL', None, (16, 0)), ('LDZOFBA002.WL', None, (17, 0)),
    ('LDZOFBA002.WL', None, (3, 0)), ('LDZOFBA002.WL', None, (48, 0)),
    ('LDZOFBA003.WL', 'LDZOFBA003', (1, 0)), ('LDZOFBA005.WL', 'LDZOFBA005', (1, 0)),
    ('LDLYAAE001.WL', 'LDLYAAE001', (1, 0)),
]
fig, axes = plt.subplots(len(SPECS), 1, figsize=(10, len(SPECS) * 0.6 + 0.3))
for ax, (fname, sheet_lt, (lt, aux)) in zip(axes, SPECS):
    ok = draw_linestyle(ax, lt, aux)
    ax.set_xlim(-0.1, 4.1)
    ax.set_ylim(-0.35, 0.35)
    ax.set_aspect('equal', adjustable='box')
    for sp in ax.spines.values():
        sp.set_visible(False)
    ax.set_xticks([]); ax.set_yticks([])
    label = '%s  %d|%d' % (fname, lt, aux)
    ax.text(-0.02, 0.5, label, transform=ax.transAxes, fontsize=8,
            va='center', ha='right', fontweight='bold', fontfamily='monospace')
fig.subplots_adjust(left=0.24, right=0.98, top=0.99, bottom=0.004, hspace=0.3)
fig.savefig(ROOT + '\\_render_linestyle_panel.png', dpi=110,
            bbox_inches='tight', pad_inches=0.02)
print('linestyle panel ok')
print('ALL DONE')
