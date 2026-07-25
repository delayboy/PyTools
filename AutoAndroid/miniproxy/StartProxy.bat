mitmdump.exe -s proxy.py -p 7070 -k --set connection_strategy=lazy --set upstream_cert=false
pause
rem  --mode regular@8080  --mode upstream:http://127.0.0.1:10809