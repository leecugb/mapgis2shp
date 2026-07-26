# mapgis2shp 项目上下文（保存于 2026-07-21）

## 项目状态总览

- **包名（PyPI）**：`mapgis2shp`
- **当前版本**：`2.0.3`
- **PyPI 页面**：https://pypi.org/project/mapgis2shp/
- **Python 导入名**：`pymapgis`（`from pymapgis import Reader`）
- **安装命令**：`pip install mapgis2shp`
- **许可证**：Apache-2.0
- **作者邮箱**：1045105061@qq.com

## 版本发布历史

| 版本 | 内容 |
|------|------|
| 2.0.0 | 首次发布（包名原为 pymapgis-reader，后改名 mapgis2shp） |
| 2.0.1 | （由用户手动发布，内容同 2.0.0 附近） |
| 2.0.2 | 代码级梳理优化（见下文） |
| 2.0.3 | 删除 `rendering` 模块，包聚焦读取转换 |

## 项目结构

```
/media/lee/ASAHI/J43C001002/MAPGIS/JWD/
├── src/pymapgis/
│   ├── __init__.py        # 导出 Reader 与异常
│   ├── __main__.py        # python -m pymapgis
│   ├── _version.py        # __version__ = "2.0.3"
│   ├── cli.py             # pymapgis CLI（input.wp output.shp）
│   └── reader.py          # 核心读取逻辑（约 800 行）
├── tests/
│   ├── conftest.py        # fixtures + DATA_DIR
│   ├── test_pure.py       # 纯函数单元测试
│   ├── test_reader.py     # 真实文件集成测试
│   └── test_cli.py        # CLI 测试
├── docs/
│   └── MapGIS_Vector_Format.md   # MapGIS 二进制格式文档
├── pyproject.toml         # hatchling 构建配置
├── README.md              # 英文 README（含格式技术文档）
├── LICENSE                # Apache-2.0
├── MANIFEST.in            # sdist 包含规则（排除 *.WT/*.WL/*.WP）
├── publish.sh             # 上传脚本（需 bash publish.sh）
├── PYPI_UPLOAD.md         # 发布说明
├── verify_pymapgis.py     # 36 文件冒烟回归脚本
├── pymapgis_baseline.json # 回归基线
└── *.WT/*.WL/*.WP         # 36 个真实测试数据文件（不入包）
```

## 2.0.2 代码级优化内容

### reader.py
1. 删除死代码 `_read_attribute_table`、未使用的 `__version__` 导入、`Reader._file` 属性
2. `_PolygonTopologyBuilder.__init__` 预计算 `polygon_id -> [(arc_idx, reverse)]` 映射，`build()` 从全表扫描降为 O(1) 查询
3. `_build_multipolygon` 预创建 Shapely 对象 + bbox 预过滤，消除内层循环 n² 次 Polygon 构造
4. `_merge_arcs_into_rings` 浮点索引计算简化为 `x // 2` / `x % 2`
5. `_read_lines` 新增 `point_count`/`point_offset` 负数校验
6. 新增 `Reader.__repr__`
7. `_read_crs` 返回类型修正为 `Tuple[Any, float]`

### cli.py
- 合并重复 except 块为 `except (InvalidFileError, MapGISError)`

### pyproject.toml
- description 更新为官方英文描述
- 删除无代码对应的 mbtiles extra

## 2.0.3 变更

- 删除 `src/pymapgis/rendering/`（ir.py、pattern_engine.py、symbol_engine.py）
- 包完全聚焦 MapGIS 读取转换
- wheel 从 69.4 KB 减至 59.3 KB
- 注意：仓库根目录依赖 `pymapgis.rendering` 的脚本（render_faults.py、render_strict_standard_map.py、verify_rendering_rules.py、verify_pattern_tiles.py、verify_fault_line_colors.py、render_thematic_maps.py）将无法从包导入渲染功能

## 验证状态

- `ruff check src/ tests/` → All checks passed
- `pytest` → 42/42 通过
- `verify_pymapgis.py`（36 个真实文件）→ 全部 OK，invalid=0
- `pip install mapgis2shp==2.0.3` → 验证成功

## 已识别的后续优化方向

### 已实施（2026-07-21，代码级优化）
1. ✅ **弧段合并哈希化**：`_merge_arcs_into_rings` 从 O(n³)（每轮重建 Chebyshev 全距离矩阵）改为空间哈希 + 双向生长 + 闭合竞争，O(n)。`tol=1e-5` 覆盖 1e-6 端点噪声，大缝隙走 O(n) 回退（与原全局最近贪心语义等价）。LDZOFBB001.WP 0.807s→0.331s（2.44×），全部 36 文件 0.74s。
2. ✅ **`_raw_dms_to_degrees` 纯算术**：原字符串 `:.0f` 切分会丢失小数秒且负值脆弱；改为 `%` / `//` 算术分解，保留小数秒、正确处理西经负值。测试数据 proj=0 未调用，无基线风险。
3. ✅ **日期/时间字段容错**：month/day=0 等非法值 try/except 返回 None，不再中断整文件解析。
4. ✅ **属性表头批量读取**：`_read_attribute_header` 由 ~12 + 9×字段数 次 `read()` 改为 2 次批量读 + `struct.Struct` 解包；移除死常量 `_ATTR_FIELD_NAME_SIZE`。

### 未实施（按收益/成本比排序）

### ⭐⭐ 中优先级
5. **shell/hole STRtree 优化**：用 `shapely.STRtree` 替代 `_build_multipolygon` 中手写 bbox 双重循环。注意 n 通常很小（1–10），主要成本是 shapely Polygon 构造（不可优化），STRtree 仅能优化 `within` 子部分，收益有限。

### ⭐ 低优先级
6. 属性表数值列 NumPy 向量化解码
7. 惰性读取（lazy=True）、np.memmap、logging 支持

### 不建议做
- 多进程并行（GIL + 进程开销）
- Cython/C 扩展（维护成本）
- MapGIS K9 支持（格式完全不同，等于重写）

## 发布流程备忘

```bash
# 1. 修改版本号（两处）
#    pyproject.toml: version = "x.y.z"
#    src/pymapgis/_version.py: __version__ = "x.y.z"

# 2. 验证
pytest -q
python verify_pymapgis.py
ruff check src/ tests/

# 3. 构建上传
python -m build
TWINE_USERNAME=__token__ TWINE_PASSWORD=<token> twine upload dist/mapgis2shp-x.y.z*

# 4. 验证安装（PyPI 索引更新需等约 30 秒）
pip install mapgis2shp==x.y.z
```

## PyPI token 说明

- 用户曾提供 token 用于 2.0.0/2.0.2/2.0.3 上传（对话中可见）
- 建议用户在 PyPI 后台删除该 token 并生成 scoped token（仅限 mapgis2shp 项目）
- token 管理页面：https://pypi.org/manage/account/token/

## 其他备忘

- `pymapgis` 名字在 PyPI 已被占用，故发布名为 `mapgis2shp`，导入名仍为 `pymapgis`
- `pyproject.toml` 中 `Homepage`/`Repository` URL 仍为占位符（https://github.com/pymapgis/pymapgis），待真实仓库建立后更新
- rendering 模块代码已从包中删除，如本地渲染脚本需要，可考虑拆分为独立包 `mapgis2shp-renderer`
