from PyTools.MyAwesomeTool.MyTcpHelper import TcpClient, DefaultTcpClientHandler

if __name__ == '__main__':
    ce_client = TcpClient(DefaultTcpClientHandler(), server_port=5151)
    pk = ce_client.send_str("return json.encode({msg='hello from agent', num=42})", wait=True)
    if pk is not None:
        json_str = pk.get_str_data()
        print("return:",json_str)
    ce_client.stop()
