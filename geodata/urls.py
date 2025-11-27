"""
遥感数据管理系统URL配置

本模块定义了遥感数据管理系统的所有URL路由规则，包括：
- 地图显示和交互
- 数据上传和下载
- 工作站管理
- API接口
"""

from django.urls import path
from . import views

# 定义应用的命名空间，用于URL反向解析
app_name = 'geodata'

# URL模式列表
urlpatterns = [
    # 基础页面
    path('', views.map_view, name='map'),  # 主地图页面，显示所有遥感影像范围
    
    # 数据上传相关
    path('upload/', views.process_envi, name='upload'),  # 单文件上传页面
    path('batch-upload/', views.batch_upload, name='batch_upload'),  # 批量上传页面
    path('alteration-upload/', views.alteration_upload, name='alteration_upload'),  # 蚀变数据上传页面
    
    # 文件管理相关
    path('file_list/', views.file_list_view, name='file_list'),  # 文件列表页面
    path('download/<int:file_id>/', views.download_file, name='download_file'),  # 文件下载，需要文件ID
    
    # 工作站管理
    path('workstation/', views.workstation_list, name='workstation_list'),  # 工作站列表页面
    path('workstation/<int:pk>/', views.workstation_detail, name='workstation_detail'),  # 工作站详情页面
    path('workstation/create/', views.create_workstation, name='create_workstation'),  # 创建新工作站
    path('workstation/add-to/', views.add_to_workstation, name='add_to_workstation'),  # 添加文件到工作站
    path('workstation/remove-from/', views.remove_from_workstation, name='remove_from_workstation'),  # 从工作站移除文件
    path('workstation/save-note/', views.save_file_note, name='save_file_note'),  # 保存文件备注
    path('workstation/batch-download/', views.batch_download, name='batch_download'),  # 批量下载工作站文件
    
    # API接口
    path('api/envi-data/', views.envi_data_api, name='envi_data_api'),  # 获取所有遥感数据的GeoJSON
    path('api/spatial-query/', views.spatial_query, name='spatial_query'),  # 空间查询接口
    path('api/download/<str:image_id>/', views.download_image, name='download_image'),  # 影像下载接口
    path('api/image-info/<int:image_id>/', views.image_info, name='image_info'),  # 获取影像详细信息
]