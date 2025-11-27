import os
import shutil
import datetime

def create_project_package():
    # 创建打包时间戳
    timestamp = datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
    package_name = f'envi_web_package_{timestamp}'
    
    # 创建打包目录
    os.makedirs(package_name, exist_ok=True)
    
    # 复制项目文件
    dirs_to_copy = [
        'accounts',
        'geodata',
        'envi_web',
        'static',
        'media',
        'staticfiles',
    ]
    
    files_to_copy = [
        'manage.py',
        'requirements.txt',
        'DEPLOYMENT.md',
        'envi_geo_backup.dump',
    ]
    
    # 复制目录
    for dir_name in dirs_to_copy:
        if os.path.exists(dir_name):
            shutil.copytree(dir_name, os.path.join(package_name, dir_name))
            print(f'已复制目录: {dir_name}')
    
    # 复制文件
    for file_name in files_to_copy:
        if os.path.exists(file_name):
            shutil.copy2(file_name, package_name)
            print(f'已复制文件: {file_name}')
    
    # 创建打包文件
    shutil.make_archive(package_name, 'zip', package_name)
    
    # 清理临时目录
    shutil.rmtree(package_name)
    
    print(f'\n打包完成！文件名: {package_name}.zip')
    print('请确保将以下文件一并迁移：')
    print('1. 数据库备份文件: envi_geo_backup.dump')
    print('2. media 目录中的所有文件')
    print('3. static 目录中的所有文件')
    print('4. requirements.txt')
    print('5. DEPLOYMENT.md 部署指南\n')

if __name__ == '__main__':
    create_project_package() 