# ENVI Web 项目部署指南

## 环境要求

1. Python 3.8+ 
2. PostgreSQL 14+ 与 PostGIS 扩展
3. GDAL 库
4. 操作系统：Windows/Linux

## 部署步骤

### 1. 安装必要的系统依赖

#### Windows:
1. 安装 PostgreSQL 和 PostGIS
   - 下载并安装 PostgreSQL: https://www.postgresql.org/download/windows/
   - 在 PostgreSQL 安装时选择 PostGIS 扩展
   
2. 安装 GDAL
   - 推荐通过 OSGeo4W 安装：https://trac.osgeo.org/osgeo4w/
   - 或通过 Conda 安装

#### Linux (Ubuntu/Debian):
```bash
# 安装 PostgreSQL 和 PostGIS
sudo apt update
sudo apt install postgresql postgresql-contrib postgis

# 安装 GDAL
sudo apt install gdal-bin python3-gdal
```

### 2. 数据库配置

1. 创建数据库和用户：
```sql
CREATE USER geouser WITH PASSWORD 'geo123';
CREATE DATABASE envi_geo;
\c envi_geo
CREATE EXTENSION postgis;
GRANT ALL PRIVILEGES ON DATABASE envi_geo TO geouser;
```

2. 恢复数据库备份：
```bash
pg_restore -U geouser -h localhost -d envi_geo envi_geo_backup.dump
```

### 3. Python 环境配置

1. 创建虚拟环境：
```bash
python -m venv venv
source venv/bin/activate  # Linux
venv\Scripts\activate     # Windows
```

2. 安装依赖：
```bash
pip install -r requirements.txt
```

### 4. 项目配置

1. 配置环境变量：
   - 创建 `.env` 文件在项目根目录
   ```
   DJANGO_SECRET_KEY=your_secret_key
   DJANGO_DEBUG=False
   ALLOWED_HOSTS=your_domain,localhost
   DB_NAME=envi_geo
   DB_USER=geouser
   DB_PASSWORD=geo123
   DB_HOST=localhost
   DB_PORT=5432
   ```

2. 配置 GDAL 路径：
   - 在 settings.py 中更新 GDAL 路径为新环境的路径

### 5. 静态文件和媒体文件

1. 收集静态文件：
```bash
python manage.py collectstatic
```

2. 创建媒体文件目录：
```bash
mkdir media
```

3. 确保权限正确：
```bash
chmod 755 media staticfiles
```

### 6. 运行项目

1. 测试运行：
```bash
python manage.py runserver
```

2. 生产环境部署：
   - 使用 Gunicorn/uWSGI 作为应用服务器
   - 使用 Nginx 作为反向代理
   - 配置 SSL 证书

## 注意事项

1. 确保数据库备份文件 `envi_geo_backup.dump` 已经复制到新服务器
2. 检查并更新 settings.py 中的所有路径配置
3. 确保所有媒体文件都已经复制到新服务器的对应目录
4. 检查文件权限，确保 web 服务器可以访问所有必要的文件
5. 在生产环境中禁用 DEBUG 模式
6. 更新 ALLOWED_HOSTS 设置为实际的域名

## 故障排除

1. 如果遇到 GDAL 相关错误：
   - 检查 GDAL 是否正确安装
   - 验证环境变量是否正确设置
   - 确认 settings.py 中的 GDAL 路径配置

2. 如果遇到数据库连接错误：
   - 检查 PostgreSQL 服务是否运行
   - 验证数据库用户权限
   - 确认防火墙设置

3. 如果遇到静态文件 404 错误：
   - 运行 collectstatic 命令
   - 检查 Nginx 配置
   - 验证文件权限

## 联系方式

如有问题，请联系项目维护者。 