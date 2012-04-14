# -*- coding: utf-8 -*-
import webapp2

import test_base

from protorpc import messages
from protorpc import remote
from protorpc.webapp import service_handlers

from webapp2_extras import protorpc

# Hello service ---------------------------------------------------------------

class HelloRequest(messages.Message):
    my_name = messages.StringField(1, required=True)

class HelloResponse(messages.Message):
    hello = messages.StringField(1, required=True)

class HelloService(remote.Service):
    @remote.method(HelloRequest, HelloResponse)
    def hello(self, request):
        return HelloResponse(hello='Hello, %s!' %
                             request.my_name)

    @remote.method(HelloRequest, HelloResponse)
    def hello_error(self, request):
        raise ValueError()

class AhoyService(remote.Service):
    @remote.method(HelloRequest, HelloResponse)
    def ahoy(self, request):
        return HelloResponse(hello='Ahoy, %s!' %
                             request.my_name)

class HolaService(remote.Service):
    @remote.method(HelloRequest, HelloResponse)
    def hola(self, request):
        return HelloResponse(hello='Hola, %s!' %
                             request.my_name)

service_mappings = protorpc.service_mapping([
    ('/hello', HelloService),
    AhoyService,
])
app = webapp2.WSGIApplication(service_mappings)

service_mappings2 = protorpc.service_mapping({
    '/hola': HolaService,
})
app2 = webapp2.WSGIApplication(service_mappings2)

# Tests -----------------------------------------------------------------------

class TestProtoRPC(test_base.BaseTestCase):

    def test_example(self):
        req = webapp2.Request.blank('/hello.hello')
        req.method = 'POST'
        req.headers['Content-Type'] = 'application/json'
        req.body = '{"my_name": "bob"}'

        rsp = req.get_response(app)
        self.assertEqual(rsp.status_int, 200)
        self.assertEqual(rsp.body, '{"hello": "Hello, bob!"}')

    def test_run_services(self):
        import os
        os.environ['REQUEST_METHOD'] = 'POST'
        os.environ['PATH_INFO'] = '/hello.hello'
        protorpc.run_services([('/hello', HelloService)])

    def test_ahoy(self):
        req = webapp2.Request.blank('/extras_protorpc_test/AhoyService.ahoy')
        req.method = 'POST'
        req.headers['Content-Type'] = 'application/json'
        req.body = '{"my_name": "bob"}'

        rsp = req.get_response(app)
        self.assertEqual(rsp.status_int, 200)
        self.assertEqual(rsp.body, '{"hello": "Ahoy, bob!"}')

    def test_hola(self):
        req = webapp2.Request.blank('/hola.hola')
        req.method = 'POST'
        req.headers['Content-Type'] = 'application/json'
        req.body = '{"my_name": "bob"}'

        rsp = req.get_response(app2)
        self.assertEqual(rsp.status_int, 200)
        self.assertEqual(rsp.body, '{"hello": "Hola, bob!"}')

    def test_unrecognized_rpc_format(self):
        # No content type
        req = webapp2.Request.blank('/hello.hello')
        req.method = 'POST'
        req.body = '{"my_name": "bob"}'

        rsp = req.get_response(app)
        self.assertEqual(rsp.status_int, 400)

        # Invalid content type
        req = webapp2.Request.blank('/hello.hello')
        req.method = 'POST'
        req.headers['Content-Type'] = 'text/xml'
        req.body = '{"my_name": "bob"}'

        rsp = req.get_response(app)
        self.assertEqual(rsp.status_int, 415)

        # Bad request method
        req = webapp2.Request.blank('/hello.hello')
        req.method = 'PUT'
        req.headers['Content-Type'] = 'application/json'
        req.body = '{"my_name": "bob"}'

        rsp = req.get_response(app)
        self.assertEqual(rsp.status_int, 405)

    def test_invalid_method(self):
        # Bad request method
        req = webapp2.Request.blank('/hello.ahoy')
        req.method = 'POST'
        req.headers['Content-Type'] = 'application/json'
        req.body = '{"my_name": "bob"}'

        rsp = req.get_response(app)
        self.assertEqual(rsp.status_int, 400)

    def test_invalid_json(self):
        # Bad request method
        req = webapp2.Request.blank('/hello.hello')
        req.method = 'POST'
        req.headers['Content-Type'] = 'application/json'
        req.body = '"my_name": "bob"'

        rsp = req.get_response(app)
        self.assertEqual(rsp.status_int, 500)

    def test_response_error(self):
        # Bad request method
        req = webapp2.Request.blank('/hello.hello_error')
        req.method = 'POST'
        req.headers['Content-Type'] = 'application/json'
        req.body = '{"my_name": "bob"}'

        rsp = req.get_response(app)
        self.assertEqual(rsp.status_int, 500)

    def test_invalid_paths(self):
        # Not starting with slash.
        #self.assertRaises(ValueError, protorpc.service_mapping, [
        #    ('hello', HelloService),
        #])
        # Trailing slash.
        self.assertRaises(ValueError, protorpc.service_mapping, [
            ('/hello/', HelloService),
        ])
        # Double paths.
        self.assertRaises(protorpc.service_handlers.ServiceConfigurationError,
            protorpc.service_mapping, [
                ('/hello', HelloService),
                ('/hello', HelloService),
            ]
        )

    def test_lazy_services(self):
        service_mappings = protorpc.service_mapping([
            ('/bonjour', 'resources.protorpc_services.BonjourService'),
            'resources.protorpc_services.CiaoService',
        ])
        app = webapp2.WSGIApplication(service_mappings)

        # Bonjour
        req = webapp2.Request.blank('/bonjour.bonjour')
        req.method = 'POST'
        req.headers['Content-Type'] = 'application/json'
        req.body = '{"my_name": "bob"}'

        rsp = req.get_response(app)
        self.assertEqual(rsp.status_int, 200)
        self.assertEqual(rsp.body, '{"hello": "Bonjour, bob!"}')

        # Ciao
        req = webapp2.Request.blank('/resources/protorpc_services/CiaoService.ciao')
        req.method = 'POST'
        req.headers['Content-Type'] = 'application/json'
        req.body = '{"my_name": "bob"}'

        rsp = req.get_response(app)
        self.assertEqual(rsp.status_int, 200)
        self.assertEqual(rsp.body, '{"hello": "Ciao, bob!"}')


if __name__ == '__main__':
    test_base.main()
