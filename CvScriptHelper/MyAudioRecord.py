import threading

import numpy as np



if __name__ == '__main__':
    myDll = MyDll.MyDll()
    myDll.register_event_hook(1, True)



    def do_record():
        ar.start_record()


    def hook_callback(pk: MyDll.HookPackage):
        if pk.wParam == MyDll.WM_KEYDOWN:
            if pk.code == 162:  # ctrl
                ar.on_ctrl = True

                start_thread(do_record, ())
        else:
            if pk.code == 162:  # ctrl
                ar.on_ctrl = False


    myDll.set_py_hook_proc(hook_callback)
    myDll.message_loop()
