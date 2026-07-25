from PyTools.MyAwesomeTool.MyUtil import get_file_from_env_path
from __future__ import annotations
import os as os
import pythoncom as pythoncom
import sys as sys
import win32com as win32com
__all__ = ['get_file_from_env_path', 'os', 'pythoncom', 'read_link', 'smart_guess_file_or_link', 'sys', 'walk_all_file', 'win32com', 'write_link']
def read_link(lnk_path: str) -> str:
    ...
def smart_guess_file_or_link(lnk_path: str, use_env = True) -> str:
    ...
def walk_all_file(rootDir) -> list:
    ...
def write_link(lnk_path, target_path):
    ...
