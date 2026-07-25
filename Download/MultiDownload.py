from queue import Queue
import requests
import threading
import os


# download settings


class DownloadThread(threading.Thread):
    def __init__(self, bytes_queue: Queue, url):
        super().__init__(daemon=True)
        self.bytes_queue = bytes_queue
        self.url = url

    def run(self):
        while not self.bytes_queue.empty():
            bytes_range = self.bytes_queue.get()
            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/92.0.4515.159 Safari/537.36 Edg/92.0.902.84",
                "Range": "bytes={}".format(bytes_range[1])
            }
            response = requests.get(self.url, headers=headers)
            with open("files/{}.tmp".format(bytes_range[0]), "wb") as f:
                f.write(response.content)


def get_file_size(url) -> int:
    response = requests.head(url)
    file_length = int(response.headers['Content-Length'])

    return file_length


def get_thread_download(file_length,copies_count) -> list:
    bytes = Queue(copies_count)

    start_bytes = -1
    for i in range(copies_count):
        bytes_size = int(file_length / copies_count) * i

        if i == copies_count - 1: bytes_size = file_length
        bytes_length = "{}-{}".format(start_bytes + 1, bytes_size)

        bytes.put([i, bytes_length])
        start_bytes = bytes_size

    return bytes


def create_threading(bytes_queue,thread_count,url):
    thread_list = []
    for i in range(thread_count):
        thread = DownloadThread(bytes_queue, url)
        thread.start()
        thread_list.append(thread)

    for thread in thread_list:
        thread.join()


def composite_file(filename, copies_count):
    if os.path.isfile(filename): os.remove(filename)
    with open(filename, "ab") as f:
        for i in range(copies_count):
            with open("files/{}.tmp".format(i), "rb") as bytes_f:
                f.write(bytes_f.read())

    for i in os.listdir("files"):
        os.remove("files/{}".format(i))


def main():
    d_url = "http://img1.baidu.com/it/u=2476325767,3197989021&fm=26&fmt=auto"
    filename = "img.jpg"
    thread_count = 5
    copies_count = 20
    file_length = get_file_size(d_url)
    copies_queue = get_thread_download(file_length,copies_count)
    create_threading(copies_queue,thread_count,d_url)
    composite_file(filename, copies_count)


if __name__ == '__main__':
    main()
