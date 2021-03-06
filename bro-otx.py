#!/usr/bin/env python

import requests
import sys

from ConfigParser import ConfigParser
from datetime import datetime, timedelta

# The URL is hard coded. I'm comfortable doing this since it's unlikely that
# the URL will change without resulting in an API change that will require
# changes to this script.
_URL = 'http://otx.alienvault.com/api/v1/pulses/subscribed'

# Bro Intel file header format
_HEADER = "#fields\tindicator\tindicator_type\tmeta.source\tmeta.url\tmeta.do_notice\n"

# Mapping of OTXv2 Indicator types to Bro Intel types, additionally,
# identifies unsupported intel types to prevent errors in Bro.
_MAP = {"IPv4":"Intel::ADDR",
           "IPv6":"Intel::ADDR",
           "domain":"Intel::DOMAIN",
           "hostname":"Intel::DOMAIN",
           "email":"Intel::EMAIL",
           "URL":"Intel::URL",
           "URI":"Intel::URL",
           "FileHash-MD5":"Intel::FILE_HASH",
           "FileHash-SHA1":"Intel::FILE_HASH",
           "FileHash-SHA256":"Intel::FILE_HASH",
           "CVE":"Unsupported",
           "Mutex":"Unsupported",
           "CIDR":"Unsupported"}

def _get(key, mtime, limit=20, next_request=''):
    '''
    Retrieves a result set from the OTXv2 API using the restrictions of
    mtime as a date restriction.
    '''

    headers = {'X-OTX-API-KEY': key}
    params = {'limit': limit, 'modified_since': mtime}
    if next_request == '':
        r = requests.get(_URL, headers=headers, params=params)
    else:
        r = requests.get(next_request, headers=headers)

    # Depending on the response code, return the valid response.
    if r.status_code == 200:
        return r.json()
    if r.status_code == 403:
        print("An invalid API key was specified.")
        sys.exit(1)
    if r.status_code == 400:
        print("An invalid request was made.")
        sys.exit(1)

def iter_pulses(key, mtime, limit=20):
    '''
    Creates an iterator that steps through Pulses since mtime using key.
    '''

    # Populate an initial result set, after this the API will generate the next
    # request in the loop for every iteration.
    initial_results = _get(key, mtime, limit)
    for result in initial_results['results']:
        yield result

    next_request = initial_results['next']
    while next_request:
        json_data = _get(key, mtime, next_request=next_request)
        for result in json_data['results']:
            yield result
        next_request = json_data['next']

def map_indicator_type(indicator_type):
    '''
    Maps an OTXv2 indicator type to a Bro Intel Framework type.
    '''

    return _MAP[indicator_type]

def main():
    '''Retrieve intel from OTXv2 API.'''

    config = ConfigParser()
    config.read('bro-otx.conf')
    key = config.get('otx', 'api_key')
    days = int(config.get('otx', 'days_of_history'))
    outfile = config.get('otx', 'outfile')
    do_notice = config.get('otx', 'do_notice')

    mtime = (datetime.now() - timedelta(days=days)).isoformat()

    with open(outfile, 'wb') as f:
        f.write(_HEADER)
        for pulse in iter_pulses(key, mtime):
            for indicator in pulse[u'indicators']:
                bro_type = map_indicator_type(indicator[u'type'])
                if bro_type == 'Unsupported':
                    continue
                try:
                    url = pulse[u'references'][0]
                except IndexError:
                    url = 'https://otx.alienvault.com'
                fields = [indicator[u'indicator'],
                    bro_type,
                    pulse[u'author_name'],
                    url,
                    do_notice + '\n']
                f.write('\t'.join(fields))

if __name__ == '__main__':
    main()
