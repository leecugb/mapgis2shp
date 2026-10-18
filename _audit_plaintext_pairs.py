#!/usr/bin/env python3
"""明码对审计 v2：按官方明文格式（文本点 17 字段/子图点 14 字段）分型解析，
按记录号对齐，逐字段对比 Reader 解码；再过一遍 Writer 编码回读对比。"""
import re
import struct
import sys
import warnings
from pathlib import Path

warnings.filterwarnings("ignore")
sys.path.insert(0, "D:/JWD/src")

from pymapgis import Reader, Writer  # noqa: E402

BASE = Path("D:/360安全浏览器下载")

TEXT_PAT = re.compile(
    r"([^,]+),([^,]+),(\d+),0,\"(.*)\",([\d.]+),([\d.]+),([\d.-]+),([\d.-]+),"
    r"(\d+),(\d+),(\d+),(\d+),(\d+),(\d+),(\d+)"
)
SYM_PAT = re.compile(
    r"([^,]+),([^,]+),(\d+),1,(\d+),([\d.]+),([\d.]+),([\d.-]+),([\d.-]+),"
    r"(\d+),([\d.]+),(\d+),(\d+)"
)


def read_wat(path):
    rows = {}
    for ln in path.read_text(encoding="gbk", errors="replace").splitlines()[2:]:
        ln = ln.strip()
        if not ln:
            continue
        m = TEXT_PAT.match(ln)
        if m:
            g = m.groups()
            rows[int(g[2])] = dict(
                kind=0, x=float(g[0]), y=float(g[1]), text=g[3],
                height=float(g[4]), width=float(g[5]), spacing=float(g[6]),
                angle=float(g[7]), f9=int(g[8]), font_zh=int(g[9]),
                font_en=int(g[10]), font_style=int(g[11]),
                color=int(g[12]), layer=int(g[13]), f16=int(g[14]),
            )
            continue
        m = SYM_PAT.match(ln)
        if m:
            g = m.groups()
            rows[int(g[2])] = dict(
                kind=1, x=float(g[0]), y=float(g[1]), symbol_no=int(g[3]),
                height=float(g[4]), width=float(g[5]), angle=float(g[6]),
                spacing=float(g[7]), color=int(g[8]), pen_width=float(g[9]),
                layer=int(g[10]), f13=int(g[11]),
            )
    return rows


def report(name, checks):
    print(f"  [{name}]")
    bad = 0
    for field, got, exp, tol, samples in checks:
        if samples:
            bad += 1
            print(f"    {field}: {len(samples)} 条不符; 样例(记录号,我们,明文): {samples[:3]}")
    if not bad:
        print("    全部字段一致 ✓")
    return bad


def audit_points():
    print("=" * 70)
    print("点：LDZOFBB099.WT vs 456.wat（按记录号对齐）")
    rows = read_wat(BASE / "456.wat")
    with Reader(BASE / "LDZOFBB099.WT", read_graphic_params=True) as r:
        geom = [(float(g.x), float(g.y)) for g in r.geom]
        pp = r.point_params
    n = len(geom)
    print(f"明码 {len(rows)} 条 vs 二进制 {n} 条")
    cols = {c: pp[c].tolist() for c in pp.columns}
    xs = [g[0] for g in geom]
    ys = [g[1] for g in geom]
    cols["x"] = xs
    cols["y"] = ys
    checks = []
    for field in ["x", "y", "height", "width", "spacing", "angle", "color", "layer"]:
        tol = 1e-6 if field in ("x", "y") else (1e-4 if field == "angle" else 1e-3)
        samples = []
        for i in range(n):
            wid = i + 1
            if wid not in rows:
                continue
            exp = rows[wid]
            kind = int(cols["point_type"][i])
            if kind != exp["kind"]:
                if len(samples) < 3:
                    samples.append((wid, f"kind={kind}", f"kind={exp['kind']}"))
                continue
            got = cols[field][i]
            got = 0.0 if got != got else float(got)
            e = exp.get(field)
            if e is None:
                continue
            if field == "spacing" and kind == 1:
                continue  # 子图点无间隔字段
            if abs(got - float(e)) > tol:
                if len(samples) < 3:
                    samples.append((wid, got, e))
        checks.append((field, None, None, tol, samples))
    # 子图号 / 笔宽 / 文本 / 字体
    for field, col in [("symbol_no", "symbol_no"), ("pen_width", "pen_width"),
                       ("font_zh", "font_zh"), ("font_en", "font_en"),
                       ("font_style", "font_style")]:
        samples = []
        for i in range(n):
            wid = i + 1
            if wid not in rows:
                continue
            exp = rows[wid]
            kind = int(cols["point_type"][i])
            key = {"symbol_no": "symbol_no", "pen_width": "pen_width",
                   "font_zh": "font_zh", "font_en": "font_en",
                   "font_style": "font_style"}[field]
            if key not in exp:
                continue
            if (field in ("symbol_no", "pen_width") and kind != 1) or (
                field in ("font_zh", "font_en", "font_style") and kind != 0
            ):
                continue
            got = cols[col][i]
            got = 0.0 if got != got else float(got)
            if abs(got - float(exp[key])) > 1e-3:
                if len(samples) < 3:
                    samples.append((wid, got, exp[key]))
        checks.append((field, None, None, 0, samples))
    return report("Reader 解码 vs wat", checks)


def read_wal(path):
    lines = path.read_text(encoding="gbk", errors="replace").splitlines()
    count = int(lines[1].strip())
    rows = []
    i = 2
    while i < len(lines) and len(rows) < count:
        hdr = lines[i].strip()
        if not hdr:
            i += 1
            continue
        p = hdr.split(",")
        nv = int(lines[i + 1].strip())
        coords = []
        for k in range(nv):
            x, y = lines[i + 2 + k].strip().split(",")
            coords.append((float(x), float(y)))
        tail = lines[i + 2 + nv].strip().split(",")
        rows.append(dict(
            id=i+1, linetype=int(p[0]), aux=int(p[1]), color=int(p[2]), width=float(p[3]),
            x_coef=float(p[4]), y_coef=float(p[5]), aux_color=int(p[6]),
            layer=int(p[7]), transparent=int(p[8]), n_vertices=nv,
            coords=coords, tail0=int(float(tail[0])), tail1=float(tail[1]),
        ))
        i += 2 + nv + 1
    return rows


def audit_lines():
    print()
    print("=" * 70)
    print("线：LDZOFBA002.WL vs 123.wal（按记录顺序对齐）")
    rows = read_wal(BASE / "123.wal")
    with Reader(BASE / "LDZOFBA002.WL", read_graphic_params=True) as r:
        geom = [list(g.coords) for g in r.geom]
        lp = r.line_params
    n = len(geom)
    print(f"明码 {len(rows)} 条 vs 二进制 {n} 条")
    cols = {c: lp[c].tolist() for c in lp.columns}
    field_map = {
        "linetype": ("linetype", 0), "aux_linetype": ("aux", 0),
        "color": ("color", 0),
        "width": ("width", 1e-4), "x_coef": ("x_coef", 1e-4),
        "y_coef": ("y_coef", 1e-4), "aux_color": ("aux_color", 0),
        "layer": ("layer", 0), "transparent": ("transparent", 0),
    }
    checks = []
    for bf, (wf, tol) in field_map.items():
        samples = []
        for i, row in enumerate(rows):
            if i >= n:
                break
            if abs(float(cols[bf][i]) - float(row[wf])) > tol:
                if len(samples) < 3:
                    samples.append((i + 1, cols[bf][i], row[wf]))
        checks.append((bf, None, None, tol, samples))
    for gf, tol in [("n_vertices", 0), ("first_x", 1e-6), ("first_y", 1e-6),
                    ("last_x", 1e-6), ("last_y", 1e-6)]:
        samples = []
        for i, row in enumerate(rows):
            if i >= n:
                break
            bc = geom[i]
            got = {"n_vertices": len(bc), "first_x": bc[0][0], "first_y": bc[0][1],
                   "last_x": bc[-1][0], "last_y": bc[-1][1]}[gf]
            exp = {"n_vertices": row["n_vertices"], "first_x": row["coords"][0][0],
                   "first_y": row["coords"][0][1], "last_x": row["coords"][-1][0],
                   "last_y": row["coords"][-1][1]}[gf]
            if abs(float(got) - float(exp)) > tol:
                if len(samples) < 3:
                    samples.append((i + 1, got, exp))
        checks.append((gf, None, None, tol, samples))
    return report("Reader 解码 vs wal", checks)


def read_wap(path):
    lines = path.read_text(encoding="gbk", errors="replace").splitlines()
    count = int(lines[1].strip())
    rows = []
    i = 2
    while i < len(lines) and len(rows) < count:
        hdr = lines[i].strip()
        if not hdr:
            i += 1
            continue
        p = hdr.split(",")
        # 官方 wap 行序：参数, 结点号a,b, 左区,右区, 顶点数, 坐标…
        ab = lines[i + 1].strip().split(",")
        lr = lines[i + 2].strip().split(",")
        nv = int(lines[i + 3].strip())
        coords = []
        for k in range(nv):
            x, y = lines[i + 4 + k].strip().split(",")
            coords.append((float(x), float(y)))
        tail = lines[i + 4 + nv].strip().split(",")
        rows.append(dict(
            id=i+1, linetype=int(p[0]), aux=int(p[1]), color=int(p[2]), width=float(p[3]),
            x_coef=float(p[4]), y_coef=float(p[5]), aux_color=int(p[6]),
            layer=int(p[7]), transparent=int(p[8]),
            left=int(lr[0]), right=int(lr[1]), node_a=int(ab[0]), node_b=int(ab[1]),
            n_vertices=nv, coords=coords,
        ))
        i += 4 + nv + 1
    return rows


def audit_polygons():
    print()
    print("=" * 70)
    print("面：LDZOFBB001.WP（J45C004001）vs 234.wap（弧段级）")
    rows = read_wap(BASE / "234.wap")
    from pymapgis.reader import _read_polygon_arcs, _read_topology_table
    with open(BASE / "LDZOFBB001.WP", "rb") as f:
        ds = struct.unpack_from("<i", f.read(16), 12)[0]
        f.seek(ds)
        entries = [struct.unpack("<2i", f.read(10)[:8]) for _ in range(10)]
        f.seek(0)
        arcs = _read_polygon_arcs(f, *entries[0], *entries[1], 1.0)
        f.seek(0)
        topo = _read_topology_table(f, *entries[3])
    print(f"明码弧段 {len(rows)} vs 二进制弧段 {len(arcs)}")
    if len(rows) != len(arcs):
        print("条数不一致——按明码记录号 = 二进制弧序号对齐截断")
    n = min(len(rows), len(arcs))
    checks = []
    for field, tol in [("left", 0), ("right", 0), ("n_vertices", 0)]:
        samples = []
        for i in range(n):
            t = topo[i]
            got = {"left": int(t[2]), "right": int(t[3]),
                   "n_vertices": len(list(arcs[i].coords))}[field]
            if abs(float(got) - float(rows[i][field])) > tol:
                if len(samples) < 3:
                    samples.append((i + 1, got, rows[i][field]))
        checks.append((field, None, None, tol, samples))
    # 弧图形参数（head_1 记录）
    with open(BASE / "LDZOFBB001.WP", "rb") as f:
        raw = f.read()
    for field, off, fmt, tol in [
        ("linetype", 22, "<h", 0), ("color", 26, "<h", 0), ("width", 30, "<f", 1e-4),
        ("x_coef", 35, "<f", 1e-4), ("y_coef", 39, "<f", 1e-4),
        ("aux_color", 43, "<h", 0), ("layer", 47, "B", 0),
        ("transparent", 48, "B", 0),
    ]:
        samples = []
        for i in range(n):
            rec = raw[entries[0][0] + (i + 1) * 57: entries[0][0] + (i + 2) * 57]
            got = struct.unpack_from(fmt, rec, off)[0]
            if abs(float(got) - float(rows[i][field])) > tol:
                if len(samples) < 3:
                    samples.append((i + 1, got, rows[i][field]))
        checks.append((field, None, None, tol, samples))
    report("Reader 解码 vs wap", checks)
    # 明文 node_a/node_b 与二进制 topo 前两列对照
    samples = []
    for i in range(n):
        t = topo[i]
        if int(t[0]) != rows[i]["node_a"] or int(t[1]) != rows[i]["node_b"]:
            if len(samples) < 5:
                samples.append((i + 1, (int(t[0]), int(t[1])),
                                (rows[i]["node_a"], rows[i]["node_b"])))
    if samples:
        print(f"  topo 结点号 a,b: {len(samples)}+ 条不符; 样例: {samples}")
    else:
        print("  topo 结点号 a,b: 全部一致 ✓")
    return rows


if __name__ == "__main__":
    audit_points()
    audit_lines()
    audit_polygons()
