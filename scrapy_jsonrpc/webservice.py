import logging
import six

from twisted.web import server, resource
from twisted.python.compat import _PY3, nativeString

from scrapy.exceptions import NotConfigured
from scrapy import signals
from scrapy.utils.reactor import listen_tcp

from scrapy_jsonrpc.jsonrpc import jsonrpc_server_call
from scrapy_jsonrpc.serialize import ScrapyJSONEncoder, ScrapyJSONDecoder
from scrapy_jsonrpc.txweb import JsonResource as JsonResource_


logger = logging.getLogger(__name__)


class JsonResource(JsonResource_):

    def __init__(self, crawler, target=None):
        super(JsonResource, self).__init__()

        self.crawler = crawler
        self.json_encoder = ScrapyJSONEncoder(crawler=crawler)

    def getChildWithDefault(self, path, request):
        path = path.decode('UTF-8')
        return super(JsonResource, self).getChildWithDefault(path, request)


class JsonRpcResource(JsonResource):

    def __init__(self, crawler, target=None):
        super(JsonRpcResource, self).__init__(crawler, target)

        self.json_decoder = ScrapyJSONDecoder(crawler=crawler)
        self.crawler = crawler
        self._target = target

    def render_GET(self, request):
        return self.get_target()

    def render_POST(self, request):
        reqstr = request.content.getvalue()
        target = self.get_target()
        return jsonrpc_server_call(target, reqstr, self.json_decoder)

    def getChild(self, name, request):
        target = self.get_target()
        try:
            newtarget = getattr(target, name)
            return JsonRpcResource(self.crawler, newtarget)
        except AttributeError:
            return resource.ErrorPage(404, "No Such Resource", "No such child resource.")

    def get_target(self):
        return self._target


class CrawlerResource(JsonRpcResource):

    ws_name = 'crawler'

    def __init__(self, crawler):
        super(CrawlerResource, self).__init__(crawler, target=crawler)


class RootResource(JsonResource):

    def render_GET(self, request):
        return {'resources': list(self.children.keys())}

    def getChild(self, name, request):
        if name == '':
            return self
        return JsonResource.getChild(self, name, request)


class WebService(server.Site, object):

    def __init__(self, crawler):
        if not crawler.settings.getbool('JSONRPC_ENABLED'):
            raise NotConfigured

        logfile = crawler.settings['JSONRPC_LOGFILE']
        self.crawler = crawler
        self.portrange = [int(x) for x in crawler.settings.getlist('JSONRPC_PORT', [6023, 6073])]
        self.host = crawler.settings.get('JSONRPC_HOST', '127.0.0.1')
        self.noisy = False

        root = RootResource(crawler)
        root.putChild('crawler', CrawlerResource(self.crawler))

        super(WebService, self).__init__(root, logPath=logfile)

        crawler.signals.connect(self.start_listening, signals.engine_started)
        crawler.signals.connect(self.stop_listening, signals.engine_stopped)

    @classmethod
    def from_crawler(cls, crawler):
        return cls(crawler)

    def start_listening(self):
        self.port = listen_tcp(self.portrange, self.host, self)

        logger.debug(
            'Web service listening on {host.host:s}:{host.port:d}'.format(
                host=self.port.getHost()))

    def stop_listening(self):
        self.port.stopListening()

    def log(self, request):
        """
        Write a line representing C{request} to the access log file.

        @param request: The request object about which to log.
        @type request: L{Request}
        """
        try:
            logFile = self.logFile
        except AttributeError:
            pass
        else:
            line = self._logFormatter(self._logDateTime, request) + u"\n"
            if self._nativeize:
                line = nativeString(line)
            # If we're on Python3, we don't need to encode it
            elif _PY3 is False:
                line = line.encode("utf-8")
            logFile.write(line)
