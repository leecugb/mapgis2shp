# mapgis2shp 项目上下文（保存于 2026-07-21，更新于 2026-09-02）

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

---

# 地质图渲染上下文（保存于 2026-09-02）

> 本节记录「库尔干幅（J43C001002）1:25万地质图渲染」任务的全部上下文，
> 覆盖渲染方案决策、已落地的代码与数据文件、核验结果与后续方向。

## 任务目标

基于 DZ/T 0179《地质图用色标准》与 MapGIS 矢量数据，
将库尔干幅（J43C001002）1:25万地质图渲染为标准 PDF。

## 关键决策

| 决策点 | 结论 |
|--------|------|
| 输出格式 | PDF（`output/kurgan_geology.pdf`，300 DPI） |
| 配色标准 | DZ/T 0179 色表（`data/dz_t_0179_colors.json`） |
| 投影 | 数据原生坐标（经纬度约 73.4–75.1°E, 38.9–40.1°N），未强制重投影；⚠️ 文献规定原数据为**北京54坐标系**（见 `jianzao_gouzao_db_summary.md`），与 WGS84/CGCS2000 有数十米级基准偏差，单幅独立成图不受影响，与外部数据套合前需做基准转换 |
| 花纹填充 | matplotlib hatch（侵入岩点状/V形、变质岩斜线/短线） |
| 断层装饰 | 正断层锯齿、逆断层三角齿、推覆双排齿、平移箭头、韧性剪切带斜线 |
| 代号标注重构 | 并查集空间聚类合并碎片化代号点（`eps=0.012`） |

## 数据文件清单（MapGIS 矢量）

### 面（.WP）
| 文件 | 要素数 | 角色 |
|------|-------|------|
| LDZOFBB001.WP | 608 | 正式沉积地层（主） |
| LDZOFBB002.WP | 10 | 补充沉积地层 |
| LDZOFBB003.WP | 46 | 侵入岩 |
| LDZOFBB004.WP | 49 | 变质岩 |
| LDZOFBB009.WP | 20 | 深部断裂 |
| LDZOFBB010.WP | 4 | 构造岩浆岩带 |
| LDLYAAE002.WP | 128 | 冰川/常年积雪面（GB 全为 73020，非水体面） |

### 线（.WL）
| 文件 | 要素数 | 角色 |
|------|-------|------|
| LDZOFBA002.WL | 2222 | 地质界线总层（GZBD 分类，含义见 `gzbd_code_analysis.md`：01实测界线165、02第四系界线986、04角度不整合33、10断层593、11侵入接触79、16推测1、24平行不整合50、43渐变2、60脉动2、81冰雪区界线311） |
| LDZOFBA003.WL | 310 | 实测断层专层（GZEEB 9类，定稿见 `gzeeb_code_analysis.md`；F9/F48/F50 命名断裂） |
| LDZOFBA005.WL | 4 | 褶皱轴 |
| LDZOFBB098.WL | 245 | 引线 |
| LYGREBA001.WL | 71 | 遥感解译断层 |
| LHTQGTA001.WL | 4 | 地球化学界线 |
| LDLYAAE001.WL | 1143 | 水系+冰雪混合层（GB=21010 河流609、21021 时令河223、73020 冰雪界线311） |

### 点（.WT）
| 文件 | 要素数 | 角色 |
|------|-------|------|
| LDZOFBB099.WT | 2024 | 代号(1362)+产状(307)+断层辅助点(299)+化石(27)+泥火山(21)+褶皱辅助点(8) |
| LDZOFBA016.WT | 305 | 产状点（GZBBAB走向/GZBBAC倾向/GZBBAD倾角/GZBBGA产状类型） |
| LDLYAAI002.WT | 242 | 水系标注点 |

## 关键属性字段

| 字段 | 含义 | 示例 |
|------|------|------|
| QDUECC | 地层/岩石代号（含控制符） | `→D↓2→t`（托格买提组） |
| QDUECD | 地层/岩石名称 | 托格买提组 |
| CHFCEC | 点类型 | 代号/产状/断层辅助点/化石/泥火山 |
| CHFCED | 点编码 | `C#-1`、`y`、倾角数值 |
| GZBD | 线类型（建造构造图层） | 01实测界线、02第四系界线、04角度不整合、10断层、11侵入接触、24平行不整合、81冰雪区界线（全表见 `data/gzbd_codes.json`） |
| GZEEB | 断层类型（2026-09-03 定稿） | 01断层、04推测、05逆、07推覆体边界、16右型走滑、18左型走滑、28区域性大断裂、31复活、41边界断裂（全表见 `data/gzeeb_codes.json`） |
| GZELD | 断层运动学性质 | 101压性(逆)、103右行走滑、104左行走滑、109一般；与GZEEB互证 |
| GZEEE | 断层规模级别 | 101一般、102区域性、103边界级；有倾角者仅见于101/102 |
| KCDDEF | 断层带总体走向(°) | 按整条断层赋值（F48全15段=130.56°），非单段几何走向 |
| GZECE | 断层倾角 | 72.0、0.0（0表示无倾角，251/310未实测） |
| GZEAB | 断层名称 | F9（边界断裂）、F48（区域性大断裂+逆冲复活）、F50（边界断裂+推测段） |

## 新增/修改的文件

### 数据文件（`data/`）
- `dz_t_0179_colors.json` — DZ/T 0179 色表（正式地层/侵入岩/断层等 RGB）
- `geological_unit_color_mapping_final.json` — 地质单元配色映射（38 沉积+15 侵入+3 变质）
- `fault_rendering_styles.json` — 断层渲染样式（2026-09-03 按 GZEEB 定稿表更新）
- `gzbd_codes.json` — LDZOFBA002 GZBD 代码含义表（2026-09-02 用户核实定稿）
- `gzeeb_codes.json` — LDZOFBA003 GZEEB 代码含义表 + 字段语义（2026-09-03 用户核实定稿）
- `fault_type_codes_A115_gzeeb.md` — 城市地质规范表A.115 三位数断层代码表（154 项，体系参考）
- `render_targets.json` — 渲染对象存档：4 面图层 57 单元 + 2 线图层（LDZOFBA002 按 GZBD 10 类、LDZOFBA003 按 GZEEB 9 类）
- `jianzao_gouzao_db_doc.pdf` / `jianzao_gouzao_db_doc_cn.txt` — 《中国陆域1:25万分幅建造构造图空间数据库》文献原文及全文提取
- `city_geo_db_spec.pdf` / `mineral_map_db_spec.pdf` / `active_fault_mapping_spec.pdf` / `shenzhen_city_geo_spec.pdf` — 检索到的相关标准 PDF

### 分析存档（根目录）
- `gzbd_code_analysis.md` — GZBD 代号核定报告（含空间验证证据与渲染拆分建议）
- `gzeeb_code_analysis.md` — GZEEB 代号核定报告 + LDZOFBA003 字段关系分析（2026-09-03 定稿）
- `jianzao_gouzao_db_summary.md` — 《中国陆域1:25万分幅建造构造图空间数据库》文献梳理（图层语义坐实 + 北京54坐标系警示）
- `render_targets.md` — 渲染对象存档文档
- `vector_inventory.json` — 36 个矢量文件全字段盘点

### 渲染模块（`src/pymapgis/rendering/`，已恢复）
- `ir.py` — 渲染中间表示（Layer/Rule/Map/SymbolRef）
- `palette.py` — DZ/T 0179 色表加载与查询
- `symbol_engine.py` — 地质符号引擎（产状/断层装饰/褶皱轴/化石等 14 函数）
- `pattern_engine.py` — 花纹填充引擎（hatch）
- `pdf_writer.py` — PDF 输出引擎 + 代号碎片合并
- `__init__.py` — 模块导出

### 脚本
- `render_strict_standard_map.py` — 主渲染脚本
- `verify_rendering.py` — 渲染核验脚本（5 项检查）

## 代号碎片合并逻辑

MapGIS 中一个完整地层代号被拆分为多个独立点：
- `C#-1`（主代号 C 下标 1）+ `y`（组名）→ `C1y`
- `K#-1` + `#=kz` → `K1kz`
- `Qp#-3` + `#+pal` → `Qp3pal`

实现（`pdf_writer.py`）：
1. `_parse_code_fragment` — 解析片段为主代号/组名/上标三元组
2. `_merge_fragment_codes` — 合并三元组为完整代号
3. `_cluster_and_merge_labels` — 并查集空间聚类（`eps=0.012`），1362 碎片点 → 587 完整代号

控制符规则：`→` 前缀、`↓` 下标、`↑` 上标、`#-` 下标分隔、`#=` 组名连接、`#+` 上标分隔、`.` 岩群标记。

## 核验结果（2026-09-02，全部通过）

1. **颜色一致性**：51/51 代号与色表 100% 一致
2. **产状垂直性**：8 个走向角度的倾向短刺均与走向线垂直
3. **断层颜色**：11 种断层类型全部符合红色系标准
4. **数据覆盖**：沉积 38/38、侵入 15/15、断层 9/9 全映射
5. **PDF 输出**：3.34 MB，格式有效

## 已修复的问题

- 5 个地层代号拼写错误（如 `→D↓3→kz↓1` → `→D↓3→kz↑1` 克孜尔塔格组）
- matplotlib 颜色需归一化到 0-1（`_rgb` 辅助函数）
- `_cluster_and_merge_labels` 需先判断 `type_field` 列存在

## 后续可选方向

- 代号标注仍可能残留少量孤立片段（约 49 个，取决于 eps 阈值），可进一步微调
- 产状符号的走向（strike）目前默认 0，可研究从邻近线要素推导真实走向
- 图例/注记排版可进一步美化（分栏、避让）
- 如需发布，可将渲染功能拆分为独立包（CONTEXT.md 前文已提及 `mapgis2shp-renderer`）

## 命令备忘

```bash
# 渲染（默认 300 DPI）
python3 render_strict_standard_map.py

# 指定分辨率
python3 render_strict_standard_map.py --dpi 200

# 核验
python3 verify_rendering.py
```

