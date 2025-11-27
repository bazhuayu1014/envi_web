"""
ENVI遥感数据处理命令模块

本模块实现了一个Django管理命令，用于处理ENVI格式的遥感数据。主要功能包括：
1. 数据格式转换（ENVI -> GeoTIFF）
2. 坐标系转换和校正
3. 波长信息提取
4. 缩略图生成
5. 地图瓦片生成
6. 元数据提取和存储

支持的数据类型：
- Sentinel-2 多光谱数据
- GF5 高光谱数据
- ASTER 多光谱数据
- PRISMA 高光谱数据
"""

from django.core.management.base import BaseCommand
from django.contrib.gis.geos import Polygon, Point
from django.db import transaction
from osgeo import gdal, osr
from datetime import datetime
from django.conf import settings
import json
import os
import subprocess
import logging
import sys
import math
import shutil

# 配置日志记录器
logger = logging.getLogger(__name__)

class Command(BaseCommand):
    """
    ENVI数据处理命令类
    
    实现了对ENVI格式遥感数据的完整处理流程，包括：
    - 数据预处理和格式转换
    - 坐标系转换和几何校正
    - 波谱信息提取
    - 缩略图和瓦片生成
    - 数据入库
    """
    
    help = '处理ENVI格式遥感数据并导入系统'

    def add_arguments(self, parser):
        """
        添加命令行参数
        
        Args:
            parser: 命令行参数解析器
            
        添加的参数:
            hdr_path: ENVI头文件路径
            img_path: ENVI影像文件路径
        """
        parser.add_argument('hdr_path', type=str, help='.hdr头文件路径')
        parser.add_argument('img_path', type=str, help='.img影像文件路径')

    def _configure_gdal(self, hdr_path, img_path):
        """
        配置GDAL环境
        
        设置GDAL运行所需的环境变量和配置项，包括：
        - PROJ数据库路径
        - GDAL数据路径
        - 系统PATH路径
        - GDAL配置选项
        
        Args:
            hdr_path: ENVI头文件路径
            img_path: ENVI影像文件路径
            
        Raises:
            Exception: PROJ数据库文件不存在
            ValueError: 无效的影像文件格式
        """
        # 设置GDAL相关路径
        proj_path = r'D:\Anaconda3\envs\envi_web\Library\share\proj'
        gdal_path = r'D:\Anaconda3\envs\envi_web\Library\share\gdal'
        bin_path = r'D:\Anaconda3\envs\envi_web\Library\bin'

        # 验证PROJ数据库文件
        if not os.path.exists(os.path.join(proj_path, 'proj.db')):
            raise Exception(f'PROJ数据库文件不存在于: {proj_path}')

        # 更新环境变量
        os.environ.update({
            'PROJ_LIB': proj_path,
            'GDAL_DATA': gdal_path,
            'PATH': f"{bin_path};{os.environ['PATH']}"
        })

        # 配置GDAL选项
        gdal.SetConfigOption('GDAL_DATA', gdal_path)
        gdal.SetConfigOption('PROJ_LIB', proj_path)
        gdal.SetConfigOption('USE_RPC', 'YES')  # 启用RPC模型支持
        gdal.AllRegister()  # 注册所有GDAL驱动
        
        # 验证影像格式
        if not gdal.IdentifyDriver(img_path):
            raise ValueError('无效的影像文件格式')
        gdal.UseExceptions()  # 启用GDAL异常处理

    def parse_filename(self, hdr_path):
        """
        解析文件名
        
       从文件路径中提取基础文件名（不含扩展名）
        
        Args:
            hdr_path: ENVI头文件路径
            
        Returns:
            str: 基础文件名
        """
        return os.path.splitext(os.path.basename(hdr_path))[0]

    def calculate_bounds(self, dataset):
        """
        计算数据边界范围
        
        计算遥感影像的地理边界范围，支持：
        - 坐标系自动识别和转换
        - RPC模型支持
        - 坐标序转换（经纬度顺序调整）
        - 边界多边形生成
        
        Args:
            dataset: GDAL数据集对象
            
        Returns:
            Polygon: Django GIS多边形对象，表示数据边界
            
        Raises:
            Exception: 坐标转换或边界计算失败
        """
        try:
            # 获取原始坐标系
            src_srs = osr.SpatialReference()
            projection = dataset.GetProjection()
            
            # 处理投影信息缺失的情况
            if not projection:
                logger.warning("未检测到投影信息，尝试使用RPC信息...")
                src_srs.ImportFromEPSG(4326)  # 默认使用WGS84
            else:
                try:
                    src_srs.ImportFromWkt(projection)
                except Exception as e:
                    logger.error(f"解析投影信息失败: {str(e)}，使用默认WGS84")
                    src_srs.ImportFromEPSG(4326)
            
            # 创建目标坐标系（WGS84）
            tgt_srs = osr.SpatialReference()
            tgt_srs.ImportFromEPSG(4326)
            
            # 创建坐标转换器
            transform = osr.CoordinateTransformation(src_srs, tgt_srs)
            
            # 获取原始地理变换参数
            geo_transform = dataset.GetGeoTransform()
            width = dataset.RasterXSize
            height = dataset.RasterYSize

            # 计算四个角点坐标
            points = [
                (geo_transform[0], geo_transform[3]),  # 左上角
                (geo_transform[0] + width * geo_transform[1], geo_transform[3]),  # 右上角
                (geo_transform[0] + width * geo_transform[1], geo_transform[3] + height * geo_transform[5]),  # 右下角
                (geo_transform[0], geo_transform[3] + height * geo_transform[5]),  # 左下角
                (geo_transform[0], geo_transform[3])  # 闭合多边形
            ]
            
            # 执行坐标转换
            transformed_points = []
            basename = self.parse_filename(dataset.GetDescription())
            is_gf5 = basename.startswith('GF5')  # 检查是否为GF5数据
            
            for x, y in points:
                try:
                    if is_gf5:
                        # GF5数据需要交换坐标顺序（纬度-经度）
                        lon, lat, _ = transform.TransformPoint(y, x)
                    else:
                        # 其他数据保持原有顺序（经度-纬度）
                        lon, lat, _ = transform.TransformPoint(x, y)
                    
                    transformed_points.append((lon, lat))
                except Exception as e:
                    logger.error(f"坐标转换失败: {str(e)}")
                    # 转换失败时使用原始坐标
                    if is_gf5:
                        transformed_points.append((y, x))
                    else:
                        transformed_points.append((x, y))

            # 记录转换结果
            logger.info(f"原始坐标: {[(round(x, 8), round(y, 8)) for x, y in points]}")
            logger.info(f"转换后坐标: {[(round(x, 8), round(y, 8)) for x, y in transformed_points]}")
           
            # 创建并返回多边形
            return Polygon(transformed_points)
            
        except Exception as e:
            logger.error(f"计算边界失败: {str(e)}")
            raise

    def generate_tiles(self, tif_path, basename):
        """
        生成地图瓦片
        
        将GeoTIFF格式的遥感影像转换为Web地图瓦片，支持：
        - 不同传感器类型的数据处理
        - 自适应缩放级别设置
        - 波段组合和拉伸优化
        - 多进程并行处理
        
        Args:
            tif_path: GeoTIFF文件路径
            basename: 基础文件名
            
        Returns:
            str: 瓦片URL模板
            
        Raises:
            Exception: 瓦片生成失败
        """
        # 创建临时VRT文件路径
        vrt_path = os.path.join(settings.BASE_DIR, 'static', 'temp', f'{basename}.vrt')
        os.makedirs(os.path.dirname(vrt_path), exist_ok=True)

        # 获取源数据信息
        ds = gdal.Open(tif_path)
        try:
            # 获取并验证坐标系
            src_srs = osr.SpatialReference()
            src_srs.ImportFromWkt(ds.GetProjection())
            epsg = src_srs.GetAuthorityCode(None)
            if not epsg:
                epsg = '4326'  # 默认使用WGS84
            
            # 获取图像参数
            width = ds.RasterXSize
            height = ds.RasterYSize
            geotransform = ds.GetGeoTransform()
            
            # 根据传感器类型设置缩放级别
            if basename.startswith('GF5'):
                # GF5高光谱数据（30m分辨率）
                min_zoom = 8   # 最小缩放级别（约610米/像素）
                max_zoom = 12  # 最大缩放级别（约38米/像素）
                logger.info(f'GF5数据使用固定缩放级别范围: {min_zoom}-{max_zoom}')
            elif basename.startswith('AST'):
                # ASTER数据（15m分辨率）
                min_zoom = 10
                max_zoom = 14
                logger.info(f'ASTER数据使用固定缩放级别范围: {min_zoom}-{max_zoom}')
            elif basename.startswith('PRS'):
                # PRISMA数据（30m分辨率）
                min_zoom = 8
                max_zoom = 12
                logger.info(f'PRISMA数据使用固定缩放级别范围: {min_zoom}-{max_zoom}')
            else:
                # Sentinel-2等其他数据，根据分辨率动态计算
                resolution = abs(geotransform[1])  # 像素宽度（X方向分辨率）
                logger.info(f'数据分辨率: {resolution}米')
                data_extent = width * resolution
                min_zoom = max(1, int(round(math.log2(40075016.686 / data_extent))))
                max_zoom = 14 if resolution <= 10 else (13 if resolution <= 20 else 12)
            
        finally:
            ds = None

        # 创建VRT文件
        basename = os.path.splitext(os.path.basename(tif_path))[0]
        sensor_type = self._detect_sensor_type(basename)
        
        # 根据传感器类型选择不同的波段组合和处理参数
        if sensor_type == 'PRISMA':
            # PRISMA高光谱数据使用特定波段组合（约RGB波段）
            vrt_cmd = (
                f'gdal_translate -of VRT -ot Byte '
                f'-scale_1 0 4096 0 255 '  # 数据拉伸参数
                f'-scale_2 0 4096 0 255 '
                f'-scale_3 0 4096 0 255 '
                f'-b 29 -b 20 -b 11 '  # 使用~630nm(红)、~550nm(绿)、~450nm(蓝)波段
                f'-r average '  # 使用平均值重采样
                f'"{tif_path}" "{vrt_path}"'
            )
        elif sensor_type == 'ASTER':
            # ASTER使用VNIR波段，2-1-1波段组合（真彩色）
            # 获取数据的实际范围以优化拉伸参数
            ds = gdal.Open(tif_path)
            try:
                band1 = ds.GetRasterBand(1)
                band2 = ds.GetRasterBand(2)
                stats1 = band1.GetStatistics(True, True)
                stats2 = band2.GetStatistics(True, True)
                min_val = min(stats1[0], stats2[0])
                max_val = max(stats1[1], stats2[1])
                logger.info(f"ASTER数据实际范围: min={min_val}, max={max_val}")
            except Exception as e:
                logger.warning(f"获取数据范围失败: {str(e)}, 使用默认范围")
                min_val = 0
                max_val = 255
            finally:
                ds = None

            vrt_cmd = (
                f'gdal_translate -of VRT -ot Byte '
                f'-scale_1 {min_val} {max_val} 0 255 '  # 红色波段（波段2）
                f'-scale_2 {min_val} {max_val} 0 255 '  # 绿色波段（波段1）
                f'-scale_3 {min_val} {max_val} 0 255 '  # 蓝色波段（波段1）
                f'-b 3 -b 2 -b 1 '  # 使用2-1-1波段组合
                f'-r average '  # 使用平均值重采样
                f'"{tif_path}" "{vrt_path}"'
            )
        elif sensor_type == 'GF5':
            # GF5高光谱数据使用特定波段组合
            vrt_cmd = (
                f'gdal_translate -of VRT -ot Byte '
                f'-scale_1 0 4096 0 255 '
                f'-scale_2 0 4096 0 255 '
                f'-scale_3 0 4096 0 255 '
                f'-b 29 -b 20 -b 11 '  # 使用类似PRISMA的波段组合
                f'-r cubic '  # 使用三次卷积重采样
                f'"{tif_path}" "{vrt_path}"'
            )
        else:
            # Sentinel-2使用标准RGB波段组合
            vrt_cmd = (
                f'gdal_translate -of VRT -ot Byte '
                f'-scale_1 0 4096 0 255 '
                f'-scale_2 0 4096 0 255 '
                f'-scale_3 0 4096 0 255 '
                f'-b 4 -b 3 -b 2 '  # 使用标准RGB波段
                f'-r bilinear '  # 使用双线性重采样
                f'"{tif_path}" "{vrt_path}"'
            )

        # 执行VRT文件创建命令
        subprocess.run(vrt_cmd, shell=True, check=True,
                     stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                     universal_newlines=True)

        # 创建瓦片目录
        tile_dir = os.path.join(settings.BASE_DIR, 'static', 'tiles', basename)
        os.makedirs(tile_dir, exist_ok=True)

        # 验证gdal2tiles工具路径
        gdal2tiles_path = r'D:\Anaconda3\envs\envi_web\Scripts\gdal2tiles.py'
        if not os.path.exists(gdal2tiles_path):
            raise FileNotFoundError(f'找不到gdal2tiles.py，已尝试路径: {gdal2tiles_path}')

        python_exe = r'D:\Anaconda3\envs\envi_web\python.exe'
        if not os.path.exists(python_exe):
            raise FileNotFoundError(f'找不到Python解释器，路径: {python_exe}')
        
        # 根据传感器类型设置瓦片生成参数
        if sensor_type == 'ASTER':
            # ASTER数据处理参数
            gdal2tiles_cmd = (
                f'"{python_exe}" "{gdal2tiles_path}" '
                f'-p mercator '  # 使用Web墨卡托投影
                f'--s_srs EPSG:{epsg} '  # 源数据坐标系
                f'-z {min_zoom}-{max_zoom} '  # 缩放级别范围
                f'--xyz '  # 使用XYZ瓦片格式
                f'--resampling=near '  # 最近邻重采样
                f'--processes=4 '  # 使用4个进程并行处理
                f'-w all '  # 处理所有像素
                f'--srcnodata 0 '  # 设置源数据中的无数据值
                f'--tmscompatible '  # 生成TMS兼容瓦片
                f'"{vrt_path}" "{tile_dir}"'
            )
            logger.info("使用ASTER专用参数生成瓦片")

        elif sensor_type == 'PRISMA':
            # PRISMA高光谱数据处理参数
            gdal2tiles_cmd = (
                f'"{python_exe}" "{gdal2tiles_path}" '
                f'-p mercator '
                f'--s_srs EPSG:{epsg} '
                f'-z {min_zoom}-{max_zoom} '
                f'--xyz '
                f'--resampling=average '  # 使用平均值重采样
                f'--processes=4 '
                f'--srcnodata 0 '
                f'--tmscompatible '
                f'"{vrt_path}" "{tile_dir}"'
            )
            logger.info("使用PRISMA专用参数生成瓦片")

        elif sensor_type == 'GF5':
            # GF5高光谱数据处理参数
            gdal2tiles_cmd = (
                f'"{python_exe}" "{gdal2tiles_path}" '
                f'-p mercator '
                f'--s_srs EPSG:{epsg} '
                f'-z {min_zoom}-{max_zoom} '
                f'--xyz '
                f'--resampling=cubic '  # 使用三次卷积重采样
                f'--processes=4 '
                f'--srcnodata 0 '
                f'--tmscompatible '
                f'"{vrt_path}" "{tile_dir}"'
            )
            logger.info("使用GF5专用参数生成瓦片")

        else:
            # Sentinel-2等其他数据使用标准参数
            gdal2tiles_cmd = (
                f'"{python_exe}" "{gdal2tiles_path}" '
                f'-p mercator '
                f'--s_srs EPSG:{epsg} '
                f'-z {min_zoom}-{max_zoom} '
                f'--xyz '
                f'--resampling=bilinear '  # 使用双线性重采样
                f'--processes=4 '
                f'--tmscompatible '
                f'"{vrt_path}" "{tile_dir}"'
            )
            logger.info("使用标准参数生成瓦片")

        logger.info(f"执行瓦片生成命令: {gdal2tiles_cmd}")

        try:
            # 执行瓦片生成命令
            result = subprocess.run(gdal2tiles_cmd, shell=True, check=True,
                         stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                         universal_newlines=True)
            logger.info(f'瓦片生成输出: {result.stdout}')
            if result.stderr:
                logger.warning(f'瓦片生成警告: {result.stderr}')
            
            logger.info(f'瓦片生成完成，缩放级别范围: {min_zoom}-{max_zoom}')
            
        except subprocess.CalledProcessError as e:
            logger.error(f'瓦片生成失败: {e.stderr}')
            raise

        # 清理临时文件
        if os.path.exists(vrt_path):
            os.remove(vrt_path)
        
        # 返回瓦片URL模板
        return f'/static/tiles/{basename}/{{z}}/{{x}}/{{y}}.png'

    def _detect_sensor_type(self, basename):
        """
        检测传感器类型
        
        根据文件名前缀判断数据来源的传感器类型。
        
        Args:
            basename: 文件基础名
            
        Returns:
            str: 传感器类型代码（S2/GF5/ASTER/PRISMA）
        """
        if basename.startswith('S2'):
            return 'S2'
        elif basename.startswith('GF5'):
            return 'GF5'
        elif basename.startswith('AST'):
            return 'ASTER'
        elif basename.startswith('PRS'):
            return 'PRISMA'
        else:
            return 'S2'  # 默认使用S2

    def handle(self, *args, **options):
        """
        命令入口函数
        
        实现完整的ENVI数据处理流程，包括：
        1. 文件复制和组织
        2. GDAL环境配置
        3. 数据格式转换
        4. 波长信息提取
        5. RPC模型处理
        6. 坐标系转换
        7. 缩略图生成
        8. 瓦片生成
        9. 元数据入库
        
        Args:
            options: 命令行参数字典，包含hdr_path和img_path
            
        Raises:
            Exception: 数据处理过程中的任何错误
        """
        try:
            hdr_path = options['hdr_path']
            img_path = options['img_path']
            
            # 创建按日期组织的目录结构
            today = datetime.now()
            relative_path = os.path.join('envi_files', 
                                       str(today.year),
                                       str(today.month).zfill(2),
                                       str(today.day).zfill(2))
            
            # 创建目标目录
            target_dir = os.path.join(settings.MEDIA_ROOT, relative_path)
            os.makedirs(target_dir, exist_ok=True)
            
            # 复制文件到目标目录
            target_hdr = os.path.join(target_dir, os.path.basename(hdr_path))
            target_img = os.path.join(target_dir, os.path.basename(img_path))
            
            # 避免重复复制
            if not os.path.exists(target_hdr):
                shutil.copy2(hdr_path, target_hdr)
            if not os.path.exists(target_img):
                shutil.copy2(img_path, target_img)
            
            # 更新文件路径
            hdr_path = target_hdr
            img_path = target_img
            
            # 配置GDAL环境
            self._configure_gdal(hdr_path, img_path)
            basename = self.parse_filename(hdr_path)
            sensor_type = self._detect_sensor_type(basename)

            # 提取波长信息
            wavelength_info = None
            try:
                with open(hdr_path, 'r') as f:
                    header_content = f.read()
                    # 解析波长信息
                    wavelength_start = header_content.find('wavelength = {')
                    if wavelength_start != -1:
                        wavelength_end = header_content.find('}', wavelength_start)
                        wavelength_str = header_content[wavelength_start:wavelength_end+1]
                        wavelength_list = [float(w.strip()) for w in wavelength_str.replace('wavelength = {', '').replace('}', '').split(',') if w.strip()]
                        
                        # 获取波长单位
                        units_start = header_content.find('wavelength units = ')
                        if units_start != -1:
                            units_end = header_content.find('\n', units_start)
                            units = header_content[units_start:units_end].split('=')[1].strip()
                        else:
                            units = 'Nanometers'  # 默认单位
                        
                        wavelength_info = {
                            'wavelengths': wavelength_list,
                            'units': units
                        }
                        
                        # 单位转换：微米转纳米
                        if units.lower() == 'micrometers':
                            wavelength_info['wavelengths'] = [w * 1000 for w in wavelength_list]
                            wavelength_info['units'] = 'Nanometers'
                            
                    logger.info(f"检测到波长信息: {len(wavelength_list) if wavelength_list else 0}个波段")
            except Exception as e:
                logger.warning(f"波长信息提取失败: {str(e)}")

            # 检查RPC信息
            has_rpc = False
            try:
                with open(hdr_path, 'r') as f:
                    header_content = f.read()
                    if any(term in header_content.lower() for term in ['rpc info', 'rational polynomial coefficients']):
                        has_rpc = True
                        logger.info("检测到RPC模型信息")
            except Exception as e:
                logger.warning(f"读取头文件RPC信息失败: {str(e)}")

            # 格式转换：ENVI -> GeoTIFF
            tif_path = os.path.join(settings.BASE_DIR, 'static', 'temp', f'{basename}.tif')
            os.makedirs(os.path.dirname(tif_path), exist_ok=True)
            
            # 清理已存在的临时文件
            if os.path.exists(tif_path):
                os.remove(tif_path)
            
            # 执行格式转换
            translate_cmd = (
                f'gdal_translate -of GTiff '  # 输出为GeoTIFF格式
                f'-co "COMPRESS=LZW" '  # 使用LZW压缩
                f'-co "TILED=YES" '  # 启用分块
                f'-co "BIGTIFF=IF_NEEDED" '  # 支持大文件
                f'"{img_path}" "{tif_path}"'
            )
            subprocess.run(translate_cmd, shell=True, check=True)

            # RPC模型处理
            if has_rpc:
                warp_path = os.path.join(settings.BASE_DIR, 'static', 'temp', f'{basename}_warp.tif')
                
                # 清理已存在的临时文件
                if os.path.exists(warp_path):
                    os.remove(warp_path)
                    
                try:
                    # 执行RPC校正和投影变换
                    warp_cmd = (
                        f'gdalwarp -r bilinear '  # 双线性重采样
                        f'-t_srs EPSG:4326 '  # 输出为WGS84坐标系
                        f'-rpc '  # 启用RPC模型
                        f'-order 1 '  # 一次多项式变换
                        f'-et 0.5 '  # 误差阈值
                        f'-co "COMPRESS=LZW" '
                        f'-co "TILED=YES" '
                        f'-co "BIGTIFF=IF_NEEDED" '
                        f'"{tif_path}" "{warp_path}"'
                    )
                    
                    # 执行变换命令
                    result = subprocess.run(warp_cmd, shell=True, check=True,
                                         stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                         universal_newlines=True)
                    
                    if result.stderr:
                        logger.warning(f"Warp警告: {result.stderr}")
                    
                    # 使用变换后的文件
                    if os.path.exists(warp_path):
                        os.replace(warp_path, tif_path)
                        logger.info("完成RPC坐标转换")
                        
                        # 验证转换结果
                        ds = gdal.Open(tif_path)
                        if ds:
                            gt = ds.GetGeoTransform()
                            logger.info(f"转换后的地理变换参数: {gt}")
                            ds = None
                except Exception as e:
                    logger.error(f"RPC坐标转换失败: {str(e)}")
                    if os.path.exists(warp_path):
                        os.remove(warp_path)
                    logger.warning("使用原始文件继续处理")

            # 打开转换后的TIFF文件
            dataset = gdal.Open(tif_path)
            if not dataset:
                raise ValueError('无法打开TIFF文件')

            try:
                # 坐标系验证和处理
                src_srs = osr.SpatialReference()
                projection = dataset.GetProjection()
                
                if not projection:
                    # 尝试从ENVI头文件读取投影信息
                    logger.warning("GDAL未检测到投影信息，尝试从ENVI头文件读取...")
                    try:
                        with open(hdr_path, 'r') as f:
                            header_content = f.read()
                            
                        # 检查map info信息
                        if 'map info' in header_content.lower():
                            logger.info("从ENVI头文件中检测到map info")
                            map_info_start = header_content.find('map info = {')
                            if map_info_start != -1:
                                map_info_end = header_content.find('}', map_info_start)
                                map_info = header_content[map_info_start:map_info_end+1]
                                logger.info(f"Map info: {map_info}")
                                src_srs.ImportFromEPSG(4326)  # 使用WGS84
                        else:
                            logger.warning("在ENVI头文件中也未找到投影信息，使用默认WGS84")
                            src_srs.ImportFromEPSG(4326)
                    except Exception as e:
                        logger.error(f"读取ENVI头文件失败: {str(e)}")
                        src_srs.ImportFromEPSG(4326)
                else:
                    try:
                        src_srs.ImportFromWkt(projection)
                    except Exception as e:
                        logger.error(f"解析投影信息失败: {str(e)}，使用默认WGS84")
                        src_srs.ImportFromEPSG(4326)
                
                # 创建目标坐标系（WGS84）
                tgt_srs = osr.SpatialReference()
                tgt_srs.ImportFromEPSG(4326)
                
                # 获取坐标系信息
                coordinate_system = src_srs.GetName() if src_srs.GetName() else 'WGS84'
                
                # 提示坐标系转换
                if not src_srs.IsSame(tgt_srs):
                    self.stdout.write(self.style.WARNING(
                        f'检测到非WGS84坐标系({coordinate_system})，已执行自动转换'
                    ))

                # 生成缩略图
                thumbnail_dir = os.path.join(settings.BASE_DIR, 'media', 'thumbnails')
                os.makedirs(thumbnail_dir, exist_ok=True)
                thumbnail_path = os.path.join(thumbnail_dir, f'{basename}_thumb.png')

                # 检查数据集信息
                band_count = dataset.RasterCount
                logger.info(f"数据集波段数量: {band_count}")
                logger.info(f"检测到的传感器类型: {sensor_type}")
                
                # 根据传感器类型选择波段组合
                if sensor_type == 'GF5':
                    # GF5高光谱数据
                    red_band = 29    # ~630nm
                    green_band = 20  # ~550nm
                    blue_band = 11   # ~450nm
                    scale_params = "0 2000 0 255"
                elif sensor_type == 'PRISMA':
                    # PRISMA高光谱数据
                    red_band = 29    # ~630nm
                    green_band = 20  # ~550nm
                    blue_band = 11   # ~450nm
                    scale_params = "0 4000 0 255"
                elif sensor_type == 'ASTER':
                    # ASTER VNIR波段
                    red_band = 3     # Band 2 (Red, 0.661μm)
                    green_band = 2  # Band 1 (Green, 0.556μm)
                    blue_band = 1    # Band 1 (代替蓝色波段)

                    # 获取数据范围
                    ds = gdal.Open(tif_path)
                    try:
                        band1 = ds.GetRasterBand(1)
                        band2 = ds.GetRasterBand(2)
                        stats1 = band1.GetStatistics(True, True)
                        stats2 = band2.GetStatistics(True, True)
                        min_val = min(stats1[0], stats2[0])
                        max_val = max(stats1[1], stats2[1])
                        scale_params = f"{min_val} {max_val} 0 255"
                        logger.info(f"ASTER数据范围: {scale_params}")
                    except Exception as e:
                        logger.warning(f"获取数据范围失败: {str(e)}, 使用默认范围")
                        scale_params = "0 255 0 255"
                    finally:
                        ds = None
                else:
                    # Sentinel-2标准RGB波段
                    red_band = 4    # Band 4 (Red)
                    green_band = 3  # Band 3 (Green)
                    blue_band = 2   # Band 2 (Blue)
                    scale_params = "0 4000 0 255"

                logger.info(f"使用波段: 红={red_band}, 绿={green_band}, 蓝={blue_band}")
                
                # 创建VRT文件用于波段组合
                vrt_path = os.path.join(settings.BASE_DIR, 'static', 'temp', f'{basename}_thumb.vrt')
                
                try:
                    # 创建VRT文件
                    vrt_cmd = (
                        f'gdalbuildvrt -separate '
                        f'-b {red_band} -b {green_band} -b {blue_band} '
                        f'"{vrt_path}" "{tif_path}"'
                    )
                    logger.info(f"执行VRT命令: {vrt_cmd}")
                    subprocess.run(vrt_cmd, shell=True, check=True,
                                stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                universal_newlines=True)
                    
                    # 验证VRT文件
                    if not os.path.exists(vrt_path):
                        raise Exception("VRT文件创建失败")
                    
                    # 根据传感器类型选择缩略图生成参数
                    if sensor_type == 'ASTER':
                        # ASTER数据使用最近邻重采样
                        translate_cmd = (
                            f'gdal_translate -of PNG -ot Byte '
                            f'-outsize 256 256 '
                            f'-scale {scale_params} '
                            f'-r near '  # 最近邻重采样
                            f'-a_nodata 0 '  # 设置无数据值
                            f'"{vrt_path}" "{thumbnail_path}"'
                        )
                        logger.info("使用ASTER专用参数生成缩略图")
                    
                    elif sensor_type == 'PRISMA':
                        # PRISMA数据使用平均值重采样
                        translate_cmd = (
                            f'gdal_translate -of PNG -ot Byte '
                            f'-outsize 256 256 '
                            f'-scale {scale_params} '
                            f'-r average '  # 平均值重采样
                            f'-a_nodata 0 '
                            f'"{vrt_path}" "{thumbnail_path}"'
                        )
                        logger.info("使用PRISMA专用参数生成缩略图")
                    
                    elif sensor_type == 'GF5':
                        # GF5数据使用双线性重采样
                        translate_cmd = (
                            f'gdal_translate -of PNG -ot Byte '
                            f'-outsize 256 256 '
                            f'-scale {scale_params} '
                            f'-r bilinear '  # 双线性重采样
                            f'-a_nodata 0 '
                            f'"{vrt_path}" "{thumbnail_path}"'
                        )
                        logger.info("使用GF5专用参数生成缩略图")
                    
                    else:
                        # Sentinel-2等数据使用标准参数
                        translate_cmd = (
                            f'gdal_translate -of PNG -ot Byte '
                            f'-outsize 256 256 '
                            f'-scale {scale_params} '
                            f'-r bilinear '  # 双线性重采样
                            f'"{vrt_path}" "{thumbnail_path}"'
                        )
                        logger.info("使用标准参数生成缩略图")

                    # 执行缩略图生成
                    result = subprocess.run(translate_cmd, shell=True, check=True,
                                         stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                         universal_newlines=True)
                    
                    if result.stderr:
                        logger.warning(f"转换警告: {result.stderr}")
                    
                    # 验证缩略图生成
                    if not os.path.exists(thumbnail_path):
                        raise Exception("缩略图生成失败")
                    
                except subprocess.CalledProcessError as e:
                    logger.error(f"命令执行失败: {e.stderr}")
                    raise
                except Exception as e:
                    logger.error(f"缩略图生成过程出错: {str(e)}")
                    raise
                finally:
                    # 清理临时VRT文件
                    if os.path.exists(vrt_path):
                        try:
                            os.remove(vrt_path)
                        except Exception as e:
                            logger.warning(f"清理VRT文件失败: {str(e)}")

                # 获取数据基本信息
                resolution = dataset.GetGeoTransform()[1]  # 空间分辨率
                bounds = self.calculate_bounds(dataset)  # 数据范围
                tile_url = self.generate_tiles(tif_path, basename)  # 生成瓦片

                # 准备波段描述信息
                if sensor_type == 'ASTER':
                    # ASTER标准波段描述
                    band_descriptions = [
                        'VNIR Band 1 (Green)',
                        'VNIR Band 2 (Red)',
                        'VNIR Band 3N (NIR)',
                        'SWIR Band 4',
                        'SWIR Band 5',
                        'SWIR Band 6',
                        'SWIR Band 7',
                        'SWIR Band 8',
                        'SWIR Band 9',
                        'TIR Band 10',
                        'TIR Band 11',
                        'TIR Band 12',
                        'TIR Band 13',
                        'TIR Band 14'
                    ]
                elif sensor_type in ['GF5', 'PRISMA']:
                    # 高光谱数据使用波长信息
                    if wavelength_info and 'wavelengths' in wavelength_info:
                        band_descriptions = [
                            f'Band {i+1} ({wavelength_info["wavelengths"][i]:.2f}nm)'
                            for i in range(dataset.RasterCount)
                        ]
                    else:
                        band_descriptions = [f'Band {i+1}' for i in range(dataset.RasterCount)]
                else:
                    # Sentinel-2标准波段描述
                    band_descriptions = [
                        'Band 1 - Coastal aerosol',
                        'Band 2 - Blue',
                        'Band 3 - Green',
                        'Band 4 - Red',
                        'Band 5 - Vegetation Red Edge',
                        'Band 6 - Vegetation Red Edge',
                        'Band 7 - Vegetation Red Edge',
                        'Band 8 - NIR',
                        'Band 8A - Vegetation Red Edge',
                        'Band 9 - Water vapour',
                        'Band 10 - SWIR/Cirrus',
                        'Band 11 - SWIR',
                        'Band 12 - SWIR'
                    ]
                    # 处理波段数不匹配的情况
                    if len(band_descriptions) != dataset.RasterCount:
                        band_descriptions = [f'Band {i+1}' for i in range(dataset.RasterCount)]

                # 数据入库
                with transaction.atomic():
                    from geodata.models import EnviData
                    
                    # 解析获取日期
                    acquisition_date = None
                    parts = basename.split('_')
                    for part in parts:
                        if len(part) >= 8 and part[:8].isdigit():
                            try:
                                acquisition_date = datetime.strptime(part[:8], '%Y%m%d').date()
                                break
                            except ValueError:
                                continue
                    
                    if not acquisition_date:
                        logger.warning(f"无法从文件名解析日期，使用当前日期")
                        acquisition_date = datetime.now().date()
                    
                    # 创建或更新数据记录
                    EnviData.objects.update_or_create(
                        name=basename,
                        defaults={
                            'file_path': hdr_path,
                            'sensor_type': sensor_type,
                            'acquisition_date': acquisition_date,
                            'resolution': resolution,
                            'center_point': bounds.centroid,
                            'bounds': bounds,
                            'tile_url': tile_url,
                            'coordinate_system': coordinate_system,
                            'thumbnail': f'thumbnails/{basename}_thumb.png',
                            'bands_info': json.dumps({
                                'count': dataset.RasterCount,
                                'descriptions': band_descriptions[:dataset.RasterCount]
                            }),
                            'wavelength_info': json.dumps(wavelength_info) if wavelength_info else None
                        }
                    )

            finally:
                # 清理资源
                if dataset:
                    dataset.FlushCache()
                    dataset = None

                # 清理GDAL驱动
                for i in reversed(range(gdal.GetDriverCount())):
                    drv = gdal.GetDriver(i)
                    if drv is not None:
                        try:
                            drv.Deregister()
                        except Exception as e:
                            logger.warning(f'驱动清理失败: {str(e)}')

                # 清理临时文件
                if os.path.exists(tif_path):
                    try:
                        os.remove(tif_path)
                    except PermissionError as pe:
                        self.stdout.write(self.style.WARNING(f'文件删除重试: {tif_path}'))
                        subprocess.run(f'timeout 5 /C "del /F /Q "{tif_path}""', shell=True)

        except Exception as e:
            logger.error(f'处理失败: {str(e)}')
            raise

            