import re
import gzip
import httplib
import logging
import StringIO

import requests
from requests.auth import OAuth1

from flixpy.catalog import NetflixCatalog

log = logging.getLogger('flixpy.client')

class NetflixClient(object):
    def __init__(self, application_name, client_key, client_secret, resource_owner_key=None, resource_owner_secret=None, callback=None):
        self.application_name = application_name
        self.server = 'api-public.netflix.com'
        self.connection = httplib.HTTPConnection(self.server, '80')

        # Setting up the OAuth client
        self.client_key = unicode(client_key)
        self.client_secret = unicode(client_secret)

        if callback:
            self.callback = unicode(callback)
        else:
            self.callback = None

        if resource_owner_key and resource_owner_secret:
            self.resource_owner_key = unicode(resource_owner_key)
            self.resource_owner_secret = unicode(resource_owner_secret)
        else:
            self.resource_owner_key = self.resource_owner_secret = None

        # Attach the netflix catalog functions
        self.catalog = NetflixCatalog(self)

    def _request(self, method, url, params=None, default_params=True):
        if not re.match('http', url):
            url = "http://%s%s" % (self.server, url)

        request_params = {}

        if default_params:
            request_params['output'] = u'json'
            request_params['v'] = u'2.0'
            # request_params['application_name'] = self.application_name
        if params:
            request_params = dict(request_params.items() + params.items())

        oauth = OAuth1(self.client_key, self.client_secret, self.resource_owner_key, self.resource_owner_secret, signature_type='auth_header')

        response = requests.request(method, url, params=request_params, allow_redirects=True, auth=oauth, headers={'Accept-encoding': 'gzip'})

        # raise an error if we get it
        response.raise_for_status()

        return response.json

    def get_resource(self, url, params=None, default_params=True):
        return self._request('get', url, params, default_params)

    def post_resource(self, url, params=None):
        return self._request('post', url, params)

    def delete_resource(self, url, params=None):
        return self._request('delete', url, params)

    # Auth

    def get_request_token_url(self):
        response = self.get_resource('/oauth/request_token')
        secret_and_token = (response['oauth_token_secret'], response['oauth_token'])

        url = response['login_url'] + '&application_name=%s&oauth_consumer_key=%s' % (response['application_name'], self.consumer_key)

        if self.callback:
            url += '&oauth_callback=%s' % self.callback

        return (secret_and_token, url)

    def get_access_token(self, secret, token):

        self.client = requests.session(hooks={'pre_request': OAuthHook(token, secret)})

        response = self.get_resource('/oauth/access_token', params={
            'oauth_token': token
        }, default_params=False)

        ## We don't get anything here because we, as normal, send the response twice
        ## issue is that you can only send this once, and requests breaks down there.

    def verify_credentials(self):
        pass

