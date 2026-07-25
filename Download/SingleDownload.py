import requests
import os


def download_file_requests(url, filename=None, chunk_size=8192):
    """
    使用requests库下载文件（支持大文件分块下载）

    Args:
        url (str): 文件的URL地址
        filename (str, optional): 保存的文件名。如果为None，则使用URL中的文件名
        chunk_size (int, optional): 分块大小，默认为8KB
    """
    response = requests.get(url + "&token=" + token)
    uuid_str = response.json()['uuid']
    # 如果没有指定文件名，则从URL中提取
    if filename is None:
        filename = url.split('/')[-1]

    # 发送GET请求
    try:
        print(f"开始下载: {url}")
        with requests.get(f"http://10.141.153.10:14624/fserver/filePathNew/downLoadFileByUUID?uuid={uuid_str}&isOFD=false&token={token}", stream=True) as r:
            r.raise_for_status()  # 检查请求是否成功

            # 获取文件总大小（如果服务器提供）
            total_size = int(r.headers.get('content-length', 0))

            # 写入文件
            with open(filename, 'wb') as f:
                if total_size == 0:
                    # 没有内容长度信息，直接写入
                    f.write(r.content)
                else:
                    # 分块下载并显示进度
                    downloaded = 0
                    for chunk in r.iter_content(chunk_size=chunk_size):
                        if chunk:  # 过滤掉保持连接的新块
                            f.write(chunk)
                            downloaded += len(chunk)
                            # 显示下载进度
                            print(f"\r下载进度: {downloaded}/{total_size} bytes "
                                  f"({downloaded / total_size * 100:.2f}%)", end='')

            print(f"\n文件已保存为: {filename}")
            return True

    except Exception as e:
        print(f"下载失败: {e}")
        return False


token = "eyJraWQiOiJjZDg5MDQyOWYxNmE0MDQ4ODFlMzY3M2U5YTg1ZTg5OCIsImFsZyI6IlJTMjU2In0.eyJzdWIiOiJhcmNoc2VyIiwiaWF0IjoxNzU1ODM0NjA5LCJleHAiOjE3NTU5MjEwMDksIm5hbWUiOiI3MTAxMDM0OUBIUSIsImlwIjoiMTAuMjUxLjQ2LjI0OCJ9.r1eX0vXJEVRg5mmu7n5McT-5uv-5IqhZ7cq8a7QDoegvUz7vDSW7RSfLrlHAczzaYP8RCHlOLFGiv6TaXpo8GM7uqTJif1u6oOy6GBXDvlvrZiycicrInnp6388migl-LC5cu9aTvCuQnd9ArN8j8BSHmT-yHWQTc6Ajz-o8AGPbrFsdPB8A32cCS53HngGF4ur6RPvcdbFTFJmREvwnx54_rSk_esxdRtzgpvW6ddP3trizJC-f_1ClJbAidBT04x9a_Z0w36YEu16WECM6vPS-uuB6y-PDU5AYCxXr6XE_6jqPkvsUuXeWS1NGfQ-5-LWN9QoDaW7jqcjgHWQp5A"

aim_url = input("输入http地址:\n")
aim_file = input("输入保存的文件名:\n")
# 使用示例

download_file_requests(aim_url, aim_file)
