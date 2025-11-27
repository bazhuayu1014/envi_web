from django.contrib.gis.db import models  # GeoDjango模型
from django.utils import timezone  # 时区工具
from django.core.files.storage import FileSystemStorage  # 文件存储
import os  # 操作系统接口

class KeepNameFileStorage(FileSystemStorage):
    """自定义文件存储类
    保持原始文件名，如果文件已存在则覆盖
    """
    def get_valid_name(self, name):
        """保持原始文件名"""
        return name

    def get_available_name(self, name, max_length=None):
        """如果文件已存在，先删除它"""
        if self.exists(name):
            self.delete(name)
        return name

# 创建存储实例
keep_name_storage = KeepNameFileStorage()

class EnviFile(models.Model):
    """ENVI文件模型
    存储ENVI格式的遥感影像文件对（.hdr和.img文件）
    支持原始数据和两种蚀变分析方法的结果
    """
    # 基本信息
    name = models.CharField('文件名', max_length=500, blank=True)  # 文件名
    description = models.TextField('描述', blank=True)  # 文件描述
    upload_date = models.DateTimeField('上传时间', auto_now_add=True)  # 上传时间
    download_count = models.IntegerField('下载次数', default=0)  # 下载计数
    
    # 原始数据文件
    hdr_file = models.FileField(
        'HDR文件', 
        upload_to='envi_files/', 
        max_length=500, 
        storage=keep_name_storage
    )  # 头文件
    img_file = models.FileField(
        'IMG文件', 
        upload_to='envi_files/', 
        max_length=500, 
        storage=keep_name_storage
    )  # 数据文件
    
    # PC方法蚀变数据文件
    pc_hdr_file = models.FileField(
        'PC方法HDR文件', 
        upload_to='alteration_files/', 
        null=True, 
        blank=True, 
        max_length=500, 
        storage=keep_name_storage
    )  # PC方法头文件
    pc_img_file = models.FileField(
        'PC方法IMG文件', 
        upload_to='alteration_files/', 
        null=True, 
        blank=True, 
        max_length=500, 
        storage=keep_name_storage
    )  # PC方法数据文件
    
    # Ratio方法蚀变数据文件
    ratio_hdr_file = models.FileField(
        'Ratio方法HDR文件', 
        upload_to='alteration_files/', 
        null=True, 
        blank=True, 
        max_length=500, 
        storage=keep_name_storage
    )  # Ratio方法头文件
    ratio_img_file = models.FileField(
        'Ratio方法IMG文件', 
        upload_to='alteration_files/', 
        null=True, 
        blank=True, 
        max_length=500, 
        storage=keep_name_storage
    )  # Ratio方法数据文件

    @property
    def has_pc_alteration(self):
        """检查是否有PC方法蚀变数据"""
        return bool(self.pc_hdr_file and self.pc_img_file)
    
    @property
    def has_ratio_alteration(self):
        """检查是否有Ratio方法蚀变数据"""
        return bool(self.ratio_hdr_file and self.ratio_img_file)
    
    @property
    def file_size(self):
        """获取文件大小"""
        try:
            return self.img_file.size if self.img_file else 0
        except:
            return 0

    def __str__(self):
        """返回文件的字符串表示"""
        return self.name or self.hdr_file.name
    
    def save(self, *args, **kwargs):
        """保存模型
        如果没有设置名称，使用文件名作为名称
        """
        if not self.name and self.hdr_file:
            self.name = os.path.splitext(os.path.basename(self.hdr_file.name))[0]
        super().save(*args, **kwargs)
    
    class Meta:
        verbose_name = 'ENVI文件'
        verbose_name_plural = verbose_name
        ordering = ['-upload_date']

class EnviData(models.Model):
    """遥感影像元数据模型
    存储遥感影像的元数据信息，包括空间信息、波段信息等
    """
    # 传感器类型选项
    SENSOR_TYPES = (
        ('S2', 'Sentinel-2 多光谱'),
        ('GF5', 'GF5 高光谱'),
        ('ASTER', 'ASTER 多光谱'),
        ('PRISMA', 'PRISMA 高光谱'),
    )
    
    # 基本信息
    name = models.CharField('影像名称', max_length=500, unique=True)  # 影像名称
    sensor_type = models.CharField(
        '传感器类型', 
        max_length=10, 
        choices=SENSOR_TYPES, 
        default='S2'
    )  # 传感器类型
    file_path = models.FilePathField(
        '文件路径', 
        path='E:/graduation_bzy/data', 
        max_length=500
    )  # 文件路径
    acquisition_date = models.DateField('获取时间')  # 获取时间
    
    # 空间信息
    coordinate_system = models.CharField('坐标系', max_length=500)  # 坐标系
    resolution = models.FloatField('分辨率(m)')  # 空间分辨率
    bounds = models.PolygonField('空间范围', srid=4326, dim=2)  # 空间范围
    center_point = models.PointField('中心点', srid=4326, dim=2)  # 中心点
    
    # 波段信息
    bands_info = models.JSONField('波段信息')  # 波段信息
    wavelength_info = models.JSONField('波长信息', null=True, blank=True)  # 波长信息
    
    # 显示信息
    thumbnail = models.ImageField('缩略图', upload_to='thumbnails/', max_length=500)  # 缩略图
    tile_url = models.CharField(
        '瓦片URL', 
        max_length=500, 
        default='/static/tiles/default/{z}/{x}/{y}.png'
    )  # 瓦片URL模板
    
    # 关联信息
    envi_file = models.OneToOneField(
        EnviFile,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='envi_data'
    )  # 关联的ENVI文件
    
    # 时间信息
    created_at = models.DateTimeField('创建时间', default=timezone.now)  # 创建时间
    updated_at = models.DateTimeField('更新时间', auto_now=True)  # 更新时间
  
    class Meta:
        db_table = 'geodata_envidata'  # 数据库表名
        ordering = ['-created_at']  # 按创建时间倒序排序

    def __str__(self):
        """返回影像的字符串表示"""
        return self.name

    def save(self, *args, **kwargs):
        """保存模型
        设置创建时间
        """
        if not self.created_at:
            self.created_at = timezone.now()
        super().save(*args, **kwargs)

class WorkStation(models.Model):
    """个人工作站模型
    用于组织和管理用户的遥感影像数据
    """
    name = models.CharField('工作站名称', max_length=100)  # 工作站名称
    description = models.TextField('描述', blank=True, null=True)  # 描述
    user = models.ForeignKey(
        'auth.User', 
        on_delete=models.CASCADE, 
        verbose_name='用户'
    )  # 所属用户
    created_at = models.DateTimeField('创建时间', auto_now_add=True)  # 创建时间
    updated_at = models.DateTimeField('更新时间', auto_now=True)  # 更新时间

    class Meta:
        verbose_name = '工作站'
        verbose_name_plural = verbose_name
        ordering = ['-created_at']

    def __str__(self):
        """返回工作站的字符串表示"""
        return f"{self.user.username}的工作站: {self.name}"

class WorkStationFile(models.Model):
    """工作站文件关联模型
    管理工作站和ENVI文件的关联关系
    """
    workstation = models.ForeignKey(
        WorkStation, 
        on_delete=models.CASCADE, 
        verbose_name='工作站'
    )  # 关联的工作站
    envi_file = models.ForeignKey(
        EnviFile, 
        on_delete=models.CASCADE, 
        verbose_name='ENVI文件'
    )  # 关联的ENVI文件
    added_at = models.DateTimeField('添加时间', auto_now_add=True)  # 添加时间
    notes = models.TextField('备注', blank=True, null=True)  # 备注

    class Meta:
        verbose_name = '工作站文件'
        verbose_name_plural = verbose_name
        ordering = ['-added_at']
        # 确保同一个文件不会被重复添加到同一个工作站
        unique_together = ['workstation', 'envi_file']

    def __str__(self):
        """返回关联的字符串表示"""
        return f"{self.workstation.name} - {self.envi_file.name}"