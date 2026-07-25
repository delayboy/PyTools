#!/usr/bin/env python

"""
Diego Martins de Siqueira
MIT License
DSDownload - DSDownload is a fully featured download library with focus on performance
"""

import sys
import argparse
import logging
import DSDownload


def main2():
    urls = ['http://favor.delayboy.cn/api/cacheFile?token=Default&filename=%E4%BF%AE%E5%A4%8D%20Windows%2010%20%E5%92%8C%2011%20%E4%B8%8A%E7%9A%84%E6%B0%94%E6%B3%A1%E5%B1%8F%E4%BF%9D_%20_%20r_windows%20(7_26_2025%2012_36_33%20AM).html']
    workers = 2
    output = 'My-Files'

    DSDownload.DSDownload(urls, workers, output)


def main():
    description = "DSDownload is a fully featured download library with focus on performance"
    parser = argparse.ArgumentParser(
        description=description)
    parser.add_argument("--version", action="version", version='1.6.0.2',
                        help="Version Info")
    parser.add_argument("--workers", type=int, default=5,
                        help="Number of parallel downloads. The default is 5.")
    parser.add_argument("--output", type=str, default="downloads",
                        help="Output folder")
    parser.add_argument('urls', type=str, nargs='+',
                        help='URLs to be downloaded')
    parser.add_argument("-v", "--verbose", action="store_true",
                        help="increase output verbosity")

    args = parser.parse_args()

    if args.verbose:
        logging.basicConfig(level=logging.DEBUG)

    download = DSDownload
    if type(sys) is type(DSDownload):
        download = DSDownload.DSDownload

    try:
        download(args.urls, args.workers, args.output)
        print('All files were downloaded.')
    except KeyboardInterrupt:
        print('Interrupt received, stopping downloads')

    sys.exit()


if __name__ == "__main__":
    main2()
