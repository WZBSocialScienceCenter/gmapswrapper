"""
Google Maps API wrapper. Main class `GMapsWrapper`.

Enables convenient caching of Google Maps API results.

Markus Konrad <markus.konrad@wzb.eu>
January 2019
"""

import os
import pickle
import logging
from datetime import datetime

import googlemaps


CACHE_FILE = 'gmapswrapper_cache.pickle'
AUTSAVE_CACHE_EVERY_NTH_REQUEST = 10

logger = logging.getLogger('gmapswrapper')
logger.addHandler(logging.NullHandler())


class GMapsWrapper:
    def __init__(self, cache_dir, api_key, **kwargs):
        """
        Create new Google Maps wrapper object by passing a writable cache directory and the Google Cloud API key.
        Pass additional options for `googlemaps.Client()` as `kwargs`.
        """
        if api_key:
            kwargs.update({'key': api_key})

        logger.info('creating googlemaps client')
        self.gmaps = googlemaps.Client(**kwargs)

        if not os.path.exists(cache_dir):
            logger.info('creating cache directory `%s`' % cache_dir)
            os.makedirs(cache_dir)

        self.cachefile = os.path.join(cache_dir, CACHE_FILE)
        logger.info('using cache file `%s`' % self.cachefile)

    def clean_cache(self):
        """Delete cache file."""
        if os.path.isfile(self.cachefile):
            os.unlink(self.cachefile)

    def remove_item_from_cache(self, item_id, section='geocoding'):
        """Remove item from cache with cache key `item_id`."""
        cache = self._load_cache()
        if item_id in cache[section]:
            del cache[section][item_id]
            logger.info('removed item `%s` in cache section `%s`' % (item_id, section))
        self._write_cache(cache)

    def geocode(self, addresses):
        """
        Geocode addresses in list/tuple/set `addresses` using Google Cloud Geocoding API. Will cache the results.
        Returns dict with address -> result mapping.
        """
        if type(addresses) not in (list, tuple, set):
            raise ValueError('`addresses` must be a list, tuple or set')

        cache = self._load_cache()
        geocoding_cache = cache['geocoding']

        geocoded_addresses = {}
        fetched_res_since_last_cachewrite = False

        for i, addr in enumerate(addresses):
            if addr in geocoding_cache:   # cache hit -> use this result
                geocode_results = geocoding_cache[addr]
                logger.info('found %d geocoding results in cache for address `%s`' % (len(geocode_results), addr))
            else:  # no cache hit -> get result from API
                logger.info('requesting Geocoding API for address `%s`' % addr)
                fetched_res_since_last_cachewrite = True

                try:
                    cache['_requests']['geocoding'].append(datetime.now())
                    geocode_results = self.gmaps.geocode(addr)
                except Exception as exc:
                    t_exc = type(exc)
                    if t_exc == googlemaps.exceptions.HTTPError:
                        logger.error("geocoding failure - HTTP error: '%s'" % str(exc))
                    elif t_exc == googlemaps.exceptions.TransportError:
                        logger.error("geocoding failure - transport error: '%s'" % str(exc))
                    elif t_exc == googlemaps.exceptions.Timeout:
                        logger.error("geocoding failure - timeout: '%s'" % str(exc))
                    else:
                        logger.error("geocoding failure - unknown exception: '%s'" % str(exc))

                    geocode_results = None

                if geocode_results:
                    # save valid result to cache
                    logger.info('will save %d geocoding results to cache' % len(geocode_results))
                    geocoding_cache[addr] = geocode_results

            # store in result dict
            geocoded_addresses[addr] = geocode_results

            # regularly write cache to file
            if ((i+1) % AUTSAVE_CACHE_EVERY_NTH_REQUEST == 0 or i == len(addresses)-1)\
                    and fetched_res_since_last_cachewrite:
                cache['geocoding'] = geocoding_cache
                self._write_cache(cache)
                fetched_res_since_last_cachewrite = False

        return geocoded_addresses

    def _load_cache(self):
        """Load cache from pickle file `self.cachefile` or create new cache object."""
        if os.path.isfile(self.cachefile):
            with open(self.cachefile, 'rb') as f:
                logger.info('loading cache from file `%s`' % self.cachefile)
                return pickle.load(f)
        else:
            logger.info('creating new cache object')
            return {
                '_version': 1,
                '_requests': {
                    'geocoding': [],
                },
                'geocoding': {}
            }

    def _write_cache(self, cache):
        """Write cache `cache` as pickle file to `self.cachefile`."""
        with open(self.cachefile, 'wb') as f:
            logger.info('writing cache to file `%s`' % self.cachefile)
            pickle.dump(cache, f)
