rem /d (符号链接) 可以识别相对路径
rem /j (目录联接) 只记录绝对路径
mklink /d  "Z:\Computer\Program\Program_maker\python3\PyTools\BaHelper\PaddleOcrModel" "Z:\Computer\Program\Program_maker\manyPython\MinerU-mineru-2.5.0\mineru_pdf_model_cache\hub\models--opendatalab--PDF-Extract-Kit-1.0\snapshots\ed6b654c018d742e65a17671e379c5e6ecc87ec9"
rem New-Item -ItemType SymbolicLink -Path "C:\MyLink" -Target "D:\RealFolder"