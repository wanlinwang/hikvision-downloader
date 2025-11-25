# 海康威视NVR多通道批量下载

## 简介

`media_download_all_channels.py` 是专门用于从海康威视NVR/DVR设备下载所有通道监控视频的脚本。

## 重要说明

从您的截图可以看出，所有摄像头共享同一个IP地址（10.19.2.2），这说明它们连接到一个NVR（网络录像机）或DVR（数字录像机）设备。每个摄像头对应NVR的不同**通道**。

### 通道ID规则

海康威视ISAPI使用trackID来标识不同通道：
- 通道1的视频：trackID = **101**
- 通道2的视频：trackID = **201**
- 通道3的视频：trackID = **301**
- 通道N的视频：trackID = **N01**

## 功能特点

- ✅ **自动检测通道**：自动扫描NVR并识别有录像的通道
- ✅ **手动指定通道**：支持指定要下载的通道号
- ✅ **并发下载**：可同时从多个通道下载（默认3个）
- ✅ **独立文件夹**：每个通道的视频保存在独立文件夹
- ✅ **独立日志**：每个通道有独立的日志文件
- ✅ **详细报告**：提供每个通道的下载统计

## 使用方法

### 1. 设置环境变量

```powershell
# Windows PowerShell
$env:HIK_USERNAME = 'admin'
$env:HIK_PASSWORD = 'your_password'
```

### 2. 自动检测并下载所有通道

```powershell
python media_download_all_channels.py 10.19.2.2 2024-11-25 08:00:00 2024-11-25 18:00:00
```

这个命令会：
1. 自动扫描NVR的所有通道（默认扫描1-32号通道）
2. 检测哪些通道在指定时间段有录像
3. 从所有有录像的通道下载视频

### 3. 下载指定通道

如果您知道具体的通道号（例如从截图中的"监控04"、"监控08"等），可以直接指定：

```powershell
# 下载通道4、8、9
python media_download_all_channels.py --channels 4,8,9 10.19.2.2 2024-11-25 08:00:00 2024-11-25 18:00:00

# 下载通道1到8
python media_download_all_channels.py --channels 1-8 10.19.2.2 2024-11-25 08:00:00 2024-11-25 18:00:00

# 混合使用
python media_download_all_channels.py --channels 1,3-6,8 10.19.2.2 2024-11-25 08:00:00 2024-11-25 18:00:00
```

### 4. 调整并发数和扫描范围

```powershell
# 最多同时从5个通道下载
python media_download_all_channels.py -c 5 10.19.2.2 2024-11-25 08:00:00 2024-11-25 18:00:00

# 扫描更多通道（例如64通道的NVR）
python media_download_all_channels.py -m 64 10.19.2.2 2024-11-25 08:00:00 2024-11-25 18:00:00
```

### 5. 下载照片

```powershell
python media_download_all_channels.py -p 10.19.2.2 2024-11-25 08:00:00 2024-11-25 18:00:00
```

### 6. 使用UTC时间

```powershell
python media_download_all_channels.py -u 10.19.2.2 2024-11-25 00:00:00 2024-11-25 23:59:59
```

## 命令行参数

```
positional arguments:
  NVR_IP               NVR/DVR设备的IP地址
  START_DATE           开始日期 (YYYY-MM-DD)
  START_TIME           开始时间 (HH:MM:SS)
  END_DATE             结束日期 (YYYY-MM-DD)
  END_TIME             结束时间 (HH:MM:SS)

optional arguments:
  -h, --help           显示帮助信息
  -u, --utc            使用UTC时间（默认使用摄像头本地时间）
  -p, --photo          下载照片而非视频
  -c N, --concurrent N 最大并发下载通道数（默认：3）
  -m N, --max-channel N 最大扫描通道号（默认：32）
  --channels CHANNELS  指定要下载的通道，例如 '1,2,3' 或 '1-8'
                      如果不指定，则自动检测所有通道
```

## 文件组织结构

下载的文件会按照NVR IP和通道号组织：

```
media/
├── 10.19.2.2/
│   ├── channel_01/
│   │   ├── 2024-11-25_08-00-00.mp4
│   │   ├── 2024-11-25_08-10-00.mp4
│   │   └── ...
│   ├── channel_02/
│   │   ├── 2024-11-25_08-00-00.mp4
│   │   └── ...
│   ├── channel_04/     # "监控04_jiankong"
│   │   └── ...
│   ├── channel_08/     # "监控08_jiankong"
│   │   └── ...
│   └── ...
```

## 日志文件

每个通道会生成独立的日志文件：

```
media/
├── 10.19.2.2_main.log           # 主日志
├── 10.19.2.2_channel_01.log     # 通道1日志
├── 10.19.2.2_channel_02.log     # 通道2日志
└── ...
```

## 示例输出

```
Connecting to NVR 10.19.2.2...

Scanning NVR 10.19.2.2 for available channels...
(This may take a moment, checking channels 1-32)
  ✓ Channel 01 has recordings
  ✓ Channel 02 has recordings
  ✓ Channel 04 has recordings
  ✓ Channel 08 has recordings

Found 4 channel(s) with recordings: [1, 2, 4, 8]

Starting download from 4 channel(s)...
Time range: 2024-11-25 08:00:00 to 2024-11-25 18:00:00
Content type: Videos
Max concurrent downloads: 3

Starting download from channel 01...
Starting download from channel 02...
Starting download from channel 04...
✓ Channel 01: Successfully downloaded 15 files
Starting download from channel 08...
✓ Channel 02: Successfully downloaded 12 files
✓ Channel 04: Successfully downloaded 18 files
✓ Channel 08: Successfully downloaded 20 files

======================================================================
DOWNLOAD SUMMARY FOR NVR: 10.19.2.2
======================================================================

Total channels processed: 4
Successful: 4
Failed: 0
Total files downloaded: 65

✓ Successful channels:
  - Channel 01: 15 files
  - Channel 02: 12 files
  - Channel 04: 18 files
  - Channel 08: 20 files
======================================================================
```

## 常见问题

### 1. 如何确定摄像头对应的通道号？

从您的截图中可以看到摄像头别名（如"监控04_jiankong"、"监控08_jiankong"），数字部分通常对应通道号。您可以：

1. **使用自动检测**（推荐）：
   ```powershell
   python media_download_all_channels.py 10.19.2.2 2024-11-25 08:00:00 2024-11-25 09:00:00
   ```
   脚本会显示所有有录像的通道

2. **通过NVR的Web界面查看**：登录NVR管理界面，查看通道配置

3. **逐个测试**：
   ```powershell
   # 测试通道1
   python media_download_all_channels.py --channels 1 10.19.2.2 2024-11-25 08:00:00 2024-11-25 08:10:00
   ```

### 2. 自动检测很慢怎么办？

如果您知道NVR只有少量通道（例如8通道），可以减少扫描范围：

```powershell
python media_download_all_channels.py -m 8 10.19.2.2 2024-11-25 08:00:00 2024-11-25 18:00:00
```

或直接指定通道号：

```powershell
python media_download_all_channels.py --channels 1-8 10.19.2.2 2024-11-25 08:00:00 2024-11-25 18:00:00
```

### 3. 可以加快下载速度吗？

可以增加并发数，但要注意：
- 网络带宽限制
- NVR性能限制
- 硬盘写入速度

建议从3开始，逐步增加：

```powershell
python media_download_all_channels.py -c 5 10.19.2.2 2024-11-25 08:00:00 2024-11-25 18:00:00
```

### 4. 支持不同的NVR品牌吗？

此脚本专门为海康威视（Hikvision）和海康威视（Hiwatch）设备设计，使用ISAPI接口。其他品牌的NVR可能不兼容。

### 5. 下载中断后可以继续吗？

目前脚本会跳过已存在的文件。如果中断，重新运行相同的命令即可继续下载未完成的部分。

## 性能建议

1. **网络环境**：
   - 确保与NVR在同一局域网内
   - 避免通过VPN或远程连接下载大量视频

2. **并发设置**：
   - 4-8通道NVR：并发2-3个
   - 16通道NVR：并发3-5个
   - 32+通道NVR：并发5-8个

3. **时间段选择**：
   - 建议按天或半天进行下载
   - 避免一次下载过长时间段（如整月）

4. **存储空间**：
   - 确保有足够的磁盘空间
   - 1小时1080P视频约占1-2GB
   - 1小时4K视频约占4-8GB

## 与其他脚本的对比

| 特性 | media_download.py | media_download_multi.py | media_download_all_channels.py |
|------|-------------------|-------------------------|-------------------------------|
| 单摄像头 | ✅ | ✅ | ❌ |
| 多摄像头（不同IP） | ❌ | ✅ | ❌ |
| NVR多通道 | ❌ | ❌ | ✅ |
| 自动检测通道 | ❌ | ❌ | ✅ |
| 并发下载 | ❌ | ✅ | ✅ |
| 独立通道目录 | ❌ | ❌ | ✅ |

## 技术说明

### 通道与TrackID的对应关系

```
通道1 -> 视频trackID=101, 照片trackID=103
通道2 -> 视频trackID=201, 照片trackID=203
通道3 -> 视频trackID=301, 照片trackID=303
...
通道N -> 视频trackID=N01, 照片trackID=N03
```

### ISAPI端点

脚本使用以下海康威视ISAPI端点：
- `/ISAPI/System/time` - 获取设备时间
- `/ISAPI/ContentMgmt/search` - 搜索录像文件
- `/ISAPI/ContentMgmt/download` - 下载录像文件

## 依赖项

与其他脚本相同：
- Python 3
- requests
- defusedxml

## 故障排除

### 错误：Unauthorised

检查用户名和密码是否正确：
```powershell
$env:HIK_USERNAME = 'admin'
$env:HIK_PASSWORD = 'your_password'
```

### 错误：Connection error

1. 检查NVR IP地址是否正确
2. 确认网络连接
3. 尝试ping NVR：`ping 10.19.2.2`

### 没有检测到任何通道

1. 确认时间范围内有录像
2. 尝试更短的时间范围测试
3. 检查NVR录像设置
4. 尝试手动指定已知的通道号

### 某些通道下载失败

1. 检查该通道的独立日志文件
2. 该通道可能在指定时间段没有录像
3. 可能是网络临时问题，可以重新运行脚本

## 高级用法

### 定时批量下载所有通道

创建PowerShell脚本 `download_daily.ps1`：

```powershell
# download_daily.ps1
$env:HIK_USERNAME = 'admin'
$env:HIK_PASSWORD = 'your_password'

$yesterday = (Get-Date).AddDays(-1).ToString('yyyy-MM-dd')

python media_download_all_channels.py 10.19.2.2 "$yesterday 00:00:00" "$yesterday 23:59:59"
```

使用Windows任务计划程序每天自动运行此脚本。

### 结合通道筛选和时间段

```powershell
# 只下载通道4和8的早8点到晚8点的录像
python media_download_all_channels.py --channels 4,8 10.19.2.2 2024-11-25 08:00:00 2024-11-25 20:00:00
```
