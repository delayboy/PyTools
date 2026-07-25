#!/usr/bin/env python

"""
Diego Martins de Siqueira
MIT License
DSDownload - DSDownload is a fully featured download library with focus on performance
"""
import threading
import os
import logging
import queue as Queue
import urllib.request as urllib2


def myLogInfo(s: str):
    print(s)


class DownloadThread(threading.Thread):
    colors = [
        '\033[91m',
        '\033[92m',
        '\033[94m',
        '\033[96m',
        '\033[97m',
        '\033[93m',
        '\033[95m',
        '\033[90m',
        '\033[90m',
        '\033[99m',
    ]

    color_reset = '\033[0m'

    def __init__(self, queue, dest_folder='downloads'):
        super(DownloadThread, self).__init__()

        self._queue = queue
        self._dest_folder = dest_folder
        self.daemon = True

        self._handle_folder(self._dest_folder)

    @staticmethod
    def _handle_folder(folder):
        myLogInfo('Testing Folder: ' + folder)
        if not os.path.exists(folder):
            myLogInfo('Folder not found')
            myLogInfo('Creating Folder: ' + folder)
            os.makedirs(folder)

    def run(self):

        while True:
            myLogInfo('Getting URL from Queue')
            url = self._queue.get()
            myLogInfo('URL:' + url)

            try:
                myLogInfo('Preparing to Download url:' + url)
                self.prepare_download(url)
                myLogInfo('Download complete url:' + url)

            except Exception as e:
                myLogInfo('Error downloading')
                print("Error: {0}".format(e))
                raise e

            myLogInfo('Task Done!')
            self._queue.task_done()

    def get_color(self, num):
        myLogInfo('Getting Color')
        color_index = int(num) % len(self.colors)

        myLogInfo('ColorIndex to Worker' + str(num) + ': ' + str(color_index))
        return self.colors[color_index]

    @staticmethod
    def get_file_name(headers, url):

        myLogInfo('Getting Content Disposition')
        con_disposition = headers.get('Content-Disposition')

        if con_disposition:
            myLogInfo('Content Disposition Found')
            myLogInfo('Searching for filename')
            con_name = con_disposition.split('filename=')[-1].replace('"', '').replace(';', '')

            if con_name:
                myLogInfo('Filename found: ' + con_name)
                return con_name

        myLogInfo('Spliting URL for filename')
        file_name = str(url.split('/')[-1])
        if file_name.__contains__("?"):
            file_name = file_name.split("?")[0]
        myLogInfo('Filename: ' + file_name)

        return file_name

    def prepare_download(self, url):

        wnum = threading.current_thread().name.split('-')[-1]
        myLogInfo('Finding Worker number: ' + wnum)

        color = self.get_color(wnum)

        myLogInfo('Opening connection')
        require = urllib2.Request(url)
        require.add_header('User-Agent', "pan.baidu.com")
        url_con = urllib2.urlopen(require)

        myLogInfo('Getting metadata')
        meta = url_con.info()

        file_name = self.get_file_name(meta, url)

        dest = os.path.join(self._dest_folder, file_name)
        myLogInfo('Folder: ' + self._dest_folder)
        myLogInfo('Destination: ' + dest)

        myLogInfo('Opening file')
        dest_file = open(dest, 'wb')

        myLogInfo('Getting file size')
        file_size = meta.get("Content-Length")
        myLogInfo('File size:' + str(file_size))

        print(color + "Downloading: %s Bytes: %s" % (file_name, file_size) + self.color_reset)

        file_size = 0
        block_size = 8192
        myLogInfo('Block size:' + str(block_size))

        while True:
            buffer = url_con.read(block_size)
            if not buffer:
                break

            myLogInfo('Total Downloaded: ' + str(file_size))
            file_size += len(buffer)
            dest_file.write(buffer)

        myLogInfo('Total Downloaded: ' + str(file_size))
        myLogInfo('Closing file')
        dest_file.close()


def DSDownload(url_list, workers=5, folder_path='downloads'):
    myLogInfo('Starting DSDownload')
    queue = Queue.Queue()
    myLogInfo('Instantiating Queue')

    for url in url_list:
        myLogInfo('Add url to Queue: ' + url)
        queue.put(url)

    myLogInfo('Testing number of Workers')
    workers = workers if workers < len(url_list) else len(url_list)
    myLogInfo('Workers:' + str(workers))

    for worker in range(workers):
        worker = str(worker + 1)
        myLogInfo('Instantiating Worker: ' + worker)
        t = DownloadThread(queue, folder_path)
        myLogInfo('Starting Worker: ' + worker)
        t.start()

    myLogInfo('Waiting Workers')
    queue.join()
