from title import NetflixTitle

class NetflixCatalog(object):
    def __init__(self, client):
        self.client = client

    def streaming(self):
        # NOTE this downloads *all* the streaming titles on netflix. This may take a while ;)
        return self.client.getResource('/catalog/titles/streaming', index=True)

    def _search(self, url, term, startIndex=None, maxResults=None, expand=None):
        parameters = {
            'term': term
        }

        if startIndex:
            parameters['start_index'] = startIndex
        if maxResults:
            parameters['max_results'] = maxResults
        if expand:
            parameters['expand'] = expand

        return self.client.getResource(url, parameters)

    def autocomplete(self, term, startIndex=None, maxResults=None):
        results = self._search('/catalog/titles/autocomplete', term, startIndex, maxResults)

        try:
            return [x['title']['short'] for x in results['autocomplete']['autocomplete_item']]
        except KeyError:
            return []

    def search(self, term, startIndex=None, maxResults=None, expand=None):
        results = self._search('/catalog/titles', term, startIndex, maxResults, expand)

        print results

        try:
            return [NetflixTitle(title, self.client) for title in results['catalog']]
        except KeyError:
            return []
