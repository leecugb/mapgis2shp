# 表22 断裂/构造线符号图像分析结果

说明：本报告对 DZ/T 0179 PDF 页 34–35（表22 其他地质要素用色）提取的图片
进行自动行分割与线型检测。**文字内容未做 OCR，需人工对照 crop 图片判读。**

| 页面图片 | 行号 | 纵坐标范围 | 检测线型 | 墨迹占比 | 黑白过渡 | 裁剪文件 |
|----------|------|------------|----------|----------|----------|----------|
| page34_img1.png | 0 | 102–192 | `dashed` | 0.096 | 62 | `page34_img1_row000.png` |
| page34_img1.png | 1 | 244–325 | `dashed` | 0.242 | 6 | `page34_img1_row001.png` |
| page34_img1.png | 2 | 380–404 | `dashed` | 0.01 | 6 | `page34_img1_row002.png` |
| page34_img1.png | 3 | 407–438 | `dashed` | 0.138 | 69 | `page34_img1_row003.png` |
| page34_img1.png | 4 | 444–577 | `dashed` | 0.075 | 12 | `page34_img1_row004.png` |
| page34_img2.png | 0 | 41–68 | `dashed` | 0.054 | 32 | `page34_img2_row000.png` |
| page34_img2.png | 1 | 109–176 | `dashed` | 0.108 | 62 | `page34_img2_row001.png` |
| page34_img2.png | 2 | 183–248 | `dashed` | 0.019 | 12 | `page34_img2_row002.png` |
| page34_img2.png | 3 | 249–328 | `dashed` | 0.158 | 77 | `page34_img2_row003.png` |
| page34_img2.png | 4 | 331–408 | `dashed` | 0.081 | 40 | `page34_img2_row004.png` |
| page34_img2.png | 5 | 416–472 | `dashed` | 0.125 | 60 | `page34_img2_row005.png` |
| page34_img2.png | 6 | 488–549 | `dashed` | 0.119 | 57 | `page34_img2_row006.png` |
| page34_img2.png | 7 | 560–625 | `dashed` | 0.081 | 37 | `page34_img2_row007.png` |
| page34_img2.png | 8 | 633–706 | `dashed` | 0.067 | 42 | `page34_img2_row008.png` |
| page35_img1.png | 0 | 40–64 | `dashed` | 0.058 | 32 | `page35_img1_row000.png` |
| page35_img1.png | 1 | 102–176 | `dashed` | 0.052 | 32 | `page35_img1_row001.png` |
| page35_img1.png | 2 | 179–243 | `dashed` | 0.143 | 62 | `page35_img1_row002.png` |
| page35_img1.png | 3 | 256–328 | `dashed` | 0.152 | 64 | `page35_img1_row003.png` |
| page35_img1.png | 4 | 336–393 | `dashed` | 0.092 | 38 | `page35_img1_row004.png` |
| page35_img1.png | 5 | 408–475 | `dashed` | 0.05 | 24 | `page35_img1_row005.png` |
| page35_img2.png | 0 | 44–72 | `dashed` | 0.054 | 28 | `page35_img2_row000.png` |
| page35_img2.png | 1 | 112–176 | `dashed` | 0.04 | 22 | `page35_img2_row001.png` |
| page35_img2.png | 2 | 185–248 | `dashed` | 0.067 | 32 | `page35_img2_row002.png` |
| page35_img2.png | 3 | 261–314 | `dashed` | 0.031 | 18 | `page35_img2_row003.png` |
| page35_img2.png | 4 | 336–392 | `dashed` | 0.035 | 20 | `page35_img2_row004.png` |
| page35_img2.png | 5 | 403–468 | `dashed` | 0.069 | 40 | `page35_img2_row005.png` |
| page35_img2.png | 6 | 472–544 | `dashed` | 0.035 | 20 | `page35_img2_row006.png` |
| page35_img2.png | 7 | 560–616 | `dashed` | 0.056 | 40 | `page35_img2_row007.png` |

## 线型说明

- `solid`：实线

- `dashed`：虚线（长间隔）

- `dotted`：点线

- `dash_dot`：点划线

- `mixed`：混合/复杂图案

- `none`：未检测到明显水平线


## 下一步

1. 人工查看 `pdf_fault_symbol_rows/` 中的裁剪图片；

2. 将每一行的中文名称/代码与检测到的线型对应；

3. 更新 `fault_rendering_styles.json` 中的 `type_map`。
