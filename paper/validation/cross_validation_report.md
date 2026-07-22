# Cross-validation: pymapgis vs official MapGIS export

Layers compared: 36

- Count match (all): True
- Total features pymapgis: 16874
- Total features native:  16874
- Attr columns match (all): True
- Attr strict match rate (mean): 0.896300
- Attr equivalence rate (mean, incl. native-truncated): 0.999995
- Real attr mismatches (total): 2
- Attr cells native-truncated (pymapgis more precise), total: 10245
- Mean geom match rate: 1.000000
- Layers with geom match rate >= 0.999: 36/36

| layer | type | count(pm/nat) | attr_strict | attr_equiv | attr_mismatch | geom_match |
|---|---|---|---|---|---|---|
| LDLYAAA005 | WL | 16/16 | 0.7083 | 1.0000 | 0 | 1.0000 |
| LDLYAAE001 | WL | 1143/1143 | 0.8845 | 1.0000 | 0 | 1.0000 |
| LDLYAAE002 | WP | 128/128 | 0.8082 | 1.0000 | 0 | 1.0000 |
| LDLYAAI002 | WT | 242/242 | 0.9938 | 1.0000 | 0 | 1.0000 |
| LDZOFBA002 | WL | 2222/2222 | 0.8178 | 1.0000 | 0 | 1.0000 |
| LDZOFBA003 | WL | 310/310 | 0.8845 | 1.0000 | 0 | 1.0000 |
| LDZOFBA005 | WL | 4/4 | 1.0000 | 1.0000 | 0 | 1.0000 |
| LDZOFBA016 | WT | 305/305 | 1.0000 | 1.0000 | 0 | 1.0000 |
| LDZOFBB001 | WP | 608/608 | 0.8830 | 0.9999 | 1 | 1.0000 |
| LDZOFBB002 | WP | 10/10 | 0.9333 | 1.0000 | 0 | 1.0000 |
| LDZOFBB003 | WP | 46/46 | 0.9273 | 1.0000 | 0 | 1.0000 |
| LDZOFBB004 | WP | 49/49 | 0.9323 | 1.0000 | 0 | 1.0000 |
| LDZOFBB009 | WP | 20/20 | 0.9250 | 1.0000 | 0 | 1.0000 |
| LDZOFBB010 | WP | 4/4 | 0.9750 | 1.0000 | 0 | 1.0000 |
| LDZOFBB098 | WL | 245/245 | 0.6673 | 1.0000 | 0 | 1.0000 |
| LDZOFBB099 | WT | 2024/2024 | 0.9998 | 1.0000 | 0 | 1.0000 |
| LFZYBAA002 | WL | 5/5 | 1.0000 | 1.0000 | 0 | 1.0000 |
| LFZYBAB002 | WL | 24/24 | 1.0000 | 1.0000 | 0 | 1.0000 |
| LFZYBCBA01 | WT | 6/6 | 1.0000 | 1.0000 | 0 | 1.0000 |
| LFZYBCBA02 | WL | 10/10 | 0.7667 | 1.0000 | 0 | 1.0000 |
| LFZYBCT001 | WT | 6981/6981 | 1.0000 | 1.0000 | 0 | 1.0000 |
| LFZYBCT002 | WL | 2331/2331 | 0.6797 | 0.9999 | 1 | 1.0000 |
| LHCPGDAC01 | WL | 3/3 | 1.0000 | 1.0000 | 0 | 1.0000 |
| LHCPGDAC05 | WP | 2/2 | 0.8333 | 1.0000 | 0 | 1.0000 |
| LHCPGDAC06 | WL | 2/2 | 0.6667 | 1.0000 | 0 | 1.0000 |
| LHCPGDAC08 | WP | 4/4 | 0.8636 | 1.0000 | 0 | 1.0000 |
| LHCPGDAC09 | WL | 4/4 | 0.8333 | 1.0000 | 0 | 1.0000 |
| LHCPGDAC11 | WP | 8/8 | 0.8750 | 1.0000 | 0 | 1.0000 |
| LHCPGDAC12 | WL | 10/10 | 0.8000 | 1.0000 | 0 | 1.0000 |
| LHTQGTA001 | WL | 4/4 | 0.9444 | 1.0000 | 0 | 1.0000 |
| LYGREBA001 | WL | 71/71 | 0.9534 | 1.0000 | 0 | 1.0000 |
| LYGREBA004 | WL | 25/25 | 0.9345 | 1.0000 | 0 | 1.0000 |
| LZLPGDJ002 | WL | 3/3 | 1.0000 | 1.0000 | 0 | 1.0000 |
| LZLPGDJ004 | WP | 2/2 | 0.9062 | 1.0000 | 0 | 1.0000 |
| LZLPGDJ006 | WP | 1/1 | 0.9412 | 1.0000 | 0 | 1.0000 |
| LZLPGDJ009 | WP | 2/2 | 0.9286 | 1.0000 | 0 | 1.0000 |