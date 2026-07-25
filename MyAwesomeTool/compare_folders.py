# -*- coding: utf-8 -*-
"""
Python script for comparing the contents of two directories.
@author: Roger Woodman
"""
import fnmatch
import os
import re


class DirectoryComparison():
    """Compare the contents of two directories"""

    def __init__(self, path1, path2):
        """Initialise variables

        :param path1: First path to compare
        :param path2: Second path to compare
        """
        # The folders containing files
        self.path1 = path1
        self.path2 = path2

    def printDirecotryDifferences(self):
        """Print all the file differences for the two paths"""
        filesAndSizes1 = self.getAllFilesAndSizes(self.path1)
        filesAndSizes2 = self.getAllFilesAndSizes(self.path2)

        # Display file and size for path 1
        print("-----------------------------")
        print("Number of files: %s" % str(len(filesAndSizes1)))
        print("-----------------------------")
        for pair in filesAndSizes1:
            print(pair)

        # Display file and size for path 2
        print("-----------------------------")
        print("Number of files: %s" % str(len(filesAndSizes2)))
        print("-----------------------------")
        for pair in filesAndSizes2:
            print(pair)

            # Display the differences for path 1
        difference = list(set(filesAndSizes1) - set(filesAndSizes2))
        print("-----------------------------")
        print("Files in '%s', not in other folder: %s" % (self.path2, str(len(difference))))
        print("-----------------------------")
        for pair in difference:
            print(pair)

            # Display the differences for path 2
        difference = list(set(filesAndSizes2) - set(filesAndSizes1))
        print("-----------------------------")
        print("Files in '%s', not in other folder: %s" % (self.path1, str(len(difference))))
        print("-----------------------------")
        for pair in difference:
            print(pair)

    def getAllFilesAndSizes(self, searchPath):
        """Gets all the file names and sizes in a path

        :param searchPath: Search path
        """
        includes = ['*.doc', '*.odt']  # for files only
        excludes = ['node_modules']  # for dirs and files

        # transform glob patterns to regular expressions
        includes = r'|'.join([fnmatch.translate(x) for x in includes])
        excludes = r'|'.join([fnmatch.translate(x) for x in excludes]) or r'$.'
        pairs = []
        # Loop and add files to list.
        for path, dirs, files in os.walk(searchPath):
            # exclude dirs
            dirs[:] = [os.path.join(path, d) for d in dirs]
            dirs[:] = [d for d in dirs if not re.match(excludes, d)]
            # exclude/include files
            # files = [os.path.join(path, f) for f in files]
            # files = [f for f in files if not re.match(excludes, f)]
            # files = [f for f in files if re.match(includes, f)]
            if path.__contains__("node_modules"):
                print("skip")
                continue
            for name in files:
                location = os.path.join(path, name)
                print(location)
                # Get size and add to list of tuples.
                size = os.path.getsize(location)
                pairs.append((size, name))

        # Sort list of tuples by the first element, size.
        pairs.sort(key=lambda s: s[0])
        return pairs


if __name__ == '__main__':
    # Directory comparison test
    directoryComparison = DirectoryComparison(r"D:\ComputerBackup\Program\Program_maker",
                                              r"Z:\Computer\Program\Program_maker")
    directoryComparison.printDirecotryDifferences()
