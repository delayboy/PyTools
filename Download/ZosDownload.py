import requests
import hmac
import hashlib
import base64
from datetime import datetime
from urllib.parse import quote, urlparse
import time


class ZOSDownloader:
    def __init__(self, access_id, access_key, endpoint, bucket_name):
        self.access_id = access_id
        self.access_key = access_key
        self.endpoint = endpoint
        self.bucket_name = bucket_name

    def _get_s3_date(self):
        """获取S3格式的日期"""
        return datetime.utcnow().strftime('%a, %d %b %Y %H:%M:%S GMT')

    def _sign_v2_s3(self, method, bucket_name, object_key, headers):
        """生成S3兼容的V2签名"""
        # 构建规范化的资源路径
        resource = f"/{bucket_name}/{object_key}"

        # 获取必要的头信息
        content_md5 = headers.get('Content-MD5', '')
        content_type = headers.get('Content-Type', '')
        date = headers.get('Date', '')

        # 构建规范化的头信息（以x-amz-开头的头）
        amz_headers = []
        for key, value in headers.items():
            if key.lower().startswith('x-amz-'):
                amz_headers.append(f"{key.lower()}:{value.strip()}")

        amz_headers.sort()
        canonical_amz_headers = '\n'.join(amz_headers)
        if canonical_amz_headers:
            canonical_amz_headers += '\n'

        # 构建待签名的字符串
        string_to_sign = (
            f"{method}\n"
            f"{content_md5}\n"
            f"{content_type}\n"
            f"{date}\n"
            f"{canonical_amz_headers}"
            f"{resource}"
        )

        print("String to sign:", repr(string_to_sign))

        # 使用HMAC-SHA1进行签名
        h = hmac.new(
            self.access_key.encode('utf-8'),
            string_to_sign.encode('utf-8'),
            hashlib.sha1
        )

        # Base64编码签名
        signature = base64.b64encode(h.digest()).decode('utf-8')

        return f"AWS {self.access_id}:{signature}"

    def download_file(self, object_key, local_file_path):
        """下载文件"""
        # 构建请求头
        headers = {
            'Date': self._get_s3_date(),
            'Content-Type': '',
        }

        # 生成签名
        signature = self._sign_v2_s3('GET', self.bucket_name, object_key, headers)
        headers['Authorization'] = signature

        # 构建请求URL
        url = f"http://{self.endpoint}/{self.bucket_name}/{quote(object_key)}"
        print(f"Request URL: {url}")
        print(f"Headers: {headers}")

        try:
            # 发送GET请求下载文件
            response = requests.get(url, headers=headers, stream=True, timeout=(30, 300))

            print(f"Response status: {response.status_code}")
            print(f"Response headers: {dict(response.headers)}")

            if response.status_code == 200:
                # 保存文件到本地
                with open(local_file_path, 'wb') as f:
                    for chunk in response.iter_content(chunk_size=8192):
                        if chunk:
                            f.write(chunk)
                print(f"文件下载成功: {local_file_path}")
                return True
            else:
                print(f"下载失败，状态码: {response.status_code}")
                print(f"错误信息: {response.text}")
                return False

        except Exception as e:
            print(f"下载过程中发生错误: {str(e)}")
            return False


# 使用示例
if __name__ == "__main__":
    # 配置参数
    OOS_ACCESS_ID = "KYWASH05KGNTBW1FUFTE"
    OOS_ACCESS_KEY = "sFhvLe0WDNiJboyGPJ7n3SFWrm8Q9sg1zHaxFLKy"
    OOS_ENDPOINT = "10.141.153.10:14603"
    bucketName = "mss-dams-manage-file"

    # 创建下载器实例
    downloader = ZOSDownloader(OOS_ACCESS_ID, OOS_ACCESS_KEY, OOS_ENDPOINT, bucketName)
    aim_file = input("输入要下载的文件名:")
    # 要下载的对象键和本地保存路径
    object_key = f"/duan/{aim_file}"  # 替换为实际的文件路径01c1d8c44d5341ffa5f1d2c2595311a2
    local_path = aim_file  # 本地保存路径

    # 下载文件
    success = downloader.download_file(object_key, local_path)

    if success:
        print("文件下载完成！")
    else:
        print("文件下载失败！")