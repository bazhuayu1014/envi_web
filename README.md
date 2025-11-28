# ENVI Web - 遥感影像数据管理系统

一个基于 Django 的 Web 遥感影像数据库管理系统，用于管理和处理多种类型的遥感影像数据。

## ✨ 功能特性

- 🗺️ **Web 地图展示**: 在线浏览遥感影像的空间范围和属性信息
- 📤 **数据上传**: 支持单文件和批量上传 ENVI 格式遥感数据
- 🔄 **自动处理**: 自动进行格式转换、坐标系转换、瓦片生成
- 🔍 **空间查询**: 支持多边形、缓冲区等空间查询功能
- 📊 **蚀变分析**: 支持 PC 方法和 Ratio 方法蚀变数据管理
- 💼 **工作站管理**: 个人工作空间，组织和管理遥感数据
- 👥 **用户系统**: 基于邀请码的用户注册和权限管理

## 🛠️ 技术栈

### 后端
- **Django 4.2.19** - Web 框架
- **GeoDjango** - 地理空间数据处理
- **PostgreSQL + PostGIS** - 空间数据库
- **GDAL/GEOS** - 地理数据处理库

### 前端
- **Leaflet** - 交互式地图库
- **Bootstrap** - UI 框架
- **JavaScript/jQuery** - 前端交互

### 支持的传感器
- Sentinel-2 (多光谱)
- GF5 (高光谱)
- ASTER (多光谱)
- PRISMA (高光谱)

## 📋 系统要求

- Python 3.8+
- PostgreSQL 14+ with PostGIS 扩展
- GDAL 库
- 操作系统: Windows/Linux

## 🚀 快速开始

### 1. 克隆项目

```bash
git clone https://github.com/YOUR_USERNAME/envi-web.git
cd envi-web
```

### 2. 安装依赖

```bash
# 创建虚拟环境
python -m venv venv
source venv/bin/activate  # Linux
venv\Scripts\activate     # Windows

# 安装 Python 依赖
pip install django==4.2.19
pip install psycopg2-binary
pip install pillow
pip install concurrent-log-handler
```

### 3. 配置数据库

创建 PostgreSQL 数据库：

```sql
CREATE USER geouser WITH PASSWORD 'geo123';
CREATE DATABASE envi_geo;
\c envi_geo
CREATE EXTENSION postgis;
GRANT ALL PRIVILEGES ON DATABASE envi_geo TO geouser;
```

### 4. 配置 GDAL

在 `envi_web/settings.py` 中更新 GDAL 路径为你的环境路径：

```python
GDAL_LIBRARY_PATH = r'YOUR_PATH\gdal.dll'
GEOS_LIBRARY_PATH = r'YOUR_PATH\geos_c.dll'
```

### 5. 运行迁移

```bash
python manage.py migrate
```

### 6. 创建超级用户

```bash
python manage.py createsuperuser
```

### 7. 运行开发服务器

```bash
python manage.py runserver
```

访问 http://localhost:8000 查看系统。

## 📖 详细部署指南

请参考 [DEPLOYMENT.md](DEPLOYMENT.md) 获取完整的部署说明。

## 📁 项目结构

```
envi_web/
├── accounts/              # 用户认证模块
│   ├── models.py         # 用户模型（邀请码、用户配置）
│   └── views.py          # 登录、注册视图
├── geodata/              # 核心遥感数据管理模块
│   ├── models.py         # 数据模型（EnviFile, EnviData, WorkStation）
│   ├── views.py          # 视图函数（地图、上传、下载）
│   ├── utils.py          # ENVI 文件处理工具
│   └── management/commands/
│       └── process_envi.py  # 核心数据处理命令
├── envi_web/             # 项目配置
│   ├── settings.py       # Django 设置
│   └── urls.py           # URL 路由
├── static/               # 静态资源
├── media/                # 用户上传文件（不包含在 Git 中）
└── manage.py             # Django 管理脚本
```

## 🔧 核心功能说明

### 数据处理流程

1. **上传 ENVI 文件** (.hdr + .img)
2. **自动格式转换** (ENVI → GeoTIFF)
3. **坐标系转换** (转换为 WGS84)
4. **RPC 校正** (如果包含 RPC 信息)
5. **波段组合** (根据传感器类型选择 RGB 波段)
6. **瓦片生成** (金字塔切片，用于 Web 展示)
7. **元数据提取** (空间范围、波长信息等)
8. **数据入库** (存储到 PostgreSQL)

### 金字塔瓦片原理

系统使用 `gdal2tiles` 工具将大型遥感影像切分为多级金字塔瓦片：
- 不同缩放级别对应不同分辨率
- 按需加载，提高 Web 展示性能
- 支持 Web 墨卡托投影

## 📸 功能截图



## ⚠️ 注意事项

1. **数据文件不包含在仓库中**: `media/`, `staticfiles/`, `static/tiles/` 等目录已被 `.gitignore` 排除
2. **敏感信息**: 请在生产环境中使用环境变量管理数据库密码和 SECRET_KEY
3. **GDAL 配置**: 需要根据你的环境配置 GDAL 路径
4. **存储空间**: 遥感影像数据量大，确保有足够的磁盘空间

## 📝 开发说明

### 添加新的传感器支持

在 `geodata/management/commands/process_envi.py` 中：
1. 更新 `_detect_sensor_type` 方法
2. 在 `generate_tiles` 中添加对应的波段组合
3. 在 `models.py` 的 `SENSOR_TYPES` 中添加新类型

### 自定义数据处理

修改 `process_envi.py` 中的处理流程，可以自定义：
- 波段组合方式
- 数据拉伸参数
- 瓦片缩放级别
- 重采样方法

## 🤝 贡献

欢迎提交 Issue 和 Pull Request！

## 📄 许可证

本项目仅用于学习和研究目的。

## 👨‍💻 作者

- 八爪鱼
- 2004250011@email.cugb.edu.cn

## 🙏 致谢

- Django 框架
- GDAL 项目
- PostGIS 项目
- Leaflet 地图库

---

**注**: 禁止搬运，后果自负！
