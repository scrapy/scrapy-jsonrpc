import json

from twisted.web import resource


class JsonResource(resource.Resource, object):

    json_encoder = json.JSONEncoder()

    def __init__(self):
        super(JsonResource, self).__init__()

    def render(self, txrequest):
        r = super(JsonResource, self).render(txrequest)
        return self.render_object(r, txrequest)

    def render_object(self, obj, txrequest):
        r = (self.json_encoder.encode(obj) + "\n").encode()

        txrequest.setHeader('Content-Type', 'application/json')
        txrequest.setHeader('Access-Control-Allow-Origin', '*')
        txrequest.setHeader('Access-Control-Allow-Methods', 'GET, POST, PATCH, PUT, DELETE')
        txrequest.setHeader('Access-Control-Allow-Headers', 'X-Requested-With')
        txrequest.setHeader('Content-Length', len(r))
        return r
