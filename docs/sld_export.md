# SLD 样式导出说明

本项目除生成 PNG/MBTiles 外，还可将 DZ/T 0179 配色规则导出为 **OGC SLD 1.0** 样式文件，供 GeoServer 等 WMS 服务使用。

## 1. 生成 SLD 文件

```bash
python3 export_sld_styles.py
```

输出文件：

```
data/sld/kurgan_dzt0179_styles.sld
```

脚本会读取 `geological_unit_color_mapping_final.json`，按解析后的 `key` 字段聚合生成 Rule，并自动验证：

- XML 格式正确；
- 每个 key 的填充色与映射表一致；
- 包含默认 `ElseFilter` 回退规则。

## 2. 命令行参数

```bash
python3 export_sld_styles.py \
  --mapping geological_unit_color_mapping_final.json \
  --palette dz_t_0179_colors.json \
  --out-dir data/sld \
  --out-name kurgan_dzt0179_styles.sld \
  --property-name key \
  --layer-name kurgan_geology \
  --style-name kurgan_dzt0179 \
  --style-title "库尔干幅 DZ/T 0179 标准色" \
  --stroke "#555555" \
  --stroke-width 0.15
```

| 参数 | 说明 | 默认值 |
|------|------|--------|
| `--mapping` | 地质单元颜色映射表 | `geological_unit_color_mapping_final.json` |
| `--palette` | DZ/T 0179 标准色表 | `dz_t_0179_colors.json` |
| `--out-dir` | 输出目录 | `data/sld` |
| `--out-name` | 输出文件名 | `kurgan_dzt0179_styles.sld` |
| `--property-name` | SLD Filter 使用的属性字段名 | `key` |
| `--layer-name` | SLD 中 NamedLayer 名称 | `kurgan_geology` |
| `--style-name` | SLD 中 UserStyle 名称 | `kurgan_dzt0179` |
| `--style-title` | SLD 中 UserStyle 标题 | `库尔干幅 DZ/T 0179 标准色` |
| `--stroke` | 面边界线颜色 | `#555555` |
| `--stroke-width` | 面边界线宽度 | `0.15` |

## 3. SLD 结构

生成的 SLD 采用 OGC SLD 1.0 标准结构：

```xml
<?xml version="1.0" encoding="UTF-8"?>
<StyledLayerDescriptor xmlns="http://www.opengis.net/sld"
                       xmlns:ogc="http://www.opengis.net/ogc"
                       version="1.0.0">
  <NamedLayer>
    <Name>kurgan_geology</Name>
    <UserStyle>
      <Name>kurgan_dzt0179</Name>
      <Title>库尔干幅 DZ/T 0179 标准色</Title>
      <FeatureTypeStyle>
        <Rule>
          <Name>D2</Name>
          <Title>D2</Title>
          <ogc:Filter>
            <ogc:PropertyIsEqualTo>
              <ogc:PropertyName>key</ogc:PropertyName>
              <ogc:Literal>D2</ogc:Literal>
            </ogc:PropertyIsEqualTo>
          </ogc:Filter>
          <PolygonSymbolizer>
            <Fill>
              <CssParameter name="fill">#bf9999</CssParameter>
            </Fill>
            <Stroke>
              <CssParameter name="stroke">#555555</CssParameter>
              <CssParameter name="stroke-width">0.15</CssParameter>
            </Stroke>
          </PolygonSymbolizer>
        </Rule>
        <!-- ... 更多 Rule ... -->
        <Rule>
          <Name>default</Name>
          <Title>未分类/默认</Title>
          <ElseFilter/>
          <PolygonSymbolizer>
            <Fill>
              <CssParameter name="fill">#c8c8c8</CssParameter>
            </Fill>
            <Stroke>
              <CssParameter name="stroke">#555555</CssParameter>
              <CssParameter name="stroke-width">0.15</CssParameter>
            </Stroke>
          </PolygonSymbolizer>
        </Rule>
      </FeatureTypeStyle>
    </UserStyle>
  </NamedLayer>
</StyledLayerDescriptor>
```

## 4. 在 GeoServer 中使用

### 4.1 准备数据

使用 `export_for_mapnik.py` 生成带 `key` 字段的 GeoJSON：

```bash
python3 export_for_mapnik.py
```

输出文件 `data/mapnik/geology_polygons.geojson` 中包含 `key`、`fill` 等字段。

### 4.2 发布图层

1. 登录 GeoServer，进入 **工作区** → 添加工作区（如 `kurgan`）。
2. 进入 **数据** → **存储** → **添加新的存储** → 选择 **GeoJSON**。
3. 选择 `data/mapnik/geology_polygons.geojson`，创建 Store。
4. 发布图层，命名为 `kurgan_geology`。

### 4.3 上传 SLD 样式

1. 进入 **样式** → **添加新样式**。
2. 样式名填写 `kurgan_dzt0179`。
3. 上传 `data/sld/kurgan_dzt0179_styles.sld`。
4. 点击 **提交**。

### 4.4 绑定样式

1. 进入 `kurgan_geology` 图层编辑页面。
2. 在 **发布** 标签页中，找到 **默认样式**。
3. 选择 `kurgan_dzt0179`。
4. 保存。

### 4.5 预览

进入 **Layer Preview**，选择 `kurgan:geology_polygons`，渲染效果应与 `kurgan_strict_standard_map.png` 一致。

## 5. 字段名说明

SLD 中的 `PropertyName` 默认使用 `key` 字段。该字段的值为：

- 普通地层：年代键，如 `Ch`、`D2`、`CP`、`EK`、`Qh` 等。
- 侵入岩：岩性大类与时代/代组合，如 `acid_intermediate:T1`、`neutral:Mz`、`basic:fallback` 等。
- 默认回退：无匹配时使用 `ElseFilter` 规则。

如果数据源中的字段名不是 `key`，可通过 `--property-name` 参数指定。

## 6. 与 OneGeology 的对应关系

| OneGeology 实践 | 本项目实现 |
|-----------------|------------|
| 使用 SLD 1.0 标准化样式 | `export_sld_styles.py` 生成 OGC SLD 1.0 |
| 按地质年代/岩性编码着色 | 按 `key` 字段过滤，`key` 由 DZ/T 0179 解析得到 |
| GeoServer WMS 服务 | 将 GeoJSON + SLD 发布为 WMS |
| 默认回退样式 | 使用 `ElseFilter` 防止未匹配要素透明 |

## 7. 验证

脚本内置验证会检查：

- XML 可解析；
- 非默认 Rule 数量与映射表 key 数量一致；
- 每个 key 的 SLD 填充色与 `geological_unit_color_mapping_final.json` 一致；
- 存在默认 `ElseFilter` 规则。

运行脚本时若输出 `Validation passed` 即表示验证通过。

## 8. 注意事项

- SLD 中不包含上下标、希腊字母等地质符号渲染，这些需在客户端或注记图层中单独处理。
- 当前 SLD 仅针对地质面填充，构造线、断层、产状、水系等需另外配置样式。
- 若将数据导入 PostGIS，字段名大小写可能与 GeoJSON 不同，建议在 SLD 中使用小写字段名，并通过 `--property-name` 调整。
