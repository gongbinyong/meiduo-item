from django.conf import settings
from django.core.files.storage import Storage
from fdfs_client.client import Fdfs_client

class FastDFSStorage(Storage):

    def __init__(self, client_conf=None, base_url=None):

        self.client_conf = client_conf or settings.FDFS_CLIENT_CONF
        self.base_url = base_url or settings.FDFS_BASE_URL

    def _open(self,name, mode='rb'):
        pass

    def _save(self,name, content):
        # client = Fdfs_client('meiduo_mall/utils/fastdfs/client.conf')
        client = Fdfs_client(self.client_conf)

        ret = client.upload_by_buffer(content.read())

        if ret.get('Status') != 'Upload successed.':
            raise Exception('文件上传失败')

        return ret.get('Remote file_id')


    def exists(self, name):

        return False

    def url(self, name):

        return  self.base_url + name

"""
# FastDFS
FDFS_BASE_URL = 'http://192.168.103.210:8888/'
FDFS_CLIENT_CONF = os.path.join(BASE_DIR, 'utils/fastdfs/client.conf')

{'Group name': 'group1',
 'Remote file_id': 'group1/M00/00/00/wKhn0lxNDMiAeS9zAAC4j90Tziw48.jpeg',
 'Status': 'Upload successed.',
 'Local file name': '/Users/chao/Desktop/01.jpeg',
 'Uploaded size': '46.00KB',
 'Storage IP': '192.168.103.210'}
"""
