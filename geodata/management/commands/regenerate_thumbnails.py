from django.core.management.base import BaseCommand
from django.conf import settings
from geodata.models import EnviData, EnviFile
import os
import subprocess
import logging
from osgeo import gdal, osr

logger = logging.getLogger(__name__)

class Command(BaseCommand):
    help = '重新生成所有遥感数据的缩略图'

    def _configure_gdal(self):
        """配置GDAL环境"""
        proj_path = r'D:\Anaconda3\envs\envi_web\Library\share\proj'
        gdal_path = r'D:\Anaconda3\envs\envi_web\Library\share\gdal'
        bin_path = r'D:\Anaconda3\envs\envi_web\Library\bin'

        os.environ.update({
            'PROJ_LIB': proj_path,
            'GDAL_DATA': gdal_path,
            'PATH': f"{bin_path};{os.environ['PATH']}"
        })

        gdal.SetConfigOption('GDAL_DATA', gdal_path)
        gdal.SetConfigOption('PROJ_LIB', proj_path)
        gdal.AllRegister()
        gdal.UseExceptions()

    def handle(self, *args, **options):
        self._configure_gdal()
        
        # 获取所有EnviData记录
        envi_data_records = EnviData.objects.all()
        total = envi_data_records.count()
        
        self.stdout.write(f'开始处理 {total} 条记录的缩略图...')
        
        # 创建缩略图目录
        thumbnail_dir = os.path.join(settings.BASE_DIR, 'media', 'thumbnails')
        os.makedirs(thumbnail_dir, exist_ok=True)
        
        # 清理现有缩略图
        for file in os.listdir(thumbnail_dir):
            if file.endswith('.png'):
                try:
                    os.remove(os.path.join(thumbnail_dir, file))
                except Exception as e:
                    self.stdout.write(self.style.WARNING(f'删除文件失败 {file}: {str(e)}'))

        success_count = 0
        error_count = 0
        
        for i, data in enumerate(envi_data_records, 1):
            self.stdout.write(f'处理第 {i}/{total} 条记录: {data.name}')
            
            try:
                # 创建临时TIFF文件
                basename = data.name
                tif_path = os.path.join(settings.BASE_DIR, 'static', 'temp', f'{basename}.tif')
                os.makedirs(os.path.dirname(tif_path), exist_ok=True)
                
                # 获取IMG文件路径
                if data.envi_file and data.envi_file.img_file:
                    img_path = data.envi_file.img_file.path
                else:
                    img_path = data.file_path.replace('.hdr', '.img')
                
                # 转换为TIFF格式
                subprocess.run(
                    f'gdal_translate -of GTiff "{img_path}" "{tif_path}"',
                    shell=True,
                    check=True
                )
                
                # 生成新的缩略图
                thumbnail_path = os.path.join(thumbnail_dir, f'{basename}_thumb.png')
                
                # 步骤1: 获取数据统计信息
                dataset = gdal.Open(tif_path)
                if not dataset:
                    raise Exception("无法打开TIFF文件")
                
                try:
                    # 确保有足够的波段
                    if dataset.RasterCount < 4:
                        raise Exception(f"波段数量不足: {dataset.RasterCount}")
                    
                    # 步骤2: 创建临时VRT文件用于波段组合
                    vrt_path = os.path.join(settings.BASE_DIR, 'static', 'temp', f'{basename}_thumb.vrt')
                    
                    # 使用正确的波段顺序：4(红),3(绿),2(蓝)
                    subprocess.run(
                        f'gdalbuildvrt -separate '
                        f'-b 4 -b 3 -b 2 '  # 指定波段顺序：红绿蓝
                        f'"{vrt_path}" "{tif_path}"',
                        shell=True,
                        check=True
                    )
                    
                    # 步骤3: 生成缩略图
                    # 对于Sentinel-2 L2A数据，反射率通常在0-10000范围内
                    subprocess.run(
                        f'gdal_translate -of PNG -ot Byte '
                        f'-outsize 256 256 '
                        f'-scale_1 0 4000 0 255 '  # 红波段
                        f'-scale_2 0 4000 0 255 '  # 绿波段
                        f'-scale_3 0 4000 0 255 '  # 蓝波段
                        f'-r bilinear '
                        f'"{vrt_path}" "{thumbnail_path}"',
                        shell=True,
                        check=True
                    )
                    
                finally:
                    # 清理资源
                    dataset = None
                    if os.path.exists(vrt_path):
                        os.remove(vrt_path)
                
                # 更新数据库记录
                data.thumbnail = f'thumbnails/{basename}_thumb.png'
                data.save()
                
                success_count += 1
                self.stdout.write(self.style.SUCCESS(f'成功处理: {basename}'))
                
            except Exception as e:
                error_count += 1
                self.stdout.write(self.style.ERROR(f'处理失败 {basename}: {str(e)}'))
                logger.error(f'缩略图生成失败 {basename}: {str(e)}', exc_info=True)
            
            finally:
                # 清理临时文件
                if os.path.exists(tif_path):
                    try:
                        os.remove(tif_path)
                    except Exception as e:
                        logger.warning(f'临时文件删除失败 {tif_path}: {str(e)}')
        
        # 输出总结
        self.stdout.write('\n处理完成!')
        self.stdout.write(f'成功: {success_count}')
        self.stdout.write(f'失败: {error_count}')
        if error_count > 0:
            self.stdout.write(self.style.WARNING('请检查日志获取详细错误信息')) 