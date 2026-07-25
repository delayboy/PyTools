import inspect

import os
import shutil


def generate_stub(module):
    for name, obj in inspect.getmembers(module):
        if inspect.isfunction(obj):
            args = inspect.signature(obj)
            print(f"def {name}{args}: # real signature unknown")
            print("    pass\n")
        elif inspect.isclass(obj):
            print(f"class {name}:")
            print("    pass\n")


def get_all_file(path):
    build_dir = os.path.join(path, "build")

    for root, dirs, files in os.walk(path):
        for name in files:
            file_path = os.path.join(root, name)

            if name.endswith(".pyd") and root.__contains__("MyAwesomeTool") and not root.__contains__("_internal"):
                file_path2 = os.path.join(root, os.path.splitext(name)[0] + ".pyi")
                if not os.path.exists(file_path2):
                    print(file_path)
                    os.system(
                        f'pybind11-stubgen --ignore-unresolved-names \"_abc.*\" PyTools.MyAwesomeTool.{os.path.splitext(name)[0]}')
                    input()
                # print("else", file_path)


if __name__ == '__main__':
    paths = os.path.abspath("py_files/PyTools")  # sys.argv[1]
    get_all_file(paths)
    shutil.copytree("./stubs/PyTools", "./py_files/PyTools", dirs_exist_ok=True)
    shutil.rmtree("./stubs/PyTools")
    # generate_stub(your_module)
