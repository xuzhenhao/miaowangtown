# 腾讯混元 3D V3.1 多视图上传套图（咩咩四足标准站立）

把下列 PNG 拖进混元「多张图片」对应槽位（姿态已对齐，浅灰纯净背景）：

| 混元槽位 | 文件 |
| :--- | :--- |
| 上传正图 | `01_front.png` |
| 上传左图 | `02_left.png` |
| 上传右图 | `03_right.png` |
| 上传背图 | `04_back.png` |
| 上传左45°图 | `05_left45.png` |
| 上传右45°图 | `06_right45.png` |

若你拍了绕圈视频，用：

```bash
python3 prototype/tools/extract_multiview_from_video.py path/to/orbit.mp4
```

帧会输出到 `from_video/`。
