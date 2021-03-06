import re
import gzip
import json
import time
import os.path
import httplib
import urllib2
import logging
import StringIO

from datetime import datetime

import oauth2 as oauth

from urlparse import urlparse

# For Oauth
REQUEST_TOKEN_URL = 'api-public.netflix.com/oauth/request_token'
ACCESS_TOKEN_URL  = 'api-public.netflix.com/oauth/access_token'

AUTHORIZATION_URL = 'https://api-user.netflix.com/oauth/login'

TITLE_URL = 'http://schemas.netflix.com/catalog/title'

# parent URLS
SERIES_URL = 'http://schemas.netflix.com/catalog/titles.series'
SEASON_URL = 'http://schemas.netflix.com/catalog/title.season'
DISC_URL = 'http://schemas.netflix.com/catalog/title.disc'

# children URLs
SEASONS_URL = 'http://schemas.netflix.com/catalog/titles.seasons'
DISCS_URL = 'http://schemas.netflix.com/catalog/titles.discs'
EPISODES_URL = 'http://schemas.netflix.com/catalog/titles.programs'

disk_pattern = re.compile(':? ?([Vv]ol.? \d+|[dD]isc \d+):? ?')

log = logging.getLogger('flixpy.base')

class NetflixClient:
    def __init__(self, application_name, consumer_key, consumer_secret, token_key=None, token_secret=None):
        self.server = 'api-public.netflix.com'
        self.connection = httplib.HTTPConnection(self.server, '80')

        self.catalog = NetflixCatalog(self)

        self.params = {
            'oauth_version': "1.0",
            'oauth_nonce': oauth.generate_nonce(),
            'oauth_timestamp': int(time.time()),
            'output': 'json',

            'application_name': application_name,

        }

        self.signature_method = oauth.SignatureMethod_HMAC_SHA1()

        self.consumer = oauth.Consumer(key=consumer_key, secret=consumer_secret)
        self.params['oauth_consumer_key'] = self.consumer.key

        if token_key and token_secret:
            self.token = oauth.Token(key=token_key, secret=token_secret)
            self.params['oauth_token'] = self.token.key

            self.user = NetflixUser()
        else:
            self.user = None



    def _get_resource(self, url, token=None, parameters={}):
        if not re.match('http', url):
            url = "http://%s%s" % (self.server, url)

        oauthRequest = oauth.OAuthRequest.from_consumer_and_token(
                                    self.consumer,
                                    http_url=url,
                                    parameters=parameters,
                                    token=token)
        oauthRequest.sign_request(
                                    self.signature_method_hmac_sha1,
                                    self.consumer,
                                    token)

        headers = {'Accept-encoding':'gzip'}

        req = urllib2.Request(oauthRequest.to_url(), None, headers)
        response = urllib2.urlopen(req)
        data = gzip.GzipFile(fileobj=StringIO.StringIO(response.read())).read()
        return data

    def _post_resource(self, url, token=None, parameters=None):
        if not re.match('http',url):
            url = "http://%s%s" % (HOST, url)

        oauthRequest = oauth.OAuthRequest.from_consumer_and_token(
                                    self.consumer,
                                    http_url=url,
                                    parameters=parameters,
                                    token=token,
                                    http_method='POST')
        oauthRequest.sign_request(
                                    self.signature_method_hmac_sha1,
                                    self.consumer,
                                    token)

        headers = {'Content-Type':'application/x-www-form-urlencoded',
                   'Accept-encoding':'gzip'}

        data = oauthRequest.to_postdata()
        req = urllib2.Request(oauthRequest.to_url(), data, headers)
        response = urllib2.urlopen(req)
        data = gzip.GzipFile(fileobj=StringIO.StringIO(response.read())).read()
        return data

    def _delete_resource(self, url, token=None, parameters=None):
        if not re.match('http',url):
            url = "http://%s%s" % (HOST, url)

        oauthRequest = oauth.OAuthRequest.from_consumer_and_token(
                                    self.consumer,
                                    http_url=url,
                                    parameters=parameters,
                                    token=token,
                                    http_method='DELETE')
        oauthRequest.sign_request(
                                    self.signature_method_hmac_sha1,
                                    self.consumer,
                                    token)

        self.connection.request('DELETE', oauthRequest.to_url())
        response = self.connection.getresponse()
        return response.read()

class NetflixBase(object):
    ''' This is the base netflix object class that User, Title, and Person are currently built on'''
    def __init__(self, raw_json, client):
        self.info = raw_json
        self.client = client

    def get_info(self,field):
        # try and get a token from the clients user object (if it exists)
        try:
            token = self.client.user.accessToken
        except AttributeError:
            token = None

        fields = []
        url = ''
        for link in self.info['link']:
            fields.append('title: %s | rel: %s' % (link['title'], link['rel']))
            if link['title'] == field or link['rel'] == field:
                url = link['href']
        if not url:
            errorString = "Invalid or missing field.  " + \
                          "Acceptable fields for this object are:\n" + \
                          "\n\n".join(fields)
            log.debug(errorString)
            return None
        try:
            return json.loads(self.client._get_resource(url, token))
        except:
            return []

    def get_infoLink(self,field):
        for link in self.info['link']:
            if link['title'] == field or link['rel'] == field:
                return link['href']
        return None

class NetflixUser(NetflixBase):
    def __init__(self):
        requestUrl = '/users/current'

        raw_json = json.loads(
            client._get_resource(
                requestUrl,
                token=self.accessToken
            )
        )

        super(NetflixUser, self).__init__(raw_json['user'], client)

    @property
    def name(self):
        first = self.info['first_name']
        last = self.info['last_name']

        return "%s %s" % (first, last)

    @property
    def preferred_formats(self):
        if isinstance(self.info['preferred_formats']['category'], list):
            formats = []
            for format in self.info['preferred_formats']['category']:
                formats.append(format['term'])
            return formats
        else:
            return [self.info['preferred_formats']['category']['term']]

    @property
    def can_instant_watch(self):
        return self.info['can_instant_watch'] == 'true'

    def at_home(self):
        if isinstance(self.get_info('at home')['at_home']['at_home_item'], list):
            return [NetflixTitle(title,self.client) for title in self.get_info('at home')['at_home']['at_home_item']]
        else:
            return [NetflixTitle(self.get_info('at home')['at_home']['at_home_item'],self.client)]

    def getQueue(self):
        # finish up member / queue interaction
        pass

    ### I haven't cleaned up user stuff below this line. ###

    def getRatings(self, discInfo=[], urls=[]):
        accessToken=self.accessToken

        requestUrl = '/users/%s/ratings/title' % (accessToken.key)
        if not urls:
            if isinstance(discInfo,list):
                for disc in discInfo:
                    urls.append(disc['id'])
            else:
                urls.append(discInfo['id'])
        parameters = { 'title_refs': ','.join(urls) }

        info = json.loads( self.client._get_resource(
                                    requestUrl,
                                    parameters=parameters,
                                    token=accessToken ) )

        ret = {}
        for title in info['ratings']['ratings_item']:
                ratings = {
                        'average': title['average_rating'],
                        'predicted': title['predicted_rating'],
                }
                try:
                    ratings['user'] = title['user_rating']
                except:
                    pass

                ret[ title['title']['regular'] ] = ratings

        return ret

    def getRentalHistory(self,type=None,startIndex=None,
                                    maxResults=None,updatedMin=None):
        accessToken=self.accessToken
        parameters = {}
        if startIndex:
            parameters['start_index'] = startIndex
        if maxResults:
            parameters['max_results'] = maxResults
        if updatedMin:
            parameters['updated_min'] = updatedMin

        if not isinstance(accessToken, oauth.OAuthToken):
            accessToken = oauth.OAuthToken(
                                    accessToken['key'],
                                    accessToken['secret'])

        if not type:
            requestUrl = '/users/%s/rental_history' % (accessToken.key)
        else:
            requestUrl = '/users/%s/rental_history/%s' % (accessToken.key,type)

        try:
            info = json.loads( self.client._get_resource(
                                    requestUrl,
                                    parameters=parameters,
                                    token=accessToken))
        except:
            return {}

        return info

class NetflixUserQueue:
    def __init__(self,user):
        self.user = user
        self.client = user.client
        self.tag = None

    def getContents(self, sort=None, startIndex=None,
                                    maxResults=None, updatedMin=None):
        parameters={}
        if startIndex:
            parameters['start_index'] = startIndex
        if maxResults:
            parameters['max_results'] = maxResults
        if updatedMin:
            parameters['updated_min'] = updatedMin
        if sort and sort in ('queue_sequence','date_added','alphabetical'):
            parameters['sort'] = sort

        requestUrl = '/users/%s/queues' % (self.user.accessToken.key)
        try:
            info = json.loads(self.client._get_resource(
                                    requestUrl,
                                    parameters=parameters,
                                    token=self.user.accessToken ))
        except:
            return []
        else:
            return info

    def getAvailable(self, sort=None, startIndex=None,
                                    maxResults=None, updatedMin=None,
                                    type='disc'):
        parameters={}
        if startIndex:
            parameters['start_index'] = startIndex
        if maxResults:
            parameters['max_results'] = maxResults
        if updatedMin:
            parameters['updated_min'] = updatedMin
        if sort and sort in ('queue_sequence','date_added','alphabetical'):
            parameters['sort'] = sort

        requestUrl = '/users/%s/queues/%s/available' % (
                                    self.user.accessToken.key,
                                    type)
        try:
            info = json.loads(self.client._get_resource(
                                    requestUrl,
                                    parameters=parameters,
                                    token=self.user.accessToken ))
        except:
            return []
        else:
            return info

    def getSaved(self, sort=None, startIndex=None,
                                    maxResults=None, updatedMin=None,
                                    type='disc'):
        parameters={}
        if startIndex:
            parameters['start_index'] = startIndex
        if maxResults:
            parameters['max_results'] = maxResults
        if updatedMin:
            parameters['updated_min'] = updatedMin
        if sort and sort in ('queue_sequence','date_added','alphabetical'):
            parameters['sort'] = sort

        requestUrl = '/users/%s/queues/%s/saved' % (
                                    self.user.accessToken.key,
                                    type)
        try:
            info = json.loads(self.client._get_resource(
                                    requestUrl,
                                    parameters=parameters,
                                    token=self.user.accessToken))
        except:
            return []
        else:
            return info

    def addTitle(self, discInfo=[], urls=[],type='disc',position=None):
        accessToken=self.user.accessToken
        parameters={}
        if position:
            parameters['position'] = position

        if not isinstance(accessToken, oauth.OAuthToken):
            accessToken = oauth.OAuthToken(
                                    accessToken['key'],
                                    accessToken['secret'])

        requestUrl = '/users/%s/queues/disc' % (accessToken.key)
        if not urls:
            for disc in discInfo:
                urls.append(disc['id'])
        parameters = {'title_ref': ','.join(urls)}

        if not self.tag:
            response = self.client._get_resource(
                                    requestUrl,
                                    token=accessToken)
            response = json.loads(response)
            self.tag = response["queue"]["etag"]
        parameters['etag'] = self.tag
        response = self.client._post_resource(
                                    requestUrl,
                                    token=accessToken,
                                    parameters=parameters)
        return response

    def removeTitle(self, id, type='disc'):
        accessToken=self.user.accessToken
        entryID = None
        parameters={}
        if not isinstance(accessToken, oauth.OAuthToken):
            accessToken = oauth.OAuthToken(
                                    accessToken['key'],
                                    accessToken['secret'])

        # First, we gotta find the entry to delete
        queueparams = {'max_results': 500}
        requestUrl = '/users/%s/queues/disc' % (accessToken.key)
        response = self.client._get_resource(
                                    requestUrl,
                                    token=accessToken,
                                    parameters=queueparams)
        print "Response is " + response
        response = json.loads(response)
        titles = response["queue"]["queue_item"]

        for disc in titles:
            discID = os.path.basename(urlparse(disc['id']).path)
            if discID == id:
                entryID = disc['id']

        if not entryID:
            return
        firstResponse = self.client._get_resource(
                                    entryID,
                                    token=accessToken,
                                    parameters=parameters)

        response = self.client._delete_resource(entryID, token=accessToken)
        return response

class NetflixPerson(NetflixBase):

    @property
    def id(self):
        return self.info['id'].split('/')[-1]

    @property
    def name(self):
        return self.info['name']

    def filmography(self):
        raw_films = self.get_info('filmography')['filmography']['filmography_item']

        if isinstance(raw_films, list):
            films = []
            for film in raw_films:
                films.append(NetflixTitle(film,self.client))
            return films
        else:
            return NetflixTitle(raw_films,self.client)

class NetflixTitle(NetflixBase):
    # helper functions for parent and child functions

    def _get_title_single(self, url):
        return NetflixTitle(self.get_info(url)['catalog_title'],self.client)

    def _get_title_list(self, url):
        try:
            return [NetflixTitle(title,self.client) for title in self.get_info(url)['catalog_titles']['catalog_title']]
        except TypeError:
            return []

    # These functions get the items parents, if they exist

    def disc(self):
        return self._get_title_single(DISC_URL)

    def season(self):
        return self._get_title_single(SEASON_URL)

    def series(self):
        return self._get_title_single(SERIES_URL)

    # These functions get the items children, if they exist

    def seasons(self):
        return self._get_title_list(SEASONS_URL)

    def discs(self):
        return self._get_title_list(DISCS_URL)

    def episodes(self):
        return self._get_title_list(EPISODES_URL)

    # These functions deal with the current items details

    def __repr__(self):
        return self.title

    @property
    def id(self):
        return self.get_infoLink(TITLE_URL) or self.info['id']

    @property
    def int_id(self):
        return self.info['id'].split('/')[-1]

    @property
    def type(self):
        raw = self.id.split('/')[-2]
        if raw != 'series':
            # remove the 's' from the end of everything but series
            return self.id.split('/')[-2][0:-1]
        else:
            return raw

    @property
    def title(self):
        return self.info['title']['regular']

    @property
    def series_title(self):
        if self.type == 'series':
            return self.title
        elif self.type != 'movie':
            return self.series().title
        return None

    @property
    def season_number(self):
        try:
            i = 1
            for season in self.series().seasons():
                if self.id == season.id:
                    return i
                else:
                    i += 1
        except TypeError:
            return None

    @property
    def episode_title(self):
        try:
            return self.info['title']['episode_short']
        except KeyError:
            return None

    @property
    def episode_number(self):
        try:
            i = 1
            for episode in self.season().episodes():
                if self.id == episode.id:
                    return i
                else:
                    i += 1
        except TypeError:
            return None

    @property
    def disc_title(self):
        try:
            raw_title = self.info['title']['regular']
            if re.search(disk_pattern,raw_title):
                title = re.split(disk_pattern,raw_title)[-1]
                if len(title) > 2:
                    return title
            return None
        except:
            return None

    @property
    def disc_number(self):
        try:
            i = 1
            for disc in self.season().discs():
                if self.id == disc.id:
                    return i
                else:
                    i += 1
        except TypeError:
            return None

    @property
    def length(self):
        seconds = int(self.info['runtime'])
        return seconds/60

    @property
    def mpaa_rating(self):
        for i in self.info['category']:
            if i['scheme'] == 'http://api.netflix.com/categories/mpaa_ratings':
                return i['term']
        return None

    @property
    def tv_rating(self):
        for i in self.info['category']:
            if i['scheme'] == 'http://api.netflix.com/categories/tv_ratings':
                return i['term']
        return None

    @property
    def release_year(self):
        try:
            return self.info['release_year']
        except KeyError:
            return None

    @property
    def shipped_date(self):
        try:
            return datetime.fromtimestamp(float(self.info['shipped_date']))
        except KeyError:
            return None

    # deeper info about an item (requires more queries of the netflix api)

    def formats(self):
        raw_formats = self.get_info('formats')['delivery_formats']['availability']
        if isinstance(raw_formats, list):
            formats = []
            for format in raw_formats:
                format_name = format['category']['term']
                release_date = datetime.fromtimestamp(float(format['available_from']))
                formats.append({'format':format_name, 'release_date': release_date})
            return formats
        else:
            format_name = raw_formats['category']['term']
            release_date = datetime.fromtimestamp(float(raw_formats['available_from']))
            return [{'format':format_name, 'release_date': release_date}]

    def directors(self):
        raw_directors = self.get_info('directors')
        raw_directors = raw_directors['people']['person']
        if isinstance(raw_directors, list):
            directors = []
            for director in raw_directors:
                directors.append(NetflixPerson(director, self.client))
            return directors
        else:
            return NetflixPerson(raw_directors, self.client)

    def cast(self):
        raw_cast = self.get_info('cast')
        raw_cast = raw_cast['people']['person']
        if isinstance(raw_cast, list):
            return [NetflixPerson(person, self.client) for person in raw_cast]
        else:
            return NetflixPerson(raw_cast, self.client)

    def bonus_material(self):
        raw_bonus = self.get_info('bonus materials')
        if raw_bonus:
            return [self.client.catalog.title(title['href']) for title in raw_bonus['bonus_materials']['link']]
        else:
            return []

    def similar_titles(self):
        raw_sim = self.get_info('similars')
        if raw_sim:
            raw_sim = raw_sim['similars']['similars_item']

            if isinstance(raw_sim, list):
                return [NetflixTitle(title,self.client) for title in raw_sim]
            else:
                return NetflixTitle(raw_sim, self.client)
        else:
            return []

    def user_state(self):
        user = self.client.user

        try:
            return json.loads(
                self.client._get_resource(
                    url=user.get_info('title states')['title_states']['url_template'].split('?')[0],
                    token=user.accessToken,
                    parameters={'title_refs':self.id}
                )
            )
        except:
            return []

class NetflixCatalog():
    def __init__(self,client):
        self.client = client

    def index(self):
        requestUrl = '/catalog/titles/index'

        return self.client._get_resource(
            requestUrl,
            self.client.user.accessToken,
            {},
            True
        )

    def autocomplete(self, term,startIndex=None,maxResults=None):
        requestUrl = '/catalog/titles/autocomplete'
        parameters = {'term': term}
        if startIndex:
            parameters['start_index'] = startIndex
        if maxResults:
            parameters['max_results'] = maxResults

        try:
            info = json.loads(
                self.client._get_resource(
                    requestUrl,
                    parameters=parameters
                )
            )
            return [x['title']['short'] for x in info['autocomplete']['autocomplete_item']]
        except KeyError:
            return []

    def search_titles(self, term,startIndex=None,maxResults=None):
        requestUrl = '/catalog/titles'
        parameters = {'term': term}
        if startIndex:
            parameters['start_index'] = startIndex
        if maxResults:
            parameters['max_results'] = maxResults

        try:
            info = json.loads(
                self.client._get_resource(
                    requestUrl,
                    parameters=parameters
                )
            )
            return [NetflixTitle(title,self.client) for title in info['catalog_titles']['catalog_title']]
        except KeyError:
            return []

    def search_people(self, term,startIndex=None,maxResults=None):
        requestUrl = '/catalog/people'
        parameters = {'term': term}
        if startIndex:
            parameters['start_index'] = startIndex
        if maxResults:
            parameters['max_results'] = maxResults

        try:
            info = json.loads(
                self.client._get_resource(
                    requestUrl,
                    parameters=parameters
                )
            )
            return [NetflixPerson(person,self.client) for person in info['people']['person']]
        except KeyError:
            return []

    def title(self, url):
        requestUrl = url
        try:
            info = json.loads(self.client._get_resource(requestUrl))
            return NetflixTitle(info['catalog_title'],self.client)
        except urllib2.HTTPError:
            return None

    def person(self,url):
        requestUrl = url
        try:
            info = json.loads(self.client._get_resource(requestUrl))
            return NetflixPerson(info['person'],self.client)
        except urllib2.HTTPError:
            return None
