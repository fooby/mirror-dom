import util
import time

class Blah(util.TestBrowserBase):
    pass


def main():
    server = util.get_simple_http_server()
    a = server.server_address
    print a
    print "http://%s:%s/test_javascript.html" % (a[0], a[1])
    server.serve_forever()
    #t = util.HttpServerThread(server)
    #t.start()
    #try:
    #    while True:
    #        time.sleep(0.001)
    #except KeyboardInterrupt:
    #    print "Trying to stop it"
    #    t.stop_server()

if __name__ == "__main__":
    main()
